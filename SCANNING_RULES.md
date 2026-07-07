# How scanning, scoring, and safety-checking actually works

This is a step-by-step walkthrough of what `scan.py` does to every item
before it reaches `catalog.json`, written so you can audit the logic
yourself instead of trusting a summary. If a rule here doesn't match the
code, the code is right — open an issue.

## 1. Where items come from

`scan.py` reads `sources.json`, shallow-clones (or `git pull`s) each repo
into `cache/<source_id>/`, and walks every file looking for:

| Signal in the path | Category |
|---|---|
| filename is `SKILL.md` (any case) | skill |
| an `agents/` directory anywhere in the path | agent |
| a `commands/` directory | command |
| a `hooks/` or `hook-scripts/` directory | hook |

A few filenames (`README`, `INDEX`, `LICENSE`, `CONTRIBUTING`, `CLAUDE`,
`CODE_OF_CONDUCT`, `SECURITY`, `TEMPLATE`) are skipped for agents/commands
unless they have real YAML frontmatter — otherwise every repo's own
README would show up as an "agent."

## 2. Reading the item's own metadata

For `.md` files, `scan.py` parses the YAML frontmatter block (between the
`---` fences) itself — no YAML library, just line-by-line parsing,
including YAML's block-scalar syntax (`description: |` followed by
indented lines), which a naive line-splitter would otherwise turn into
the literal string `"|"`. If a `name`/`description` field is missing, it
falls back to the filename and to the first non-heading line of the
body, respectively.

For hook scripts (no frontmatter), the description is the first
meaningful comment line in the first 15 lines of the file.

## 3. Content score — deciding which duplicate is "better"

When the same `(category, name)` shows up in more than one source (this
happens *a lot* — 654 collisions across the current 8 sources), someone
has to be picked as the one shown in the picker. Instead of an arbitrary
rule ("official always wins," "alphabetically first source wins"),
`scan.py` scores each candidate's actual content and picks the higher
score. The formula (`score_content()`):

| Signal | Points |
|---|---|
| Has a real description (not empty, not a bare `\|`, longer than 15 chars) | up to `+1.0`, scaled by length (capped at 200 chars) |
| Body word count | up to `+1.0`, scaled linearly (capped at 400 words) |
| Has a `## Usage` or `## Example` heading | `+0.3` |
| Has a fenced code block | `+0.2` |
| (Skills only) folder bundles extra files beyond `SKILL.md` | `+0.2` |
| Looks like a placeholder (`TODO`, "lorem ipsum", or under 15 words total) | `-0.5` |

The score is a rough, explainable proxy for "does this look like a
finished, documented skill" — not a claim of correctness or quality
beyond that. `content_signals` (the human-readable reasons behind the
score) travel with the item so `skipped_duplicates.json` can say *why*
one version beat another, not just that it did.

## 4. Dedup — who wins a name collision

For every `(category, name)` group, candidates are ranked by, in order:

1. **Safety first**: anything with a hard safety flag (see §5) always
   loses, even against an official-tier candidate.
2. **Content score**: higher wins.
3. **Tier**: official-tier only breaks a genuine score tie.
4. **Source order**: `sources.json` order is the final, fully
   deterministic tiebreak (so re-running `scan.py` never reshuffles a
   true tie).

Every candidate that loses is recorded in `skipped_duplicates.json` with
the specific reason — "duplicate within the same source," "flagged for
risky pattern(s): X," "kept scored higher on content (A vs B) — why," or
a tie-break note. Nothing is silently dropped without an explanation
sitting in a file you can open.

## 5. Safety scan — two tiers, by false-positive risk

Every item's raw text (frontmatter + body, or the full script for hooks)
is checked against two pattern lists, loosely modeled on the checklist
curated skill marketplaces use in 2026 (prompt injection, data
exfiltration, secret detection, dangerous commands, obfuscation,
suspicious external fetches, credential access, privilege escalation).

### Hard tier (`harmful_flags`) — gates install, always loses dedup

Reserved for patterns with essentially no legitimate use inside a
skill's own instructions:

| Label | What it catches |
|---|---|
| `curl-pipe-shell` | `curl`/`wget` piped straight into `sh`/`bash` |
| `rm-rf-root` | `rm -rf /` (or `/*`) |
| `fork-bomb` | the classic `:(){ :|:& };:` shell fork bomb |
| `base64-eval` | `eval(...)` wrapping a `base64` decode |
| `reverse-shell` | `nc -e /bin/sh`-style reverse shells, `/dev/tcp/` redirection |
| `credential-exfil` | a `curl` reading `.aws/credentials`, `.ssh/id_rsa`, or `/etc/passwd` |
| `chmod-777` | `chmod 777` (world-writable) |
| `disable-security-tool` | disabling SELinux/firewalld/ufw/apparmor/macOS quarantine |
| `prompt-injection-override` | an *imperative* "ignore previous instructions" / "disregard the system prompt" / "you are now DAN" — see the quoting rule below |

A hard match:
- is tagged `[!RISKY: label1, label2]` in the picker — even when the
  item is the only copy of its name, not just a dedup loser
- requires an explicit `y/N` confirm before installing, the same way an
  unlicensed item does

### Soft tier (`review_flags`) — informational only

Patterns with plausible legitimate uses, so hard-gating them would
mostly just annoy people writing normal documentation. This tier does
almost all of the secret-detection work — deliberately: a key's format
is either a fixed, assigned shape (in which case regex is the *right*
tool, not a weak substitute for something smarter) or it's ambiguous
enough that a hard gate would be wrong regardless of how it's detected.

| Label | What it catches |
|---|---|
| `aws-access-key` / `aws-temp-session-key` | `AKIA`/`ASIA`-prefixed AWS access keys |
| `github-token` | `ghp_`/`gho_`/`ghu_`/`ghs_`/`ghr_`-prefixed GitHub tokens |
| `slack-token` | `xoxb-`/`xoxp-`/etc. Slack tokens |
| `stripe-key` | `sk_live_`/`rk_live_` Stripe keys |
| `google-api-key` | `AIza`-prefixed Google API keys |
| `private-key-block` | a `-----BEGIN ... PRIVATE KEY-----` PEM block |
| `azure-storage-key` | an `AccountKey=` connection-string value |
| `gcp-service-account-key` | a `"type": "service_account"` JSON key file |
| `twilio-api-key` / `sendgrid-api-key` / `npm-token` | provider-specific fixed formats |
| `jwt` | a `eyJ...eyJ...` three-part JWT |
| `anthropic-api-key` / `openai-api-key` | `sk-ant-`/`sk-`(`-proj-`) prefixed keys |
| `db-connection-string-with-credentials` | `postgres://`/`mysql://`/`mongodb://`/`redis://` with embedded, non-placeholder credentials — see below |
| `high-entropy-token` | a quoted literal assigned to an `api_key`/`secret`/`token`/`password`-shaped variable name, with real Shannon entropy |
| `sudo-usage` | bare `sudo` — extremely common in normal install docs |
| `suspicious-external-fetch` | `curl`/`wget` to a host outside an allowlist (github.com, pypi.org, npmjs registry, etc.) or a known paste/tunnel host |
| `credential-file-read-broad` | a *read* (not a network exfil) of `.ssh/id_rsa`, `.netrc`, `/etc/shadow` |

Soft flags show as `[i: label1, label2]` — never a gate, never a factor
in dedup ranking.

**Placeholder suppression.** Every secret-shaped match above is checked
against a small placeholder denylist before being flagged — providers'
own documentation frequently embeds their *own* canonical example key
(AWS's docs literally use `AKIAIOSFODNN7EXAMPLE`), and connection-string
placeholders overwhelmingly follow a "same word twice" or "generic word"
convention (`user:pass@`, `postgres:postgres@`, `test:test@`,
`{{username}}:{{password}}@`). Found by testing against the real
catalog: the naive version flagged 15 items for connection strings that
were entirely doc placeholders across CI configs and README examples —
none were real credentials. The connection-string check specifically
compares the username and password parts (not a blanket substring check)
so a real-looking secret with a generic *username* — `admin:S3cr3tP4ss@`
— still gets flagged; only a generic or matching *password* suppresses it.

### The quoting/documentation rule

The single biggest source of false positives, found by testing this
against the real 2,137-item catalog: a security-conscious skill or hook
often *quotes the exact bad pattern it defends against* — e.g. a hook
literally named `block-dangerous-commands` contains the string
`chmod 777` as its own detection rule, and Anthropic's own
`architecture-critic`/`test-engineer` agents quote `"ignore previous
instructions"` as an example of what to watch for.

So before a hard match is accepted as hard, `scan.py` checks whether it's
sitting next to signals that it's being *documented* rather than
*executed*:
- immediately wrapped in backticks or quotes (`` `chmod 777` ``)
- near words like "risk", "dangerous", "detect", "block", "forbidden",
  "reason:", "matches:", "do not", "never"
- inside a `describe(...)`/`it(...)` test block
- (prompt-injection specifically) the phrase appears inside quotes at
  all, anywhere in the file — a security agent's own defensive
  instructions read very differently from an actual injected command

If any of those hold, the match is downgraded to a soft, non-gating
flag (e.g. `chmod-777-mentioned`) instead of the hard tier. This is a
heuristic, not a proof — it will occasionally miss a real payload that
happens to be phrased defensively, and it will occasionally still gate
a legitimate item (a real `curl | sh` install one-liner in a fenced code
block reads identically to a malicious one, so it stays hard-gated on
purpose; three current catalog items — `uv-package-manager`,
`linkerd-patterns`, `gitops-workflow` — trip this for exactly that
reason).

**Known limitation — this rule is a public, gameable escape hatch.**
Because `scan.py` is open source (and this exact wordlist is published
right here), a deliberately malicious skill author can read it and word
their payload to include a word from `DOCUMENTED_AS_EXAMPLE_RE` (e.g.
"this reduces risk", "prevents accidental data loss") next to a real
destructive command, downgrading it from a hard gate to a silent-ish
soft tag. This isn't a hypothetical to hand-wave past — it's a direct
consequence of fixing the false-positive problem, and there is no
regex-only fix for it (tightening the wordlist just brings back the
false positives on legitimate security tooling). The honest mitigation
is layered, not a single rule: `--llm-review` judges intent rather than
just keyword proximity, and ultimately none of this replaces actually
reading a skill's source before trusting it — which is true of every
scanner in this space, not a gap unique to this one.

**Bottom line: this is a tripwire, not an audit.** It catches
some shapes of obviously bad content and is transparent about exactly
which pattern fired and why. It cannot prove an item is safe, and it is
not a substitute for reading the source before you trust it.

## 6. Optional LLM review (`--llm-review`)

A second, opt-in pass that asks an LLM to judge only the items that
already triggered something in §5 (or whose content score lands in an
ambiguous 0.2–0.5 band) — not the whole catalog. Supports six providers,
each implemented as a plain HTTP JSON call via Python's stdlib
`urllib` — no SDK, no `pip install`, for any of them:

| Provider | Needs |
|---|---|
| `anthropic` (default) | `ANTHROPIC_API_KEY` |
| `openai` | `OPENAI_API_KEY` |
| `gemini` | `GEMINI_API_KEY` |
| `openrouter` | `OPENROUTER_API_KEY` |
| `ollama` | a local server running (no key) |
| `lmstudio` | a local server running (no key) |

If the required key is missing, or a local server isn't reachable
(checked with a fast 3-second probe before looping over any items, so
an unreachable local server fails in seconds, not minutes), `scan.py`
prints one line and continues the rest of the scan normally — this
never blocks or breaks the base flow.

The model is asked to return strict JSON — `verdict`
(safe/suspicious/malicious), `confidence`, and a short `reasoning`
string — and is explicitly told not to treat security/pentest
terminology as inherently malicious (the same false-positive shape as
§5's quoting problem, but harder to fix with regex alone). Results are
cached by a hash of `(provider, model, content)` in
`llm_review_cache.json`, so re-running `--llm-review` after sources
update only reviews items that are new or actually changed.

`install.py` shows the verdict as `[LLM: verdict confidence]` in the
picker, and prints the full reasoning before the safety-gate confirm
prompt fires — so a flagged `curl | sh` install doc can show *why* it's
probably fine right alongside the blunt regex label, letting you make an
informed call instead of just seeing a tag. **The confirm gate fires on
either signal** — a static hard flag, *or* an LLM verdict of `suspicious`/
`malicious` even with no static match at all (an item that only landed
in the ambiguous score band, with nothing tripped in §5, can still be
caught here) — so a model that disagrees with the regex isn't just a
passive tag you could miss.

Two robustness details worth knowing about:
- **Retries**: transient failures (HTTP 429 rate limits, 5xx server
  errors) get up to 2 retries with exponential backoff before that
  item's review is given up on; a 4xx auth/bad-request error is not
  retried, since retrying won't fix it.
- **JSON extraction**: models frequently wrap their JSON response in
  ` ```json ` fences despite being told not to. `scan.py` tries a direct
  parse first, then strips markdown fences, then falls back to grabbing
  the first `{...}` block in the response — before giving up and logging
  that item's review as failed.

## 7. Where this logic lives

The logic described above is split across a small `catalog/` package
rather than one large `scan.py` (which is now just the CLI entry point:
cloning sources and orchestrating the pipeline):

| File | What's in it |
|---|---|
| `catalog/paths.py` | `ROOT`/`CACHE`/`SOURCES` — the one place repo-relative paths are computed |
| `catalog/parsing.py` | frontmatter parsing, content scoring, category classification, `collect()` |
| `catalog/safety.py` | every hard/soft pattern, the documentation heuristic, dedup ranking |
| `catalog/llm_review.py` | the 6-provider HTTP client, JSON extraction, retry/backoff, caching |

## 8. Testing

`tests/test_parsing.py`, `tests/test_safety.py`, `tests/test_llm_review.py`,
and `tests/test_install.py` pin the behavior above with stdlib `unittest`
(no pytest, no dependency to install) — including regression tests for
the exact false positives found and fixed by testing against the real
catalog (the `block-dangerous-commands` hook, the quoted prompt-injection
example in `architecture-critic`). Run them from the repo root:

```bash
python -m unittest discover -s tests -t .
```

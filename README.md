<div align="center">

# 📚 claude-code-catalog

**A scanner + interactive installer for Claude Code agents, skills, commands, and hooks.**
**We don't just fetch and install — every item is content-scored, safety-scanned,**
**and its dedup decision explained, before it ever touches `~/.claude/`.**

![Python](https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-3fb950?style=flat-square)
![Dependencies](https://img.shields.io/badge/dependencies-git%20%2B%20python3-6366f1?style=flat-square)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-06b6d4?style=flat-square)
![License Audited](https://img.shields.io/badge/sources-license%20audited-e85d4a?style=flat-square)

</div>

---

## 🧭 Why this exists

Community catalogs now ship thousands of items across dozens of
repos — far too many to read through by hand. Almost none of the
existing aggregators tell you what license you're actually installing
under. Two of the eight sources below have **no LICENSE file at all**,
which under copyright law defaults to all-rights-reserved, not "free
to use because it's on GitHub."

`claude-code-catalog` treats that as a first-class problem, not a footnote:

| | This tool | Typical aggregator |
|---|---|---|
| 🔍 Per-source license tracked | ✅ recorded in `sources.json` | ❌ usually undocumented |
| 🛑 Blocks silent copy of unlicensed code | ✅ `[!NO LICENSE]` + y/N gate | ❌ copies on select |
| 🧪 Content-scored + safety-scanned before install | ✅ deterministic, reasons shown inline | ❌ none, or a paid black-box verdict |
| 📝 Attribution trail per install | ✅ `ATTRIBUTION.md`, auto-appended | ❌ rarely kept |
| 📦 Dependencies | git + python3 only — even the optional LLM review | often npm/node + a hosted directory |
| ✋ Selection model | numbered picker, explicit multi-select | varies — some install everything by default |

Nothing is installed without you choosing it, and nothing with an
unclear license — or a flagged safety pattern — is installed without
you confirming it.

Curated skill marketplaces already do content vetting (Agensi's
8-point checklist, Repello AI's skill audits) — usually paid, usually
a pass/fail badge you have to trust. This tool does the same job in
the open: every scoring decision and every flagged pattern is written
to a file you can read (`skipped_duplicates.json`, inline `[!RISKY]`/
`[i: ...]` tags), not a black box.

---

## ⚙️ How it works

```text
                     scan.py                          install.py
+--------------+                    +--------------+                    +-------------------+
| sources.json |                    | catalog.json |                    |    ~/.claude/*    |
|  (repos you  | -----------------> | (every item, | -----------------> |  + ATTRIBUTION.md |
|    trust)    |   git clone/pull   |   license-   |  numbered picker   |  + installed.json |
|              |                    |   tagged)    |   + license gate   |                   |
+--------------+                    +--------------+                    +-------------------+
```

Installs at the **user level** (`~/.claude/`), so what you pick
applies across every project on your machine, not just one repo.

---

## ✨ What's included

| Category | Where it lands | Copied as |
|---|---|---|
| 🤖 **Agents** | `~/.claude/agents/` | single file |
| 🧠 **Skills** | `~/.claude/skills/` | whole folder (bundles scripts/references) |
| ⚡ **Commands** | `~/.claude/commands/` | single file |
| 🪝 **Hooks** | `~/.claude/hooks/` | single file |
| 📋 **Attribution** | `~/.claude/ATTRIBUTION.md` | auto-appended on every install |

---

## 🚀 Quick start

Requires `git` and Python 3 (both cross-platform, no other dependencies).

**macOS / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/SID-SURANGE/claude-code-catalog/main/install.sh | bash
```

**Windows (PowerShell)**
```powershell
irm https://raw.githubusercontent.com/SID-SURANGE/claude-code-catalog/main/install.ps1 | iex
```

Both scripts clone this repo to `~/.claude-code-catalog` (or
`$env:CLAUDE_CODE_CATALOG_HOME` / `$CLAUDE_CODE_CATALOG_HOME` if set),
run the scanner, then launch the interactive picker.

**Already cloned it yourself?** Just run directly instead:

**macOS / Linux**
```bash
python3 scan.py      # build/refresh catalog.json from all sources
python3 install.py   # interactive picker
```

**Windows**
```powershell
python scan.py        # build/refresh catalog.json from all sources
python install.py     # interactive picker
```

> Windows commonly has no `python3` command (it's often shadowed by the
> Microsoft Store alias instead of a real interpreter) — use `python` or
> `py` there. macOS/Linux use `python3` since `python` may point at
> Python 2 or not exist at all.

### Usage

```bash
# Pick from everything
python3 install.py   # Windows: python install.py

# Only Anthropic's own (official-tier) items
python3 install.py --tier official

# Only one category
python3 install.py --category skill   # agent | skill | command | hook

# See curated bundles, then install one
python3 install.py --list-packs
python3 install.py --pack code-review-essentials

# Optional: LLM-review flagged/borderline items before installing
python3 scan.py --llm-review                          # Anthropic by default
python3 scan.py --llm-review --llm-provider ollama    # or openai / gemini / openrouter / lmstudio
```

Before each category's list, you're prompted for an optional keyword
to filter by name/description — press Enter to see everything
unfiltered. The filter is a real fuzzy matcher on the item name (fzf-
style: `dockr` matches `docker-development`, `pkgmgr` matches
`uv-package-manager`) plus a substring check on the description, with
multiple words requiring all of them to match (`docker compose`). With
800+ skills in the catalog, this is how you actually find something
instead of scrolling.

Long lists page 20 at a time — press Enter for more, or make your
selection right away without paging through everything. Before
choosing, type `i 5` (or `info 5`) to see an item's full description,
content score, safety flags, and skipped-duplicate alternates, without
committing to an install.

At each prompt, select items by number: `1,3,5-8`, `all`, or `none`.
Output is colorized when your terminal supports it (respects `NO_COLOR`
and auto-disables when piped/redirected).

Picking an item with no LICENSE file stops and asks first:

```text
'some-skill' has no license (No LICENSE file in the repo...).
Install anyway? [y/N]:
```

---

## 🎒 Packs

With 800+ skills across 8 sources, browsing one item at a time is slow
if you don't yet know what you need. **Packs** are curated bundles —
a named list of `{category, name}` items, which can span multiple
source repos — that install.py can list and install as a group. There
are 8 today: `git-workflow`, `code-review-essentials`, `plugin-dev`,
`docker-devops`, `kubernetes-ops`, `react-frontend`, `python-backend`,
and `testing-toolkit` — each hand-picked from items that scored well on
the content metrics described in [SCANNING_RULES.md](SCANNING_RULES.md).

```bash
python3 install.py --list-packs
python3 install.py --list-packs docker   # filter packs by keyword too
python3 install.py --pack git-workflow
```

Packs are just `packs.json` at the repo root:

```json
{
  "id": "git-workflow",
  "name": "Git Workflow Basics",
  "description": "Everyday git commands...",
  "items": [{ "category": "command", "name": "commit" }]
}
```

Add your own by appending an entry — no code changes needed. Items
are matched against `catalog.json` by `(category, name)`, so a pack
can freely mix items that came from different sources.

### Why you got item X, not item Y

When two sources ship a same-named item, `scan.py` doesn't just let
official tier or alphabetical source order win by default — it scores
each candidate's actual `.md` content and keeps the best one:

- has a real, substantive description (not a stub or a raw `|`)
- length/detail of the body — a 700-word skill beats a 40-word one
- has a usage/example section or code block
- skills that bundle scripts/references beat a lone `SKILL.md`
- placeholder content (`TODO`, near-empty bodies) is penalized

Official tier and source order only break a genuine tie in score —
they're no longer the primary decision. Every non-winning candidate
is recorded in `skipped_duplicates.json` with the actual reason, and
`install.py` surfaces it inline:

```text
1. (OFFICIAL) security-auditor — Adversarial security reviewer...
     -> skipped Awesome Claude Code Toolkit's version — kept scored higher on content (1.76 vs 1.43) — substantive description, 703-word body
```

Re-run `scan.py` to regenerate scores after sources update.

### Safety tripwire

Every item's raw content is scanned for patterns loosely modeled on
the checklist curated skill marketplaces use (prompt injection, data
exfiltration, secret detection, dangerous commands, obfuscation,
suspicious external fetches, credential access, privilege escalation).
Two tiers, by false-positive risk:

**Hard** — patterns with essentially no legitimate use in a skill's
own instructions (`curl | sh` pipelines, `rm -rf /`, fork bombs,
`eval(base64(...))`, reverse shells, credential-file exfiltration,
`chmod 777`, disabling OS security tooling, imperative prompt-injection
phrasing like "ignore previous instructions"). A hard match:

- always loses a dedup tiebreak against a clean candidate, even if
  it would otherwise score higher or come from an official source
- is tagged `[!RISKY: ...]` in the picker **even when it's the only
  copy of its name**, and gates install behind an explicit `y/N`
  confirmation, the same way unlicensed items do

**Soft** (`[i: ...]`) — patterns with plausible legitimate uses (bare
`sudo`, a fetch to a non-GitHub host, an AWS-key-shaped string, a
high-entropy token literal). Informational only — never gates install,
never affects dedup.

A pattern match sitting next to words like "risk", "detect", "block",
inside a `describe()`/`it()` test block, or wrapped in backticks/quotes
is treated as the item *documenting* the bad pattern (a security hook's
own detection rule) rather than instructing Claude to run it, and is
downgraded to the soft tier instead of gated — verified against the
real catalog: without this, Anthropic's own `architecture-critic` and
`test-engineer` agents, and hooks whose entire job is *blocking*
`chmod 777`, tripped the hard gate for quoting the exact pattern they
defend against.

This is a heuristic tripwire, not a security audit — it will still
have false positives (a skill that legitimately documents a real
`curl | sh` install command, inside a code block, stays hard-gated on
purpose) and can't catch everything. Read the source before trusting
anything it flags, or anything it doesn't.

### Optional LLM review

`python scan.py --llm-review` adds a second pass — an LLM judges only
the items that already triggered a hard or soft flag, or whose content
score lands in an ambiguous band — matching the same static-rules +
LLM-as-judge split used by tools like Cisco's MCP Scanner. Pick a
provider with `--llm-provider`:

```bash
python3 scan.py --llm-review                              # Anthropic (default)
python3 scan.py --llm-review --llm-provider openai         # needs OPENAI_API_KEY
python3 scan.py --llm-review --llm-provider gemini          # needs GEMINI_API_KEY
python3 scan.py --llm-review --llm-provider openrouter      # needs OPENROUTER_API_KEY
python3 scan.py --llm-review --llm-provider ollama           # local, no key — needs the server running
python3 scan.py --llm-review --llm-provider lmstudio         # local, no key — needs the server running
```

`--llm-model` overrides the provider's default model, `--llm-base-url`
overrides the endpoint (e.g. a remote ollama host). All six providers
are implemented as a **plain HTTP JSON call via Python's stdlib
`urllib`** — no SDK, no `pip install`, for any of them. It's fully
optional and never required for the base flow:

- a missing API key, or an unreachable local server (checked with a
  fast 3-second probe before reviewing anything, so this fails in
  seconds, not minutes), prints one line and skips the LLM pass — the
  rest of `scan.py` runs exactly as it does today
- results are cached by a hash of `(provider, model, content)` in
  `llm_review_cache.json`, so a re-scan only reviews items that are new
  or changed, not the whole catalog again
- shown in the picker as `[LLM: verdict confidence]`, and when a hard
  flag's y/N gate fires, the model's reasoning is printed first — so a
  flagged `curl | sh` install doc shows *why* it might be fine
  alongside the blunt regex label, instead of just the tag

Since it's plain HTTP with no SDK, this doesn't even add an opt-in
exception to the "git + python3 only" dependency claim above — it's
still zero pip installs, for any of the six providers.

See [SCANNING_RULES.md](SCANNING_RULES.md) for the full, step-by-step
breakdown of every rule above — scoring formula, dedup ranking, every
regex and why, and the false positives found (and fixed) by testing
this against the real 2,124-item catalog.

---

## 📦 Sources

Edit `sources.json` to add/remove repos. Each entry needs `id`,
`name`, `url`, and `tier` (`official` or `community`). Official-tier
items are always listed first in the picker and win any name collision
with a community item.

| Repo | Tier | License | Notes |
|---|---|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) | official | **none** ⚠️ | Anthropic's own skills; no LICENSE file, use via `/plugin install` |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | official | Apache-2.0 | Anthropic-curated plugin directory |
| [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) | community | MIT | ~100k★, 66 agents / 277 skills / 100 commands / 119 hooks |
| [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) | community | **none** ⚠️ | ~3.3k★, 19 agents / 20 commands / 24 hooks; no LICENSE file |
| [karanb192/claude-code-hooks](https://github.com/karanb192/claude-code-hooks) | community | MIT | Focused hook scripts (git safety, secret protection) |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | community | MIT | ~5.2k★, 108 agents / 333 skills / 105 commands / 5 hooks |
| [wshobson/agents](https://github.com/wshobson/agents) | community | MIT | Multi-harness plugin marketplace — 191 agents / 156 skills / 91 commands |
| [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit) | community | Apache-2.0 | 116 agents / 34 skills / 228 commands / 16 hooks |

Counts above are what `scan.py` currently extracts from each source
*after* cross-source de-duplication — name collisions are won by
whichever candidate scores higher on actual content (see
[Why you got item X, not item Y](#why-you-got-item-x-not-item-y)), so
a source's contribution here can be lower than its own advertised
totals. Run `python scan.py` for live numbers; they'll drift as
upstream repos change.

Adding a source doesn't require it to be spotless — it just requires
its license to be recorded honestly in `sources.json` so the picker
can warn you accurately.

---

## 🛡️ License & Attribution

**This repo's own code** (`scan.py`, `install.py`, `catalog/`, `install.sh`,
`install.ps1`, `tests/`) is MIT-licensed — see [LICENSE](LICENSE).

**Everything this tool installs is not covered by that license.** Each
item copied into `~/.claude/` remains governed by its *original*
source repo's license, listed in the table above. This tool never
bundles or redistributes third-party code in the repo itself — it only
clones sources at run time (into a gitignored `cache/`) and copies
files locally into your own `~/.claude/` on your explicit selection.

Two sources currently have **no LICENSE file** (`anthropics/skills`,
`disler/claude-code-hooks-mastery`), which under copyright law defaults
to all-rights-reserved rather than an open grant to reuse. `install.py`
flags these in the picker with `[!NO LICENSE]` and asks for explicit
confirmation before copying anything from them — review the source
repo yourself before confirming.

Every successful install appends a line to `~/.claude/ATTRIBUTION.md`
recording the item's name, source repo, license, and install path, so
you always have a record of what came from where.

---

## 🗂️ Files

| Path | What it is |
|---|---|
| `sources.json` | repo list you maintain |
| `SCANNING_RULES.md` | step-by-step writeup of every scoring/dedup/safety rule, in plain language |
| `cache/` | shallow git clones of each source (gitignored, `git pull`ed on re-scan) |
| `catalog.json` | generated: flat list of every installable item found |
| `skipped_duplicates.json` | generated: name collisions dropped during de-dup, and why |
| `llm_review_cache.json` | generated, opt-in: `--llm-review` verdicts keyed by (provider, model, content) hash |
| `packs.json` | curated bundles you maintain — see [Packs](#-packs) |
| `installed.json` | generated: manifest of what you've installed and from where |
| `scan.py` / `install.py` | the two scripts you actually run |
| `catalog/` | the scanning/scoring/safety/dedup/LLM-review logic `scan.py` orchestrates — see [SCANNING_RULES.md](SCANNING_RULES.md) |
| `install.sh` / `install.ps1` | one-line bootstrap for a fresh machine |
| `tests/` | `unittest`-based regression tests (stdlib only) — `python -m unittest discover -s tests -t .` |

## 📝 Notes

- Re-running `scan.py` does `git pull` on cached repos rather than
  re-cloning, so it's cheap to re-check sources periodically.
- Skills are copied as whole folders (they usually bundle scripts and
  references alongside `SKILL.md`); agents/commands/hooks are copied
  as single files.

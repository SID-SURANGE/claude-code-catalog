# Contributing to claude-code-catalog

This repo has two kinds of content, with different bars:

| Layer | What it is | Who can add it | Bar |
|---|---|---|---|
| `sources.json` | External repos the scanner pulls from | Anyone, via PR | Must pass the scoring/dedup/safety pipeline unmodified — no special-casing |
| `first-party/` | This repo's own hooks/agents/commands | Maintainer-reviewed | Original content only, advisory hooks only (see below) |

Most contributions should be a **new source**, not a new first-party item.

---

## Adding a source

1. Add an entry to `sources.json`:

   ```json
   {
     "id": "kebab-case-id",
     "name": "Human-readable name",
     "url": "https://github.com/owner/repo",
     "tier": "community",
     "license": "MIT",
     "license_note": ""
   }
   ```

   `tier` is `official` only for Anthropic-owned repos or this repo itself.
   Everything else is `community`.

2. Run the scanner and check the source is picked up cleanly:

   ```bash
   python3 scan.py
   ```

   Look at the printed summary for your source — item count, any
   `! license:` or safety warnings. A source with no LICENSE file or a
   restrictive license (GPL/AGPL family) is still accepted, but gets
   flagged in the picker; don't try to suppress the warning.

3. Run the tests:

   ```bash
   python3 -m unittest discover -s tests
   ```

4. Open a PR. Include the `scan.py` output for your new source in the PR
   description so reviewers can see item count and any flags without
   re-running it.

### What gets a source rejected

- Repos with no installable Claude Code items (agents/skills/commands/hooks
  the scanner can actually parse).
- Repos that are themselves aggregators of this repo or of each other
  (no re-aggregating a re-aggregation — attribution gets unverifiable).
- Anything the safety scan hard-flags that isn't a documented
  false-positive (quoted example, doc-only mention). If you believe a hard
  flag is wrong, fix the regex/rule in `catalog/` with a test, don't just
  add an exception for your source.

---

## Adding to `first-party/`

This is the higher bar, because unlike an external source, bugs here are
*this repo's* bugs, not an upstream repo's.

- [ ] **Original** — written from scratch for this repo. If informed by
  prior art, cite it as a design reference in `first-party/hooks/README.md`
  — don't copy text or logic.
- [ ] **Advisory, never blocking** — hooks inject findings via
  `additionalContext`; they must never `exit 2` or otherwise gate the
  session. This repo is installed by strangers via a picker — nobody
  should get blocked by an opinion they didn't sign up for.
- [ ] **Silent when clean** — zero output, zero tokens, in the common case.
- [ ] **At most one LLM call per turn** — and only if a provider is
  configured; unconfigured must be a silent no-op, not an error.
- [ ] **Tested** — add unit tests to `tests/test_first_party_hooks.py`
  covering the clean case and at least one flagged case.

New first-party hooks/agents/commands are maintainer-authored or
maintainer-reviewed before merge — open an issue describing the gap it
fills before writing the PR, so we don't duplicate one of the existing six
hooks or an agent that already exists in a scanned source.

---

## Local dev loop

```bash
python3 scan.py                              # rebuild catalog.json
python3 -m unittest discover -s tests -v      # run the suite (73 tests)
python3 install.py --pack first-party-quality # smoke-test the picker/install path
```

---

## Sign-off

By submitting a PR, you confirm you wrote the contribution yourself (or
have the rights to submit it) and agree to release it under this repo's
MIT license. Add to your PR description:

```text
Signed-off-by: Your Name <your@email.com>
```

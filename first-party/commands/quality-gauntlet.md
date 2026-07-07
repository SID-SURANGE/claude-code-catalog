---
name: quality-gauntlet
description: Run the full first-party quality battery on the whole repo — toolchain checks, both audit agents, and the test-integrity/completion/structure scanners — and write one scored QUALITY_REPORT.md. The manual "before I push" button.
---

Run the complete quality battery over this repository and produce a single
report. Execute the stages below in order; do not skip a stage silently —
if one cannot run, record why in the report.

## Stage 1 — toolchain (deterministic)

Detect the project's toolchain from its manifest files and run the full
repo-wide checks that exist for it:
- `pyproject.toml`/`setup.py` → ruff/flake8 if configured, mypy/pyright if
  configured, pytest.
- `package.json` → the repo's own `lint`, `typecheck`/`tsc --noEmit`, and
  `test` scripts.
- `go.mod` → `go vet ./...`, `go test ./...`.
- `Cargo.toml` → `cargo clippy`, `cargo test`.
- Anything else: use whatever check/test commands the repo documents.
Record pass/fail and the failure output (truncated) per check.

## Stage 2 — first-party scanners (deterministic)

The suite's hook scripts double as repo-wide scanners. Run each and
capture its output (they live in `~/.claude/hooks/` once installed; if not
found there, use `first-party/hooks/` in the claude-code-catalog repo):

```
python ~/.claude/hooks/test-integrity.py --scan .
python ~/.claude/hooks/completion-verifier.py --scan .
python ~/.claude/hooks/structure-sentry.py --scan .
```

(Windows: `python "%USERPROFILE%\.claude\hooks\<name>.py" --scan .`)

## Stage 3 — audit agents (semantic)

Launch both first-party agents on the current diff (or, if the worktree is
clean, on the last commit):
- **assumption-auditor** — implicit-assumption extraction, ranked by blast
  radius.
- **regression-cartographer** — caller/importer blast-radius map and
  must-re-test checklist.
Run them in parallel; include their findings verbatim (they are already
capped and ranked).

## Stage 4 — report

Write `QUALITY_REPORT.md` at the repo root:

- Header: date, git branch + short SHA, dirty/clean worktree.
- **Score out of 100**: start at 100; −15 per failing toolchain check,
  −5 per test-integrity or structure finding, −3 per unfinished-work
  marker, −5 per `breaks`-class regression finding, −2 per `unverified`
  high-blast-radius assumption. Floor at 0. Show the arithmetic.
- One section per stage with its findings (compact — file:line lists, not
  prose).
- **Top 5 actions**: the five fixes that recover the most points,
  concrete enough to hand to someone.

End by telling the user the score, the top action, and the report path.
Do not fix anything yourself in this run — this command measures; fixing
is a separate decision.

---
name: hook-doctor
description: Diagnose the first-party quality suite's own installation — hook files present, registered in settings.json, python resolvable, LLM provider reachable, goal log writable — and print exact repair steps. Run when you suspect hooks silently stopped firing.
---

Diagnose whether the first-party quality hooks are actually installed,
registered, and able to run. Hooks fail silently by design (they are
advisory and swallow their own errors), so "no findings for a week" can
mean "clean code" or "broken installation" — this command tells you which.

Run every check below; report each as PASS / FAIL / N/A with a one-line
reason, then finish with numbered repair steps for the failures only.

## Checks

1. **Files installed** — for each of `goal-anchor.py`,
   `stop-gate-review.py`, `test-integrity.py`, `completion-verifier.py`,
   `structure-sentry.py`, `claim-checker.py`: does it exist in
   `~/.claude/hooks/`? (Skip the rest of a hook's checks if absent — that
   hook is simply not installed, which may be intentional.)
2. **Registered** — read `~/.claude/settings.json` (and the project's
   `.claude/settings.json`): does each installed hook appear under the
   correct event (`UserPromptSubmit` for goal-anchor, `Stop` for
   stop-gate-review/completion-verifier/claim-checker, `PostToolUse` for
   test-integrity/structure-sentry)? An installed-but-unregistered hook
   never fires — this is the classic silent failure.
3. **Interpreter** — does the `python` command named in each registered
   hook command actually resolve (`python --version`), and is it
   Python 3? On macOS/Linux the registration must say `python3`.
4. **Smoke run** — pipe a minimal synthetic input through one
   deterministic hook and confirm exit code 0, e.g.:
   `echo {"tool_name":"Edit","tool_input":{"file_path":"x.py"}} | python ~/.claude/hooks/test-integrity.py`
   (quote appropriately for the shell in use).
5. **LLM reachability** (stop-gate-review only) — which provider does
   `CLAUDE_QUALITY_LLM_PROVIDER` select (default: anthropic)? Is its API
   key env var set, or for ollama/lmstudio does a 3-second probe of the
   base URL connect? An unconfigured provider means stop-gate-review
   no-ops silently — that may be intentional; report it as N/A with a
   note, not FAIL.
6. **Scratch state writable** — can you create and delete a file under
   the system temp dir's `claude-quality-suite/` folder (goal logs and
   caches live there)?
7. **Registration drift** — do the registered command paths match where
   the files actually are (a moved `.claude` dir breaks every hook at
   once)?

## Output

A short table of check results, then **Repairs**: exact commands or the
exact JSON block to merge into settings.json (take blocks from
`registrations.json` in the claude-code-catalog repo's `first-party/`
folder if available). If everything passes, say so in one line and stop —
do not invent maintenance work.

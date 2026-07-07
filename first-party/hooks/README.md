# First-party quality hooks

Six advisory hooks that watch the code an AI assistant (or you) writes and
feed findings back into the session — they **never block**, they inject
compact `additionalContext` and stay completely silent when everything is
clean (zero token cost in the common case).

| Hook | Event | What it catches |
|---|---|---|
| `goal-anchor.py` | UserPromptSubmit | (logger only) records each user prompt as a session goal |
| `stop-gate-review.py` | Stop | one LLM pass per turn: goal deviation vs. the logged prompts + real correctness defects in the diff |
| `test-integrity.py` | PostToolUse (Edit\|Write) | test weakening: deleted assertions, added skips/`.only`, exact checks loosened to existence checks |
| `completion-verifier.py` | Stop | unfinished work added this turn: TODO/FIXME, `NotImplementedError`, empty handlers |
| `structure-sentry.py` | PostToolUse (Write) | new-file structure mistakes: duplicate-purpose modules, source in test dirs, verbatim copy-paste, stray top-level dirs |
| `claim-checker.py` | Stop | final-message claims ("tests pass") with no matching successful command in the transcript |

Registration blocks live in `../registrations.json`; `install.py` prints the
right one after installing each hook. LLM configuration (only
`stop-gate-review.py` uses one) is documented in that file's docstring —
unconfigured means silent no-op, never an error.

`test-integrity.py`, `completion-verifier.py`, and `structure-sentry.py`
also run standalone with `--scan [path]` for a repo-wide sweep; the
`/quality-gauntlet` command uses exactly that.

## Originality & prior art

All code here is written from scratch for this repo (MIT). Design-level
prior art we knowingly differ from: tdd-guard (enforces TDD ordering, not
test weakening), spyrae/truthguard (claim-catching via pre-commit test
runs, not transcript cross-checks), FlorianBruniaux's example placeholder
hook (file-scan, not diff-scoped), mcpmarket Scope Guard (static roadmap
file, not the live conversation). No code was copied or adapted from any
of them.

#!/usr/bin/env python3
"""Session goal logger: fires on UserPromptSubmit and appends each real
user prompt to a per-session goal log. It produces NO output and adds
zero tokens to the session — it exists so stop-gate-review.py can later
judge the turn's diff against what the user actually asked for (semantic
goal-deviation detection anchored to the live conversation, not a static
roadmap file).

Install alongside stop-gate-review.py; useless on its own, harmless too.

Part of the claude-code-catalog first-party quality suite (MIT).
Written from scratch; see the suite README for prior-art references.
"""
import json
import sys
import tempfile
import time
from pathlib import Path

MAX_PROMPT_CHARS = 600
MAX_GOALS = 25


def log_path(session_id):
    d = Path(tempfile.gettempdir()) / "claude-quality-suite"
    d.mkdir(parents=True, exist_ok=True)
    return d / f"goals-{session_id or 'na'}.jsonl"


def main():
    try:
        data = json.load(sys.stdin)
        prompt = (data.get("prompt") or "").strip()
        if not prompt or prompt.startswith("/"):  # skip slash commands, they aren't goals
            sys.exit(0)
        path = log_path(data.get("session_id"))
        lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
        lines.append(json.dumps({"ts": int(time.time()), "prompt": prompt[:MAX_PROMPT_CHARS]}))
        path.write_text("\n".join(lines[-MAX_GOALS:]) + "\n", encoding="utf-8")
    except Exception:
        pass  # advisory tool: never break the session on our own bug
    sys.exit(0)


if __name__ == "__main__":
    main()

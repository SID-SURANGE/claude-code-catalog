#!/usr/bin/env python3
"""Advisory unfinished-work detector: fires on Stop and scans only the
lines ADDED in the current uncommitted diff for stubs the agent may have
left behind while declaring the task done — TODO/FIXME markers,
NotImplementedError, "not implemented" throws, empty exception handlers.
Diff-scoped on purpose: pre-existing TODOs in the codebase are not this
turn's problem. Never blocks; repeats of the same findings in one session
are reported once.

Also runs standalone: `python completion-verifier.py --scan [path]`
sweeps the whole worktree diff instead of staying quiet when clean.

Part of the claude-code-catalog first-party quality suite (MIT).
Written from scratch; see the suite README for prior-art references.
"""
import hashlib
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

STUB_PATTERNS = [
    (re.compile(r"\b(TODO|FIXME|XXX|HACK)\b"), "leftover TODO/FIXME marker"),
    (re.compile(r"\braise\s+NotImplementedError\b"), "raises NotImplementedError"),
    (re.compile(r"throw\s+new\s+Error\s*\(\s*['\"][^'\"]*not\s+implemented", re.IGNORECASE), "throws 'not implemented'"),
    (re.compile(r"\b(todo!|unimplemented!)\s*\("), "Rust todo!/unimplemented! macro"),
    (re.compile(r"^\s*pass\s*#\s*(placeholder|stub|implement)", re.IGNORECASE), "placeholder pass"),
    (re.compile(r"(except[^:\n]*:|catch\s*\([^)]*\)\s*\{)\s*(pass\s*)?$"), "empty exception handler"),
]
MAX_FINDINGS = 10


def parse_added_lines(diff):
    """Yield (file, line_no, text) for every added line in a unified diff."""
    current_file, line_no = None, 0
    for raw in diff.splitlines():
        if raw.startswith("+++ b/"):
            current_file = raw[6:]
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            line_no = int(m.group(1)) if m else 0
        elif raw.startswith("+") and not raw.startswith("+++") and current_file:
            yield current_file, line_no, raw[1:]
            line_no += 1


def find_stubs(root):
    try:
        diff = subprocess.run(
            ["git", "diff", "HEAD", "--unified=0", "--no-color"],
            capture_output=True, text=True, cwd=root, timeout=30,
        ).stdout
    except Exception:
        return []
    findings = []
    for file, line_no, text in parse_added_lines(diff):
        for pattern, label in STUB_PATTERNS:
            if pattern.search(text):
                findings.append(f"{file}:{line_no} — {label}: {text.strip()[:80]}")
                break
        if len(findings) >= MAX_FINDINGS:
            break
    return findings


def already_reported(session_id, findings):
    """One report per unique finding-set per session — avoids nagging on
    every subsequent Stop when the user chose to keep a TODO."""
    digest = hashlib.sha256("\n".join(findings).encode()).hexdigest()[:16]
    marker = Path(tempfile.gettempdir()) / "claude-quality-suite" / f"cv-{session_id or 'na'}-{digest}"
    if marker.exists():
        return True
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.touch()
    except OSError:
        pass
    return False


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--scan":
        root = sys.argv[2] if len(sys.argv) > 2 else "."
        findings = find_stubs(root)
        for f in findings:
            print(f)
        print(f"[completion-verifier] {len(findings)} unfinished-work marker(s) in the current diff")
        sys.exit(0)

    try:
        data = json.load(sys.stdin)
        if data.get("stop_hook_active"):
            sys.exit(0)  # this Stop was caused by a stop hook; don't loop
        findings = find_stubs(data.get("cwd") or ".")
        if not findings or already_reported(data.get("session_id"), findings):
            sys.exit(0)
        lines = "\n".join(f"- {f}" for f in findings)
        context = (
            f"[completion-verifier] Lines added this session contain unfinished-work markers:\n{lines}\n"
            "Finish them or tell the user explicitly that they are intentionally left."
        )
        print(json.dumps({
            "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": context[:1500]}
        }))
    except Exception:
        pass  # advisory tool: never break the session on our own bug
    sys.exit(0)


if __name__ == "__main__":
    main()

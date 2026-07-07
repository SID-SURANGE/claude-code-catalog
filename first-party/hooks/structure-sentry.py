#!/usr/bin/env python3
"""Advisory structure critic for freshly created files: fires on
PostToolUse (Write) only when the file is NEW to git, and flags the
structural mistakes AI assistants make most — a duplicate-purpose module
(second utils.py/helpers.ts), source dropped into a tests directory,
large blocks copy-pasted verbatim from an existing file, or a brand-new
top-level directory outside the project's existing conventions.
Never blocks.

Also runs standalone: `python structure-sentry.py --scan [path]` reports
same-stem module collisions across the whole repo.

Part of the claude-code-catalog first-party quality suite (MIT).
Written from scratch; see the suite README for prior-art references.
"""
import difflib
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path, PurePosixPath

TEST_DIR_RE = re.compile(r"(^|/)(tests?|__tests__|spec)(/|$)", re.IGNORECASE)
TEST_FILE_RE = re.compile(r"(^|/)test_[^/]+$|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$|(^|/)conftest\.py$", re.IGNORECASE)
GENERIC_STEMS = {"index", "main", "init", "__init__", "mod", "setup", "types", "constants", "config"}
DUP_WINDOW = 15          # lines that must match verbatim to call it copy-paste
MAX_SCAN_FILES = 300     # keep the copy-paste pass cheap on big repos
MAX_FILE_BYTES = 400_000


def git_files(root):
    try:
        out = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, cwd=root, timeout=30,
        )
        return out.stdout.splitlines() if out.returncode == 0 else []
    except Exception:
        return []


def is_tracked(root, file_path):
    try:
        out = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "--", file_path],
            capture_output=True, text=True, cwd=root, timeout=10,
        )
        return out.returncode == 0
    except Exception:
        return True  # unsure -> assume tracked, stay silent


def rel_to_root(root, file_path):
    try:
        return PurePosixPath(Path(file_path).resolve().relative_to(Path(root).resolve()).as_posix())
    except (ValueError, OSError):
        return None


def check_duplicate_stem(rel, tracked):
    stem = rel.stem.lower()
    if stem in GENERIC_STEMS:
        return None
    same, close = [], []
    for f in tracked:
        p = PurePosixPath(f)
        if p == rel or p.suffix != rel.suffix:
            continue
        other = p.stem.lower()
        if other == stem:
            same.append(f)
        elif other not in GENERIC_STEMS and difflib.SequenceMatcher(None, stem, other).ratio() >= 0.85:
            close.append(f)
    if same:
        return f"a module named '{rel.name}' already exists at {same[0]} — check whether this duplicates its purpose"
    if close:
        return f"name is very close to existing {close[0]} — a near-duplicate module, or should it live there?"
    return None


def check_layer(rel):
    in_test_dir = bool(TEST_DIR_RE.search(str(rel)))
    looks_like_test = bool(TEST_FILE_RE.search(str(rel)))
    if in_test_dir and not looks_like_test and rel.suffix in (".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java", ".cs"):
        return f"non-test source file placed inside a tests directory ({rel}) — production code doesn't belong there"
    return None


def check_new_top_dir(rel, tracked):
    if len(rel.parts) < 2:
        return None
    top = rel.parts[0]
    existing_tops = {PurePosixPath(f).parts[0] for f in tracked if "/" in f}
    if existing_tops and top not in existing_tops:
        return f"creates a new top-level directory '{top}/' — existing layout uses {', '.join(sorted(existing_tops)[:6])}"
    return None


def check_copy_paste(rel, content, tracked, root):
    new_lines = [l.rstrip() for l in content.splitlines()]
    if len(new_lines) < DUP_WINDOW:
        return None
    windows = {}
    for i in range(len(new_lines) - DUP_WINDOW + 1):
        window = tuple(new_lines[i:i + DUP_WINDOW])
        if sum(len(l.strip()) for l in window) > 60:  # skip blank/brace-only runs
            windows.setdefault(window, i + 1)
    if not windows:
        return None
    candidates = [f for f in tracked if PurePosixPath(f).suffix == rel.suffix and PurePosixPath(f) != rel]
    for f in candidates[:MAX_SCAN_FILES]:
        try:
            path = Path(root) / f
            if path.stat().st_size > MAX_FILE_BYTES:
                continue
            other = [l.rstrip() for l in path.read_text(encoding="utf-8", errors="ignore").splitlines()]
        except OSError:
            continue
        for j in range(len(other) - DUP_WINDOW + 1):
            window = tuple(other[j:j + DUP_WINDOW])
            if window in windows:
                return (
                    f"{DUP_WINDOW}+ lines starting at line {windows[window]} are identical to {f}:{j + 1} — "
                    "import/reuse it instead of copy-pasting"
                )
    return None


def run_hook():
    data = json.load(sys.stdin)
    if data.get("tool_name") != "Write":
        return None
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    root = data.get("cwd") or "."
    rel = rel_to_root(root, file_path)
    if rel is None or is_tracked(root, file_path):
        return None  # outside the repo, or an overwrite of an existing file

    tracked = git_files(root)
    if not tracked:
        return None
    findings = [f for f in (
        check_duplicate_stem(rel, tracked),
        check_layer(rel),
        check_new_top_dir(rel, tracked),
        check_copy_paste(rel, tool_input.get("content") or "", tracked, root),
    ) if f]
    if not findings:
        return None
    lines = "\n".join(f"- {f}" for f in findings)
    return (
        f"[structure-sentry] New file {rel} has structural concerns:\n{lines}\n"
        "If deliberate, briefly justify the choice to the user."
    )


def run_scan(root):
    tracked = git_files(root)
    stems = Counter(
        (PurePosixPath(f).stem.lower(), PurePosixPath(f).suffix)
        for f in tracked
        if PurePosixPath(f).stem.lower() not in GENERIC_STEMS
    )
    hits = 0
    for (stem, suffix), count in stems.items():
        if count > 1:
            paths = [f for f in tracked if PurePosixPath(f).stem.lower() == stem and PurePosixPath(f).suffix == suffix]
            print(f"'{stem}{suffix}' defined {count}x: {', '.join(paths)}")
            hits += 1
    print(f"[structure-sentry] scan complete: {hits} same-name module collision(s)")
    return 0


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--scan":
        sys.exit(run_scan(sys.argv[2] if len(sys.argv) > 2 else "."))
    try:
        context = run_hook()
    except Exception:
        sys.exit(0)  # advisory tool: never break the session on our own bug
    if context:
        print(json.dumps({
            "hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": context[:1500]}
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()

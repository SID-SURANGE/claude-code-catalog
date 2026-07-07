#!/usr/bin/env python3
"""Advisory guard against AI test-gaming: fires on PostToolUse (Edit|Write)
for test files and flags edits that weaken the suite instead of fixing the
code — deleted assertions, added skip markers, exact checks loosened to
existence checks. Never blocks; injects a compact finding list so the agent
(and you) see the weakening the moment it happens.

Also runs standalone: `python test-integrity.py --scan [path]` reports
skip markers and commented-out assertions across a whole repo.

Part of the claude-code-catalog first-party quality suite (MIT).
Written from scratch; see the suite README for prior-art references.
"""
import json
import re
import subprocess
import sys

TEST_FILE_RE = re.compile(
    r"(^|[/\\])(tests?|__tests__|spec)([/\\]|$)|(^|[/\\])test_[^/\\]+$"
    r"|_test\.[a-z]+$|\.(test|spec)\.[a-z]+$",
    re.IGNORECASE,
)

# One pattern set per concern; counted on old vs. new text.
ASSERTION_RE = re.compile(
    r"\bassert\b|\bexpect\s*\(|\bself\.assert\w+|\bassert_[a-z_]+\s*\(|\bt\.Error|\bt\.Fatal"
)
SKIP_RE = re.compile(
    r"@(pytest\.mark\.)?skip\w*|@unittest\.skip|\bxfail\b|\.skip\s*\(|\.only\s*\("
    r"|\bxit\s*\(|\bxdescribe\s*\(|\bit\.only\b|\bdescribe\.only\b|\bt\.Skip\s*\(|\[Ignore\]"
)
EXACT_CHECK_RE = re.compile(
    r"\btoBe\s*\(|\btoEqual\s*\(|\btoStrictEqual\s*\(|assertEqual\s*\(|assert\s+\w[\w.\[\]()]*\s*=="
)
EXISTENCE_CHECK_RE = re.compile(
    r"\btoBeDefined\s*\(|\btoBeTruthy\s*\(|assertIsNotNone\s*\(|is\s+not\s+None"
)
COMMENTED_ASSERT_RE = re.compile(r"^\s*(#|//)\s*.*(\bassert\b|\bexpect\s*\()", re.MULTILINE)

MAX_FINDINGS = 8


def compare(old_text, new_text):
    findings = []
    old_asserts = len(ASSERTION_RE.findall(old_text))
    new_asserts = len(ASSERTION_RE.findall(new_text))
    if new_asserts < old_asserts:
        findings.append(
            f"assertion count dropped {old_asserts} -> {new_asserts} — deleted assertions weaken the test, they don't fix the code"
        )

    old_skips = len(SKIP_RE.findall(old_text))
    new_skips = len(SKIP_RE.findall(new_text))
    if new_skips > old_skips:
        findings.append(
            f"skip/only marker added ({old_skips} -> {new_skips}) — a skipped test is a hidden red, not a green"
        )

    exact_drop = len(EXACT_CHECK_RE.findall(old_text)) - len(EXACT_CHECK_RE.findall(new_text))
    existence_rise = len(EXISTENCE_CHECK_RE.findall(new_text)) - len(EXISTENCE_CHECK_RE.findall(old_text))
    if exact_drop > 0 and existence_rise > 0:
        findings.append(
            "exact assertion loosened to an existence check (e.g. toEqual -> toBeDefined) — the test no longer verifies the value"
        )

    commented_rise = len(COMMENTED_ASSERT_RE.findall(new_text)) - len(COMMENTED_ASSERT_RE.findall(old_text))
    if commented_rise > 0:
        findings.append("assertion(s) commented out rather than removed or fixed")

    return findings


def git_head_content(file_path, cwd):
    """Previous committed version of the file, or '' if new/untracked."""
    try:
        rel = subprocess.run(
            ["git", "ls-files", "--full-name", "--", file_path],
            capture_output=True, text=True, cwd=cwd, timeout=10,
        ).stdout.strip()
        if not rel:
            return ""
        out = subprocess.run(
            ["git", "show", f"HEAD:{rel}"],
            capture_output=True, text=True, cwd=cwd, timeout=10,
        )
        return out.stdout if out.returncode == 0 else ""
    except Exception:
        return ""


def run_hook():
    data = json.load(sys.stdin)
    tool_input = data.get("tool_input") or {}
    file_path = tool_input.get("file_path") or ""
    if not TEST_FILE_RE.search(file_path):
        return None

    if data.get("tool_name") == "Edit":
        old_text = tool_input.get("old_string") or ""
        new_text = tool_input.get("new_string") or ""
    elif data.get("tool_name") == "Write":
        new_text = tool_input.get("content") or ""
        old_text = git_head_content(file_path, data.get("cwd"))
        if not old_text:
            return None  # brand-new test file: nothing to weaken
    else:
        return None

    findings = compare(old_text, new_text)
    if not findings:
        return None
    lines = "\n".join(f"- {f}" for f in findings[:MAX_FINDINGS])
    return (
        f"[test-integrity] The edit to {file_path} looks like test weakening:\n{lines}\n"
        "If intentional, state why to the user; otherwise fix the code under test instead."
    )


def run_scan(root):
    """Repo-wide advisory sweep (no baseline diff): skip markers and
    commented-out assertions currently present in test files."""
    try:
        files = subprocess.run(
            ["git", "ls-files"], capture_output=True, text=True, cwd=root, timeout=30,
        ).stdout.splitlines()
    except Exception:
        files = []
    hits = 0
    for f in files:
        if not TEST_FILE_RE.search(f):
            continue
        try:
            text = open(f"{root}/{f}", encoding="utf-8", errors="ignore").read()
        except OSError:
            continue
        skips = len(SKIP_RE.findall(text))
        commented = len(COMMENTED_ASSERT_RE.findall(text))
        if skips or commented:
            hits += 1
            print(f"{f}: {skips} skip/only marker(s), {commented} commented-out assertion(s)")
    print(f"[test-integrity] scan complete: {hits} test file(s) with findings")
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
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": context[:1500],
            }
        }))
    sys.exit(0)


if __name__ == "__main__":
    main()

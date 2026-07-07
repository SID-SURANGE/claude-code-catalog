#!/usr/bin/env python3
"""Advisory claim-vs-reality check: fires on Stop, reads the session
transcript, extracts verifiable claims from the assistant's final message
("tests pass", "build succeeds", "lint clean", "typecheck passes") and
verifies that a matching command actually ran — without error — since the
user's last prompt. If the claim was never exercised, it says so. Never
blocks. Deliberately conservative: only unambiguous claim phrasings are
matched, so silence is common and correct.

Part of the claude-code-catalog first-party quality suite (MIT).
Written from scratch; see the suite README for prior-art references
(spyrae/truthguard approaches this differently, via pre-commit test runs).
"""
import json
import re
import sys

# claim category -> (claim regex over the final message, command regex that would substantiate it)
CLAIMS = {
    "tests": (
        re.compile(r"\b(all\s+)?tests?( suite)?\s+(now\s+)?(pass(es|ing)?|are\s+passing|green)\b", re.IGNORECASE),
        re.compile(r"\b(pytest|unittest|npm\s+(run\s+)?test|npx\s+(vitest|jest)|vitest|jest|go\s+test|cargo\s+test|dotnet\s+test|mvn\s+test|rspec|phpunit|ctest)\b"),
    ),
    "build": (
        re.compile(r"\bbuild\s+(now\s+)?(succeed(s|ed)?|pass(es|ed)?|is\s+clean|compiles?)\b", re.IGNORECASE),
        re.compile(r"\b(npm\s+run\s+build|yarn\s+build|pnpm\s+build|cargo\s+build|go\s+build|dotnet\s+build|mvn\s+(package|install)|make\b|msbuild|tsc\b)"),
    ),
    "lint": (
        re.compile(r"\blint(er|ing)?\s+(is\s+)?(now\s+)?(clean|pass(es|ed)?)\b", re.IGNORECASE),
        re.compile(r"\b(ruff|eslint|flake8|pylint|golangci-lint|clippy|rubocop|biome)\b"),
    ),
    "typecheck": (
        re.compile(r"\btype[- ]?check(s|ing)?\s+(now\s+)?(pass(es|ed)?|is\s+clean|clean)\b", re.IGNORECASE),
        re.compile(r"\b(mypy|pyright|tsc\b|ty\s+check|flow\s+check)"),
    ),
}


def read_transcript(path):
    entries = []
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    except OSError:
        pass
    return entries


def is_real_user_prompt(entry):
    """User-typed message, not a tool_result carrier."""
    if entry.get("type") != "user":
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return any(b.get("type") == "text" for b in content if isinstance(b, dict)) and not any(
            b.get("type") == "tool_result" for b in content if isinstance(b, dict)
        )
    return False


def turn_slice(entries):
    last_user = 0
    for i, e in enumerate(entries):
        if is_real_user_prompt(e):
            last_user = i
    return entries[last_user:]


def final_assistant_text(entries):
    for e in reversed(entries):
        if e.get("type") != "assistant":
            continue
        content = (e.get("message") or {}).get("content")
        if isinstance(content, list):
            text = " ".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
            if text.strip():
                return text
        elif isinstance(content, str) and content.strip():
            return content
    return ""


def successful_commands(entries):
    """Bash commands run this turn whose tool_result was not an error."""
    commands, errored = {}, set()
    for e in entries:
        content = (e.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for b in content:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use" and b.get("name") == "Bash":
                commands[b.get("id")] = (b.get("input") or {}).get("command", "")
            elif b.get("type") == "tool_result" and b.get("is_error"):
                errored.add(b.get("tool_use_id"))
    return [cmd for use_id, cmd in commands.items() if use_id not in errored]


def check(entries):
    turn = turn_slice(entries)
    text = final_assistant_text(turn)
    if not text:
        return []
    ran = " ; ".join(successful_commands(turn))
    findings = []
    for label, (claim_re, cmd_re) in CLAIMS.items():
        m = claim_re.search(text)
        if m and not cmd_re.search(ran):
            findings.append(
                f'claimed "{m.group(0).strip()}" but no successful {label} command ran since the last user prompt'
            )
    return findings


def main():
    try:
        data = json.load(sys.stdin)
        if data.get("stop_hook_active"):
            sys.exit(0)  # this Stop was caused by a stop hook; don't loop
        entries = read_transcript(data.get("transcript_path") or "")
        findings = check(entries)
        if findings:
            lines = "\n".join(f"- {f}" for f in findings)
            context = (
                f"[claim-checker] The final message makes claims the transcript doesn't back up:\n{lines}\n"
                "Run the command(s) to verify, or correct the claim for the user."
            )
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": context[:1500]}
            }))
    except Exception:
        pass  # advisory tool: never break the session on our own bug
    sys.exit(0)


if __name__ == "__main__":
    main()

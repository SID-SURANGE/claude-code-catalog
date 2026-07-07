#!/usr/bin/env python3
"""The suite's single LLM pass per turn: fires on Stop, sends ONE combined
prompt — the session's goal log (written by goal-anchor.py) plus the
current uncommitted diff — to a configurable LLM, and asks two questions
at once: (1) does the diff serve the stated goals (deviation / scope
creep / silently dropped requirements), and (2) does it contain real
correctness defects (unhandled errors, race conditions, resource leaks,
off-by-one, dead branches — explicitly NOT style, NOT security: dedicated
security tooling covers that). Advisory only, never blocks.

Cost controls: verdicts are cached by content hash so repeated Stops on
an unchanged diff are free; an unconfigured or unreachable provider means
a silent no-op, never an error. Configure with:
  CLAUDE_QUALITY_LLM_PROVIDER  anthropic (default) | openai | gemini | openrouter | ollama | lmstudio
  CLAUDE_QUALITY_LLM_MODEL     override the provider default
  CLAUDE_QUALITY_LLM_BASE_URL  override the endpoint (e.g. remote ollama)
Keys come from the provider's usual env var (ANTHROPIC_API_KEY, ...).

Zero dependencies: plain HTTPS via urllib, same design ethos as the
catalog's own --llm-review. Part of the claude-code-catalog first-party
quality suite (MIT). Written from scratch.
"""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from pathlib import Path

MAX_DIFF_CHARS = 14000
MAX_FINDINGS = 6
HTTP_TIMEOUT = 40

SYSTEM_PROMPT = (
    "You review a code diff produced by an AI coding assistant during one work session. "
    "You are given the user's actual prompts (the goals) and the uncommitted git diff. "
    "Answer in strict JSON only, no markdown, with this shape: "
    '{"deviation": {"ok": true|false, "notes": ["..."]}, "bugs": [{"where": "file:line", "issue": "..."}]}. '
    "deviation.notes: changes that serve no stated goal, and stated goals not addressed by the diff. "
    "bugs: only real correctness defects — unhandled errors, race conditions, resource leaks, "
    "off-by-one, dead or unreachable branches, broken edge cases. "
    "Do NOT report style, naming, formatting, or security findings. "
    "Empty notes/bugs arrays and ok=true mean the work is clean; say so rather than inventing findings."
)


def _post(url, headers, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def call_anthropic(user_text, model, key, base_url):
    out = _post(
        f"{base_url}/v1/messages",
        {"x-api-key": key, "anthropic-version": "2023-06-01"},
        {"model": model, "max_tokens": 1024, "system": SYSTEM_PROMPT,
         "messages": [{"role": "user", "content": user_text}]},
    )
    return "".join(b.get("text", "") for b in out.get("content", []))


def call_openai_compatible(user_text, model, key, base_url):
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    out = _post(
        f"{base_url}/v1/chat/completions", headers,
        {"model": model, "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_text},
        ]},
    )
    return out["choices"][0]["message"]["content"]


def call_gemini(user_text, model, key, base_url):
    out = _post(
        f"{base_url}/v1beta/models/{model}:generateContent?key={key}", {},
        {"system_instruction": {"parts": [{"text": SYSTEM_PROMPT}]},
         "contents": [{"parts": [{"text": user_text}]}]},
    )
    return out["candidates"][0]["content"]["parts"][0]["text"]


PROVIDERS = {
    "anthropic": ("ANTHROPIC_API_KEY", "claude-haiku-4-5-20251001", "https://api.anthropic.com", call_anthropic),
    "openai": ("OPENAI_API_KEY", "gpt-4o-mini", "https://api.openai.com", call_openai_compatible),
    "gemini": ("GEMINI_API_KEY", "gemini-2.0-flash", "https://generativelanguage.googleapis.com", call_gemini),
    "openrouter": ("OPENROUTER_API_KEY", "anthropic/claude-haiku-4.5", "https://openrouter.ai/api", call_openai_compatible),
    "ollama": (None, "qwen2.5-coder", "http://localhost:11434", call_openai_compatible),
    "lmstudio": (None, "local-model", "http://localhost:1234", call_openai_compatible),
}


def get_diff(root):
    try:
        out = subprocess.run(
            ["git", "diff", "HEAD", "--no-color"],
            capture_output=True, text=True, cwd=root, timeout=30,
        )
        return out.stdout[:MAX_DIFF_CHARS] if out.returncode == 0 else ""
    except Exception:
        return ""


def get_goals(session_id):
    path = Path(tempfile.gettempdir()) / "claude-quality-suite" / f"goals-{session_id or 'na'}.jsonl"
    goals = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                goals.append(json.loads(line)["prompt"])
            except (json.JSONDecodeError, KeyError):
                continue
    return goals


def cache_file():
    d = Path(tempfile.gettempdir()) / "claude-quality-suite"
    d.mkdir(parents=True, exist_ok=True)
    return d / "stop-gate-cache.json"


def parse_verdict(raw):
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`").lstrip("json").strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start == -1 or end == -1:
        return None
    try:
        return json.loads(raw[start:end + 1])
    except json.JSONDecodeError:
        return None


def review(diff, goals):
    provider_name = os.environ.get("CLAUDE_QUALITY_LLM_PROVIDER", "anthropic")
    if provider_name not in PROVIDERS:
        return None
    env_key, default_model, default_base, call = PROVIDERS[provider_name]
    key = os.environ.get(env_key) if env_key else None
    if env_key and not key:
        return None  # unconfigured -> silent no-op
    model = os.environ.get("CLAUDE_QUALITY_LLM_MODEL") or default_model
    base_url = os.environ.get("CLAUDE_QUALITY_LLM_BASE_URL") or default_base
    if not env_key:
        try:  # local server: fast probe so an offline ollama costs 3s, not 40
            urllib.request.urlopen(base_url, timeout=3)
        except urllib.error.HTTPError:
            pass  # reachable, just not a 200 on /
        except Exception:
            return None

    goals_text = "\n".join(f"- {g}" for g in goals) if goals else "(no goal log for this session)"
    user_text = f"USER GOALS THIS SESSION:\n{goals_text}\n\nUNCOMMITTED DIFF:\n{diff}"
    try:
        return parse_verdict(call(user_text, model, key, base_url))
    except Exception:
        return None


def format_context(verdict):
    parts = []
    deviation = verdict.get("deviation") or {}
    notes = [n for n in (deviation.get("notes") or []) if n][:MAX_FINDINGS]
    if not deviation.get("ok", True) and notes:
        parts.append("Goal deviation:\n" + "\n".join(f"- {n}" for n in notes))
    bugs = [b for b in (verdict.get("bugs") or []) if isinstance(b, dict)][:MAX_FINDINGS]
    if bugs:
        parts.append("Possible defects:\n" + "\n".join(f"- {b.get('where', '?')}: {b.get('issue', '')}" for b in bugs))
    if not parts:
        return None
    return (
        "[stop-gate-review] External review of this session's diff:\n"
        + "\n".join(parts)
        + "\nThese are advisory findings from a second model — verify each before acting, dismiss with a stated reason."
    )


def main():
    try:
        data = json.load(sys.stdin)
        if data.get("stop_hook_active"):
            sys.exit(0)  # this Stop was caused by a stop hook; don't loop
        diff = get_diff(data.get("cwd") or ".")
        if not diff.strip():
            sys.exit(0)
        goals = get_goals(data.get("session_id"))

        digest = hashlib.sha256(
            (diff + "\x00".join(goals) + os.environ.get("CLAUDE_QUALITY_LLM_PROVIDER", "anthropic")).encode()
        ).hexdigest()
        cf = cache_file()
        cache = json.loads(cf.read_text(encoding="utf-8")) if cf.exists() else {}
        if digest in cache:
            sys.exit(0)  # same diff+goals already reviewed this machine

        verdict = review(diff, goals)
        if verdict is None:
            sys.exit(0)
        cache[digest] = True
        cf.write_text(json.dumps(dict(list(cache.items())[-200:])), encoding="utf-8")

        context = format_context(verdict)
        if context:
            print(json.dumps({
                "hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": context[:2000]}
            }))
    except Exception:
        pass  # advisory tool: never break the session on our own bug
    sys.exit(0)


if __name__ == "__main__":
    main()

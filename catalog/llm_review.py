import hashlib
import json
import os
import re
from datetime import datetime, timezone

from catalog.paths import ROOT

LLM_REVIEW_CACHE_FILE = ROOT / "llm_review_cache.json"
LLM_SCORE_BAND = (0.2, 0.5)


def needs_llm_review(item):
    return bool(item["harmful_flags"]) or bool(item["review_flags"]) or (
        LLM_SCORE_BAND[0] <= item["content_score"] <= LLM_SCORE_BAND[1]
    )


def load_llm_cache():
    if LLM_REVIEW_CACHE_FILE.exists():
        return json.loads(LLM_REVIEW_CACHE_FILE.read_text())
    return {}


def save_llm_cache(cache):
    LLM_REVIEW_CACHE_FILE.write_text(json.dumps(cache, indent=2))


LLM_REVIEW_SYSTEM_PROMPT = """You are a security reviewer for a third-party Claude Code skill/agent/command \
catalog. You will be shown the raw markdown/script content of one installable item. Classify it strictly \
on its literal content — do not assume malicious intent from mere presence of security-testing or \
offensive-security terminology if the stated purpose is legitimate (e.g. a pentesting or red-team skill \
is not automatically malicious).

Return JSON only, no other text: {"verdict": "safe"|"suspicious"|"malicious", "confidence": 0.0-1.0, \
"reasoning": "<=280 chars"}"""


def _http_post_json(url, headers, payload, timeout=60, retries=2):
    import time
    import urllib.error
    import urllib.request

    req_body = json.dumps(payload).encode("utf-8")
    last_error = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(
                url, data=req_body,
                headers={"Content-Type": "application/json", **headers}, method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            last_error = e
            # 429 (rate limit) and 5xx (transient server error) are worth a
            # retry with backoff; anything else (bad request, auth failure)
            # won't fix itself on retry.
            if e.code != 429 and e.code < 500:
                raise
        except Exception as e:
            last_error = e
        if attempt < retries:
            time.sleep(2 ** attempt)
    raise last_error


def _extract_json(raw_text):
    """LLMs frequently wrap JSON in ```json fences despite instructions not
    to. Try a direct parse first, then strip fences / grab the first {...}
    block before giving up."""
    raw_text = raw_text.strip()
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        pass

    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_text, re.DOTALL)
    if fenced:
        return json.loads(fenced.group(1))

    brace_match = re.search(r"\{.*\}", raw_text, re.DOTALL)
    if brace_match:
        return json.loads(brace_match.group(0))

    raise json.JSONDecodeError("no JSON object found in LLM response", raw_text, 0)


def _call_anthropic(system, user, model, api_key, base_url):
    body = _http_post_json(
        f"{base_url}/v1/messages",
        {"x-api-key": api_key, "anthropic-version": "2023-06-01"},
        {"model": model, "max_tokens": 300, "system": system, "messages": [{"role": "user", "content": user}]},
    )
    return body["content"][0]["text"]


def _call_openai_compatible(system, user, model, api_key, base_url):
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    body = _http_post_json(
        f"{base_url}/v1/chat/completions",
        headers,
        {
            "model": model,
            "max_tokens": 300,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
        },
    )
    return body["choices"][0]["message"]["content"]


def _call_gemini(system, user, model, api_key, base_url):
    body = _http_post_json(
        f"{base_url}/v1beta/models/{model}:generateContent?key={api_key}",
        {},
        {"system_instruction": {"parts": [{"text": system}]}, "contents": [{"parts": [{"text": user}]}]},
    )
    return body["candidates"][0]["content"]["parts"][0]["text"]


# Every provider is a plain HTTPS/HTTP JSON call via urllib (stdlib only) —
# no SDK, no pip install, for any of them. Local providers (ollama, lmstudio)
# need no API key but do need their server running; that failure is caught
# per-item in run_llm_review() like any other request error.
LLM_PROVIDERS = {
    "anthropic": {
        "env_key": "ANTHROPIC_API_KEY", "default_model": "claude-sonnet-5",
        "default_base_url": "https://api.anthropic.com", "call": _call_anthropic,
    },
    "openai": {
        "env_key": "OPENAI_API_KEY", "default_model": "gpt-4o-mini",
        "default_base_url": "https://api.openai.com", "call": _call_openai_compatible,
    },
    "gemini": {
        "env_key": "GEMINI_API_KEY", "default_model": "gemini-2.0-flash",
        "default_base_url": "https://generativelanguage.googleapis.com", "call": _call_gemini,
    },
    "openrouter": {
        "env_key": "OPENROUTER_API_KEY", "default_model": "anthropic/claude-sonnet-4.5",
        "default_base_url": "https://openrouter.ai/api", "call": _call_openai_compatible,
    },
    "ollama": {
        "env_key": None, "default_model": "llama3.1",
        "default_base_url": "http://localhost:11434", "call": _call_openai_compatible,
    },
    "lmstudio": {
        "env_key": None, "default_model": "local-model",
        "default_base_url": "http://localhost:1234", "call": _call_openai_compatible,
    },
}


def run_llm_review(items, cache, provider_name, model_override, base_url_override):
    provider = LLM_PROVIDERS[provider_name]
    model = model_override or provider["default_model"]
    base_url = base_url_override or provider["default_base_url"]

    api_key = None
    if provider["env_key"]:
        api_key = os.environ.get(provider["env_key"])
        if not api_key:
            print(
                f"  ! --llm-review --llm-provider {provider_name} requires {provider['env_key']} "
                "to be set — skipping, base scan unaffected."
            )
            return
    else:
        # Local providers (ollama, lmstudio) have no key to check, so probe
        # reachability once up front with a short timeout — otherwise an
        # unreachable/firewalled local server means every triggered item
        # hangs on its own request timeout instead of failing fast.
        import urllib.error
        import urllib.request

        try:
            urllib.request.urlopen(base_url, timeout=3)
        except urllib.error.HTTPError:
            pass  # server responded (even with an error status) — it's reachable
        except Exception:
            print(
                f"  ! --llm-review --llm-provider {provider_name} could not reach {base_url} "
                "— is the local server running? Skipping, base scan unaffected."
            )
            return

    triggered = [i for i in items if needs_llm_review(i)]
    print(f"\nLLM-reviewing {len(triggered)} flagged/borderline item(s) via {provider_name}/{model}...")

    for item in triggered:
        text = item["_raw_text"][:6000]
        digest = hashlib.sha256(f"{provider_name}:{model}:{text}".encode("utf-8", errors="ignore")).hexdigest()
        if digest in cache:
            item["llm_review"] = cache[digest]
            continue

        user_prompt = (
            f"Item name: {item['name']}  Category: {item['category']}  Source: {item['source_name']}\n"
            f"Flags already detected by static regex: harmful={item['harmful_flags']}, "
            f"review={item['review_flags']}\n\n--- CONTENT ---\n{text}"
        )
        try:
            raw_text = provider["call"](LLM_REVIEW_SYSTEM_PROMPT, user_prompt, model, api_key, base_url)
            verdict = _extract_json(raw_text)
        except Exception as e:
            print(f"  ! LLM review failed for {item['name']} via {provider_name}: {e}")
            continue

        result = {
            "verdict": verdict.get("verdict", "unknown"),
            "confidence": verdict.get("confidence"),
            "reasoning": verdict.get("reasoning", ""),
            "provider": provider_name,
            "model": model,
            "reviewed_at": datetime.now(timezone.utc).isoformat(),
        }
        item["llm_review"] = result
        cache[digest] = result

    save_llm_cache(cache)

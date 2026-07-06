import math
import re

# Deterministic, offline safety scan — flags patterns that read as
# destructive or exfiltration-shaped. Not a substitute for actually
# reading a skill before trusting it; just a first-pass tripwire.
# Hard tier: gates install behind a y/N confirm and always loses a dedup
# tiebreak, even against an official-tier or higher-scoring candidate.
# Kept to patterns with essentially no legitimate use in a skill's own
# instructions, to keep false positives rare.
HARMFUL_PATTERNS = [
    ("curl-pipe-shell", r"(curl|wget)\s+[^\n|]*\|\s*(sudo\s+)?(ba)?sh\b"),
    ("rm-rf-root", r"rm\s+-rf\s+/(?:\s|$|\*)"),
    ("fork-bomb", r":\(\)\s*\{\s*:\s*\|\s*:\s*&\s*\}\s*;\s*:"),
    ("base64-eval", r"eval\s*\(.{0,40}base64"),
    ("reverse-shell", r"(nc|ncat)\s+-e\s+/bin/(ba)?sh|/dev/tcp/\d"),
    ("credential-exfil", r"curl\s+[^\n]*(\.aws/credentials|\.ssh/id_rsa|/etc/passwd)"),
    ("chmod-777", r"chmod\s+(-R\s+)?0?777\b"),
    (
        "disable-security-tool",
        r"\b(setenforce\s+0|systemctl\s+(stop|disable)\s+(firewalld|ufw|apparmor)"
        r"|ufw\s+disable|xattr\s+-d\s+com\.apple\.quarantine)\b",
    ),
]

# Checked separately from the generic loop above because a quoted example
# of the phrase ("...crafted to look like 'ignore previous instructions'...")
# reads very differently from the phrase used as an actual imperative — the
# former shows up in exactly the security-conscious agents we trust most
# (verified against real catalog data: Anthropic's own architecture-critic
# and test-engineer quote this phrase as an example of what to defend
# against). Quoted mentions are downgraded to a soft review flag instead of
# a hard gate.
PROMPT_INJECTION_RE = re.compile(
    r"(ignore\s+(all\s+)?(the\s+)?(previous|prior|above)\s+instructions"
    r"|disregard\s+(the\s+)?system\s+prompt|you\s+are\s+now\s+DAN\b|do\s+anything\s+now\b)",
    re.IGNORECASE,
)


def check_prompt_injection(text):
    """Returns 'hard' if found as a bare imperative, 'soft' if only ever quoted, None if absent."""
    found_quoted = False
    for m in PROMPT_INJECTION_RE.finditer(text):
        before = text[max(0, m.start() - 3):m.start()]
        after = text[m.end():m.end() + 3]
        if any(q in before or q in after for q in ('"', "'", "`")):
            found_quoted = True
            continue
        return "hard"
    return "soft" if found_quoted else None


# Soft tier: informational only. Never gates install, never affects dedup
# ranking — these patterns have plausible legitimate uses (a normal install
# doc using sudo, a vendor fetch from a non-github host), so flagging them
# as hard would drown the signal in false positives.
# Secret/key-shaped patterns, each matched against a real provider's fixed
# key format. Every hit is checked against PLACEHOLDER_MARKERS below before
# being flagged, since docs frequently embed a provider's own canonical
# example key (e.g. AWS's own docs use AKIAIOSFODNN7EXAMPLE) or an obvious
# fill-in-the-blank placeholder, which would otherwise read as a real leak.
SECRET_PATTERNS = [
    ("aws-access-key", r"\bAKIA[0-9A-Z]{16}\b"),
    ("aws-temp-session-key", r"\bASIA[0-9A-Z]{16}\b"),
    ("github-token", r"\bgh[pousr]_[A-Za-z0-9]{36,}\b"),
    ("slack-token", r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    ("stripe-key", r"\b(sk|rk)_live_[A-Za-z0-9]{20,}\b"),
    ("google-api-key", r"\bAIza[0-9A-Za-z_\-]{35}\b"),
    ("private-key-block", r"-----BEGIN (RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    ("azure-storage-key", r"\bAccountKey=[A-Za-z0-9+/]{80,}={0,2}"),
    ("gcp-service-account-key", r'"type"\s*:\s*"service_account"'),
    ("twilio-api-key", r"\bSK[0-9a-fA-F]{32}\b"),
    ("sendgrid-api-key", r"\bSG\.[A-Za-z0-9_\-]{22}\.[A-Za-z0-9_\-]{43}\b"),
    ("npm-token", r"\bnpm_[A-Za-z0-9]{36}\b"),
    ("jwt", r"\beyJ[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\.[A-Za-z0-9_\-]+\b"),
    ("anthropic-api-key", r"\bsk-ant-[A-Za-z0-9_\-]{20,}\b"),
    ("openai-api-key", r"\bsk-(proj-)?[A-Za-z0-9]{20,}\b"),
]

# Handled separately from SECRET_PATTERNS because "is this a placeholder"
# needs the username/password parts individually, not a substring check on
# the whole match — connection-string placeholders overwhelmingly follow a
# "same word twice" or "generic word" convention (user:pass@, postgres:
# postgres@, test:test@) that's better generalized than enumerated.
DB_CONNECTION_RE = re.compile(
    r"\b(?:postgres|postgresql|mysql|mongodb(?:\+srv)?|redis)://([^:\s/]+):([^@\s/]+)@", re.IGNORECASE
)
GENERIC_CREDENTIAL_WORDS = {
    "user", "username", "pass", "password", "admin", "test", "demo",
    "guest", "root", "changeme",
}


def _is_placeholder_db_credential(user, password):
    # Only the *password* being a generic word is a reliable placeholder
    # signal — a generic *username* (e.g. "admin:S3cr3tP4ss@") is common in
    # real production credentials and shouldn't suppress a real-looking one.
    user, password = user.lower(), password.lower()
    if user == password:
        return True
    if password in GENERIC_CREDENTIAL_WORDS:
        return True
    return _is_placeholder(user) or _is_placeholder(password)


def scan_db_connection_strings(text):
    for m in DB_CONNECTION_RE.finditer(text):
        if not _is_placeholder_db_credential(m.group(1), m.group(2)):
            return ["db-connection-string-with-credentials"]
    return []

# Substring markers (case-insensitive) that mean a secret-shaped match is
# almost certainly a placeholder/example, not a real leaked credential.
PLACEHOLDER_MARKERS = (
    "example", "your_", "your-", "yourkey", "placeholder", "changeme",
    "xxxx", "insert_", "insert-", "replace_", "replace-", "dummy",
    "sample", "fake", "1234567890", "abcdef",
    # generic connection-string credential placeholders
    "{{", "****", ":pass@", ":password@", "postgres:postgres",
    "root:root", "admin:admin",
)


def _is_placeholder(token):
    lowered = token.lower()
    return any(marker in lowered for marker in PLACEHOLDER_MARKERS)


# Soft tier, non-secret: informational only. Never gates install, never
# affects dedup ranking — these patterns have plausible legitimate uses (a
# normal install doc using sudo, a vendor fetch from a non-github host), so
# flagging them as hard would drown the signal in false positives.
REVIEW_PATTERNS = [
    ("sudo-usage", r"\bsudo\s+"),
    (
        "suspicious-external-fetch",
        r"(curl|wget)\s+[^\n]*https?://(?!(www\.)?(github\.com|raw\.githubusercontent\.com|"
        r"githubusercontent\.com|pypi\.org|files\.pythonhosted\.org|registry\.npmjs\.org|npmjs\.com))"
        r"[^\s\"']*|(curl|wget)\s+[^\n]*https?://(\d{1,3}\.){3}\d{1,3}"
        r"|(pastebin\.com|hastebin\.com|transfer\.sh|ngrok\.io)\b",
    ),
    (
        "credential-file-read-broad",
        r"\b(cat|open)\s*\(?[^\n]*(\.ssh/id_rsa|\.netrc|/etc/shadow)\b",
    ),
]


# A hard pattern match sitting next to these signals almost always means the
# item is *documenting* the bad pattern (a security hook's own detection
# rule, a "don't do this" bullet list) rather than instructing Claude to run
# it. Verified against real catalog data: chmod-777 hits inside a hook named
# "block-dangerous-commands" and a "safety-guard" skill's own don't-do-this
# list were false positives under the naive scan.
#
# Known limitation — this rule is a public, gameable escape hatch: a
# deliberately malicious skill author can read this exact wordlist and word
# their payload to include one of these words next to a real destructive
# command, downgrading it from a hard gate to a soft tag. There's no
# regex-only fix for this (tightening the wordlist just brings back the
# false positives on legitimate security tooling) — see SCANNING_RULES.md.
DOCUMENTED_AS_EXAMPLE_RE = re.compile(
    r"(reason\s*:|risk|dangerous|detect|prevent|block|forbidden|disallow|matches\s*:"
    r"|do\s+not|don't|avoid|never\s+(run|do)|describe\(|it\(|should|^\s*[-*]\s)",
    re.IGNORECASE | re.MULTILINE,
)
REGEX_LITERAL_CONTEXT_RE = re.compile(r"\\s\+|\\b|\\d|\.\*|\bregex\b")


def _looks_like_documentation(text, match):
    window = text[max(0, match.start() - 50):match.end() + 50]
    tight_before = text[max(0, match.start() - 3):match.start()]
    tight_after = text[match.end():match.end() + 3]
    quoted_inline = any(q in tight_before for q in ('`', "'", '"')) and any(
        q in tight_after for q in ('`', "'", '"')
    )
    return (
        bool(DOCUMENTED_AS_EXAMPLE_RE.search(window))
        or bool(REGEX_LITERAL_CONTEXT_RE.search(window))
        or quoted_inline
    )


def scan_harmful(text):
    hard, mentioned = [], []
    for label, pattern in HARMFUL_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            continue
        if _looks_like_documentation(text, m):
            mentioned.append(f"{label}-mentioned")
        else:
            hard.append(label)
    return hard, mentioned


def scan_review(text):
    flags = [label for label, pattern in REVIEW_PATTERNS if re.search(pattern, text, re.IGNORECASE)]
    flags += scan_db_connection_strings(text)

    for label, pattern in SECRET_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m and not _is_placeholder(m.group(0)):
            flags.append(label)

    for token in re.findall(
        r"(?i)(?:api[_-]?key|secret|token|password)\s*[:=]\s*[\"']([A-Za-z0-9+/_\-]{20,})[\"']", text
    ):
        if not _is_placeholder(token) and _shannon_entropy(token) > 3.5:
            flags.append("high-entropy-token")
            break

    return flags


def _shannon_entropy(s):
    if not s:
        return 0.0
    freq = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    length = len(s)
    return -sum((count / length) * math.log2(count / length) for count in freq.values())


def _dedup_rank(item):
    return (bool(item["harmful_flags"]), -item["content_score"], item["tier"] != "official", item["source_id"])


def dedupe_catalog(catalog):
    """De-dupe identical (category, name) pairs across sources by ranking
    candidates on actual content, not source metadata:
      1. anything with a harmful-pattern flag always loses
      2. higher content_score wins
      3. official tier as a tiebreak on a genuine score tie
      4. source_id order as the final, fully-deterministic tiebreak

    Returns (deduped_items, skipped_by_kept) — skipped_by_kept maps
    "category:name" to a list of {source_id, source_name, source_url, reason}
    for every candidate that lost, with a human-readable reason.
    """
    groups = {}
    for item in catalog:
        key = (item["category"], item["name"].lower())
        groups.setdefault(key, []).append(item)

    deduped = []
    skipped_by_kept = {}
    for key, candidates in groups.items():
        candidates.sort(key=_dedup_rank)
        kept, losers = candidates[0], candidates[1:]
        deduped.append(kept)
        for item in losers:
            if kept["source_id"] == item["source_id"]:
                reason = "duplicate within the same source"
            elif item["harmful_flags"]:
                reason = f"flagged for risky pattern(s): {', '.join(item['harmful_flags'])}"
            elif kept["content_score"] != item["content_score"]:
                why = ", ".join(kept["content_signals"][:2]) or "more complete content"
                reason = f"kept scored higher on content ({kept['content_score']} vs {item['content_score']}) — {why}"
            elif kept["tier"] == "official" and item["tier"] != "official":
                reason = "official tier takes precedence over community (content scores tied)"
            else:
                reason = "earlier source in sources.json order wins name collisions (content scores tied)"
            skipped_by_kept.setdefault(f"{key[0]}:{key[1]}", []).append(
                {
                    "source_id": item["source_id"],
                    "source_name": item["source_name"],
                    "source_url": item["source_url"],
                    "reason": reason,
                }
            )

    deduped.sort(key=lambda i: (i["tier"] != "official", i["source_id"], i["category"], i["name"]))
    return deduped, skipped_by_kept

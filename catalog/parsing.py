import re
from pathlib import Path

from catalog.safety import check_prompt_injection, scan_harmful, scan_review

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)

NON_ITEM_STEMS = {
    "readme", "index", "license", "contributing",
    "claude", "code_of_conduct", "security", "template",
}


def parse_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fields = {}
    lines = m.group(1).splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if ":" in line and not line.startswith((" ", "\t")):
            k, _, v = line.partition(":")
            k = k.strip()
            v = v.strip()
            if v in ("|", ">", "|-", ">-", "|+", ">+"):
                # YAML block scalar: following more-indented lines are the value
                block = []
                i += 1
                while i < len(lines) and (lines[i].startswith((" ", "\t")) or not lines[i].strip()):
                    block.append(lines[i].strip())
                    i += 1
                fields[k] = " ".join(b for b in block if b)
                continue
            fields[k] = v.strip('"')
        i += 1
    return fields


def score_content(description, body_text, has_extra_files):
    score = 0.0
    signals = []
    desc = (description or "").strip()
    if desc and desc not in ("|", ">") and len(desc) > 15:
        score += min(len(desc), 200) / 200
        signals.append("substantive description")

    word_count = len(body_text.split())
    score += min(word_count, 400) / 400
    if word_count > 80:
        signals.append(f"{word_count}-word body")

    if re.search(r"##?\s*(usage|example)", body_text, re.IGNORECASE):
        score += 0.3
        signals.append("has usage/example section")
    if "```" in body_text:
        score += 0.2
        signals.append("has code block")
    if has_extra_files:
        score += 0.2
        signals.append("bundles extra files")

    if re.search(r"\bTODO\b|\blorem ipsum\b", body_text, re.IGNORECASE) or word_count < 15:
        score -= 0.5
        signals.append("placeholder/stub content")

    return round(score, 3), signals


def category_for_path(rel_path: Path):
    parts = {p.lower() for p in rel_path.parts}
    if rel_path.name.upper() == "SKILL.MD":
        return "skill"
    if "agents" in parts:
        return "agent"
    if "commands" in parts:
        return "command"
    if "hooks" in parts or "hook-scripts" in parts:
        return "hook"
    return None


def collect(repo, dest: Path):
    items = []
    for path in dest.rglob("*"):
        if not path.is_file():
            continue
        if ".git" in path.parts or "__pycache__" in path.parts:
            continue
        if path.suffix in (".pyc", ".pyo"):
            continue
        rel = path.relative_to(dest)
        cat = category_for_path(rel)
        if cat is None:
            continue

        if cat == "hook" and path.suffix == ".md":
            # real hooks are scripts (.sh/.js/.py/...); a .md here is documentation
            continue

        has_extra_files = False
        if path.suffix == ".md":
            text = path.read_text(encoding="utf-8", errors="ignore")
            fm = parse_frontmatter(text)
            if cat in ("agent", "command") and not fm and path.stem.lower() in NON_ITEM_STEMS:
                continue
            name = fm.get("name") or path.stem
            description = fm.get("description") or ""
            if not description:
                # first non-empty, non-heading line as a fallback description
                for line in text.splitlines():
                    line = line.strip().lstrip("#").strip()
                    if line and not line.startswith("---"):
                        description = line[:200]
                        break
            fm_match = FRONTMATTER_RE.match(text)
            body_text = text[fm_match.end():] if fm_match else text
            if cat == "skill":
                has_extra_files = any(
                    p.is_file() and p != path for p in path.parent.iterdir()
                )
        elif cat == "hook":
            text = path.read_text(encoding="utf-8", errors="ignore")
            body_text = text
            name = path.stem
            description = ""
            strip_chars = "#/*\"' \t"
            for line in text.splitlines()[:15]:
                line = line.strip().strip(strip_chars).strip()
                if not line or line.startswith("!/") or line.startswith("{") or line.endswith("{"):
                    continue
                if re.fullmatch(r"[-=*#/]+", line):
                    continue
                description = line[:200]
                break
        else:
            continue

        content_score, content_signals = score_content(description, body_text, has_extra_files)
        harmful_flags, documented_flags = scan_harmful(text)
        review_flags = scan_review(text) + documented_flags
        injection = check_prompt_injection(text)
        if injection == "hard":
            harmful_flags.append("prompt-injection-override")
        elif injection == "soft":
            review_flags.append("prompt-injection-mention")

        items.append(
            {
                "source_id": repo["id"],
                "source_name": repo["name"],
                "source_url": repo["url"],
                "local_path": repo.get("path", ""),
                "tier": repo["tier"],
                "license": repo.get("license", "UNKNOWN"),
                "license_note": repo.get("license_note", ""),
                "category": cat,
                "name": name,
                "description": description,
                "rel_path": str(rel).replace("\\", "/"),
                "content_score": content_score,
                "content_signals": content_signals,
                "harmful_flags": harmful_flags,
                "review_flags": review_flags,
                "_raw_text": text,
            }
        )
    return items

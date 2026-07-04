#!/usr/bin/env python3
"""
Clones each repo listed in sources.json (shallow) into ./cache/<id>,
then walks it for installable items: agents, skills, commands, hooks.
Writes catalog.json — a flat list every install.py picker can render.

Re-running re-pulls each repo (git pull) instead of re-cloning, so this
is safe to run repeatedly to pick up upstream updates.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
CACHE = ROOT / "cache"
SOURCES = json.loads((ROOT / "sources.json").read_text())

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def parse_frontmatter(text):
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fields = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fields[k.strip()] = v.strip().strip('"')
    return fields


def clone_or_update(repo):
    dest = CACHE / repo["id"]
    if dest.exists():
        subprocess.run(["git", "-C", str(dest), "pull", "--ff-only", "--quiet"], check=False)
    else:
        subprocess.run(
            ["git", "clone", "--depth", "1", "--quiet", repo["url"], str(dest)],
            check=False,
        )
    return dest


def category_for_path(rel_path: Path):
    parts = {p.lower() for p in rel_path.parts}
    if "skills" in parts or rel_path.name.upper() == "SKILL.MD":
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
        if ".git" in path.parts:
            continue
        rel = path.relative_to(dest)
        cat = category_for_path(rel)
        if cat is None:
            continue

        if path.suffix == ".md":
            text = path.read_text(encoding="utf-8", errors="ignore")
            fm = parse_frontmatter(text)
            name = fm.get("name") or path.stem
            description = fm.get("description") or ""
            if not description:
                # first non-empty, non-heading line as a fallback description
                for line in text.splitlines():
                    line = line.strip().lstrip("#").strip()
                    if line and not line.startswith("---"):
                        description = line[:200]
                        break
        elif cat == "hook":
            name = path.stem
            description = ""
            strip_chars = "#/*\"' \t"
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()[:15]:
                line = line.strip().strip(strip_chars).strip()
                if not line or line.startswith("!/") or line.startswith("{") or line.endswith("{"):
                    continue
                if re.fullmatch(r"[-=*#/]+", line):
                    continue
                description = line[:200]
                break
        else:
            continue

        items.append(
            {
                "source_id": repo["id"],
                "source_name": repo["name"],
                "tier": repo["tier"],
                "category": cat,
                "name": name,
                "description": description,
                "rel_path": str(rel).replace("\\", "/"),
            }
        )
    return items


def main():
    catalog = []
    for repo in SOURCES:
        print(f"Scanning {repo['name']} ({repo['url']}) ...")
        dest = clone_or_update(repo)
        if not dest.exists():
            print(f"  ! clone failed, skipping {repo['id']}")
            continue
        items = collect(repo, dest)
        print(f"  found {len(items)} installable items")
        catalog.extend(items)

    # de-dupe identical (category, name) pairs across sources, keep first (official tier sorted first)
    catalog.sort(key=lambda i: (i["tier"] != "official", i["source_id"], i["category"], i["name"]))
    seen = set()
    deduped = []
    for item in catalog:
        key = (item["category"], item["name"].lower())
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    out = ROOT / "catalog.json"
    out.write_text(json.dumps(deduped, indent=2))
    print(f"\nWrote {len(deduped)} items to {out}")


if __name__ == "__main__":
    main()

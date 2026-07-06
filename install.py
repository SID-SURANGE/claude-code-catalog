#!/usr/bin/env python3
"""
Interactive picker over catalog.json. Presents items grouped by category
with a fuzzy keyword filter and pagination, lets the user inspect an item
('i N') or select by number (comma/range: "1,3,5-8" or "all" or "none"),
then copies chosen items into ~/.claude/{agents,skills,commands,hooks}/.

Tracks what's been installed (and from where) in installed.json so
re-running scan.py + install.py later can show what's new vs. already-installed.

Usage:
    python install.py            # interactive, all categories
    python install.py --tier official   # only official-tier items
    python install.py --category skill # only one category
    python install.py --list-packs      # curated bundles, see packs.json
    python install.py --pack docker-devops
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).parent
CLAUDE_HOME = Path.home() / ".claude"
CATEGORY_DIRS = {
    "agent": CLAUDE_HOME / "agents",
    "skill": CLAUDE_HOME / "skills",
    "command": CLAUDE_HOME / "commands",
    "hook": CLAUDE_HOME / "hooks",
}
INSTALLED_MANIFEST = ROOT / "installed.json"
ATTRIBUTION_FILE = CLAUDE_HOME / "ATTRIBUTION.md"
PACKS_FILE = ROOT / "packs.json"
SKIPPED_DUPLICATES_FILE = ROOT / "skipped_duplicates.json"
PAGE_SIZE = 20


# --- color -------------------------------------------------------------
# Plain ANSI codes, stdlib only. Respects NO_COLOR (https://no-color.org)
# and disables automatically when output isn't a real terminal (piped,
# redirected, or run in a test harness), matching how most modern CLIs
# (git, ripgrep, fzf) decide whether to color their output.
_COLOR_ENABLED = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
_CODES = {
    "reset": "\033[0m", "bold": "\033[1m", "dim": "\033[2m",
    "red": "\033[31m", "green": "\033[32m", "yellow": "\033[33m",
    "cyan": "\033[36m", "magenta": "\033[35m",
}


def c(text, *styles):
    if not _COLOR_ENABLED or not text:
        return text
    return "".join(_CODES[s] for s in styles) + text + _CODES["reset"]


# --- fuzzy matching ------------------------------------------------------
def _fuzzy_score(query, text):
    """Subsequence match, fzf-style: query's chars must appear in text in
    order (not necessarily contiguous). Returns None if no match, else a
    score where lower is better — the tightest, earliest match wins."""
    query, text = query.lower(), text.lower()
    if not query:
        return 0
    ti, first = 0, None
    for qc in query:
        idx = text.find(qc, ti)
        if idx == -1:
            return None
        if first is None:
            first = idx
        ti = idx + 1
    span = (ti - 1) - first + 1
    score = span - len(query)  # 0 if contiguous, grows with gaps
    if query in text:
        score -= 1000  # strongly prefer a real substring match
    score += first * 0.01  # tiny tiebreak toward earlier matches
    return score


def _item_score(query_words, item):
    """All space-separated words must match somewhere (name preferred over
    description) — an AND across terms, not just one big substring.

    Fuzzy subsequence matching only applies to `name`, which is short (a
    real fzf-style use case: typo tolerance, partial words). Applying it to
    full-sentence descriptions is a false economy — over a ~100+ char
    paragraph, common letters like "d,o,c,k,e,r" or "k,8,s" will subsequence
    -match almost any prose by pure chance, which was verified to surface
    completely unrelated items (an email-template-builder skill "matched"
    a "docker k8s" search). Descriptions get a real substring check.
    """
    total = 0
    for word in query_words:
        name_score = _fuzzy_score(word, item["name"])
        if name_score is not None:
            total += name_score
        elif word.lower() in item["description"].lower():
            total += 50  # description-only match ranks below any name match
        else:
            return None
    return total


def load_installed():
    if INSTALLED_MANIFEST.exists():
        return json.loads(INSTALLED_MANIFEST.read_text())
    return {}


def load_packs():
    if PACKS_FILE.exists():
        return json.loads(PACKS_FILE.read_text())
    return []


def load_skipped_duplicates():
    if SKIPPED_DUPLICATES_FILE.exists():
        return json.loads(SKIPPED_DUPLICATES_FILE.read_text())
    return {}


def list_packs(keyword=None):
    packs = load_packs()
    if not packs:
        print("No packs defined yet. Add bundles to packs.json — see README for the schema.")
        return

    if keyword:
        words = keyword.lower().split()
        packs = [
            p for p in packs
            if all(w in (p["id"] + p["name"] + p["description"]).lower() for w in words)
        ]
        if not packs:
            print(f"No packs match '{keyword}'.")
            return

    print(f"\n=== PACKS ({len(packs)}) ===")
    for p in packs:
        preview = ", ".join(i["name"] for i in p["items"][:3])
        if len(p["items"]) > 3:
            preview += f", +{len(p['items']) - 3} more"
        padded_id = f"{p['id']:<24}"
        print(f"  {c(padded_id, 'bold', 'cyan')} {p['name']} ({len(p['items'])} items)")
        print(f"    {p['description']}")
        print(c(f"    contains: {preview}", "dim"))
    print(f"\nInstall one with: {c('python install.py --pack <id>', 'bold')}")


def save_installed(manifest):
    INSTALLED_MANIFEST.write_text(json.dumps(manifest, indent=2))


def append_attribution(item, dest):
    is_new = not ATTRIBUTION_FILE.exists()
    with open(ATTRIBUTION_FILE, "a", encoding="utf-8") as f:
        if is_new:
            f.write(
                "# Attribution\n\n"
                "Auto-generated by claude-code-catalog. Each entry below is an "
                "item copied into this ~/.claude/ tree, its original source, "
                "and that source's license at install time. Items remain "
                "governed by their original repo's license, not this tool's.\n\n"
            )
        f.write(
            f"- **{item['name']}** ({item['category']}) <- "
            f"[{item['source_name']}]({item['source_url']}) "
            f"— license: {item['license']}"
            + (f" ({item['license_note']})" if item.get("license_note") else "")
            + f" — installed to `{dest}`\n"
        )


def filter_by_keyword(items, category):
    raw = input(f"Filter {category}s by keyword (name/description), or Enter for all: ").strip()
    if not raw:
        return items
    words = raw.split()
    scored = []
    for item in items:
        score = _item_score(words, item)
        if score is not None:
            scored.append((score, item))
    if not scored:
        print(f"  no matches for '{raw}' — showing all {category}s instead.")
        return items
    scored.sort(key=lambda pair: pair[0])
    return [item for _, item in scored]


def parse_selection(raw, max_n):
    raw = raw.strip().lower()
    if raw in ("all", "a"):
        return set(range(1, max_n + 1))
    if raw in ("none", "n", ""):
        return set()
    chosen = set()
    for chunk in raw.split(","):
        chunk = chunk.strip()
        if "-" in chunk:
            lo, _, hi = chunk.partition("-")
            chosen.update(range(int(lo), int(hi) + 1))
        elif chunk:
            chosen.add(int(chunk))
    return {n for n in chosen if 1 <= n <= max_n}


def print_item_line(idx, item, installed, skipped_duplicates):
    key = f"{item['category']}:{item['name'].lower()}"
    tag = c(" [installed]", "dim") if key in installed else ""
    is_official = item["tier"] == "official"
    tier_tag = c("OFFICIAL", "green", "bold") if is_official else c(item["source_name"], "dim")
    desc = item["description"][:90]
    lic = item.get("license", "UNKNOWN")
    lic_tag = f" [{lic}]" if lic not in ("NONE", "UNKNOWN") else c(" [!NO LICENSE]", "red", "bold")
    alts = skipped_duplicates.get(key, [])
    alt_tag = c(f" [+{len(alts)} similar skipped]", "dim") if alts else ""
    risky = item.get("harmful_flags") or []
    risk_tag = c(f" [!RISKY: {', '.join(risky)}]", "red", "bold") if risky else ""
    reviewed = item.get("review_flags") or []
    review_tag = c(f" [i: {', '.join(reviewed)}]", "yellow") if reviewed else ""
    llm_review = item.get("llm_review")
    if llm_review:
        verdict_style = {"safe": "green", "suspicious": "yellow", "malicious": "red"}.get(llm_review["verdict"], "dim")
        llm_tag = c(f" [LLM: {llm_review['verdict']} {llm_review['confidence']}]", verdict_style)
    else:
        llm_tag = ""
    print(f"  {idx:>3}. ({tier_tag}) {item['name']}{lic_tag}{risk_tag}{review_tag}{llm_tag}{tag}{alt_tag} — {desc}")

    grouped = {}
    for alt in alts:
        grouped.setdefault((alt["source_name"], alt["reason"]), 0)
        grouped[(alt["source_name"], alt["reason"])] += 1
    for (source_name, reason), count in grouped.items():
        times = f" ({count}x)" if count > 1 else ""
        print(c(f"       -> skipped {source_name}'s version{times} — {reason}", "dim"))


def print_item_detail(item, skipped_duplicates):
    key = f"{item['category']}:{item['name'].lower()}"
    print(f"\n{c(item['name'], 'bold')} ({item['category']})")
    print(f"  Source:      {item['source_name']} <{item['source_url']}>")
    print(f"  Tier:        {item['tier']}")
    print(f"  License:     {item.get('license', 'UNKNOWN')}" + (f" — {item['license_note']}" if item.get("license_note") else ""))
    print(f"  Description: {item['description']}")
    print(f"  Content score: {item.get('content_score')} ({', '.join(item.get('content_signals') or []) or 'no signals'})")
    if item.get("harmful_flags"):
        print(c(f"  RISKY (gated): {', '.join(item['harmful_flags'])}", "red", "bold"))
    if item.get("review_flags"):
        print(c(f"  Informational: {', '.join(item['review_flags'])}", "yellow"))
    if item.get("llm_review"):
        lr = item["llm_review"]
        print(f"  LLM review ({lr['provider']}/{lr['model']}): {lr['verdict']} (confidence {lr['confidence']}) — {lr['reasoning']}")
    alts = skipped_duplicates.get(key, [])
    if alts:
        print("  Similar items skipped during dedup:")
        for alt in alts:
            print(f"    - {alt['source_name']} <{alt['source_url']}> — {alt['reason']}")
    print()


def install_item(item, source_root: Path):
    src = source_root / item["source_id"] / item["rel_path"]
    dest_dir = CATEGORY_DIRS[item["category"]]
    dest_dir.mkdir(parents=True, exist_ok=True)

    if item["category"] in ("agent", "command"):
        dest = dest_dir / Path(item["rel_path"]).name
    elif item["category"] == "skill":
        # skills are usually a folder with SKILL.md; install the whole folder
        skill_folder = src.parent
        dest = dest_dir / skill_folder.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(skill_folder, dest)
        return dest
    else:  # hook
        dest = dest_dir / Path(item["rel_path"]).name

    shutil.copy2(src, dest)
    return dest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", choices=["official", "community"])
    ap.add_argument("--category", choices=list(CATEGORY_DIRS))
    ap.add_argument("--pack", help="install a curated bundle from packs.json by id")
    ap.add_argument(
        "--list-packs", nargs="?", const="", default=None, metavar="KEYWORD",
        help="show available packs and exit; optionally filter by keyword, e.g. --list-packs docker",
    )
    args = ap.parse_args()

    if args.list_packs is not None:
        list_packs(args.list_packs or None)
        return

    catalog_path = ROOT / "catalog.json"
    if not catalog_path.exists():
        print("catalog.json not found — run scan.py first.")
        return
    catalog = json.loads(catalog_path.read_text())
    skipped_duplicates = load_skipped_duplicates()

    if args.pack:
        packs = {p["id"]: p for p in load_packs()}
        pack = packs.get(args.pack)
        if not pack:
            print(f"No pack named '{args.pack}'. Run --list-packs to see available packs.")
            return
        wanted = {(i["category"], i["name"].lower()) for i in pack["items"]}
        catalog = [i for i in catalog if (i["category"], i["name"].lower()) in wanted]
        print(f"\n=== PACK: {pack['name']} ===\n{pack['description']}")

    if args.tier:
        catalog = [i for i in catalog if i["tier"] == args.tier]
    if args.category:
        catalog = [i for i in catalog if i["category"] == args.category]

    installed = load_installed()

    for category in ("agent", "skill", "command", "hook"):
        items = [i for i in catalog if i["category"] == category]
        if not items:
            continue
        print(f"\n=== {category.upper()}S ({len(items)} total) ===")
        if not args.pack:
            items = filter_by_keyword(items, category)
        print(f"--- showing {len(items)} {category}(s) ---")

        unlicensed_sources = {i["source_name"] for i in items if i.get("license") in ("NONE", "UNKNOWN")}

        shown = 0
        raw = ""
        while True:
            upper = min(shown + PAGE_SIZE, len(items))
            for idx in range(shown, upper):
                print_item_line(idx + 1, items[idx], installed, skipped_duplicates)
            shown = upper

            if shown < len(items):
                prompt = (
                    f"\n-- showing {shown}/{len(items)}. Enter for more, "
                    f"'i N' for details, or make your selection now: "
                )
            else:
                if unlicensed_sources:
                    print(
                        "\n  Note: items from "
                        + ", ".join(sorted(unlicensed_sources))
                        + " have no LICENSE file (defaults to all-rights-reserved)."
                        + " Review the source repo before installing from it."
                    )
                prompt = f"\nSelect {category}s to install (e.g. 1,3,5-8 / all / none, 'i N' for details): "

            # Inner loop: re-prompt at this SAME page for "i N" detail
            # requests, without printing more items — only a blank (page
            # forward) or a real selection breaks out to the outer loop.
            while True:
                raw = input(prompt)
                stripped = raw.strip().lower()
                if stripped.startswith("i ") or stripped.startswith("info "):
                    _, _, arg = stripped.partition(" ")
                    try:
                        detail_idx = int(arg.strip())
                        if 1 <= detail_idx <= len(items):
                            print_item_detail(items[detail_idx - 1], skipped_duplicates)
                        else:
                            print(f"  no item #{detail_idx} in this list.")
                    except ValueError:
                        print("  usage: i <item number>")
                    continue
                break

            if stripped == "" and shown < len(items):
                continue  # blank at a "more" prompt pages forward
            break

        chosen = parse_selection(raw, len(items))
        for idx in chosen:
            item = items[idx - 1]
            if item.get("license") in ("NONE", "UNKNOWN"):
                confirm = input(
                    f"  '{item['name']}' has no license ({item.get('license_note', 'no info')}). "
                    "Install anyway? [y/N]: "
                ).strip().lower()
                if confirm != "y":
                    print("  skipped.")
                    continue
            lr = item.get("llm_review")
            lr_concern = bool(lr) and lr.get("verdict") in ("suspicious", "malicious")
            if item.get("harmful_flags") or lr_concern:
                if lr:
                    print(
                        f"  LLM review ({lr['provider']}/{lr['model']}): {lr['verdict']} "
                        f"(confidence {lr['confidence']}) — {lr['reasoning']}"
                    )
                reasons = []
                if item.get("harmful_flags"):
                    reasons.append(f"matched risky pattern(s): {', '.join(item['harmful_flags'])}")
                if lr_concern and not item.get("harmful_flags"):
                    reasons.append(f"the LLM review flagged it as {lr['verdict']} with no static pattern match")
                confirm = input(
                    f"  '{item['name']}' " + "; ".join(reasons) + ". "
                    "This is a heuristic tripwire, not a guarantee — read the source before trusting it. "
                    "Install anyway? [y/N]: "
                ).strip().lower()
                if confirm != "y":
                    print("  skipped.")
                    continue
            dest = install_item(item, ROOT / "cache")
            key = f"{item['category']}:{item['name'].lower()}"
            installed[key] = {
                "source": item["source_name"],
                "source_id": item["source_id"],
                "source_url": item["source_url"],
                "license": item.get("license", "UNKNOWN"),
                "installed_to": str(dest),
            }
            append_attribution(item, dest)
            print(f"  installed -> {dest}")

    save_installed(installed)
    print(f"\nDone. Manifest: {INSTALLED_MANIFEST}")


if __name__ == "__main__":
    main()

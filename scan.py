#!/usr/bin/env python3
"""
Clones each repo listed in sources.json (shallow) into ./cache/<id>,
then walks it for installable items: agents, skills, commands, hooks.
Writes catalog.json — a flat list every install.py picker can render.

Re-running re-pulls each repo (git pull) instead of re-cloning, so this
is safe to run repeatedly to pick up upstream updates.

The actual scanning/scoring/safety/dedup/LLM-review logic lives in the
catalog/ package alongside this file; this script is just the CLI entry
point that orchestrates it.
"""
import argparse
import json
import subprocess
import sys

from catalog.llm_review import LLM_PROVIDERS, load_llm_cache, run_llm_review
from catalog.parsing import collect
from catalog.paths import CACHE, ROOT, SOURCES
from catalog.safety import dedupe_catalog

sys.stdout.reconfigure(encoding="utf-8")


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


def scan_all_sources():
    catalog = []
    for repo in SOURCES:
        print(f"Scanning {repo['name']} ({repo['url']}) ...")
        if repo.get("license") in (None, "NONE", "UNKNOWN"):
            print(f"  ! license: {repo.get('license', 'UNKNOWN')} — {repo.get('license_note', 'no license info recorded')}")
        dest = clone_or_update(repo)
        if not dest.exists():
            print(f"  ! clone failed, skipping {repo['id']}")
            continue
        items = collect(repo, dest)
        print(f"  found {len(items)} installable items")
        catalog.extend(items)
    return catalog


def build_arg_parser():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--llm-review",
        action="store_true",
        help="optional second pass: LLM-judge flagged/borderline items (plain HTTP, no SDK — needs an API key or a local server)",
    )
    ap.add_argument(
        "--llm-provider",
        choices=list(LLM_PROVIDERS),
        default="anthropic",
        help="which provider to use for --llm-review (default: anthropic)",
    )
    ap.add_argument("--llm-model", help="override the provider's default model")
    ap.add_argument("--llm-base-url", help="override the provider's default base URL (e.g. a different ollama host)")
    return ap


def main():
    args = build_arg_parser().parse_args()

    catalog = scan_all_sources()
    deduped, skipped_by_kept = dedupe_catalog(catalog)

    if args.llm_review:
        run_llm_review(deduped, load_llm_cache(), args.llm_provider, args.llm_model, args.llm_base_url)

    for item in deduped:
        item.pop("_raw_text", None)

    out = ROOT / "catalog.json"
    out.write_text(json.dumps(deduped, indent=2))
    print(f"\nWrote {len(deduped)} items to {out}")

    skipped_out = ROOT / "skipped_duplicates.json"
    skipped_out.write_text(json.dumps(skipped_by_kept, indent=2))
    if skipped_by_kept:
        print(
            f"Recorded {sum(len(v) for v in skipped_by_kept.values())} skipped "
            f"duplicate(s) across {len(skipped_by_kept)} name collision(s) -> {skipped_out}"
        )


if __name__ == "__main__":
    main()

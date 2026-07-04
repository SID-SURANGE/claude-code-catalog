# claude-code-catalog

A scanner + interactive installer for community and official Claude
Code agents, skills, commands, and hooks. Installs at the **user
level** (`~/.claude/`), so what you pick applies across every project
on your machine, not just one repo.

## Why

Repos like `affaan-m/everything-claude-code` (100k+ stars) ship
hundreds of items in one place — too many to read through by hand.
This tool clones each source repo, parses every agent/skill/command's
frontmatter (or a hook script's leading comment) into a single
`catalog.json`, then lets you multi-select what to actually install
via a numbered picker. Nothing is installed without you choosing it.

## Install

Requires `git` and `python3` (both cross-platform, no other
dependencies).

**macOS / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/SID-SURANGE/claude-code-catalog/main/install.sh | bash
```

**Windows (PowerShell)**
```powershell
irm https://raw.githubusercontent.com/SID-SURANGE/claude-code-catalog/main/install.ps1 | iex
```

Both scripts clone this repo to `~/.claude-code-catalog` (or
`$env:CLAUDE_CODE_CATALOG_HOME` / `$CLAUDE_CODE_CATALOG_HOME` if set),
run the scanner, then launch the interactive picker.

**Already cloned it yourself?** Just run directly instead:
```bash
python3 scan.py      # build/refresh catalog.json from all sources
python3 install.py   # interactive picker
```

## Usage

```bash
# Pick from everything
python3 install.py

# Only Anthropic's own (official-tier) items
python3 install.py --tier official

# Only one category
python3 install.py --category skill   # agent | skill | command | hook
```

At each prompt, select items by number: `1,3,5-8`, `all`, or `none`.

## Sources

Edit `sources.json` to add/remove repos. Each entry needs `id`,
`name`, `url`, and `tier` (`official` or `community`). Official-tier
items are always listed first in the picker and win any name collision
with a community item.

| Repo | Tier | License | Notes |
|---|---|---|---|
| [anthropics/skills](https://github.com/anthropics/skills) | official | **none** ⚠️ | Anthropic's own skills; no LICENSE file, use via `/plugin install` |
| [anthropics/claude-plugins-official](https://github.com/anthropics/claude-plugins-official) | official | Apache-2.0 | Anthropic-curated plugin directory |
| [affaan-m/everything-claude-code](https://github.com/affaan-m/everything-claude-code) | community | MIT | ~100k★, 28 agents / 119 skills / 60 commands |
| [disler/claude-code-hooks-mastery](https://github.com/disler/claude-code-hooks-mastery) | community | **none** ⚠️ | ~3.3k★, hook patterns; no LICENSE file |
| [karanb192/claude-code-hooks](https://github.com/karanb192/claude-code-hooks) | community | MIT | Focused hook scripts (git safety, secret protection) |
| [alirezarezvani/claude-skills](https://github.com/alirezarezvani/claude-skills) | community | MIT | ~5.2k★, 330+ skills |

## License & Attribution

**This repo's own code** (`scan.py`, `install.py`, `install.sh`,
`install.ps1`) is MIT-licensed — see [LICENSE](LICENSE).

**Everything this tool installs is not covered by that license.** Each
item copied into `~/.claude/` remains governed by its *original*
source repo's license, listed in the table above. This tool never
bundles or redistributes third-party code in the repo itself — it only
clones sources at run time (into a gitignored `cache/`) and copies
files locally into your own `~/.claude/` on your explicit selection.

Two sources currently have **no LICENSE file** (`anthropics/skills`,
`disler/claude-code-hooks-mastery`), which under copyright law defaults
to all-rights-reserved rather than an open grant to reuse. `install.py`
flags these in the picker with `[!NO LICENSE]` and asks for explicit
confirmation before copying anything from them — review the source
repo yourself before confirming.

Every successful install appends a line to `~/.claude/ATTRIBUTION.md`
recording the item's name, source repo, license, and install path, so
you always have a record of what came from where.

## Files

- `sources.json` — repo list you maintain
- `cache/` — shallow git clones of each source (gitignored, `git pull`ed on re-scan)
- `catalog.json` — generated: flat list of every installable item found
- `installed.json` — generated: manifest of what you've installed and from where
- `scan.py` / `install.py` — the two scripts you actually run
- `install.sh` / `install.ps1` — one-line bootstrap for a fresh machine

## Notes

- Re-running `scan.py` does `git pull` on cached repos rather than
  re-cloning, so it's cheap to re-check sources periodically.
- Skills are copied as whole folders (they usually bundle scripts and
  references alongside `SKILL.md`); agents/commands/hooks are copied
  as single files.

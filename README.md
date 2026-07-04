<div align="center">

# 📚 claude-code-catalog

**A scanner + interactive installer for Claude Code agents, skills, commands, and hooks —**
**with license auditing built in, not bolted on.**

![Python](https://img.shields.io/badge/Python-3-3776AB?style=flat-square&logo=python&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-3fb950?style=flat-square)
![Dependencies](https://img.shields.io/badge/dependencies-git%20%2B%20python3-6366f1?style=flat-square)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-06b6d4?style=flat-square)
![License Audited](https://img.shields.io/badge/sources-license%20audited-e85d4a?style=flat-square)

</div>

---

## 🧭 Why this exists

Community catalogs now ship thousands of items across dozens of
repos — far too many to read through by hand. Almost none of the
existing aggregators tell you what license you're actually installing
under. Two of the eight sources below have **no LICENSE file at all**,
which under copyright law defaults to all-rights-reserved, not "free
to use because it's on GitHub."

`claude-code-catalog` treats that as a first-class problem, not a footnote:

| | This tool | Typical aggregator |
|---|---|---|
| 🔍 Per-source license tracked | ✅ recorded in `sources.json` | ❌ usually undocumented |
| 🛑 Blocks silent copy of unlicensed code | ✅ `[!NO LICENSE]` + y/N gate | ❌ copies on select |
| 📝 Attribution trail per install | ✅ `ATTRIBUTION.md`, auto-appended | ❌ rarely kept |
| 📦 Dependencies | git + python3 only | often npm/node + a hosted directory |
| ✋ Selection model | numbered picker, explicit multi-select | varies — some install everything by default |

Nothing is installed without you choosing it, and nothing with an
unclear license is installed without you confirming it.

---

## ⚙️ How it works

```text
┌──────────────┐   scan.py    ┌──────────────┐   install.py   ┌───────────────────┐
│ sources.json │ ───────────► │ catalog.json │ ─────────────► │  ~/.claude/*        │
│ (repos you   │  git clone/  │ (every item, │  numbered      │  + ATTRIBUTION.md  │
│  trust)      │  pull + scan │  license-    │  picker +      │  + installed.json  │
│              │              │  tagged)     │  license gate  │                    │
└──────────────┘              └──────────────┘                └───────────────────┘
```

Installs at the **user level** (`~/.claude/`), so what you pick
applies across every project on your machine, not just one repo.

---

## ✨ What's included

| Category | Where it lands | Copied as |
|---|---|---|
| 🤖 **Agents** | `~/.claude/agents/` | single file |
| 🧠 **Skills** | `~/.claude/skills/` | whole folder (bundles scripts/references) |
| ⚡ **Commands** | `~/.claude/commands/` | single file |
| 🪝 **Hooks** | `~/.claude/hooks/` | single file |
| 📋 **Attribution** | `~/.claude/ATTRIBUTION.md` | auto-appended on every install |

---

## 🚀 Quick start

Requires `git` and `python3` (both cross-platform, no other dependencies).

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

**macOS / Linux**
```bash
python3 scan.py      # build/refresh catalog.json from all sources
python3 install.py   # interactive picker
```

**Windows**
```powershell
python scan.py        # build/refresh catalog.json from all sources
python install.py     # interactive picker
```

> Windows commonly has no `python3` command (it's often shadowed by the
> Microsoft Store alias instead of a real interpreter) — use `python` or
> `py` there. macOS/Linux use `python3` since `python` may point at
> Python 2 or not exist at all.

### Usage

```bash
# Pick from everything
python3 install.py   # Windows: python install.py

# Only Anthropic's own (official-tier) items
python3 install.py --tier official

# Only one category
python3 install.py --category skill   # agent | skill | command | hook
```

At each prompt, select items by number: `1,3,5-8`, `all`, or `none`.

Picking an item with no LICENSE file stops and asks first:

```text
'some-skill' has no license (No LICENSE file in the repo...).
Install anyway? [y/N]:
```

---

## 📦 Sources

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
| [wshobson/agents](https://github.com/wshobson/agents) | community | MIT | Multi-harness plugin marketplace — 192 agents / 156 skills / 102 commands |
| [rohitg00/awesome-claude-code-toolkit](https://github.com/rohitg00/awesome-claude-code-toolkit) | community | Apache-2.0 | 135 agents / 35 skills / 42 commands / 20 hooks |

Adding a source doesn't require it to be spotless — it just requires
its license to be recorded honestly in `sources.json` so the picker
can warn you accurately.

---

## 🛡️ License & Attribution

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

---

## 🗂️ Files

| Path | What it is |
|---|---|
| `sources.json` | repo list you maintain |
| `cache/` | shallow git clones of each source (gitignored, `git pull`ed on re-scan) |
| `catalog.json` | generated: flat list of every installable item found |
| `installed.json` | generated: manifest of what you've installed and from where |
| `scan.py` / `install.py` | the two scripts you actually run |
| `install.sh` / `install.ps1` | one-line bootstrap for a fresh machine |

## 📝 Notes

- Re-running `scan.py` does `git pull` on cached repos rather than
  re-cloning, so it's cheap to re-check sources periodically.
- Skills are copied as whole folders (they usually bundle scripts and
  references alongside `SKILL.md`); agents/commands/hooks are copied
  as single files.

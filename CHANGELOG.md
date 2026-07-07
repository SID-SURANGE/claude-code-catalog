# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- First-party quality suite under `first-party/`, scanned as a local
  `path`-type source with the same scoring/safety/dedup as external repos:
  - Six advisory, non-blocking hooks: `goal-anchor`, `stop-gate-review`
    (cached LLM pass for goal deviation + correctness defects),
    `test-integrity`, `completion-verifier`, `structure-sentry`,
    `claim-checker`.
  - Two agents: `assumption-auditor`, `regression-cartographer`.
  - Three commands: `/quality-gauntlet`, `/hook-doctor`, `/solution-design`
    (end-to-end AI-system design pipeline).
  - Two packs: `first-party-quality`, `ai-architect-studio`.
  - 24 new unit tests (73 total).
- Local-path source resolution and hook-registration printout in
  `install.py`.
- `__pycache__` / `.pyc` exclusion in the scanner.

### Fixed

- Stale exact-count references to the catalog size in `README.md` and
  `SCANNING_RULES.md`, updated from 2,124 to the current 2,137-item catalog.

## [0.1.0] - 2026-07-06

### Added

- Content-based dedup: colliding item names across sources are resolved by
  content score, with official tier breaking genuine ties.
- Safety scanning: secrets/keys, prompt-injection patterns, and dangerous
  shell commands, with quoting/documentation-context awareness to suppress
  false positives (e.g. a hook that documents `chmod 777` as the pattern it
  blocks).
- Optional LLM review across six providers via plain `urllib` (no SDK, no
  pip install), cached by content hash.
- Curated packs for one-command install of related item bundles.
- Fuzzy CLI search and picker pagination.

### Also included in 0.1.0

- Initial catalog scanner and interactive installer for Claude Code
  agents/skills/commands/hooks, aggregating official and top community
  repos.
- License tracking and per-source attribution.
- Item categorization tightening and keyword filter in the picker.

[Unreleased]: https://github.com/SID-SURANGE/claude-code-catalog/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/SID-SURANGE/claude-code-catalog/releases/tag/v0.1.0

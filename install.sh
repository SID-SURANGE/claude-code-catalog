#!/usr/bin/env bash
# Bootstrap for macOS / Linux.
# Clones this repo (if not already inside it) to ~/.claude-code-catalog,
# then runs the scanner and the interactive picker.
set -euo pipefail

REPO_URL="https://github.com/SID-SURANGE/claude-code-catalog.git"
INSTALL_DIR="${CLAUDE_CODE_CATALOG_HOME:-$HOME/.claude-code-catalog}"

command -v git >/dev/null 2>&1 || { echo "git is required but not found." >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required but not found." >&2; exit 1; }

if [ -f "$(dirname "$0")/scan.py" ]; then
  # Already running from inside a clone of this repo.
  cd "$(dirname "$0")"
else
  if [ -d "$INSTALL_DIR/.git" ]; then
    git -C "$INSTALL_DIR" pull --ff-only --quiet
  else
    git clone --depth 1 --quiet "$REPO_URL" "$INSTALL_DIR"
  fi
  cd "$INSTALL_DIR"
fi

echo "Scanning sources..."
python3 scan.py

echo
echo "Launching installer..."
python3 install.py "$@"

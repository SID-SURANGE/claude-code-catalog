import json
from pathlib import Path

# catalog/paths.py -> catalog/ -> repo root. This is the one place
# __file__-relative paths are computed; every other module imports
# ROOT/CACHE/SOURCES from here instead of recomputing them. If this
# package is ever nested deeper, update the .parent chain here only.
ROOT = Path(__file__).parent.parent
CACHE = ROOT / "cache"
SOURCES = json.loads((ROOT / "sources.json").read_text())

"""Root conftest: make `edgen_*` packages importable without an editable install.

Each package follows src-layout under packages/<name>/src. In CI / dev we
normally `pip install -e` them (see Makefile), but tests also run with a plain
PYTHONPATH fallback so a fresh clone only needs `pip install -r` deps.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
for pkg in sorted((ROOT / "packages").glob("*/src")):
    p = str(pkg)
    if p not in sys.path:
        sys.path.insert(0, p)

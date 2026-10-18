import sys
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1]
for p in (ASSETS, ASSETS.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

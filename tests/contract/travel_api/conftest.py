"""Make the travel-api package importable without installing it (see the
sibling comment in tests/unit/travel_api/conftest.py for rationale).
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TRAVEL_API_SRC = _REPO_ROOT / "src" / "travel-api"
if str(_TRAVEL_API_SRC) not in sys.path:
    sys.path.insert(0, str(_TRAVEL_API_SRC))

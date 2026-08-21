"""Make the travel-api package importable without installing it.

src/travel-api owns its own dependencies (see src/travel-api/pyproject.toml
and requirements.txt) and is intentionally not registered with the
repository-root pyproject.toml. Adding its path here lets these unit tests
import `travel_api` directly against whatever Python environment `pytest` is
running in, without requiring an editable install.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_TRAVEL_API_SRC = _REPO_ROOT / "src" / "travel-api"
if str(_TRAVEL_API_SRC) not in sys.path:
    sys.path.insert(0, str(_TRAVEL_API_SRC))

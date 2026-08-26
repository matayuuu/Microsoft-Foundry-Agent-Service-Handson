"""Make src/hosted-agent importable without installing it.

src/hosted-agent owns its own dependencies (see
src/hosted-agent/requirements.txt) and is intentionally not registered with
the repository-root pyproject.toml, mirroring how src/travel-api is handled
(see tests/unit/travel_api/conftest.py). Adding its path here keeps this test directory ready for small source-level
tests without requiring an editable install.
"""

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_HOSTED_AGENT_SRC = _REPO_ROOT / "src" / "hosted-agent"
if str(_HOSTED_AGENT_SRC) not in sys.path:
    sys.path.insert(0, str(_HOSTED_AGENT_SRC))

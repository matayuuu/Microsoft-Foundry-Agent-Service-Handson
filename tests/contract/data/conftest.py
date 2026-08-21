"""conftest for tests/contract/data.

Adds src/travel-api to sys.path so test_per_diem_rates_match_policy can
import travel_api.domain.rates without requiring FastAPI (rates.py has no
FastAPI dependency, so no pytest.importorskip is needed here).
"""

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"
_TRAVEL_API_SRC = REPO_ROOT / "src" / "travel-api"
if str(_TRAVEL_API_SRC) not in sys.path:
    sys.path.insert(0, str(_TRAVEL_API_SRC))


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT

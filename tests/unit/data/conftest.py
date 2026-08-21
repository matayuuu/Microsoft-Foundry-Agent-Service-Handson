"""conftest for tests/unit/data.

Requires the jsonschema and PyYAML packages, which ARE part of the
repository root pyproject.toml dependencies, so these tests are expected to
run in the root CI environment without any extra sub-venv.
"""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
DATA_DIR = REPO_ROOT / "data"


@pytest.fixture(scope="session")
def data_dir() -> Path:
    return DATA_DIR


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT

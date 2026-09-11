"""Keep the Travel Ops API runtime aligned with Cloud Shell and root CI."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
TRAVEL_API_ROOT = REPO_ROOT / "src" / "travel-api"


def test_travel_api_uses_python_312_across_package_container_and_docs() -> None:
    pyproject = (TRAVEL_API_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    dockerfile = (TRAVEL_API_ROOT / "Dockerfile").read_text(encoding="utf-8")
    readme = (TRAVEL_API_ROOT / "README.md").read_text(encoding="utf-8")

    assert 'requires-python = ">=3.12,<3.13"' in pyproject
    assert "FROM python:3.12-slim-bookworm" in dockerfile
    assert "Requires Python 3.12." in readme

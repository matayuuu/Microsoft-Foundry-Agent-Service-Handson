from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolate_cloud_shell_markers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Copied-script fixtures must not inherit their runner's interactive environment."""
    for name in ("ACC_VERSION", "AZUREPS_HOST_ENVIRONMENT", "WORKSHOP_CLOUD_SHELL_REPO"):
        monkeypatch.delenv(name, raising=False)

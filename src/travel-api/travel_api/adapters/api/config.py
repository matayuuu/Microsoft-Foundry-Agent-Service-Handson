"""Process-boundary configuration for the Travel Ops HTTP adapter."""

from __future__ import annotations

import os

WORKSHOP_SOURCE_BASE_ENV = "WORKSHOP_SOURCE_BASE"


def workshop_source_base() -> str | None:
    value = os.getenv(WORKSHOP_SOURCE_BASE_ENV, "").strip()
    return value.rstrip("/") if value else None

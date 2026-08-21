"""FastAPI application entrypoint: uvicorn travel_api.main:app --host 0.0.0.0 --port 8080."""

from __future__ import annotations

from fastapi import FastAPI

from travel_api.adapters.api.routes import router

API_DESCRIPTION = """
Deterministic, stateless mock **Travel Ops API** for the Contoso travel/expense
Foundry Agent Service workshop.

* No persistence: every response is computed fresh from fixed, in-memory
  fixtures and the request payload.
* No PII: employee identifiers, when present at all, are opaque synthetic
  aliases such as `employee-001`.
* `POST /preapprovals` is a **simulation only** and never grants a real
  approval; every decision value is prefixed with `simulated_`.
"""

app = FastAPI(
    title="Contoso Travel Ops API",
    description=API_DESCRIPTION,
    version="1.0.0",
    openapi_version="3.1.0",
)

app.include_router(router)

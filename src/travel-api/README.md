# Contoso Travel Ops API

A deterministic, stateless mock backend for the Microsoft Foundry Agent
Service workshop's "Contoso 出張・経費" scenario. It has no database, no
external calls, and no randomness — every response is computed from the
request plus fixed, in-memory fixtures, which makes it safe to use as a
reproducible tool target for agent evaluation and optimization.

- Clean architecture: `travel_api/domain` (pure policy rules, no I/O) →
  `travel_api/application` (use cases, still framework-agnostic) →
  `travel_api/adapters/api` (thin FastAPI adapter: request/response
  translation and HTTP status mapping only).
- OpenAPI 3.1, explicit `operationId` on every operation, typed
  Pydantic request/response models.
- `POST /preapprovals` is **always a simulation**: every decision value is
  prefixed `simulated_` and the response includes an explicit disclaimer.
  It never grants a real travel approval.
- No PII: the only identifiers ever accepted or returned are opaque
  synthetic aliases such as `employee-001`.

## Endpoints

| Method | Path | operationId | Purpose |
|---|---|---|---|
| GET | `/health` | `getHealth` | Liveness/readiness check |
| GET | `/per-diem?city=&date=` | `getPerDiem` | Deterministic meal allowance + lodging cap for a city/date |
| POST | `/trip-estimates` | `createTripEstimate` | Deterministic flight/lodging/meal cost estimate |
| POST | `/preapprovals` | `createPreapproval` | Simulated preapproval decision (never a real approval) |

The interactive OpenAPI docs are served at `/docs` (Swagger UI) and
`/redoc`; the raw spec is at `/openapi.json`.

## Local run

Requires Python 3.13. From this directory (`src/travel-api`):

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

uvicorn travel_api.main:app --host 0.0.0.0 --port 8080
```

Then, in another terminal:

```bash
curl http://127.0.0.1:8080/health
curl "http://127.0.0.1:8080/per-diem?city=Osaka&date=2026-05-11"
```

## Run with Docker

```bash
docker build -t travel-ops-api:local .
docker run --rm -p 8080:8080 travel-ops-api:local
curl http://127.0.0.1:8080/health
```

The container runs as a non-root user, listens on port 8080, and declares a
`HEALTHCHECK` that probes `/health` with Python's standard library (the
`-slim` base image has no `curl`/`wget`). It has no persistent volumes, so it
is safe for Azure Container Apps to scale it to zero between requests.

## Tests

This sub-project intentionally keeps its own dependencies out of the
repository root `pyproject.toml` (see `requirements.txt` / `pyproject.toml`
in this directory). To run the unit and contract tests that exercise this
API (owned by the data/API workstream under `tests/unit/travel_api/` and
`tests/contract/travel_api/`), install this sub-project's dependencies
first:

```bash
cd src/travel-api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

cd ../..
python -m pytest tests/unit/travel_api tests/contract/travel_api
```

Pure domain unit tests (`tests/unit/travel_api/`) only need the `travel_api`
package on `sys.path` (no FastAPI required). Contract tests that exercise the
HTTP layer or `/openapi.json` (`tests/contract/travel_api/`) additionally
need `fastapi`/`httpx`, and skip themselves cleanly
(`pytest.importorskip`) if those are not installed in the environment
running `pytest` — so `make test` at the repository root keeps working even
before the root project depends on this sub-project's packages.

## Keeping numbers in sync with the policy corpus

The per-diem/lodging rate table in `travel_api/domain/rates.py` intentionally
mirrors the tables in `data/policies/03-hotels.md` and
`data/policies/04-per-diem-meals.md`. A contract test
(`tests/contract/data/test_per_diem_rates_match_policy.py`) parses those
Markdown tables and asserts they match this module byte-for-byte on the
numbers, so the two owned areas (`data/**` and `src/travel-api/**`) cannot
silently drift apart.

## Container publishing

`.github/workflows/publish-travel-api.yml` builds and pushes a public GHCR
image on tagged releases (`travel-api-v*`) and manual dispatch. It never
publishes `latest` as the documented tag — Terraform (owned by the
`infra/` workstream) should pin to the immutable digest the workflow job
summary exposes.

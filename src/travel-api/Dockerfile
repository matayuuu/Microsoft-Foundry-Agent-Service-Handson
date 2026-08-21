# syntax=docker/dockerfile:1
# Contoso Travel Ops API - deterministic mock backend for the Foundry Agent
# Service workshop. Designed to scale to zero on Azure Container Apps: no
# persistence, fast cold start, minimal image.

FROM python:3.13-slim-bookworm

WORKDIR /app

# Install pinned, minimal runtime dependencies only (see requirements.txt).
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# Application code.
COPY travel_api/ ./travel_api/

# Run as a non-root, unprivileged user.
RUN groupadd --system --gid 1000 travelapi \
    && useradd --system --uid 1000 --gid travelapi --no-create-home travelapi \
    && chown -R travelapi:travelapi /app
USER travelapi

EXPOSE 8080

# No shell utilities (curl/wget) in -slim; probe with Python's stdlib instead.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request,sys; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3).read(); sys.exit(0)"]

ENTRYPOINT ["uvicorn", "travel_api.main:app", "--host", "0.0.0.0", "--port", "8080"]

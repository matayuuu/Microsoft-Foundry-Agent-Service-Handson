ARG AZURE_CLI_VERSION
FROM mcr.microsoft.com/azure-cli:${AZURE_CLI_VERSION}

COPY pyproject.toml README.md /workshop/
WORKDIR /workshop

RUN python3 -I -c "import sys, venv, ensurepip, ssl; assert (3, 10) <= sys.version_info[:2] < (3, 14), sys.version" \
    && python3 -I -m venv /tmp/workshop-python \
    && /tmp/workshop-python/bin/python -I -m pip --isolated --disable-pip-version-check install --no-input --no-cache-dir . \
    && /tmp/workshop-python/bin/python -I -c "import azure.ai.projects, azure.identity, azure.search.documents, httpx, jsonschema, openai, pydantic, tiktoken, yaml; print('Provisioning runtime imports succeeded')"

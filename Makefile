.PHONY: install install-hosted format lint test test-hosted shell-validate terraform-validate validate

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]" -e "./src/travel-api[dev]"

install-hosted:
	python3.13 -m venv src/hosted-agent/.venv
	src/hosted-agent/.venv/bin/python -m pip install --upgrade pip
	src/hosted-agent/.venv/bin/python -m pip install -r src/hosted-agent/requirements.txt pytest ruff

format:
	python -m ruff format .
	terraform fmt -recursive

lint:
	python -m ruff check .
	python -m ruff format --check .

test:
	python -m pytest

test-hosted:
	src/hosted-agent/.venv/bin/python -m pytest tests/unit/hosted_agent tests/contract/hosted_agent -q

shell-validate:
	bash -n scripts/admin-preflight.sh scripts/preflight.sh scripts/setup.sh scripts/destroy.sh

terraform-validate:
	terraform -chdir=infra init -backend=false
	terraform -chdir=infra validate

validate: lint test test-hosted shell-validate terraform-validate

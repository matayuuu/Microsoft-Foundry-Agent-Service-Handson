.PHONY: install install-hosted format lint test test-hosted shell-validate bicep-build bicep-validate validate

install:
	python -m pip install --upgrade pip
	python -m pip install -e ".[dev]" -e "./src/travel-api[dev]"

install-hosted:
	python3.13 -m venv src/hosted-agent/.venv
	src/hosted-agent/.venv/bin/python -m pip install --upgrade pip
	src/hosted-agent/.venv/bin/python -m pip install -r src/hosted-agent/requirements.txt pytest ruff ipykernel

format:
	python -m ruff format .

lint:
	python -m ruff check .
	python -m ruff format --check .

test:
	python -m pytest

test-hosted:
	src/hosted-agent/.venv/bin/python -m pytest tests/unit/hosted_agent tests/contract/hosted_agent -q

shell-validate:
	@for script in scripts/admin-preflight.sh scripts/request-quota-increase.sh scripts/bootstrap-custom-template.sh; do bash -n "$$script" || exit; done

bicep-build:
	az bicep build --file infra/main.bicep --outfile infra/azuredeploy.json

bicep-validate:
	python scripts/check_template_artifact.py

validate: lint test test-hosted shell-validate bicep-validate

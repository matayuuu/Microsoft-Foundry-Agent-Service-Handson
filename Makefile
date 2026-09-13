.PHONY: install install-hosted setup format lint test test-hosted assets assets-check shell-validate bicep-build bicep-validate validate

PYTHON ?= $(if $(WORKSHOP_MANAGEMENT_PYTHON),$(WORKSHOP_MANAGEMENT_PYTHON),python)
HOSTED_PYTHON ?= $(if $(WORKSHOP_HOSTED_PYTHON),$(WORKSHOP_HOSTED_PYTHON),$(HOME)/.venvs/foundry-hosted-agent/bin/python)

install install-hosted: setup

setup:
	python3.12 scripts/setup_dev_environment.py

format:
	"$(PYTHON)" -m ruff format .

lint:
	"$(PYTHON)" -m ruff check .
	"$(PYTHON)" -m ruff format --check .

test:
	"$(PYTHON)" -m pytest

test-hosted:
	"$(HOSTED_PYTHON)" -m pytest tests/unit/hosted_agent tests/contract/hosted_agent -q

assets:
	"$(PYTHON)" -B -m scripts.build_common_assets

assets-check:
	"$(PYTHON)" -B -m scripts.build_common_assets --check

shell-validate:
	@for script in scripts/admin-preflight.sh scripts/request-quota-increase.sh scripts/bootstrap-custom-template.sh; do bash -n "$$script" || exit; done

bicep-build:
	az bicep build --file infra/main.bicep --outfile infra/azuredeploy.json

bicep-validate:
	"$(PYTHON)" scripts/check_template_artifact.py

validate: lint test test-hosted assets-check shell-validate bicep-validate

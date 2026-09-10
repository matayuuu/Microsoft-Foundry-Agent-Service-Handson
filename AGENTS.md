# AGENTS.md

## Project overview

This repository contains a Japanese, portal-first Microsoft Foundry Agent Service
workshop. It provisions an isolated workshop environment in an existing Azure
resource group, seeds synthetic Contoso travel and expense data, and guides
participants through prompt agents, Foundry IQ, tools and toolboxes, evaluation,
optimization, and a Microsoft Agent Framework workflow deployed as a Hosted Agent.

This project was built with the microsoft-foundry skill. Before working on or
answering questions about Foundry agents, read the microsoft-foundry skill first.

## Architecture and ownership

- `infra/`: Terraform control-plane resources. Use AzureRM for stable Azure resources
  and AzAPI only where the new Foundry resource model or connections require it.
- `scripts/`: thin command-line adapters for preflight, setup, data bootstrap,
  evaluation, Hosted Agent deployment, validation, and cleanup.
- `src/travel-api/`: deterministic mock Travel Ops API. Keep policy and calculation
  rules pure; HTTP handlers only translate requests and responses.
- `src/hosted-agent/`: Python 3.13 Microsoft Agent Framework workflow and its
  Responses-protocol host.
- `data/`: synthetic, redistributable RAG, fixture, receipt, and evaluation data.
- `labs/`: participant instructions in workshop order.
- `docs/`: architecture plus administrator and participant prerequisites.
- `instructor/`: facilitation notes and fallback assets.
- `tests/`: unit, contract, and integration tests.

Terraform owns Azure infrastructure. Python SDK wrappers own Foundry data-plane
objects such as toolbox versions, evaluation runs, and Hosted Agent versions. Do
not make Terraform and SDK scripts manage the same object.
Cloud Shell's user-specific Storage account, Azure Files share, and optional
Cloud-Shell-created resource group are environment prerequisites managed separately
through the Azure portal, not Terraform workload resources. Delete only the dedicated
Cloud Shell resources after workload cleanup succeeds.

## Non-negotiable constraints

- Participants use Azure CLI sign-in (`az login` or Cloud Shell's existing session);
  do not require client secrets, API keys, or a separate `azd auth login` in the core
  workshop.
- Participant workload automation may write only inside the existing resource group
  supplied by the user. It must not register resource providers, change quota, create
  resource groups, or write subscription-scope role assignments. Before running that
  automation, the participant may create the dedicated workload resource group in the
  Azure portal when the workshop explicitly assumes subscription-level Owner or
  equivalent permissions. The Cloud Shell first-run UI may separately create its own
  dedicated storage resource group. Both prerequisite actions stay outside Terraform.
- Use public endpoints with Microsoft Entra ID/RBAC. Private networking is out of
  scope.
- Do not add Cosmos DB, ACR, or an Agent capability host to the core Basic Agent
  Setup.
- Keep all three model deployments required: `gpt-5.6-luna` for Prompt/Hosted
  Agent runtimes, shared `gpt-5.5` for Foundry IQ plus Labs 5/6, and
  `text-embedding-3-small` for vectors. Preflight must resolve one region with
  the required GlobalStandard headroom for all three before setup proceeds.
- Treat Terraform state as sensitive. Never commit it or print computed credentials.
- All sample content must remain synthetic and must not contain personal or customer
  data.
- Keep actionable billing, authentication, data-boundary, simulation, and cleanup
  guidance visible in the labs. Omit generic preview disclaimers from the
  participant path; retain actual UI labels, API versions, and operational limits.
- Preserve both browser paths: Codespaces VS Code and Azure Cloud Shell Bash with
  JupyterLab Web preview. Branch only during environment preparation; share Labs
  2–9 and the existing Lab 7/8 notebooks. Keep environment-specific UI instructions
  in `docs/participant/environments/`.
- Cloud Shell requires verified persistent HOME storage. Prefer the first-run
  **We will create a storage account for you** path when its subscription-level
  permissions and policy are approved; retain existing-storage selection as the
  controlled alternative. Never run Terraform in an ephemeral session, place virtual
  environments directly on the clouddrive SMB share, reset existing user settings
  silently, or remove recovery state before cleanup succeeds. A saved notebook does
  not persist kernel memory.
- Do not require sudo, OS package installation, or Docker in Cloud Shell. Keep
  Jupyter authentication and XSRF enabled, restrict access to the actual preview
  origin, and never expose tokens or credentials in logs or screenshots.

## Setup commands

Codespaces developer setup (the existing devcontainer path):

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]" -e "./src/travel-api[dev]"

python3.13 -m venv src/hosted-agent/.venv
src/hosted-agent/.venv/bin/python -m pip install -r src/hosted-agent/requirements.txt pytest ruff ipykernel
az login --use-device-code
```

Cloud Shell participants use the
[environment guide](docs/participant/environments/cloud-shell.md), including
storage creation/mounting, Jupyter authentication, and reconnection. From the
repository under persistent HOME:

```bash
bash scripts/setup-cloud-shell.sh
source scripts/activate-cloud-shell.sh
bash scripts/start-cloud-shell-jupyter.sh
```

The default launcher prepares or reuses dependencies, asks for a private password,
and captures the actual Web preview URL from the authenticated preview tab. Keep
explicit `--discover-preview` / `--preview-url` only as troubleshooting paths.

Keep Python 3.13 and both virtual environments. Root tooling requires
`azure-ai-projects==2.5.0`; Hosted Agent dependencies require a version below 2.4.
Keep kernel names `foundry-workshop` and `foundry-hosted-agent`. Activation limits
Cloud Shell local tooling to `AZURE_TOKEN_CREDENTIALS=AzureCliCredential`; never
propagate that restriction to the deployed Hosted Agent's managed identity.

Participant environment lifecycle:

```bash
./scripts/preflight.sh --subscription <subscription-id> --resource-group <resource-group>
./scripts/setup.sh --subscription <subscription-id> --resource-group <resource-group>
./scripts/destroy.sh
```

Subscription administrators use `./scripts/admin-preflight.sh`; its default mode
must remain read-only.
Administrators, not participants or bootstrap scripts, register
`Microsoft.CloudShell` and `Microsoft.Storage`, approve storage/network policy,
and arrange any increase to Cloud Shell's default 20 concurrent users per tenant.

## Development workflow

- Keep domain rules independent from Azure SDK, FastAPI, Terraform, and filesystem
  details.
- Put orchestration in explicit use cases and adapters at process or HTTP boundaries.
- Prefer small typed modules over generic `utils.py` files.
- Reuse `.workshop/context.json` for generated resource identifiers; never duplicate
  endpoints in source files.
- All setup and cleanup operations must be safe to retry.
- Poll long-running Azure operations with a timeout and terminal failure handling;
  do not use unbounded loops or fixed success-shaped sleeps.
- Use official Microsoft Learn and official Microsoft repositories for Foundry API
  behavior. Document the retrieval date when a preview contract is encoded.

## Testing and validation

```bash
make format
make lint
make test
make terraform-validate
make validate
```

- Unit tests cover pure policy, naming, configuration, and data transformation logic.
- Contract tests validate JSONL schemas, OpenAPI 3.1, Terraform outputs, and Foundry
  SDK payload builders without calling Azure.
- Integration tests require an explicitly selected disposable resource group and
  must be skipped by default.
- Tests must never use a real employee, email, expense, booking, or production
  endpoint.
- Add or update tests for every behavior change.

## Code style

- Python 3.13, type hints on public functions, Ruff formatting/linting, 100-character
  line length.
- Shell scripts use Bash, `set -euo pipefail`, quoted variables, and actionable
  failure messages.
- Terraform uses `terraform fmt`, typed variables with validation, stable names, and
  explicit dependencies only where Azure propagation requires them.
- Markdown participant instructions use Japanese prose and English identifiers.
- Avoid broad exception handling, silent fallback, and logging bearer tokens or
  Terraform outputs that can contain credentials.

## Build and deployment

- The Travel Ops API image is built by GitHub Actions and published publicly to GHCR.
  Terraform must reference an immutable image digest.
- The core Hosted Agent deployment uses `scripts/deploy_hosted_agent.py` and Foundry
  source-code remote build. `azd` and container/ACR deployment belong in optional
  material only.
- Every Hosted Agent deployment creates an immutable version. Cleanup must delete
  SDK-managed data-plane objects before Terraform destroys their parent project.

## Pull request checks

Before merging, run the same `make validate` command used by CI. PR descriptions must
state whether they change infrastructure, workshop timing, preview APIs, permissions,
cost, or data-boundary behavior.

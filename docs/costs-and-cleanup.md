# Costs and cleanup

## Cost posture

The workshop favors small, short-lived, scale-to-zero resources, but it is not free.
Always review current Azure pricing in the target region before an event.

Main cost drivers:

- Azure AI Search Basic is billed while the service exists.
- Model inference, embeddings, evaluation judges, and Agent Optimizer are token billed.
- Web Search and Code Interpreter have charges separate from model tokens.
- Agentic retrieval can bill Search retrieval tokens and model query-planning tokens.
- Container Apps scales to zero, but requests and supporting Log Analytics ingestion
  can incur charges.
- Application Insights and Log Analytics charge for retained telemetry above included
  allowances.

The administrator preflight calculates required model capacity from participant/team
count. It does not estimate currency because prices and regional offers change.

## Cost controls

- Use a dedicated resource group per participant or team.
- Use Search Basic with one replica and one partition.
- Keep the Travel Ops API at minimum replicas zero.
- Use a small live evaluation subset and a small Optimizer candidate count.
- Keep Agentic Retrieval reasoning at `low` for the core lab.
- Use only the requests shown in the labs.
- Run cleanup immediately after the event.

## Cleanup order

Run:

```bash
./scripts/destroy.sh
```

Review the target resources and approve deletion. This removes the workshop's
Foundry project / account along with the other Terraform-managed resources, but
preserves the resource group. See [Lab 8](../labs/08-observability-cleanup.md).
If deletion fails because of Toolbox or Skill references, follow
[participant cleanup troubleshooting](participant/troubleshooting.md#cleanup).

The script must:

1. Read `.workshop/context.json`, or the pre-Terraform
   `.workshop/terraform-inputs.json` recovery file when setup stopped early, and
   confirm the selected subscription and RG.
2. Delete the workshop Hosted Agent and its versions through the Foundry SDK.
3. Run optional data-plane cleanup helpers when present; report missing helpers.
4. Run `terraform destroy` against the existing state.
5. Verify no tagged workshop resources remain in the RG.
6. Preserve the RG itself.
7. Remove local context and state only after successful verification.

If cleanup fails, do not delete Terraform state. Follow
[administrator troubleshooting](admin/troubleshooting.md) with the exact resource and
operation reported by the script. `setup.sh` writes
`.workshop/terraform-inputs.json` before Terraform can create resources, so
`destroy.sh` can normally recover a partial setup without arguments. Explicit inputs
remain available if both setup context files are unavailable.

## State handling

Local Terraform state is the default because not every participant can access a shared
state account. It is stored only in the persistent Codespaces workspace, ignored by
Git, and treated as sensitive. Do not delete the Codespace before cleanup.

Organizers can opt into the Azure Blob backend example when they can provision a state
account and grant each participant data-plane access.

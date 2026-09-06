# Administrator troubleshooting

Failures reported here are diagnosed with the subscription administrator's tools
(`az`, the Azure portal Activity Log, `scripts/admin-preflight.sh`). If a participant
hits one of these during `scripts/setup.sh`, they cannot fix it themselves — it needs
either a subscription-scope action from you, or an Azure support ticket.

## `admin-preflight.sh` reports a resource provider as `NotRegistered`

Run `./scripts/admin-preflight.sh --subscription "<id>" --apply` to register it. If
registration itself fails with an authorization error, the identity you used does not
have provider-registration rights at the subscription scope; use an identity with
Contributor (or equivalent) at that scope, not a resource-group-scoped role — RG-scoped
Owner cannot register providers, by design.

## `admin-preflight.sh` reports insufficient model quota/capacity

This means the subscription's regional quota for `gpt-5.6-luna`, `gpt-5.5`,
or `text-embedding-3-small` is below what the workshop needs for your
expected participant/team count in that region. Options, in order of speed:

1. Re-run with `--location swedencentral` (or `eastus2`, whichever you did not just
   check) — the workshop supports either as a full alternative, not a degraded mode.
2. Request a quota increase for the relevant model/SKU via the Azure portal
   (Quotas blade) or an Azure support ticket. Quota increases are not instant; plan
   for lead time before the event.
3. Reduce concurrent participant/team count, or stagger sessions, so the existing
   quota covers the smaller concurrent footprint.

Never tell participants to proceed against a subscription with confirmed insufficient
capacity — `terraform apply` will fail late, mid-workshop, with a much worse
participant experience than catching it here first.

Luna is shared by Prompt/Hosted Agents; GPT-5.5 is shared by Foundry IQ query planning,
configurable LLM judges, and Optimizer. Check each deployment's own same-SKU
`usageName` evidence, using default capacities 40/100/40K TPM respectively.
Do not infer a quota bucket from a model name or substitute an old model version.

## HTTP 429 or Foundry IQ timeouts despite available subscription quota

Subscription quota headroom and a deployment's allocated throughput are different.
During a 2026-09-06 rehearsal, a seven-row Portal evaluation produced 36 HTTP 429
responses between 01:37 and 01:42 UTC with the shared GPT-5.5 deployment at 20 capacity
units. ARM reported `rateLimits` of 20 requests/60 seconds and 20,000 tokens/60 seconds;
Foundry IQ retrieval also reached its 90-second timeout.

The default `optimizer_model_capacity` is now **100**, shared by Foundry IQ query
planning, configurable LLM judges, and Optimizer. Luna and embedding remain at 40.
This allocates more deployment throughput within existing GlobalStandard model/SKU
quota; it does not raise the subscription quota limit or purchase a fixed token-spend
bill. Actual model consumption is still chargeable, and other Azure service charges
remain. Higher throughput can permit more consumption.

For an existing environment, review the Terraform plan and any explicit capacity
override before applying: an old tfvars or `-var` override of 20 still wins over the
new default. Confirm the resulting deployment capacity and actual `rateLimits`, then
repeat a controlled evaluation after the previous run is terminal. 100 units does
not mathematically guarantee zero 429s: request bursts, token volume, and service-side
limits still matter. Reduce overlapping workloads and honor retry guidance if
throttling persists; do not blindly resubmit a running chargeable evaluation.

## A model appears in the catalog but not in the Portal picker

Catalog availability, quota, and feature/API support are separate checks. Confirm the
selected project and deployment names in `.workshop/context.json`. Prompt/Hosted
Agents use `primary_model_deployment_name` (`gpt-5.6-luna`). Foundry IQ, configurable
LLM evaluation judges, and both Optimizer model selections use
`optimizer_model_deployment_name` (`gpt-5.5`); service-managed evaluators do not expose
a configurable judge.

In the new Portal checked on 2026-09-06, the knowledge-base Chat completions model
picker offered the deployed GPT-5.5 but not Luna, even after choosing Medium. The Agent
picker offered Luna and agent inference succeeded. Use GPT-5.5 for the knowledge base;
do not change the Agent to match it. A model's availability through a
[Search API](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
does not guarantee that the current Portal exposes it.
If the required picker/API is unavailable, stop and record the blocker rather than
adding another deployment or silently switching models.

## Updating an environment with old deployment names

Changing `primary`/`optimizer` to `gpt-5.6-luna`/`gpt-5.5` can replace model resources.
Review the Terraform plan and reconnect any saved agent/knowledge/evaluation references
after the change. State recovery only imports the exact current deployment IDs; do not
delete state to bypass a mismatch. Preserve the original cleanup inputs and state until
cleanup succeeds, and never delete the existing resource group.

## Azure AI Search reports `InsufficientResourcesAvailable`

Search capacity is a live regional constraint that the resource-provider availability
metadata cannot predict. Re-run `scripts/setup.sh` with the supported alternate region:

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --location swedencentral
```

Use `eastus2` instead when the failed attempt targeted `swedencentral`. Setup is
idempotent, safely imports deterministic workshop-tagged resources and exact RBAC
assignments that exist without a local state entry, and refreshes its Terraform plan
after any partial apply. If recovery refuses an import because ownership tags differ,
do not force-import or delete that resource; investigate the name collision first.

## `admin-preflight.sh` reports an Azure Policy that may deny required resource types

The script's policy scan is **best-effort**: it lists policy assignments whose
effect (`deny`, `disable`, etc.) and resource-type scope look like they could block
`Microsoft.CognitiveServices/accounts`, `Microsoft.Search/searchServices`,
`Microsoft.App/*`, or their sub-resources, but it cannot exhaustively evaluate every
policy's condition logic (initiative-nested policies, tag-based conditions, and
`deployIfNotExists` effects in particular are hard to statically resolve). If the
report flags a candidate policy:

1. Open it in the portal (Policy > Definitions) and read its `if` condition against
   the exact resource types above.
2. If it denies one of them without an exemption path, either request a
   policy exemption scoped to the workshop resource group, or choose a
   different resource group/subscription that is not subject to it.
3. If the report shows **no** flagged policies, that is not a guarantee — it means
   none matched the script's heuristics. A real `terraform apply` failure with a
   policy-denial error message is authoritative; the preflight scan is a fast,
   non-exhaustive early warning only.

Workshop versions before 2026-08-31 provisioned a Storage account for a redundant copy
of the source documents. A management-group `modify` policy that disabled its public
access caused bootstrap to fail from Codespaces. The current core path no longer
provisions or accesses Storage; it indexes the repository's synthetic policy files
directly into Azure AI Search. Update the checkout and rerun `setup.sh` to remove the
legacy Storage resources through Terraform.

## A participant's `preflight.sh` fails even though `admin-preflight.sh` passed

`scripts/preflight.sh` is participant/resource-group scoped and additionally checks
things `admin-preflight.sh` cannot see from the subscription level: whether the named
resource group actually exists, whether the participant's own identity has Owner on
it, and live model-catalog availability at the exact region `preflight.sh` resolves
to. Confirm:

- The resource group name/subscription ID the participant passed match what you
  provisioned for them.
- The participant is signed in (`az login`) as the identity you granted Owner to,
  not a different account or a service principal.
- The provider registration and quota checks were performed for the **same** region
  the participant is targeting (`--location`), not just the workshop default.

## Terraform apply fails with an authorization error inside the resource group

This should not happen if `admin-preflight.sh` and the participant's `preflight.sh`
both passed, since Terraform never operates outside the named resource group or at
subscription scope. If it does happen, it is very likely one of:

- The participant's Owner role assignment on the resource group has not finished
  propagating yet (Entra role propagation can take a few minutes) — wait and retry
  `scripts/setup.sh`, which is idempotent.
- The role was assigned at a different scope (e.g. a child resource) instead of the
  resource group itself.

## Cleanup (`destroy.sh`) reports resources still present after `terraform destroy`

See [costs and cleanup](../costs-and-cleanup.md#cleanup-order) for the full teardown
order. If Azure resources remain tagged as workshop resources in the resource group
after a reported-successful `terraform destroy`, do not delete `.workshop/` state —
re-run `scripts/destroy.sh`; Terraform destroy is idempotent and safe to retry against
existing state. If it still leaves resources, inspect the exact resource and error
`destroy.sh` reports; do not delete resources by hand outside of Terraform, since that
can desynchronize local state from the real resource group and complicate a later
retry.

If setup failed before `.workshop/context.json` was written, run
`./scripts/destroy.sh` normally. Setup persists the resolved, non-secret Terraform
inputs to `.workshop/terraform-inputs.json` before Terraform can create resources, and
destroy uses that file automatically.

Only if both context files are unavailable, pass the original inputs explicitly so
Terraform can destroy the partial state:

```bash
./scripts/destroy.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --travel-api-image-ref "ghcr.io/<owner>/travel-ops-api@sha256:<digest>" \
  --location "<eastus2-or-swedencentral>" \
  --source-base "https://github.com/<owner>/<repo>/blob/main" \
  --optimizer-model-version "<version>" \
  --primary-model-version "<version>" \
  --embedding-model-version "<version>" \
  --auto-approve
```

## See also

- [Administrator prerequisites](prerequisites.md)
- [Costs and cleanup](../costs-and-cleanup.md)
- [Architecture](../architecture.md)

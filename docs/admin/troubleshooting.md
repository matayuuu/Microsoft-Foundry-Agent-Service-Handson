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

This means the subscription's regional quota for `gpt-4.1`, the discovered `gpt-5`
family model, or `text-embedding-3-small` is below what the workshop needs for your
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
idempotent and refreshes its Terraform plan after any partial apply.

## `admin-preflight.sh` reports an Azure Policy that may deny required resource types

The script's policy scan is **best-effort**: it lists policy assignments whose
effect (`deny`, `disable`, etc.) and resource-type scope look like they could block
`Microsoft.CognitiveServices/accounts`, `Microsoft.Search/searchServices`,
`Microsoft.Storage/storageAccounts`, `Microsoft.App/*`, or their sub-resources, but it
cannot exhaustively evaluate every policy's condition logic (initiative-nested
policies, tag-based conditions, and `deployIfNotExists` effects in particular are hard
to statically resolve). If the report flags a candidate policy:

1. Open it in the portal (Policy > Definitions) and read its `if` condition against
   the exact resource types above.
2. If it denies one of them without an exemption path, either request a
   policy exemption scoped to the workshop resource group, or choose a
   different resource group/subscription that is not subject to it.
3. If the report shows **no** flagged policies, that is not a guarantee — it means
   none matched the script's heuristics. A real `terraform apply` failure with a
   policy-denial error message is authoritative; the preflight scan is a fast,
   non-exhaustive early warning only.

A management-group `modify` policy can also allow Storage creation to report success
while rewriting `publicNetworkAccess` to `Disabled`. The later data bootstrap then
fails with Storage `AuthorizationFailure` even when `Storage Blob Data Contributor`
is present. Confirm this case in the resource Activity Log by looking for
`Microsoft.Authorization/policies/modify/action` on the Storage account. The core
workshop intentionally uses public endpoints and does not provision private
networking, so use a compatible subscription or have an administrator approve a
resource-group-scoped exemption for that specific policy definition reference.
Participants must not create governance exemptions themselves.

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

If setup failed before `.workshop/context.json` was written, pass the original inputs
explicitly so Terraform can destroy the partial state:

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

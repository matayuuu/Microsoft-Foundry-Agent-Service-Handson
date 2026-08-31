# Administrator prerequisites

This page is for the **subscription administrator** who prepares the Azure subscription
before the workshop event. Participants do not need subscription-level permissions and
must not perform any of the steps described here; see
[participant prerequisites](../participant/prerequisites.md) for what they need instead.

## Why a separate administrator step exists

Registering resource providers, verifying regional model quota/capacity, and reviewing
Azure Policy are subscription-scope operations. A participant who is Owner only on an
existing resource group cannot perform them. `scripts/admin-preflight.sh` is the tool
that performs (or, by default, only reports) these subscription-scope checks, so that
`scripts/preflight.sh` and `scripts/setup.sh` — run later by each participant — never
need subscription-level permissions themselves.

## What you need

- Azure CLI (`az`) signed in (`az login`) with an identity that has at least
  **Reader** at the subscription scope, so the read-only checks can run.
- To also register missing resource providers (`--apply`), the identity additionally
  needs a role that can perform
  `Microsoft.Support/register/action` / provider-registration actions at the
  subscription scope (for example, **Contributor** or the built-in
  **Azure Resource Manager Provider Registration** capability many subscriptions grant
  to administrators). This workshop does not grant or assume any specific role name —
  confirm your own tenant's convention.
- Network access to `management.azure.com`.
- The target region(s): default `eastus2`, fallback `swedencentral`. Both are always
  checked so participants can fail over without a second administrator pass.

## What `admin-preflight.sh` checks

Run from the repository root:

```bash
./scripts/admin-preflight.sh --subscription "<subscription-id>" [--location eastus2]
```

By default this is **strictly read-only**. It never creates or deletes a resource
group, never changes subscription quota or Azure Policy, and never writes a role
assignment. It reports, per region (`eastus2` and `swedencentral`):

1. **Resource provider registration state** for the five providers this workshop
   depends on:
   - `Microsoft.CognitiveServices` (Foundry/Azure AI Services accounts)
   - `Microsoft.Search` (Azure AI Search)
   - `Microsoft.Insights` (Application Insights)
   - `Microsoft.OperationalInsights` (Log Analytics)
   - `Microsoft.App` (Container Apps, for the Travel Ops API)
2. **Model quota/capacity** for the three model deployments the workshop creates, each
   checked against the exact SKU/usage bucket Terraform will request, and against the
   **aggregate** requirement for all participants/teams the event will run at once (see
   `--participant-count` below), not just one environment's worth:
   - `gpt-4.1` — SKU `GlobalStandard`, required headroom **40K TPM per environment**.
     Primary agent inference, evaluation judge, and Foundry IQ query planning model.
   - a supported `gpt-5` family model — SKU `GlobalStandard`, required headroom
     **20K TPM per environment**. Agent Optimizer. The exact model name/version is
     **not hardcoded**; the script queries the live model catalog for the
     subscription/region and reports whichever supported `gpt-5` variant(s) are
     actually available there. Never assume a specific version is available before the
     script confirms it.
   - `text-embedding-3-small` — SKU `GlobalStandard`, required headroom **40K TPM per
     environment**. The vector index embedding model.
   - For each model/region pair the script reads the model's own
     `model.skus[].usageName` (never guessed or string-built from the model name —
     usageName spelling is inconsistent across model families, for example a
     hyphen-less `...gpt4.1` bucket versus a hyphenated `...gpt-5` bucket) and looks
     up that exact bucket in `az cognitiveservices usage list --location <region>`.
     The Markdown/JSON report shows, per model/region: the resolved model
     version(s), the required SKU, the resolved `usageName`, the per-environment
     capacity, the `--participant-count`-scaled aggregate requirement, and the
     headroom/limit/current-usage numbers used to decide pass/warn — so you can see
     the evidence, not just a verdict.
   - The report always states the discovered/available capacity explicitly. If the
     script cannot resolve the required SKU on a model, cannot find that
     `usageName` bucket in the usage-list output, or the `az cognitiveservices
     usage list` call itself fails, it reports that as an **unknown/failed check**
     (`warn`), never as an implicit pass — never assume unqueried capacity is
     sufficient. (`scripts/preflight.sh`, run later by each participant, applies the
     same SKU/usageName evidence but **fails hard** — rather than warns — on any
     unknown or insufficient headroom, since a participant cannot proceed without a
     usable region.)
3. **Azure Policy** effects that could block the workshop's resource types (best
   effort; Azure Policy evaluation is not exhaustively enumerable via a preflight
   script, so absence of a reported denial is not a guarantee — see
   [troubleshooting](troubleshooting.md)).
4. Resource group existence and each participant's **Owner** role are checked by
   the participant-facing `scripts/preflight.sh --resource-group <name>`. The
   administrator must create/assign those RGs before distributing the
   admin-preflight report; `admin-preflight.sh` itself is subscription-scoped and
   intentionally has no `--resource-group` option.

The report is emitted as JSON by default; pass `--format markdown` for a
human-readable version, and `--output <file>` to write it to a file instead of
stdout.

### Checking quota for more than one participant/team

Each participant or team runs the workshop in their own resource group and gets their
own set of model deployments, but every environment in the same region draws from the
**same subscription-level quota pool**. Pass `--participant-count <n>` (default `1`) to
verify the region can actually support the whole event at once, not just a single
environment:

```bash
./scripts/admin-preflight.sh --subscription "<subscription-id>" --participant-count 12
```

This multiplies each model's per-environment required capacity by `<n>` (for example,
`gpt-4.1`'s 40K TPM per environment becomes a 480K TPM aggregate requirement for 12
participants) and reports the exact `per-environment capacity * participant-count =
required aggregate capacity` arithmetic alongside the discovered headroom for every
model/region check, plus the participant count itself in the JSON/Markdown report
header — never a single opaque number. `--participant-count` must be a positive
integer; the script exits `1` before making any Azure call if it is not.

## Applying the fix

If the report shows one or more of the six providers is `NotRegistered`, register
them explicitly:

```bash
./scripts/admin-preflight.sh --subscription "<subscription-id>" --apply
```

`--apply` performs exactly one class of mutation: `az provider register` for the
providers reported as missing. It still never touches quota, policy, resource
groups, or role assignments. Re-run without `--apply` afterward to confirm every
check now passes.

## Publish the workshop Travel Ops API image

Before participants run setup, a repository maintainer must publish the immutable
Travel Ops API image:

1. Push a tag matching `travel-api-v*` (the participant default resolves
   `travel-api-v1.0.3`) or run **Publish Travel Ops API** manually.
2. Open the resulting `travel-ops-api` package settings on GitHub and set the
   package visibility to **Public**. A package built from a private repository
   remains private by default, and GitHub doesn't provide a supported workflow-token
   REST operation for changing this setting.
3. Run participant setup once in a rehearsal RG. Its anonymous OCI lookup must
   resolve the tag to an immutable `sha256:` digest before Terraform starts.

If your organization can't expose a public GHCR package, publish the same image to
an approved public registry and pass its immutable digest through
`--travel-api-image-ref`.

## Handing off to participants

Once `admin-preflight.sh` (without `--apply`, and with `--participant-count` set to
your expected number of environments) reports all required providers as `Registered`
and model quota/capacity as sufficient for that aggregate in at least one of
`eastus2`/`swedencentral`, you can create (or designate) one existing resource group
per participant or team, grant each participant **Owner** on their resource group
only, and share this repository plus the
[README quick start](../../README.md#quick-start). Participants then run
`scripts/preflight.sh` and `scripts/setup.sh` themselves — both are strictly
resource-group scoped and never require the permissions described on this page.

## See also

- [Administrator troubleshooting](troubleshooting.md)
- [Costs and cleanup](../costs-and-cleanup.md)
- [Architecture](../architecture.md)

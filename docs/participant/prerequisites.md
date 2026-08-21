# Participant prerequisites

This page is for the **workshop participant**. You do not need any subscription-level
permission — everything here is scoped to the one existing resource group you were
given. If something here looks like it needs subscription access, stop and ask your
workshop administrator; see [administrator prerequisites](../admin/prerequisites.md)
for what they are responsible for instead.

## What you need before the event

- A GitHub account with access to GitHub Codespaces (or a local dev environment
  equivalent — the workshop is designed and tested against Codespaces).
- The Azure CLI (`az`), available inside the provided Codespace.
- From your workshop administrator:
  - An Azure **subscription ID**.
  - The name of an **existing** Azure **resource group** in that subscription.
  - Confirmation that you have been granted the **Owner** role on that resource group
    (not Contributor — Terraform needs Owner to write role assignments scoped to the
    resource group's own resources).
  - Confirmation that your administrator has completed
    [administrator prerequisites](../admin/prerequisites.md) (resource provider
    registration and model quota/capacity verification) for the region you will use
    (default `eastus2`, fallback `swedencentral`).
- A Travel Ops API container image. You normally do **not** need to supply
  `--travel-api-image-ref` yourself: `setup.sh` resolves the immutable `@sha256`
  digest for the maintainer's default public GHCR release
  (`ghcr.io/matayuuu/travel-ops-api:v1.0.0` by default) itself, via an anonymous
  GHCR registry lookup — no image build/push, Docker, or `docker login` needed on
  your side. Only pass `--travel-api-image-ref` explicitly if your administrator
  gives you a different, already-resolved `ghcr.io/...@sha256:<digest>` reference.

## What you must never need to do

By design, none of the following are required of you, and the workshop scripts never
attempt them on your behalf:

- Creating or deleting a resource group.
- Registering an Azure resource provider (`az provider register`).
- Changing subscription-level quota or Azure Policy.
- Creating or managing a service principal, client secret, or API key. You
  authenticate once with `az login`; Terraform and the Python scripts reuse that same
  Entra ID session (`DefaultAzureCredential`) for every Azure call, and runtime access
  to Search/Storage/Foundry is keyless (Entra ID/RBAC only).

If a script ever prompts you for one of the above, or fails with an error suggesting
you need it, stop and contact your workshop administrator rather than trying to grant
yourself broader access — the resource group Owner role is deliberately the ceiling of
what this workshop asks you to hold.

## Signing in

```bash
az login --use-device-code
```

Use the account your administrator granted Owner to on the resource group. Confirm you
are on the right subscription:

```bash
az account show --query "{subscriptionId:id, name:name, user:user.name}" -o table
```

## Checking your own environment before setup

You can run your own read-only preflight at any time — it never mutates anything and
is safe to run repeatedly:

```bash
./scripts/preflight.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  [--location eastus2]
```

This confirms: your identity actually has Owner on the named resource group, the
region you asked for (or `swedencentral` as an automatic fallback) has the required
resource providers already registered and sufficient model quota/capacity, and it
discovers a real, currently-available `gpt-5` family model version for the Agent
Optimizer step instead of you having to guess one. A non-zero exit code means you
should not proceed to `setup.sh` yet — read the reported detail and, if it points at
something subscription-scoped, escalate to your administrator using
[administrator troubleshooting](../admin/troubleshooting.md).

## Running setup

Once `preflight.sh` passes:

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  [--location eastus2] \
  [--source-base "https://github.com/<org>/<repo>/blob/main"] \
  [--travel-api-image-ref "<ghcr-image-ref>@sha256:<digest>"]
```

This is one command and is safe to re-run if it is interrupted or fails partway
through — every step (Terraform apply, data bootstrap, environment validation) is
idempotent. It never writes anything outside your resource group and never prints a
secret. It creates `.workshop/context.json`, `.workshop/.env`,
`.workshop/preflight-report.json`, and `.workshop/tfplan`; all are local,
git-ignored workshop state. Treat the plan/context as sensitive operational
artifacts even though scripts never write API keys or client secrets into them.

The data bootstrap and environment validation steps each retry automatically (a
bounded number of attempts with a short delay between them) if they hit a transient
failure — this absorbs the brief propagation delay that role assignments Terraform
just created (Storage Blob Data Contributor, Search index-data roles, Foundry User)
and the Travel Ops API's own cold start can need right after `terraform apply`. Every
attempt's error is still printed, so a genuine (non-transient) failure is never
hidden, only retried a bounded number of times before `setup.sh` reports it and stops.

### Environment validation

The final step (`validate_environment.py`) confirms your deployed environment, not
just that Terraform apply succeeded. In addition to the RBAC and Azure AI Search
checks, it also confirms that the AI Services account, Storage account, Search
service, and Travel Ops API container app all still exist as ARM resources, and that
the Travel Ops API responds `200` on its own `/health` endpoint — so `setup.sh` never
reports success while the Travel Ops API container app is unreachable.

`--source-base` controls the public URL prefix that Foundry IQ citations link back to
for each policy document. You do not normally need to pass it: `setup.sh` derives it
automatically from your Codespace's `git remote get-url origin` (always the `main`
branch, never a private/unpushed branch or a local `file://` path), falling back to
this repository's own public URL if that cannot be resolved. Override it only if your
workshop administrator asks you to point citations at a different public mirror.

### Travel Ops API image resolution

You do not normally need to pass `--travel-api-image-ref` either. By default,
`setup.sh` resolves the immutable digest for
`ghcr.io/matayuuu/travel-ops-api:v1.0.0` itself, using an **anonymous** GHCR
registry token + manifest lookup (no credentials, no `docker login`) — the resulting
`ghcr.io/...@sha256:<digest>` reference is what actually reaches Terraform. This
keeps setup a genuine one-command flow even though the image is built and published
by a different part of the workshop.

If you need to point at a different published image (for example, your
administrator maintains a private fork's release), you have two options:

- `--travel-api-image-repo "ghcr.io/<owner>/travel-ops-api" --travel-api-image-tag "<tag>"`
  — same anonymous resolution, against a different repo/tag.
- `--travel-api-image-ref "ghcr.io/<owner>/travel-ops-api@sha256:<digest>"` — skips
  resolution entirely and uses your own already-pinned digest.

If `setup.sh` cannot anonymously resolve the default image (the release has not been
published yet, or the GHCR package is not public), it fails **before** touching
Terraform with an explanation that the image needs to be published — this is an
administrator/maintainer action, not something you can fix yourself. See
[administrator troubleshooting](../admin/troubleshooting.md) if you hit this.

## Cleaning up

At the end of the workshop:

```bash
./scripts/destroy.sh
```

This deletes everything `setup.sh` created — including data-plane objects (such as a
deployed Hosted Agent) that Terraform does not manage — but never deletes the resource
group itself. After `terraform destroy` runs, the script independently verifies (via
`az resource list`) that no workshop-tagged/named resource remains in the resource
group. Local Terraform state and `.workshop/` context are only removed once that
verification passes; if it finds leftover resources, or the check itself fails, the
script exits non-zero and leaves all local state in place so you (or an administrator)
can investigate before retrying. See [costs and cleanup](../costs-and-cleanup.md) for
the exact order and what to do if it reports a failure.

## See also

- [Architecture](../architecture.md)
- [Feature support matrix](../feature-support-matrix.md)
- [Costs and cleanup](../costs-and-cleanup.md)

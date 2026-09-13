# Shared workshop container

Codespaces and local **Dev Containers: Reopen in Container** use this configuration.
No host Python environment, credential directory, or Docker socket is mounted.
No Jupyter server is started and ports are not automatically forwarded.

| Runtime | Interpreter exported to terminals and notebooks | Kernel |
| --- | --- | --- |
| Python 3.12 | `WORKSHOP_MANAGEMENT_PYTHON=/home/vscode/.venvs/foundry-workshop/bin/python` | Python (Foundry Workshop) |
| Python 3.13 | `WORKSHOP_HOSTED_PYTHON=/home/vscode/.venvs/foundry-hosted-agent/bin/python` | Python (Foundry Hosted Agent) |

These variables are defined in `containerEnv`, so `devcontainer exec` inherits
them as well as VS Code; they do not depend on a terminal activation script.

Post-create runs `python3.12 scripts/setup_dev_environment.py`. It verifies **both**
`python3.12` and `python3.13`, installs the separate dependency sets and development
tools, runs `pip check`, verifies the SDK versions, and registers both user kernels.
It does not sign in or operate on Azure resources. Retry that command after a
failed dependency download; an owned partial venv can be completed. Unowned or
incompatible environments/kernels are rejected, never deleted or overwritten.
To use different venv locations, explicitly set the two variables to absolute
paths ending in the same `<kernel-name>/bin/python`, outside the checkout.

The [official Python image manifest](https://github.com/devcontainers/images/blob/main/src/python/manifest.json)
publishes `3.2.3-3.13-bookworm` for Linux amd64 and arm64. The
[Python Feature](https://github.com/devcontainers/features/blob/main/src/python/devcontainer-feature.json)
adds pinned Python 3.12 under `/usr/local/python`, leaving the image's
`/usr/local/bin/python3.13` intact. Only declared Feature options are used.
The image, Features, Azure CLI, Graphviz and development tools use explicit
release versions. Python dependency ranges in the existing project manifests
remain their source of truth; this is not a transitive dependency lockfile.
Update release pins together and test a complete container build on both
architectures before publishing a workshop revision.

After personal sign-in in the container terminal, run `notebooks/00-setup.ipynb`
using the management kernel. Select the Hosted kernel for Labs 7 and 8.

# Lab 0 — 全体像と進め方（5分）

## ゴール

架空の Contoso 社向けに、規程を検索し、費用を計算し、品質を評価できる Agent を作ります。
すべて合成データで、実際の予約・申請・承認・精算は行いません。

## 使う場所

| 場所 | 用途 |
|---|---|
| Azure Portal | workload resource group の作成・削除、Lab 7 の Compute |
| Azure Cloud Shell Bash | Lab 1 の provisioning、1 回の ZIP download、Lab 9 cleanup |
| Microsoft Foundry Portal | Labs 2〜6、Hosted Agent、trace |
| 手元の PC | ZIP 展開、Lab 4 `portal-assets` |
| Azure ML Studio | Labs 7〜8 の Notebook |

Cloud Shell は provisioning / download 専用です。Notebook、Jupyter、web preview は
使いません。

## 学習の流れ

| Lab | 到達点 |
|---|---|
| [Lab 1](01-setup.md) | Terraform resources を作成し、bundle を 1 回 download |
| [Lab 2](02-prompt-agent.md) | Prompt Agent から 1 index を検索 |
| [Lab 3](03-rag-foundry-iq.md) | Foundry IQ で複数規程を横断 |
| [Lab 4](04-tools-toolbox.md) | Toolbox / OpenAPI / Skills を公開 |
| [Lab 5](05-evaluation.md) | 合成 dataset で評価 |
| [Lab 6](06-optimization.md) | baseline と candidate を比較 |
| [Lab 7](07-agent-framework-harness.md) | Azure ML で plain / Harness Agent を比較 |
| [Lab 8](08-hosted-multi-agent.md) | sequential workflow を Hosted Agent 化 |
| [Lab 9](09-observability-cleanup.md) | trace 比較と完全 cleanup |

開始前に [参加条件](../docs/participant/prerequisites.md) と
[Cloud Shell guide](../docs/participant/environments/cloud-shell.md) を確認します。

> [!WARNING]
> Azure resources と model operations は課金対象です。実在データ、secret、device code、
> Terraform state を共有・撮影しません。ブラウザーを閉じても resources は残ります。

## 次の Lab

[Lab 1 — Cloud Shell provisioning](01-setup.md)

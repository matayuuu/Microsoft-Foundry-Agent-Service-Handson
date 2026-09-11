# Lab 0 — 全体像と進め方（5分）

## ゴール

架空の Contoso 社向けに、規程を検索し、費用を計算し、品質を評価できる Agent を作ります。
すべて合成データで、実際の予約・申請・承認・精算は行いません。

## 使う場所

| 場所 | 用途 |
|---|---|
| Azure Portal | 専用 RG の手動作成、custom template、private ZIP download、RG 削除 |
| Deployment Scripts | Azure 側で初期化・検証・教材作成を自動実行 |
| Microsoft Foundry Portal | Labs 2〜6、Hosted Agent の確認、trace |
| 手元の PC | ZIP 展開、Lab 4 `portal-assets`、安全な成果物の保存 |
| Azure Machine Learning Studio | Lab 7 の Compute 作成、Labs 7〜8 の Notebook、Compute Stop / Delete |

最初に **Resource groups > Create** で専用 RG を 1 個手動作成します。完了後に
**Deploy a custom template** を開き、作成済み RG を選びます。初期化の成功後、
Storage browser で **Microsoft Entra user account** を使い、private container
`workshop-files` の ZIP を PC へ 1 回 download します。Compute はまだ作りません。

## 学習の流れ

![学習の流れ](../docs/images/workshop-learning-flow.svg)

| Lab | 到達点 |
|---|---|
| [Lab 1](01-setup.md) | RG 手動作成 → custom template / bootstrap → private ZIP を取得・展開 |
| [Lab 2](02-prompt-agent.md) | Prompt Agent から 1 index を検索 |
| [Lab 3](03-rag-foundry-iq.md) | Foundry IQ で複数規程を横断 |
| [Lab 4](04-tools-toolbox.md) | Toolbox / OpenAPI / Skills を公開 |
| [Lab 5](05-evaluation.md) | 合成 dataset で評価 |
| [Lab 6](06-optimization.md) | baseline と candidate を比較 |
| [Lab 7](07-agent-framework-harness.md) | Compute / kernels 準備、plain / Harness Agent を比較 |
| [Lab 8](08-hosted-multi-agent.md) | sequential workflow を Hosted Agent 化 |
| [Lab 9](09-observability-cleanup.md) | Export → Hosted cleanup → Compute Stop / Delete → RG 削除確認 |

開始前に [参加条件](../docs/participant/prerequisites.md) と
[Custom template guide](../docs/participant/environments/custom-template.md) を確認します。
Lab 1 の新経路の所要時間は未計測です。

> [!WARNING]
> Azure resources と model operations は課金対象です。実在データ、secret、device code、
> 認証情報を共有・撮影しません。ブラウザーを閉じても resources は残ります。
> deployment history の削除は resource の削除ではありません。

## 次の Lab

[Lab 1 — Custom template と教材 download](01-setup.md)

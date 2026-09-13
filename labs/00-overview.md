# Lab 0 — 全体像と進め方（5分）

## ゴール

架空の Contoso 社向けに、規程を検索し、費用を計算し、品質を評価できる Agent を作ります。
すべて合成データで、実際の予約・申請・承認・精算は行いません。

## 使う場所

| 場所 | 用途 |
|---|---|
| Azure Portal | 専用 RG の手動作成、custom template、初期化の確認、RG 削除 |
| Deployment Scripts | Azure 側で Search・評価データを準備し、検証 |
| Microsoft Foundry Portal | Labs 2〜6、Hosted Agent の確認、trace |
| GitHub | 共通 Skill ZIP・OpenAPI、Notebook・Python コード |
| Codespaces / ローカル Dev Container | Labs 7〜8 の Notebook。同じ環境設定を利用 |

最初に **Resource groups > Create** で専用 RG を 1 個手動作成します。完了後に
**Deploy a custom template** を開き、Subscription と作成済み RG を選びます。
その他の既定値は変えず、初期化・検証の成功を確認してから Foundry Portal へ進みます。

## 学習の流れ

![学習の流れ](../docs/images/workshop-learning-flow.svg)

| Lab | 到達点 |
|---|---|
| [Lab 1](01-setup.md) | RG 手動作成 → custom template → 初期化・検証の成功を確認 |
| [Lab 2](02-prompt-agent.md) | Prompt Agent から 1 index を検索 |
| [Lab 3](03-rag-foundry-iq.md) | Foundry IQ で複数規程を横断 |
| [Lab 4](04-tools-toolbox.md) | Toolbox / OpenAPI / Skills を公開 |
| [Lab 5](05-evaluation.md) | 合成 dataset で評価 |
| [Lab 6](06-optimization.md) | baseline と candidate を比較 |
| [Lab 7](07-agent-framework-harness.md) | Codespaces / 初回設定、plain / Harness Agent を比較 |
| [Lab 8](08-hosted-multi-agent.md) | sequential workflow を Hosted Agent 化 |
| [Lab 9](09-observability-cleanup.md) | 保存 → Hosted cleanup → Codespace 停止・削除 → RG 削除確認 |

開始前に [参加条件](../docs/participant/prerequisites.md) と
[Custom template guide](../docs/participant/environments/custom-template.md) を確認します。
安全上の注意は [README](../README.md)、料金と終了手順は
[費用と cleanup](../docs/costs-and-cleanup.md)にまとめています。

## 次の Lab

[Lab 1 — Custom template と初期化](01-setup.md)

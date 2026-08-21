# Microsoft Foundry Agent Service Hands-on

Microsoft Foundry Agent Service の主要機能を、1つの「Contoso 社内出張・経費支援」
シナリオで体験する3時間50分のハンズオンです。

参加者は GitHub Codespaces と Microsoft Foundry（new）を使い、環境構築、Prompt
Agent、Azure AI Search/Foundry IQ、Tools/Toolbox、評価、Agent Optimizer、
Microsoft Agent Framework のマルチエージェント Hosted Agent、観測と
クリーンアップまでを通して実施します。

## 参加条件

- GitHub アカウントと Codespaces を利用できること
- Azure CLI の `az login` が可能であること
- 事前に用意された Azure subscription と既存 resource group があること
- 参加者がその resource group の **Owner** であること
- subscription 管理者が [管理者向け前提条件](docs/admin/prerequisites.md) を完了していること

resource provider 登録と model quota は subscription scope のため、resource group
Owner だけでは準備できません。参加者が subscription を操作できない構成も正式に
サポートし、管理者用と参加者用の preflight を分離します。

## Quick start

subscription 管理者または代表者は、参加者へ RG を配布する前に aggregate quota を
確認します。共通 subscription に20環境を作る例:

```bash
./scripts/admin-preflight.sh \
  --subscription "<subscription-id>" \
  --participant-count 20
```

1. この repository から Codespace を作成します。
2. Codespace の terminal で Azure にサインインします。
3. 割り当てられた subscription/resource group を指定して setup を実行します。

```bash
az login --use-device-code

./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>"
```

構築後に表示される Microsoft Foundry portal link を開き、
[Lab 0](labs/00-overview.md) から順に進めます。

Travel Ops API の公開 image は既定の `v1.0.2` tag から immutable digest へ自動解決
されます。maintainer がまだ image を公開していない場合、setup は Terraform 実行前に
停止し、`.github/workflows/publish-travel-api.yml` を使った公開手順を表示します。

終了時は Hosted Agent などの data-plane object を含めて削除します。resource group
自体は削除しません。

```bash
./scripts/destroy.sh
```

## Agenda

| 時間 | 内容 |
|---|---|
| 00:00-00:10 | オープニングと全体アーキテクチャ |
| 00:10-00:30 | Codespaces と Terraform によるワンコマンド構築 |
| 00:30-00:50 | Prompt Agent |
| 00:50-01:25 | Azure AI Search と Foundry IQ |
| 01:25-01:35 | 休憩 |
| 01:35-02:10 | Tools、Tool Catalog、Toolbox |
| 02:10-02:35 | Agent evaluation |
| 02:35-02:55 | Agent Optimizer と version 比較 |
| 02:55-03:40 | Agent Framework workflow の Hosted Agent 配布 |
| 03:40-03:50 | Observability、governance、cleanup |

## 設計方針

- **Portal-first**: Portal にない操作だけ Foundry Toolkit/Python SDK を使用します。
- **Existing RG only**: Terraform は指定された resource group の外へ書き込みません。
- **Keyless**: runtime access は Microsoft Entra ID/RBAC を使用します。
- **Repeatable**: setup/bootstrap/destroy は再実行可能にします。
- **Synthetic data**: 実データや個人情報を使用しません。
- **Current path**: 2026年12月1日に廃止予定の Workflow Designer ではなく、
  Microsoft Agent Framework をマルチエージェント本編に使用します。

詳細は [architecture](docs/architecture.md) と
[feature support matrix](docs/feature-support-matrix.md) を参照してください。

## Repository validation

root SDK/Travel API と Hosted Agent は `azure-ai-projects` の互換範囲が異なるため、
別の Python 3.13 virtual environment を使います。Codespaces では自動作成されます。

```bash
make install
make install-hosted
make validate
```

## Core と optional の境界

Fabric IQ と Work IQ は追加ライセンス、公開済み Fabric item、Entra tenant 管理者同意
などが必要なため、本編ではなく選択ラボです。Private Link/VNet、ACR container deploy、
A2A、Routines、Teams/Microsoft 365 publish、CI/CD も本編外で扱います。

- [選択ラボ index](labs/optional/README.md)
- [講師用 runbook](instructor/README.md)

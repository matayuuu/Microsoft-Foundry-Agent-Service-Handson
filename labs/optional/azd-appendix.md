# 付録 — azd（Azure Developer CLI）で Hosted Agent をデプロイする

## この文書の位置づけ

本編 [Lab 7](../07-hosted-multi-agent.md) の §5「azd（任意サイドバー）」で触れているとおり、
本編の core は `scripts/deploy_hosted_agent.py` による **source-code remote build** のみで
完結し、`azd` は一切使いません。この付録は、`azd` の Foundry 拡張機能を使った代替デプロイ
経路を、**本編とは別の認証方式が必要になる**ことを明示したうえで説明します。

> [!IMPORTANT]
> **`azd auth login` は `az login` とは別の認証です。** 本編は AGENTS.md の非交渉制約により
> `az login` のみで完結するように設計されています。この付録の手順を試す場合、`az login` に
> 加えて **`azd auth login` を別途実行する必要があります**。これは本編の設計方針を変更する
> ものではなく、azd という別のツールを使う場合にのみ必要な追加手順です。

## 1. 前提条件

| 項目 | 要件 |
|---|---|
| Azure Developer CLI (azd) | **1.25.2 以上** |
| ランタイム | Python 3.10 以上、または .NET 8 以上（Foundry 拡張機能の実行に必要） |
| Azure ロール（RG スコープ） | **Contributor**（リソースの provision）。新しい Foundry project を作成する場合は追加で **Foundry Owner** |
| 認証 | `azd auth login`（`az login` とは別に必要） |

## 2. Foundry 拡張機能をインストールする

```bash
azd version   # 1.25.2 以上であることを確認
azd auth login

azd extension install microsoft.foundry
```

`microsoft.foundry` はメタパッケージで、次の個別拡張機能をまとめてインストールします。

| 拡張機能 | 用途 |
|---|---|
| `azure.ai.agents` | agent の作成・デプロイ |
| `azure.ai.connections` | Foundry connection（ACR、Fabric、Work IQ など）の管理 |
| `azure.ai.inspector` | ローカルデバッグ・トレース閲覧 |
| `azure.ai.projects` | Foundry project の管理 |
| `azure.ai.routines` | Routines（preview）の管理 — [A2A・Routines・Publish](a2a-routines-publish.md) 参照 |
| `azure.ai.skills` | Skills の管理 — [Advanced Hosted Agent](advanced-hosted-agent.md) 参照 |

## 3. プロジェクトを初期化する

```bash
cd src/hosted-agent
azd ai agent init
```

このコマンドは対話式に次を確認します。

- 使用する既存の Foundry project（`.workshop/context.json` に記録された本編の project を
  指定することも、新しいものを作ることもできます）。
- コンテナイメージの push 先とする ACR（未指定の場合、`azd provision` がプロジェクト専用の
  新しい ACR を作成します — 詳細は [Advanced Hosted Agent](advanced-hosted-agent.md) 参照）。

`azd ai agent init` は `azure.yaml` と `next-steps.md`（azd 標準のプロジェクトメタデータ）を
生成します。本編の `.workshop/context.json` とは別のファイルであり、本編のスクリプトはこの
ファイルを読み書きしません。

## 4. デプロイする

```bash
azd ai agent deploy
```

このコマンドは、コンテナイメージのビルド・ACR への push・Foundry へのバージョン登録・
agent 用 Microsoft Entra identity の作成・必要な RBAC 割り当てまでを一括で行います。個別に
ステップを分けたい場合は、`azd ai agent build` → `azd ai agent push` → `azd ai agent deploy`
のように分割実行することもできます（詳細は [Advanced Hosted Agent](advanced-hosted-agent.md)
参照）。

## 5. 本編との違い（まとめ）

| 観点 | 本編 core（`scripts/deploy_hosted_agent.py`） | この付録（`azd ai agent`） |
|---|---|---|
| 認証 | `az login` のみ | `az login` + `azd auth login` |
| デプロイ方式 | source zip + `REMOTE_BUILD`（Foundry がサーバー側でビルド） | ローカルでコンテナビルド → ACR へ push |
| 追加インフラ | 不要（本編 Terraform の範囲内） | ACR（既存のものを使うか、`azd provision` が新規作成） |
| 対象読者 | 全参加者（本編必須） | azd に慣れた参加者向けの任意経路 |
| べき等性・cleanup | `scripts/delete_hosted_agent.py`、`destroy.sh` の対象 | azd 独自の state・ACR イメージは別途 cleanup が必要（[Advanced Hosted Agent](advanced-hosted-agent.md) §7 参照） |

## 6. この付録を使わない場合

本編の Lab 7 は `azd` を一切使わずに完結します。この付録は完全に任意であり、実施しなくても
ワークショップの他の部分には影響しません。

## 公式参照

- [Install the Azure Developer CLI Foundry extensions](https://learn.microsoft.com/azure/foundry/agents/how-to/install-cli-foundry-extensions)
- [Deploy a hosted agent with a private Azure Container Registry](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent-private-azure-container-registry)
- [Azure Developer CLI overview](https://learn.microsoft.com/azure/developer/azure-developer-cli/overview)

## 関連リンク

- [選択ラボ index](README.md)
- [Advanced Hosted Agent](advanced-hosted-agent.md)
- [本編 Lab 7 — Agent Framework workflow の Hosted Agent 配布](../07-hosted-multi-agent.md)

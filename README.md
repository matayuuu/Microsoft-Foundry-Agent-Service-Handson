**日本語** | [English](README.en.md)

# Microsoft Foundry Agent Service Hands-on

架空の「Contoso 社内出張・経費支援」を題材に、Prompt Agent、Foundry IQ、
Toolbox と Skills、評価、最適化、Hosted Agent、観測までを体験するハンズオンです。
すべてのデータは合成データです。

![ハンズオンの構成](docs/images/workshop-architecture.svg)

[構成図を Excalidraw で編集する](docs/diagrams/workshop-architecture.excalidraw)

## 参加条件

- GitHub Codespaces を利用できる GitHub account
- `az login` が可能な Azure account
- 管理者から割り当てられた subscription と**既存** resource group
- その resource group に対する **Owner** role

詳しい確認項目は
[参加者向け前提条件](docs/participant/prerequisites.md)を参照してください。

## ハンズオンを始める

**[Lab 0 — 全体像と進め方](labs/00-overview.md) から開始してください。**
環境構築のコマンドは Lab 1 で案内します。

## Agenda

| Lab | 内容 | 所要時間（目安） |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | 全体像と進め方 | 5分 |
| [Lab 1](labs/01-setup.md) | Codespaces と Terraform による環境構築 | 20分 |
| [Lab 2](labs/02-prompt-agent.md) | Prompt Agent の作成 | 10分 |
| [Lab 3](labs/03-rag-foundry-iq.md) | Azure AI Search と Foundry IQ | 35分 |
| — | 休憩 | 10分 |
| [Lab 4](labs/04-tools-toolbox.md) | Portal で Toolbox と Skills を作成 | 30分 |
| [Lab 5](labs/05-evaluation.md) | Portal で Agent evaluation | 15分 |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20分 |
| [Lab 7](labs/07-hosted-multi-agent.md) | Agent Framework の Hosted Agent | 40分 |
| [Lab 8](labs/08-observability-cleanup.md) | Observability と cleanup | 10分 |

## 困ったとき

- 操作や実行エラー:
  [参加者向けトラブルシューティング](docs/participant/troubleshooting.md)
- 管理者側の quota / provider:
  [管理者向け前提条件](docs/admin/prerequisites.md)
- 追加機能:
  [Optional labs](labs/optional/README.md)

> [!WARNING]
> Azure resources は停止するまで課金されます。ハンズオン終了時は必ず
> [Lab 8](labs/08-observability-cleanup.md) の cleanup を実行してください。

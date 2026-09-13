**日本語** | [English](README.en.md)

# Microsoft Foundry Agent Service Hands-on

架空の Contoso 社の出張・経費アシスタントを作る、10 の演習です。
検索、ツール、評価、最適化から Hosted Agent までを体験します。

[**Lab 0 から始める**](labs/00-overview.md) ·
[参加条件](docs/participant/prerequisites.md) ·
[準備ガイド](docs/participant/environments/custom-template.md)

## 進め方

1. **Lab 1**：Azure Portal で専用 RG を **1 個手動作成してから**、
   その RG に管理者指定のテンプレートを実行します。**Subscription と Resource group だけ**を
   選び、その他は既定値のまま、データ投入・検証の成功を待ちます。
2. **Labs 2〜6**：Microsoft Foundry Portal でエージェントを作ります。
   Lab 4 の共通 Skill ZIP と OpenAPI は GitHub から取得します。
3. **Labs 7〜8**：[GitHub Codespaces](docs/participant/environments/codespaces.md) で
   Azure にサインインし、初回 Notebook に subscription ID と RG 名を入力します。
   [ローカルの Dev Container](docs/participant/environments/local-dev-container.md) でも同じ手順です。
4. **Lab 9**：成果物を保存し、Hosted Agent を削除、Codespace を停止・削除してから、
   自分の専用 RG を削除します。

Notebook・Python コードはリポジトリに揃っています。フォルダーの手動アップロードは不要です。
Codespaces のブラウザー経路では、PC への Docker・Python のインストールも不要です。

## 演習一覧

| Lab | 内容 | 目安 |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | 全体像と注意点 | 5分 |
| [Lab 1](labs/01-setup.md) | 環境作成と初期化の確認 | — |
| [Lab 2](labs/02-prompt-agent.md) | Prompt Agent と Azure AI Search | 20分 |
| [Lab 3](labs/03-rag-foundry-iq.md) | Foundry IQ | 25分 |
| — | 休憩 | 10分 |
| [Lab 4](labs/04-tools-toolbox.md) | Toolbox、OpenAPI、Skills、Tool Search | 30分 |
| [Lab 5](labs/05-evaluation.md) | エージェントの評価 | 15分 |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20分 |
| [Lab 7](labs/07-agent-framework-harness.md) | Codespaces の準備、Agent Framework、Harness Agent | 50分 |
| [Lab 8](labs/08-hosted-multi-agent.md) | Hosted Agent のワークフロー | 30分 |
| [Lab 9](labs/09-observability-cleanup.md) | トレースの比較と片付け | 20分 |

[管理者の事前準備・モデル一覧](docs/admin/prerequisites.md) ·
[構成図](docs/architecture.md) ·
[困ったとき](docs/participant/troubleshooting.md)

> [!IMPORTANT]
> 合成データだけを使い、認証情報・トークンを共有・保存しないでください。
> Azure と Codespaces の利用には料金が発生する場合があります。
> 終了時は Lab 9 に従い、**自分の専用 RG だけ**を削除して、削除完了を確認します。

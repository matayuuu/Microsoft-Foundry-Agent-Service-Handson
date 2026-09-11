**日本語** | [English](README.en.md)

# Microsoft Foundry Agent Service Hands-on

架空の Contoso 社の出張・経費アシスタントを作る、10 の演習です。
検索、ツール、評価、最適化から Hosted Agent までを体験します。

[**Lab 0 から始める**](labs/00-overview.md) ·
[参加条件](docs/participant/prerequisites.md) ·
[準備ガイド](docs/participant/environments/custom-template.md)

## 進め方

1. **Lab 1**：Azure Portal で専用 RG を **1 個手動作成してから**、
   その RG に管理者指定のテンプレートを実行します。
   初期化の成功を待ち、非公開の教材 ZIP を **Microsoft Entra user account** で取得・展開します。
2. **Labs 2〜6**：Microsoft Foundry Portal でエージェントを作ります。
3. **Labs 7〜8**：[Azure ML の準備](docs/participant/environments/azure-ml.md)を行い、
   ノートブックを実行します。Compute は **Lab 7 の開始時だけ**作成します。
4. **Lab 9**：成果物を保存し、Hosted Agent、Compute、自分の RG の順に削除します。

## 演習一覧

| Lab | 内容 | 目安 |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | 全体像と注意点 | 5分 |
| [Lab 1](labs/01-setup.md) | 環境作成と教材のダウンロード | 未計測 |
| [Lab 2](labs/02-prompt-agent.md) | Prompt Agent と Azure AI Search | 20分 |
| [Lab 3](labs/03-rag-foundry-iq.md) | Foundry IQ | 25分 |
| — | 休憩 | 10分 |
| [Lab 4](labs/04-tools-toolbox.md) | Toolbox、OpenAPI、Skills、Tool Search | 30分 |
| [Lab 5](labs/05-evaluation.md) | エージェントの評価 | 15分 |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20分 |
| [Lab 7](labs/07-agent-framework-harness.md) | Azure ML の準備、Agent Framework、Harness Agent | 50分 |
| [Lab 8](labs/08-hosted-multi-agent.md) | Hosted Agent のワークフロー | 30分 |
| [Lab 9](labs/09-observability-cleanup.md) | トレースの比較と片付け | 20分 |

[管理者の事前準備・モデル一覧](docs/admin/prerequisites.md) ·
[構成図](docs/architecture.md) ·
[困ったとき](docs/participant/troubleshooting.md)

> [!IMPORTANT]
> 合成データだけを使い、認証情報を共有しないでください。Azure の利用には料金が発生します。
> 終了時は Lab 9 に従い、**自分の専用 RG だけ**を削除して、削除完了を確認します。

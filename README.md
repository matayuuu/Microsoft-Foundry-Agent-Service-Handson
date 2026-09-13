**日本語** | [English](README.en.md)

# Microsoft Foundry Agent Service Hands-on

架空の Contoso 社の出張・経費アシスタントを作る、9 つの演習です。
検索、ツール、評価、最適化から Hosted Agent までを体験します。

[**Lab 1 から始める**](labs/01-setup.md) ·
[参加条件](docs/participant/prerequisites.md) ·
[準備ガイド](docs/participant/environments/custom-template.md)


![Contoso 出張・経費アシスタントの Azure 構成図。専用 RG 内の Microsoft Foundry、Azure AI Search、Container Apps、監視基盤と、Portal・Dev Container の接続を示す。](docs/images/azure-architecture.svg)

[拡大表示（SVG）](docs/images/azure-architecture.svg) ·
[編集用 draw.io](docs/diagrams/azure-architecture.drawio) ·
[構成と通信経路の詳細](docs/architecture.md)


## 進め方

1. **Lab 1**：Azure Portal で、この演習専用のリソース グループ（RG）を 1 つ作成します。
   次に、管理者から案内されたテンプレートを使い、作成した RG に環境をデプロイします。
2. **Labs 2〜6**：Microsoft Foundry Portal でエージェントを作り、
   Foundry IQ や Toolbox を追加して機能を強化します。さらに、評価と最適化を通じて、
   エージェントの精度を継続的に改善するサイクルを学びます。
3. **Labs 7〜8**：[GitHub Codespaces](docs/participant/environments/codespaces.md) または
   [ローカルの Dev Container](docs/participant/environments/local-dev-container.md) で、Agent Framework を使ってエージェントをコードから作ります。
   Harness Agent と複数のエージェントが連携するワークフローを構築し、Hosted Agent としてデプロイします。
4. **Lab 9**：Prompt Agent と Hosted Agent のトレースを比較し、処理の流れや性能の違いを確認します。
   最後に成果物を保存し、Hosted Agent と利用した開発環境を片付けてから、専用 RG を削除します。

Notebook・Python コードはリポジトリに揃っています。フォルダーの手動アップロードは不要です。
Codespaces のブラウザー経路では、PC への Docker・Python のインストールも不要です。

## 演習一覧

| Lab | 内容 | 目安 |
|---|---|---:|
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

# 機能対応表

この表は **新しい** Microsoft Foundry を対象としています。Toolbox の UI に関する項目は、
参加者から提供されたポータルのスクリーンショットに基づき **2026-09-05** に更新しました。
Toolbox Skills の実行経路は公式 Learn と実環境の Trace に基づき **2026-09-08** に確認しました。
Agent Optimizer のモデル互換性は **2026-09-09** に確認しました。
その他の項目は 2026-09-01 時点の情報を維持しています。プレビュー機能の画面やポータルのラベルは
変更される場合があります。現在、Toolbox の公式記事は、確認済みの Web ポータルの操作よりも
SDK/Toolkit の手順を詳しく説明しています。ポータルの列がないことを、
UI が利用できない根拠として解釈しないでください。

| 機能 | ポータル | Toolkit | Python SDK/REST | 提供状況とハンズオンでの扱い |
|---|---:|---:|---:|---|
| Prompt Agent の作成・バージョン管理・テスト | 対応 | 対応 | 対応 | 必須。ポータル中心で実施 |
| エージェントへの Azure AI Search の接続 | 対応 | 対応 | 対応 | 必須。インデックスと接続は事前に構築済み |
| Foundry IQ ナレッジベースの作成 | 対応 | 該当なし | 対応 | 必須。ポータルのエージェント型検索は引き続きプレビュー |
| Toolbox の作成 | 対応を確認済み | 対応 | 対応 | 必須。Web ポータルの Build > Tools > Create toolbox |
| Toolbox のバージョンライフサイクル全体の管理 | Publish は確認済み。その他の操作は環境により異なる | 一部対応 | 対応 | SDK による代替手順は、既存の Skills、ツール、メタデータ、ガードレールを保持 |
| Web Search | Toolbox への追加を確認済み | 対応 | 対応 | 必須。Lab 4 で追加し、明示された現在の公開旅行情報だけに使用 |
| Code Interpreter | Toolbox への追加を確認済み | 対応 | 対応 | 必須。Lab 4 で追加し、API 結果の数値比較・表整形に使用 |
| Toolbox での OpenAPI 利用 | 対応を確認済み | UI の対応が案内されているが、Learn の表とは差異あり | 対応 | 必須。Add tool > Custom > OpenAPI tool で、稼働中の API の OpenAPI 3.1 定義を貼り付け |
| Skills の作成・アップロード・接続 | 対応を確認済み | Skills の記事に記載あり | 対応 | 必須。Add skill > Upload skill を使用し、ハンズオンの 2 つの Skills を両方含める |
| Toolbox Skills の利用 | Prompt Agent は未対応 | クライアントに依存 | Skill の管理・添付に対応。実行には MCP Resources 対応 client が必要 | プレビュー。`resources/list` / `resources/read` または `load_skill` で利用を確認する |
| Tool Search | Toolbox の On/Off 設定を確認済み | 対応 | 対応 | 必須。Lab 4 で `tool_search` → `call_tool` → 実 tool を Trace で確認 |
| エージェント評価の送信 | 対応 | 該当なし | 対応 | 必須手順では、準備済みの合成データセットを使用してポータルで実施 |
| 評価結果の表示 | 対応 | 対応 | 対応 | 必須。ポータルで実施 |
| Prompt Agent Optimizer | UI は対応 | 該当なし | サービスが管理 | プレビュー。対応モデルの `gpt-5.5` を評価・最適化に使用 |
| Hosted Agent Optimizer | 非対応 | 対応 | azd/SDK 連携 | 任意 |
| Agent Framework の Agent / Harness Agent 開発 | 非対応 | 対応 | コード | 必須。Lab 7 で Foundry IQ・Toolbox Tools / Skills を再利用 |
| Agent Framework Hosted workflow の開発 | 非対応 | 対応 | コード | 必須。Lab 8 で intake / policy / reviewer の通常 Agent を sequential workflow にする |
| Hosted Agent のソースデプロイ | 非対応 | 対応 | 対応 | 必須手順では、認証を `az login` のみに統一するため SDK を使用 |
| Hosted Agent Playground | 対応 | 対応 | 対応 | 必須。バージョンがアクティブになった後にポータルで実施 |
| Prompt Agent / Hosted Agent のトレース | 対応 | 対応 | OpenTelemetry | 必須。Application Insights は接続済み |
| Workflow Designer | 対応 | 該当なし | 該当なし | 2026-12-01 に廃止予定。比較のみ |
| Fabric IQ | エージェント設定 | 対応 | 対応 | 任意。ライセンス・容量・権限が必要 |
| Work IQ | エージェント設定 | 対応 | 対応 | 任意。Copilot Credits と管理者の同意が必要 |

## 必須手順の前提条件

| 項目 | 要件 |
|---|---|
| リージョン | Japan East（既定）、Australia East、Central US。3つとも Agentic retrieval、Semantic ranker、Serverless preview 対応 |
| Azure AI Search pricing model | Dedicated Basic（既定）。3 region で容量不足時は `--ai-search-serverless` で Serverless Developer preview |
| Prompt / Hosted Agent、Foundry IQ | 共有の `gpt-5.6-luna` デプロイ。`primary_model_deployment_name` |
| Lab 5 の設定可能な評価、Lab 6 の Agent Optimizer | 共有のoptional `gpt-5.5` デプロイ。`evaluation_model_deployment_name` / `optimizer_model_deployment_name`。未デプロイ時は Labs 5 / 6 をスキップ |
| 埋め込み | `text-embedding-3-small`、デプロイ名 `embedding` |
| Search | Azure AI Search Basic 以上 |
| ID | 参加者がworkload用RGを作成でき、作成した空のRGでOwnerであること。FoundryのロールはそのRG内で付与 |
| 可観測性 | プロジェクトに接続されたワークスペースベースの Application Insights |
| 開発 | Codespaces または Azure Cloud Shell Bash + JupyterLab。Python 3.13、2つの `.venv` / kernels、Azure CLI 認証を共用 |
| Cloud Shell の永続化 | 初回UIが自動作成するユーザー専用RG / Storage / share、または管理者割当の既存Storageと、再起動後のHOME保持確認が必須。Terraform管理外 |
| Cloud Shell の開催条件 | tenant あたり既定20同時ユーザー。必要時は管理者が Support へ事前相談。HTTPS / WSS と配布先への通信を確認 |

実行環境の選択は [Lab 1](../labs/01-setup.md) の準備時だけです。
Lab 2〜9 の Portal 操作と既存の Lab 7 / 8 Notebook は共通で、
Cloud Shell 向けに Notebook を CLI 演習へ置き換えません。
準備・再接続・終了は [Codespaces](participant/environments/codespaces.md) /
[Cloud Shell](participant/environments/cloud-shell.md) を参照してください。
Cloud Shell 固有の制約は2026-09-09取得の公式資料に基づきます。
採用する tenant / browser での Jupyter、認証付き HTTP kernel relay、Graphviz、永続化の検証は
[講師のリハーサル](../instructor/runbook.md)で行い、既存 Portal 機能の確認日と混同しません。

## 提供状況に関する重要事項

- モデルの役割は、**2026-09-06** に新しいポータルで確認しました。必須構成ではデプロイを
  厳密に 3 つ作成します。チャットモデルのバージョンと同一 SKU のクォータ確認情報は、
  事前チェックで取得し、固定値を使用したりモデル名から推測したりしません。
  ナレッジベースでは Luna、Optimizerの2つのモデル選択ではGPT-5.5を選択します。
  これらは確認したポータルでの観察結果であり、すべての Search API のモデル対応について
  一般化した主張ではありません。
- GPT-5.5 は Lab 5 のルーブリック / 設定可能な LLM 評価と、Lab 6 の
  Optimizer の2つのモデル選択に使用します。Violence など、
  サービスが管理する評価器は
  それぞれ固有のモデルを引き続き使用します。
- Foundry Tool Catalog と Toolboxes は一般提供されていますが、個々のツールは
  プレビューの場合があります。
- Skills と Toolbox の Skill 検出はプレビューです。Skill の参照は `tools[]` とは別であり、
  互換性のある MCP Resources の利用機能が必要です。Portal の Prompt Agent と Python SDK の
  `PromptAgentDefinition` には Toolbox Skill の runtime reference がありません。SDK から同じ
  Prompt Agent を呼び出しても `resources/read` は行われません。Skill 本文を Agent instructions
  に複製する方式も Toolbox 経由の利用ではありません。Lab 7 の Harness Agent で
  checked-in factory の Skill provider を確認します。Lab 8 の通常 Agent workflow は
  token 消費を抑えるため Toolbox Skills を使用しません。
- Lab 4 には、確認済みの Web ポータルの操作手順をスクリーンショット付きで記載しています。
  ローカルの準備では、稼働中の API の OpenAPI 定義と Skill ZIP をエクスポートするだけで、
  リモートのオブジェクトは作成しません。
- Toolkit のリリースノートでは、Toolbox 内の OpenAPI カスタムツールと Skills の対応が
  告知されています。一方、Learn の Toolbox の表では、これらの Toolkit 項目の一部が
  依然として利用不可と記載されています。その表から Web ポータルの対応を推測するのではなく、
  必須ラボに記載された確認済みのポータル手順に従ってください。
- エージェント型検索の Microsoft Foundry ポータルおよび Azure portal の操作経路は、
  新しい Search REST API 操作が一般提供されている場合でも、プレビューとして提供されます。
- Agent Optimizer はプレビューであり、評価モデルと、対応する最適化モデルの両方を使用します。
  2026-09-09 時点の公式対応一覧に含まれる `gpt-5.5` を両方に使用します。
- Agent Framework で独自のオーケストレーションを実装する場合、Hosted Agent と
  ソースコードのリモートビルドがサポートされる手順です。
- Foundry Workflow Designer は 2026-12-01 に廃止予定です。新しくオーケストレーションを
  実装する場合は、Microsoft Agent Framework を使用してください。

## 公式リファレンス

- [Foundry Agent Service のツールの種類](https://learn.microsoft.com/azure/foundry/agents/concepts/tool-catalog)
- [Toolbox の作成と管理](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox)
- [Foundry エージェントでの Skills の使用（プレビュー）](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills)
- [確認済みのポータル手順とスクリーンショット](../labs/04-tools-toolbox.md)
- [Foundry Toolkit のリリースノート](https://github.com/microsoft/foundry-dev-tools/blob/6bf72ba71785202fe2d972a4b564a6fbaeb5db0e/WHATS_NEW.md)
- [Foundry IQ とは](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq)
- [エージェント型検索の概要](https://learn.microsoft.com/azure/search/agentic-retrieval-overview)
- [ナレッジベースのクエリ計画モデルと API の対応状況](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
- [ルーブリック用の LLM 判定モデルの選択](https://learn.microsoft.com/azure/foundry/concepts/evaluation-evaluators/rubric-evaluators#choose-an-llm-judge-model)
- [AI エージェントの評価](https://learn.microsoft.com/azure/foundry/observability/how-to/evaluate-agent)
- [Agent Optimizer の概要](https://learn.microsoft.com/azure/foundry/agents/concepts/agent-optimizer-overview)
- [Hosted Agent](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents)
- [Foundry でのワークフローの構築](https://learn.microsoft.com/azure/foundry/agents/concepts/workflow)
- [Fabric IQ ツール](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq)
- [Work IQ ツール](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq)

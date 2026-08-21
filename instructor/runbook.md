# 進行台本（runbook）— 3 時間 50 分アジェンダ

対象読者: このハンズオンを進行する講師。参加者には配布しません。

## 0. 事前準備（イベントの数日前〜前日）

### 0.1 subscription 管理者との調整

- [docs/admin/prerequisites.md](../docs/admin/prerequisites.md) を subscription 管理者に
  共有し、次を確認してもらいます。
  1. `./scripts/admin-preflight.sh --subscription "<subscription-id>"`（既定は読み取り専用）
     を実行し、6 つの resource provider（`Microsoft.CognitiveServices`、
     `Microsoft.Search`、`Microsoft.Storage`、`Microsoft.Insights`、
     `Microsoft.OperationalInsights`、`Microsoft.App`）がすべての対象 region
     （`eastus2`、`swedencentral`）で `Registered` であること。
  2. 想定参加者・チーム数に対して `gpt-4.1`（40K TPM/team）、`gpt-5` 系（20K TPM/team）、
     `text-embedding-3-small`（40K TPM/team）の model quota/capacity が両 region の
     少なくとも一方で足りていること。
  3. 未登録の provider がある場合のみ `--apply` を実行してもらう（quota・policy・
     resource group・role assignment は一切変更しない設計です）。
- 各参加者（または参加チーム）に対して、既存 resource group を 1 つずつ用意し、
  参加者本人にその resource group の **Owner** ロールのみを付与してもらいます。
  subscription スコープの権限は参加者には一切付与しません。

### 0.2 講師自身のリハーサル（推奨: イベント前日までに 1 回）

- 自分用の resource group で `./scripts/preflight.sh` → `./scripts/setup.sh` を通し、
  `.workshop/context.json` が生成されることを確認します。
- Lab 5（評価）・Lab 6（Optimizer）・Lab 7（Hosted Agent デプロイ）を一度通しで
  実行し、リモートビルドや preview 機能の待ち時間の当日の目安を体感しておきます。
- [instructor/completed-run-assets/](completed-run-assets/README.md) の内容に目を通し、
  画面共有する場合にどこを見せるかを決めておきます。

### 0.3 当日開始前チェックリスト

- [ ] 参加者全員が GitHub Codespaces を起動できることを確認済み。
- [ ] 参加者全員が `az login --use-device-code` を試せる状態（会社ネットワークの
     デバイスコード認証ブロックがないか事前確認）。
- [ ] 画面共有用に、この runbook と `completed-run-assets/` を別ウィンドウで開いておく。
- [ ] タイマー（各区切りの時間管理）を用意する。

## 1. 当日の進行（[README のアジェンダ](../README.md#agenda)に対応）

各区切りは目安時間です。参加者の進捗にばらつきが出やすいのは Lab 3（Foundry IQ の
待ち時間）と Lab 7（リモートビルドの待ち時間）です。早く終わった参加者には、該当する
[選択ラボ](../labs/optional/README.md)の該当節（読むだけでも可）を勧めてください。

### 00:00–00:10 Lab 0 — オープニング

- **チェックポイント**: 全員が [labs/00-overview.md](../labs/00-overview.md) を開けている。
- **読み上げポイント**（データ境界）: 「本ハンズオンで扱う Contoso の規程・経費・旅程
  データはすべて合成データで、実在の人物・企業とは無関係です」。
- **読み上げポイント**（コスト）: 「今日作成するリソースは Azure AI Search Basic、
  model 推論・embedding・評価 judge・Agent Optimizer のトークン課金、Container Apps
  など、いずれも小さいですが無料ではありません。終了後は必ず Lab 8 の cleanup を
  実行します」（[costs-and-cleanup.md](../docs/costs-and-cleanup.md)）。

### 00:10–00:30 Lab 1 — 環境構築

- **チェックポイント**: 各参加者の `.workshop/context.json` が生成されている
  （`primary_model_deployment_name`、`optimizer_model_deployment_name`、
  `foundry_project_endpoint` などの出力が存在する）。
- **つまずきやすい点**: `az login --use-device-code` のブラウザ承認忘れ、
  resource group 名の入力ミス。[docs/participant/troubleshooting.md](../docs/participant/troubleshooting.md)
  を画面共有できるようにしておく。

### 00:30–00:50 Lab 2 — Prompt Agent（baseline）

- **デモプロンプト**（`data/eval/live_subset.jsonl` の実データ、そのまま読み上げ可）:
  - `direct_policy_fact`: 「東京から大阪へ日帰り出張する場合、食事の日当はいくらですか?」
    — baseline でも答えられることが多い単純な事実確認。
  - `multi_hop`: 「国際線でビジネスクラスを利用するには、片道飛行時間が何時間以上である
    必要があり、誰の事前承認が必要ですか?」— baseline では 2 つの規程を統合できず、
    どちらか一方しか答えられないことが多い。
  - `ambiguity_missing_info`: 「出張費はいくら戻ってきますか?」— baseline では行き先・
    日程を勝手に仮定して金額を答えてしまいがちな点を観察させる。
- **チェックポイント**: 参加者が baseline の instructions を書き換えていないこと
  （Lab 6 の Optimizer の before/after 比較に必要）。

### 00:50–01:25 Lab 3 — Azure AI Search と Foundry IQ

- **チェックポイント**: Foundry IQ Knowledge Base（**Preview**）の作成が完了し、
  Lab 2 と同じ質問（特に `multi_hop`）で改善が見られること。
- **preview の注意喚起**: Foundry IQ の agentic retrieval は preview のため、
  ウィザードの画面構成が変わっている可能性がある旨を伝える。

### 01:25–01:35 休憩

### 01:35–02:10 Lab 4 — Tools・Tool Catalog・Toolbox

- **コスト警告の再読み上げ**: Web Search は呼び出しごとに課金される旨、Code Interpreter
  はセッションごとに課金される旨を再度伝える。
- **チェックポイント**: Travel Ops API の OpenAPI ツールが Toolbox v2 として
  `scripts/create_toolbox.py` 経由で追加されていること（Portal 非対応の操作）。

### 02:10–02:35 Lab 5 — Agent evaluation

- **チェックポイント**: `.venv/bin/python scripts/run_evaluation.py --output json` が
  `status: "completed"` で終わり、`report_url` が Foundry portal で開けること。
- **live 実行が難しい場合**: judge model のレート制限や評価 API のタイムアウトで
  時間内に終わらない場合は、
  [completed-run-assets/evaluation-run.simulated.json](completed-run-assets/evaluation-run.simulated.json)
  を画面共有し、「本来この形の JSON が返ってくる」と説明したうえで、
  [labs/05-evaluation.md](../labs/05-evaluation.md) の `report_url` 以降の解説（Portal
  での結果確認の見方）に進む。実行自体は各自の宿題として案内する。

### 02:35–02:55 Lab 6 — Agent Optimizer

- **preview の注意喚起**: Optimizer は preview 機能で SLA なし、最適化中は実際に
  Travel Ops API モックを呼び出す旨を伝える（[labs/06-optimization.md](../labs/06-optimization.md)
  の warning を読み上げる）。
- **live 実行が難しい場合**: [labs/06-optimization.md](../labs/06-optimization.md) の
  「live 実行ができない場合」の節にあるとおり、事前収録デモの代わりに
  [completed-run-assets/optimizer-run.simulated.json](completed-run-assets/optimizer-run.simulated.json)
  を画面共有し、baseline との score 差分・promote の判断基準（「すべての候補が
  baseline を下回ったら現状維持」）を説明する。

### 02:55–03:40 Lab 7 — Agent Framework workflow の Hosted Agent 配布

- **チェックポイント**: `.venv/bin/python scripts/deploy_hosted_agent.py --output json` が
  `"succeeded": true` を返し、Playground でストリーミング応答が確認できること。
- **リモートビルド待ち時間の目安**: 数分程度かかることがあるため、待ち時間中に
  `src/hosted-agent/main.py`・`domain.py` のコードを解説する時間に充てる。
- **live 実行が難しい場合**（リモートビルドの混雑・失敗が続く場合）:
  [completed-run-assets/hosted-agent-deploy.simulated.json](completed-run-assets/hosted-agent-deploy.simulated.json)
  を画面共有し、`agent_name`/`version`/`status`/`portal_url` の各フィールドが何を
  意味するかを説明したうえで、`failure_hint` が出た場合の確認先（Foundry portal の
  version ページ、Lab 8 の Application Insights トレース）を案内する。

### 03:40–03:50 Lab 8 — Observability・governance・cleanup

- **チェックポイント**: 全参加者が `./scripts/destroy.sh` を実行し、正常終了
  （resource group 自体は残り、タグ付きリソースが削除される）を確認する。
- **cleanup 確認手順**:
  1. `./scripts/destroy.sh` の出力に、Hosted Agent とその version の削除、
     Toolbox/evaluation 専用削除 script が未実装である旨の明示的な `SKIPPED`、
     `terraform destroy` の成功、残存タグ付きリソースがないことの検証が
     含まれていることを確認する。Toolbox/evaluation は Foundry project の
     削除に伴って除去される。
  2. 失敗した場合は Terraform state を削除させない。
     [docs/admin/troubleshooting.md](../docs/admin/troubleshooting.md) に記載の、
     報告されたリソース・操作に対応する手順を一緒に確認する。
  3. Codespace は cleanup 完了まで削除させない（ローカル Terraform state が
     Codespaces の永続ワークスペースにのみ存在するため）。

## 2. 選択ラボへの案内（時間が余った参加者向け）

早く進んだ参加者、または本編後にさらに学びたい参加者には
[labs/optional/README.md](../labs/optional/README.md) を案内してください。いずれも
追加のライセンス・管理者権限が必要なため、その場で実施できるとは限らない前提で
紹介します。

## 3. よくある質問への回答例

| 質問 | 回答の要点 |
|---|---|
| 「本番導入でもこの構成のままでよいか?」 | 本編は Private Link/VNet を扱わない public endpoint 構成。本番導入時は組織のネットワーク方針を別途検討する必要がある旨を伝える（[architecture.md](../docs/architecture.md)の Network posture）。 |
| 「Fabric IQ・Work IQ はなぜ本編に入っていないのか?」 | 追加の Fabric/Microsoft 365 ライセンスと、Global Administrator など本編とは別の管理者による同意が必要なため。[labs/optional/fabric-iq.md](../labs/optional/fabric-iq.md)・[labs/optional/work-iq.md](../labs/optional/work-iq.md) を案内する。 |
| 「CI/CD で自動化できるか?」 | 設計は可能（[labs/optional/cicd-continuous-evaluation.md](../labs/optional/cicd-continuous-evaluation.md)）だが、本リポジトリには実働のワークフローを含めていない旨を伝える。 |

## 関連リンク

- [instructor/README.md](README.md)
- [completed-run-assets/README.md](completed-run-assets/README.md)
- [docs/admin/prerequisites.md](../docs/admin/prerequisites.md)
- [docs/admin/troubleshooting.md](../docs/admin/troubleshooting.md)
- [docs/participant/troubleshooting.md](../docs/participant/troubleshooting.md)
- [docs/costs-and-cleanup.md](../docs/costs-and-cleanup.md)

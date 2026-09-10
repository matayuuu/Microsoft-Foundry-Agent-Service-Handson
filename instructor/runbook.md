# 進行台本（runbook）— 4 時間 30 分アジェンダ

対象読者: このハンズオンを進行する講師。参加者には配布しません。

## 0. 事前準備（イベントの数日前〜前日）

### 0.1 subscription 管理者との調整

- [docs/admin/prerequisites.md](../docs/admin/prerequisites.md) を subscription 管理者に
  共有し、次を確認してもらいます。
  1. `./scripts/admin-preflight.sh --subscription "<subscription-id>"`（既定は読み取り専用）
     を実行し、5 つの resource provider（`Microsoft.CognitiveServices`、
     `Microsoft.Search`、`Microsoft.Insights`、`Microsoft.OperationalInsights`、
     `Microsoft.App`）がすべての対象 region
     （`japaneast`、`australiaeast`、`centralus`）で `Registered` であること。
  2. 想定参加者・チーム数に対して `gpt-5.6-luna`（40K TPM/team）、`gpt-5.5`（100K TPM/team）、
     `text-embedding-3-small`（40K TPM/team）の model quota/capacity が対応 region の
     少なくとも一方で足りていること。
     Luna は Prompt/Hosted Agent と Foundry IQ、GPT-5.5 は Lab 5 の評価と
     Lab 6 の Optimizer で共有します。
     最大 3 deployment を用途ごとに重複計上せず、初期容量で同時実行をリハーサルします。
     GPT-5.5 は評価と最適化で共有するため、既定を100にしています。
     これは既存 quota 内での GlobalStandard throughput の割り当てであり、
     subscription quota 上限の引き上げや、固定額のトークン料金の購入ではありません。
     実際の利用には課金され、100 でも 429 がなくなる保証はないため、実環境で再確認します。
     Dedicated Basic が3リージョンとも作成できない場合は
     `--ai-search-serverless` で Serverless Developer preview を使用します。
  3. 未登録の provider がある場合のみ `--apply` を実行してもらう（quota・policy・
     resource group・role assignment は一切変更しない設計です）。
- 参加者ごとのsandbox subscription、または参加者がworkload用RGを作成できる
  subscriptionレベルの権限を用意します。参加者へRGの命名規則とlocationを伝え、
  前提条件の冒頭で専用RGを作成してOwnerを確認してもらいます。
- Cloud Shell採用時は、同じ権限でCloud Shell専用RG / Storageも自動作成できることを確認します。
  共有subscriptionで複数参加者をOwnerにする場合は、相互アクセスのリスクを明示します。

### 0.1.1 Codespaces / Cloud Shell の開催条件

- 準備時に [Codespaces](../docs/participant/environments/codespaces.md) または
  [Cloud Shell Bash + JupyterLab](../docs/participant/environments/cloud-shell.md) を選びます。
  Lab 2 以降は同じ進行とし、Lab 7 / 8 の Notebook を CLI 手順へ置き換えません。
- **Cloud Shell は tenant あたり既定20同時ユーザーです。** 講師・補助員・他用途も数え、
  超える場合は開催前に Azure Support への引き上げ相談を管理者へ依頼します。
- 管理者に `Microsoft.CloudShell` / `Microsoft.Storage` の登録、Cloud Shell初回UIによる
  専用RG / Storage / shareの自動作成権限、共有キーとネットワークのpolicy、
  HTTPS / WSS、GitHub・GHCR・パッケージ配布先の通信を確認してもらいます。
  通常の `admin-preflight.sh` 成功だけではこれらの確認の代わりになりません。
- 既存Storageを手動作成する代替経路だけ、**Primary service: Other (tables and queues)**、general-purpose v2 用の
  **Standard**、LRS を使い、**View automation template > Parameters** の
  `kind=StorageV2` / `accountType=Standard_LRS` を作成前に確認します。
  Review の Account type が **Page blobs** と表示される不整合があるため、説明ラベルを必須条件にしません。
  作成後は `az storage account show` の kind / SKU / `Succeeded` も確認します。
  **Azure Files** の選択で **File shares / Provisioned v2** へ変わる経路は使いません。
  storage の region は選択する対応済み Cloud Shell location に合わせ、RG の region から決めません。
- share の入口は **Data storage > Classic file shares > New classic file share** です。
  **Backup** の **Enable backup** は既定 On のため、新規・演習専用で任意なら外します。
  Review の名前、**TransactionOptimized / SMB**、新規 Vault / policy がないことを確認します。
  組織必須の backup や既存の保護は変更しません。
- Cloud Shell storage はユーザーごとに分離します。受講者に subscription / 専用RG / account /
  share / region を控えてもらい、新規作成と既存割り当て、終了時の削除可否を区別します。
  標準は **We will create a storage account for you** とし、別ユーザーのshareは使わせません。
- Cloud Shell の既存利用者には設定を黙ってリセットさせません。古い share のマウント失敗後に
  ephemeral session になっている場合も同様です。別 share への切替は HOME と全 session に影響するため、
  元の `preferredLocation`、storage / 個人設定と必要なファイルを保全してから管理者と調整します。
  古い storage が割り当て RG の外にあっても削除しません。
- Cloud Shell 用 storage の準備・パッケージ取得は開始前に済ませます。
  本編の時間内に全員分の provider / policy / 同時利用の調整が終わる前提にはしません。

### 0.2 講師自身のリハーサル（推奨: イベント前日までに 1 回）

- 自分用の resource group で `./scripts/preflight.sh` → `./scripts/setup.sh` を通し、
  `.workshop/context.json` が生成されることを確認します。
- 採用する実行環境ごとに準備を確認します。Cloud Shell を採用する場合は、
  参加者ガイドどおりCloud Shellによる専用storageの自動作成・マウントから、Web previewの実URL、
  Jupyter 認証、両 kernel の Python 3.13、セルの実行・保存、Graphviz の SVG を
  ブラウザーで確認します。起動ページが表示されただけでは合格にしません。
- Cloud Shell の **Restart** で同じ repository、保存ファイル、`.venv`、作成後の state /
  `.workshop/context.json` に戻れることを確認します。**New session** は同じ container の
  別プロセスなので永続化の検証にはなりません。保存済み Notebook と kernel 内メモリーは区別します。
- リハーサル前に RG 内の既存 resource と Cloud Shell storage を記録します。終了後は
  workload cleanup → 安全な成果物の取得 → Jupyter / preview / session 終了 →
  Cloud Shell設定解除 → 自動作成された専用RG一式の削除を通し、workload用RGと
  事前からあるresourceが残ることを確認します。
  token、cookie、Jupyter runtime、Terraform state を画面共有や配布資料に含めません。
- AgentとFoundry IQは`primary_model_deployment_name`（Luna）を使います。
  Lab 5の設定可能なjudgeは`evaluation_model_deployment_name`、Lab 6の両モデル選択は
  `optimizer_model_deployment_name`（いずれも同じGPT-5.5）を使います。
  Model catalog と Portal picker の対応は同一視せず、当日もそれぞれ確認します。
  サービス管理の Violence などには judge を指定しません。
- Lab 5（評価）・Lab 6（Optimizer）・Lab 7（Harness Agent）・Lab 8（Hosted Agent デプロイ）を一度通しで
  実行し、リモートビルドや preview 機能の待ち時間の当日の目安を体感しておきます。
- [instructor/completed-run-assets/](completed-run-assets/README.md) の内容に目を通し、
  画面共有する場合にどこを見せるかを決めておきます。

### 0.3 当日開始前チェックリスト

- [ ] 全員が選んだ実行環境を起動でき、Python 3.13 と2つの kernel の準備が完了している。
- [ ] Cloud Shell 利用者は永続 HOME の保持を確認済み。tenant 同時利用枠、個人別 storage、
     HTTPS / WSS とパッケージ配布先の通信が確認済み。
- [ ] Codespaces は `az login --use-device-code`、Cloud Shell は既存 Azure CLI サインインを確認。
     未対応 audience 時の device-code 再認証も組織で許可されているか事前確認済み。
- [ ] `travel-ops-api:v1.0.3` を GHCR に publish 済みで、package visibility が
     **Public** になっている（private repository からの初回 publish 後は GitHub
     package settings で手動変更が必要）。
- [ ] 画面共有用に、この runbook と `completed-run-assets/` を別ウィンドウで開いておく。
- [ ] タイマー（各区切りの時間管理）を用意する。

## 1. 当日の進行（[README のアジェンダ](../README.md#agenda)に対応）

各区切りは目安時間です。参加者の進捗にばらつきが出やすいのは Lab 3（Foundry IQ の
待ち時間）と Lab 8（リモートビルドの待ち時間）です。早く終わった参加者には、該当する
[選択ラボ](../labs/optional/README.md)の該当節（読むだけでも可）を勧めてください。

### 00:00–00:10 Lab 0 — オープニング

- **チェックポイント**: 全員が [labs/00-overview.md](../labs/00-overview.md) を開けている。
- **読み上げポイント**（データ境界）: 「本ハンズオンで扱う Contoso の規程・経費・旅程
  データはすべて合成データで、実在の人物・企業とは無関係です」。
- **読み上げポイント**（コスト）: 「今日作成するリソースは Azure AI Search Basic、
  model 推論・embedding・評価 judge・Agent Optimizer のトークン課金、Container Apps
  など、いずれも小さいですが無料ではありません。終了後は必ず Lab 9 の cleanup を
  実行します」（[costs-and-cleanup.md](../docs/costs-and-cleanup.md)）。
- **実行環境のコスト**: 「Codespaces の稼働・保存、Cloud Shell の永続ストレージにも注意します。
  Cloud Shell の計算環境が無料でも、storage と Azure workloads は閉じるだけでは消えません」。

### 00:10–00:30 Lab 1 — 環境構築

- **チェックポイント**: 各参加者の `.workshop/context.json` が生成されている
  （`primary_model_deployment_name`、`evaluation_model_deployment_name`、
  `optimizer_model_deployment_name`、
  `foundry_project_endpoint` などの出力が存在する）。
- **GPT-5.5 不足時**: evaluation / optimizer の両outputが`null`でも構築成功です。
  Labs 5 / 6をスキップし、Lab 7へ進みます。
- **つまずきやすい点**: `az login --use-device-code` のブラウザ承認忘れ、
  resource group 名の入力ミス。[docs/participant/troubleshooting.md](../docs/participant/troubleshooting.md)
  を画面共有できるようにしておく。
- **合流の確認**: 選んだ環境の repository root と2つの `.venv` が準備できたら、
  Lab 1 の手順 2 以降を全員同じコマンドで進めます。Cloud Shell の一時セッションや
  未確認の保存先で Terraform を実行させません。

### 00:30–00:50 Lab 2 — Prompt Agent と Azure AI Search（baseline）

- **デモプロンプト**（`data/eval/live_subset.jsonl` の実データ、そのまま読み上げ可）:
  - `direct_policy_fact`: 「東京から大阪へ日帰り出張する場合、食事の日当はいくらですか?」
    — baseline でも答えられることが多い単純な事実確認。
  - `multi_hop`: 「片道12時間の国際線を出発2日前にビジネスクラスで予約したいです。
    直前予約として添付が必要なもの、ビジネスクラスの承認者と順序、申請に使う機能名、
    申請から承認完了までの標準最大営業日数をまとめてください。」— Direct search では
    直前予約の添付要件だけ、Foundry IQ では 4 項目すべてを 2 文書の citation 付きで
    回答する構成。
  - `ambiguity_missing_info`: 「出張費はいくら戻ってきますか?」— baseline では行き先・
    日程を勝手に仮定して金額を答えてしまいがちな点を観察させる。
- **チェックポイント**: 参加者が baseline の instructions を書き換えていないこと
  （Lab 6 の Optimizer の before/after 比較に必要）。

### 00:50–01:25 Lab 3 — Foundry IQ

- **チェックポイント**: Foundry IQ Knowledge Base（**Preview**）に利用条件と承認手続きの
  2 source が接続され、`multi_hop` の根拠付き回答数が Direct search の原則 1/4 から
  4/4 へ改善すること。Medium の再検索は不足時だけなので、発生自体は必須にしない。
- **preview の注意喚起**: Foundry IQ の agentic retrieval は preview のため、
  ウィザードの画面構成が変わっている可能性がある旨を伝える。

### 01:25–01:35 休憩

Cloud Shell は非対話20分で終了し得ます。Notebook を保存し、切断された場合は環境ガイドの
再接続手順を使います。休憩や長時間の remote build / evaluation のために無限 keepalive を
使わせません。Azure 側の処理は Portal で状態を確認してから再開し、重複送信しません。

### 01:35–02:10 Lab 4 — Tools・Tool Catalog・Toolbox

- **操作面**: 本編は Web Portal。`prepare_toolbox_assets.py` は素材のローカル出力のみ。
  Notebook で先に Toolbox を作らせない。2026-09-05 の実画面では OpenAPI と Skill upload
  に対応しているため、古い「Portal 非対応」という説明を使わない。
- **ダウンロードの境界**: Portal の file picker は PC 側です。Codespaces は Explorer の
  **Download**、Cloud Shell は **Manage files > Download** に生成 ZIP の絶対パスを指定します。
  `.workshop` が JupyterLab に見えないことをエラーとせず、隠しファイルの全公開や HOME 全体の
  アーカイブは行わせません。
- **チェックポイント**: Included に `travel_ops_api`、Code Interpreter、Web Search、
  `travel-estimation`、`preapproval-simulation` があり、Tool Search が On のまま
  Publish されていること。Trace で `tool_search` → `call_tool` → 実 tool を区別する。
- **Skills の説明**: API は実行機能、Skill は操作手順、Foundry IQ は規程。
  Skill は preview の MCP resource であり、登録と実際の読み込みは別。
  API call が成功しただけで Skill を利用できたと説明しない。
- **コスト・境界**: Code Interpreter は API 結果の比較、Web Search は明示された
  現在の公開旅行情報だけに使う。秘密・個人情報・顧客情報を検索へ送らない。

### 02:10–02:35 Lab 5 — Agent evaluation

- **モデルの確認**: 対象 Agent は Luna のまま、設定可能な LLM judge は GPT-5.5。
  少数の rubric 判定と理由を人の判断と照合し、モデル名だけで評価の正しさを断定しません。
- **チェックポイント**: Portal の本編 run は TaskAdherence、TaskCompletion、
  Contoso Travel Rubric の 3 evaluator を使う。`eval-009` の raw sample と Trace で
  Tool Search の meta-call と downstream call を分け、両方が sample にある場合だけ
  ToolSelection / ToolInputAccuracy を任意の別 run で使用する。
- **live 実行が難しい場合**: judge model のレート制限や評価 API のタイムアウトで
  時間内に終わらない場合は、
  [completed-run-assets/evaluation-run.simulated.json](completed-run-assets/evaluation-run.simulated.json)
  を画面共有し、「本来この形の JSON が返ってくる」と説明したうえで、
  [labs/05-evaluation.md](../labs/05-evaluation.md) の `report_url` 以降の解説（Portal
  での結果確認の見方）に進む。実行自体は各自の宿題として案内する。
- **GPT-5.5 未デプロイの場合**: Lab 5 の手動実行は省略し、completed-run-assets で
  結果の読み方を説明する。Lab 6も省略し、Optimizerの参考結果を説明してLab 7へ進む。

### 02:35–02:55 Lab 6 — Agent Optimizer

- **preview の注意喚起**: Optimizer は preview 機能で SLA なし、最適化中は実際に
  Travel Ops API モックを呼び出す旨を伝える（[labs/06-optimization.md](../labs/06-optimization.md)
  の warning を読み上げる）。
- **モデルの確認**: Optimization / Evaluation modelの両方にGPT-5.5、
  Max candidates = 1を設定してlive実行する。
- **live 実行が難しい場合**: [labs/06-optimization.md](../labs/06-optimization.md) の
  「live 実行ができない場合」の節にあるとおり、事前収録デモの代わりに
  [completed-run-assets/optimizer-run.simulated.json](completed-run-assets/optimizer-run.simulated.json)
  を画面共有し、baseline との score 差分・promote の判断基準（「すべての候補が
  baseline を下回ったら現状維持」）を説明する。

### 02:55–03:40 Lab 7 — plain Agent から Harness Agent へ

- **学習順序**: Lab 3 の Foundry IQ と Lab 4 の Toolbox / Skills を plain Agent に接続し、
  Harness Agent で plan / todo / memory と tool 選択を追加する。
- **kernel**: どちらの環境でも **Python (Foundry Hosted Agent)**。
  VS Code 固有の選択画面は Codespaces ガイド、Cloud Shell は JupyterLab ガイドを案内します。
  切断で kernel のメモリーが失われた場合は、必要な接続・plan 確認セルから再実行します。
- **チェックポイント**: 同じ remote resources を使いながら、plain Agent と Harness Agent の
  実行ループの違いを説明できること。Notebook の session state は Lab 8 に引き継がれない。
- **スキップ時**: 経験者は Lab 3 の Foundry IQ が準備済みなら Lab 7 Notebook を
  実行せず Lab 8 へ進める。Lab 8 は Harness を使用しない。

### 03:40–04:10 Lab 8 — 通常 Agent workflow の Hosted Agent 配布

- **学習順序**: 通常の `intake_agent`、Foundry IQ を持つ `policy_agent`、
  `reviewer_agent` を `SequentialBuilder` で接続し、workflow の引き継ぎを確認して deploy する。
- **チェックポイント**: policy Agent だけが Foundry IQ を使い、Harness / Toolbox / Skills を
  workflow に含めないこと、Lab 7 の Notebook state ではなく checked-in source を
  deploy することを説明できる。その後、
  `.venv/bin/python scripts/deploy_hosted_agent.py --output json` が
  `status: "active"` を返し、Playground で応答が確認できること。
- **リモートビルド待ち時間の目安**: 数分程度かかることがあるため、待ち時間中に
  Notebook と `workflow.py` / `main.py` の対応を振り返る。Notebook の観察用
  intermediate 出力と、Hosted Agent が返す最終回答の違いも確認する。
- **live 実行が難しい場合**（リモートビルドの混雑・失敗が続く場合）:
  [completed-run-assets/hosted-agent-deploy.simulated.json](completed-run-assets/hosted-agent-deploy.simulated.json)
  を画面共有し、`agent_name`/`version`/`status`/`portal_url` の各フィールドが何を
  意味するかを説明したうえで、`failure_hint` が出た場合の確認先（Foundry portal の
  version ページ、Lab 9 の Application Insights トレース）を案内する。

### 04:10–04:20 Lab 9 — Observability・governance・cleanup

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
  3. Codespace または Cloud Shell の storage / HOME image は cleanup 完了まで削除させない。
     ローカル Terraform state と復旧用 `.workshop` がそこにあるため。
  4. 成功後に保存する Notebook / 安全な結果を取得し、選択した環境ガイドの終了手順へ進む。
     Cloud Shellは設定解除の後、**Cloud Shellが自動作成した専用RG一式だけ**をAzure portalで削除する。
     workloadの`destroy.sh`はCloud Shell storageを管理しない。workload用RG、他人・他用途の
     storage、検証前からあるCloud Shell設定は削除しない。
  5. 残存 resource、実行できなかった検証、cleanup の未完了は明記して引き継ぐ。
     simulated assets を実行成功の証跡にせず、失敗時は state と storage を保持する。

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

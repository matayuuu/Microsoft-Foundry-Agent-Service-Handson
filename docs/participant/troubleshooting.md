# 参加者向けトラブルシューティング

該当する症状だけを確認してください。サブスクリプション全体への対応が必要な場合は
[管理者向けトラブルシューティング](../admin/troubleshooting.md)へ進みます。

## 実行環境と Cloud Shell

準備・再接続・終了の操作は
[Codespaces](environments/codespaces.md) / [Cloud Shell](environments/cloud-shell.md) を参照してください。
環境の問題を理由に Lab 7 / 8 を別の CLI 演習へ置き換えたり、2つの `.venv` を統合したりしません。

| 症状 | 次に行うこと |
|---|---|
| `Tenant User Over Quota` | Cloud Shell は tenant あたり既定20同時ユーザーです。講師に知らせます。参加者が quota、provider、RG を増やして解決しません |
| storage 作成・マウントが拒否される | 自動作成を選んだsubscriptionレベルの作成権限、または既存StorageのRG / account / shareを確認します。policy、firewall、共有キー制限を解除せず管理者へ連絡します |
| 永続ストレージの検査に失敗する | **Mount storage account** を選んだか、HOME の永続マウントがあるか確認します。ephemeral session のまま `setup.sh` を実行しません。[保持の確認](environments/cloud-shell.md#persistence)に戻ります |
| Python / Graphviz がない、空き容量が不足 | Cloud Shell は `setup-cloud-shell.sh` の出力を確認します。`sudo` や system Python へのインストールは行いません。他用途のファイルを消さず、容量・通信条件を講師へ伝えます |
| Jupyter が開かない、`403` / Origin エラー | **Web preview** が開いた実際の HTTPS URL とポートを使っているか確認します。古い preview URL を使わず、ガイドどおり起動し直します。認証・XSRF を無効化しません |
| Notebook の kernel が接続しない | **Python (Foundry Hosted Agent)** を選びます。Cloud Shell では専用 launcher の認証付き HTTP relay、Codespaces では通常の Notebook 接続を確認します。古い preview URL や切断された Cloud Shell を使わず、認証・XSRF を無効にしません。画面表示だけでなく確認セルを実行します |
| Cloud Shell が切断された | 非対話20分で session は終了し得ます。[再接続](environments/cloud-shell.md#resume)で同じ storage と repository に戻ります。保存ファイルは保持確認しますが、Python のメモリーは再実行が必要です |
| Jupyter に `Directory not found` が出る | 先に Cloud Shell の切断表示を確認します。期限切れなら古い preview を閉じ、同じ storage へ再接続して state を確認します。空の repository を作り直しません |
| Download が失敗する／PC に ZIP が保存されない | 入力欄の HOME prefix が二重になっていないか確認します。prefix がある欄は HOME 相対パスを入力し、続いて **Download file** 通知のファイル名リンクを選びます。[実際の手順](environments/cloud-shell.md#files)を参照してください |
| 再接続後に context / state が見えない | 新しい repository で setup を実行せず、元の account / share と HOME image を確認します。storage や `.workshop` を削除・初期化しません |

### Cloud Shell の Azure 認証で失敗する

repository root で `source scripts/activate-cloud-shell.sh` を実行し直します。
この設定はローカル教材プロセスの認証を Azure CLI に限定するもので、
Hosted Agent のデプロイ先の managed identity を変更しません。

`Audience ... is not a supported MSI token audience` と表示された場合だけ、
公式 FAQ の回復手順で同じ参加者としてサインインし、subscription を選び直します。

```bash
az login --use-device-code
az account set --subscription "<subscription-id>"
```

Conditional Access や組織の device-code 禁止で拒否された場合は管理者へ連絡します。
API key / client secret、別人のサインイン、認証保護の無効化へ切り替えません。
Jupyter を再起動した場合は必要な接続セルを再実行します。

## 事前確認とセットアップ

### Owner ロールがない

サブスクリプションとリソースグループ名、`az account show` に表示されるユーザーを確認します。
ロールの付与直後は反映に数分かかることがあります。解消しない場合は管理者へ連絡します。

### リソースプロバイダー・クォータの確認に失敗する

参加者は変更できません。`preflight.sh` の出力を管理者へ渡してください。

### Search の `InsufficientResourcesAvailable`

指定リージョンで新しい Azure AI Search サービスを作成できません。別リージョンでセットアップを
再実行します。

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --location australiaeast
```

推奨順は `japaneast`（既定）、`australiaeast`、`centralus` です。
3 region の dedicated Basic がすべて失敗した場合は、同じリージョンで
`--ai-search-serverless` を追加して Serverless Developer preview を試します。
Serverless は従量課金で SLA がなく、Dedicated との相互移行もできません。

### セットアップが途中で失敗した

同じコマンドを再実行します。Terraform の状態ファイル、Azure リソース、`.workshop/` を手動で
削除しないでください。セットアップは作成済みのリソースを確認して続行します。

### `.workshop/context.json` がない

セットアップが最後まで完了していません。`./scripts/setup.sh ...` を再実行します。

## ポータル画面

### 教材と画面が違う

- `https://ai.azure.com` を開いている
- Foundry **new** を使っている
- `.workshop/context.json` と同じアカウント・プロジェクトを開いている

を確認します。教材の画像は英語ですが、表示言語の変更は必須ではありません。
画面ラベルで迷う場合は講師に確認してください。

### Foundry IQ を選んでもナレッジベースがない

**Build > Knowledge** でナレッジベースを先に作成します。
2つのソースを保存し、**Use in an agent** から対象エージェントを選択してください。
この操作でエージェントの新しいバージョンが自動保存されるため、**Save** が無効でも異常ではありません。

### Foundry IQ のモデルを選べない

Portal のモデル選択欄に表示されるデプロイを選びます。このハンズオンでは
`.workshop/context.json` の `primary_model_deployment_name` を使います。
通常は `gpt-5.6-luna` です。評価専用の `gpt-5.5` は選びません。
エージェントのモデル選択欄に表示されるデプロイが、IQ の選択欄にも表示されるとは限りません。

### Web search などが最初から追加されている

[Lab 2](../../labs/02-prompt-agent.md) ではエージェントの既定の **Web search** を外します。
Toolbox 作成時にも推奨ツールが入る場合があります。
[Lab 4](../../labs/04-tools-toolbox.md) のとおり不要なツールを外し、
`travel_ops_api` と2つの Skills だけを残してください。ガードレールは削除しません。

## 引用リンク

### Azure AI Search の回答に `%%CITATION_0%%` が表示される

`%%CITATION_0%%` は、Portal が番号付きの citation に変換するための内部表現です。
本文や **根拠資料** にそのまま表示される状態は、意図した最終表示ではありません。

回答下部に番号付きの citation が表示され、実行情報に `azure_ai_search_call` があれば、
検索自体は成功しています。リソースや index を作り直す必要はありません。
[Lab 2](../../labs/02-prompt-agent.md) の最新の Instructions を保存し、**New chat** で
もう一度質問してください。成功時は、番号付きの citation が参照元の文書を示し、本文に
`%%CITATION_...%%` が残らないことを確認します。

公式の確認方法は
[Connect an Azure AI Search index to Foundry agents — Verify results](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/ai-search#verify-results)
を参照してください。

### Foundry IQ の引用が `mcp://searchindex/...` になり、Web ページを開けない

これは Search インデックスの MCP 取得結果を指す識別子であり、通常の Web URL ではありません。
リンクが開けないことだけを理由にセットアップをやり直したり、インデックスのフィールドを変更したりしません。
回答の **根拠資料** と `knowledge_base_retrieve` の **Output** にある文書名・カテゴリを
見比べます。元の規程を読むには [Lab 2](../../labs/02-prompt-agent.md) の教材リンクを使います。

根拠資料が出ない場合は、[Lab 2](../../labs/02-prompt-agent.md) の指示文が保存済みか
確認し、**New chat** で質問してください。取得結果にない文書名・ID・URLを作らせません。

## Portal での Toolbox 操作

### Toolbox、OpenAPI、Skill の追加画面が見つからない

[Lab 4](../../labs/04-tools-toolbox.md) のスクリーンショットと比較します。
対象は Web の Foundry (new) Portal です。**Build > Tools > Create toolbox** の
**Toolboxes** タブを開くと **Create toolbox** があり、
作成画面の **Included > + Add** に **Add tool** と **Add skill** があります。
OpenAPI は **Select a tool > Custom > OpenAPI tool**、
Skill は **Select a skill > Configured > Add skill > Upload skill** です。

項目がない場合は、対象プロジェクトと権限を確認し、講師へ画面を共有してください。
Toolbox の SDK Notebook は補助用で、Skills の作成・利用まで代替するものではありません。

### OpenAPI のサーバーがない／接続先が違う

`/openapi.json` をそのまま貼るのではなく、
`.venv/bin/python scripts/prepare_toolbox_assets.py` を実行し、
`.workshop/toolbox/travel-ops.openapi.json` を使います。
自分の環境情報にある API エンドポイントが `servers` に設定されます。
JSON 全体を貼り付け、コードブロックを囲むバッククォートは含めません。

### ブラウザーのアップロード画面でファイルが見えない

実行環境と手元の PC は別のファイルシステムです。
[Codespaces の Explorer > Download](environments/codespaces.md#files) または
[Cloud Shell の Manage files > Download](environments/cloud-shell.md#files) で、
Lab 4 が生成した2つの ZIP を手元へ保存してからアップロードします。
Cloud Shell の HOME prefix がある欄では相対パスを入力し、**Download file** 通知の
ZIP リンクを選びます。`.workshop` は隠しフォルダーなので、
JupyterLab のファイル一覧に見えなくても異常ではありません。
ZIP は `SKILL.md` が直下にある生成済みのものを使い、state や `.workshop` 全体は取得しません。

### Upload skill の後に Add を押せない

新しい Skill は **Create** でアップロードすると、そのまま Toolbox の **Included** に入ります。
**All configured skills added** は追加済みの表示です。同じ ZIP を再アップロードせず、
**Included** の Skill 名を確認してください。

### Toolbox は公開できたがエージェントから接続できない

Toolbox への認証は Entra ID/RBAC です。OpenAPI の模擬 API の **Anonymous** と混同しません。
**Microsoft Entra > Project Managed Identity**、
**Audience** = `https://ai.azure.com/` を確認します。画面上でキーを使わない接続が利用できない場合は、公開後に
`.venv/bin/python scripts/connect_toolbox.py` を実行します。
新しい Toolbox は作らず、既存のナレッジを保持して接続だけを追加します。
403 が続く場合は、対象プロジェクトと呼び出し元 ID の **Foundry User** 権限を講師に確認してもらいます。

### Tool Search が `No tools matched query` で止まる

公開済み Toolbox に対象 tool が含まれることを確認します。日本語の長い検索語では
built-in tool に一致しない場合があります。**New chat** で依頼をやり直し、
tool discovery には `web_search`、`code_interpreter`、`createTripEstimate` のような
英語の tool 名を使うよう指示します。検索対象の公開情報と、tool の発見用キーワードは別です。
Tool Search を無効化したり、無関係な tool を追加したりして回避しません。

Web Search の回答では、参照 URL、情報の基準日時、実際の取得日時を区別します。
tool の出力に取得タイムスタンプがない場合は「取得日時は未提供」と記録し、
ページの更新日時を取得日時として作り替えません。Trace の実行時刻も併せて確認します。

### Skill を追加したのに手順が反映されない

Toolbox の公開済みバージョンに Skill が含まれること、参照先 Skill のバージョン、
利用クライアントの MCP Resources／Skill プロバイダーへの対応を確認します。
Portal の Prompt Agent は Toolbox の callable tool を実行できますが、MCP Resources の Skill は
自動で読み込みません。同じ Prompt Agent を Python の `AIProjectClient` から呼び出しても
実行環境は同じです。新しい会話または再接続で `resources/read` や `load_skill` の記録を確認し、
API の成功だけを Skill の成功としません。
Lab 7 の Harness Agent は checked-in factory の Skill provider を使います。
Lab 8 は token 消費を抑えた通常 Agent の sequential workflow であり、Toolbox Skill は
使いません。Lab 7 の Notebook session state も引き継ぎません。
Skill をエージェントの指示文にコピーする代替手段は、Toolbox 経由の利用とは区別してください。

## Notebook での Toolbox 操作

以下は任意の SDK 学習・補助経路だけのトラブルシューティングです。

### `Python (Foundry Workshop)` カーネルがない

選んだ環境ガイドで初期化の完了を確認します。
Codespaces は devcontainer の再構築、Cloud Shell は永続 HOME の同じ repository で
`bash scripts/setup-cloud-shell.sh` → `source scripts/activate-cloud-shell.sh` を実行し、
Jupyter を起動し直します。Codespaces で root `.venv` が正常な場合は、Terminal で次の再登録もできます。

```bash
.venv/bin/python -m ipykernel install \
  --user \
  --name foundry-workshop \
  --display-name "Python (Foundry Workshop)"
```

### `context file not found`

Lab 1 のセットアップを完了し、リポジトリ内の
`notebooks/04-create-toolbox.ipynb` を開いてください。

### OpenAPI の取得がタイムアウトする

Container App のコールドスタート中です。正常性を確認してから、該当セルを再実行します。

```bash
curl -s "https://$(jq -r '.terraform_outputs.travel_api_fqdn.value' \
  .workshop/context.json)/health"
```

### Toolbox の作成が 403 になる

ロールの反映に数分かかることがあります。少し待ってセルを再実行します。解消しない場合は
Lab 1 の事前確認の出力とともに管理者へ連絡します。

## 評価と最適化

### 合成データを生成できない

`Unable to create data source configuration from item schema` が表示される場合が
あります。Lab 5 は **Existing dataset** の `contoso-travel-eval-live-subset` を使ってください。
一覧にない場合は Lab 1 のセットアップを同じ引数で再実行します。

### 評価が終わらない

**Evaluations** 一覧で状態を確認し、数分後に再読み込みします。同じ評価を重複して
実行しないでください。

### 評価がツールの承認待ちになる

[Lab 4](../../labs/04-tools-toolbox.md) の最後で、ハンズオン用
`contoso-travel-toolbox-mcp` だけに **Always auto-approve all tools** を設定して保存します。
ほかの MCP 接続に広げないでください。Entra ID 認証やガードレールを無効にする設定ではありません。
Lab 5 ではこの変更を保存したエージェントのバージョンを選択します。

### 評価器の応答マッピングが合わない

**TaskAdherence** と **ToolInputAccuracy** の **Response** は
`{{sample.output_items}}` です。最終回答の文章だけでなくツール呼び出しも渡します。
**TaskCompletion** と **ToolSelection** は `{{sample.output_text}}` を使います。
[Lab 5](../../labs/05-evaluation.md) の各設定画像と比較してください。

### Completed / Partial なのに Error の行がある

**Completed** は実行の終了を表し、全行が正常に採点できたという意味ではありません。
一部を採点できなかった評価は、一覧に **Partial** と表示される場合もあります。
右側の **Error** 列を確認します。

| 表示 | 対応 |
|---|---|
| スコアの **Fail** とその理由 | 回答・ツールの使い方の改善点として読む。実行エラーと区別する |
| `content_filter` | 意図的な攻撃文の行か確認する。保護機能で遮断された結果を記録し、採点できた行と区別する。ガードレールを弱めて通さない |
| `429` または IQ の `maximum runtime of 90 seconds` | 同時実行の終了を待ち、講師に共有デプロイの処理容量とレート制限を確認してもらう。原因を解消するまで評価の実行を増やさない |

処理容量の変更はクォータの引き上げとは別です。参加者が Portal で Terraform 管理の
デプロイを独自に変更せず、講師へ **Error** の内容を渡してください。

### Optimizer が改善候補を生成しない

**Optimize** tab に **No supported optimization model** が表示される場合は、
`.workshop/context.json` の `optimizer_model_deployment_name` が `gpt-5.5` か確認します。
`null` の場合はクォータ不足により省略されています。
[Lab 6](../../labs/06-optimization.md) のスキップ手順に従ってください。

GPT-5.5 がデプロイ済みで、run を開始した後に候補が生成されない場合だけ、次を確認します。
`.workshop/context.json` の `optimizer_model_deployment_name` の値を
**Optimization model** と **Evaluation model** の両方に選んでいるか確認します。
**Criteria** は組み込み評価器ではなく **Contoso Travel Rubric** を選択します。
サービス側のエラーの場合は実行を増やさず講師へ連絡します。

### 評価モデルとエージェントのモデルが違う

この教材では意図した設定です。回答する Prompt / Hosted Agent と Foundry IQ は
`gpt-5.6-luna` を使います。
`gpt-5.5` は Lab 5 の設定可能な LLM judge と、Lab 6 の **Evaluation model** /
**Optimization model** に使います。Agent本体のモデルはLunaのまま変更しません。

## Hosted Agent

### `Python (Foundry Hosted Agent)` カーネルがない

選んだ環境ガイドで初期化の完了を確認します。
Codespaces は devcontainer の再構築、Cloud Shell は永続 HOME の同じ repository で
`bash scripts/setup-cloud-shell.sh` → `source scripts/activate-cloud-shell.sh` を実行し、
Jupyter を起動し直します。Codespaces で Hosted Agent 用 `.venv` が正常な場合は、次の再登録もできます。

```bash
src/hosted-agent/.venv/bin/python -m ipykernel install \
  --user \
  --name foundry-hosted-agent \
  --display-name "Python (Foundry Hosted Agent)"
```

### Notebook のモデル呼び出しが 404 になる

`.workshop/context.json` が現在の環境のものか確認し、Notebook を再起動して上から
再実行します。

### Hosted Agent のデプロイがタイムアウト・失敗する

**Build > Agents** で `contoso-travel-hosted-planner` の状態とビルドエラーを確認します。
ソースコードを変更せずにデプロイコマンドを何度も実行しないでください。

### Hosted Agent から Foundry IQ が 403 になる

`deploy_hosted_agent.py` は agent identity に Search Index Data Reader、Foundry User、
Monitoring Metrics Publisher を workshop resource scope で付与します。deploy が `active` に
なった直後だけ失敗する場合は、role assignment の反映を待って同じ依頼を再送します。
新しい agent version を作り直したり、subscription scope の広い role を追加したりしません。
継続する場合は deploy 出力の role assignment エラーと agent identity を講師へ共有します。

## トレース

### トレースが表示されない

エージェントを1回実行し、数分待って対象エージェントの **Traces** を開き直します。
Application Insights への接続はセットアップで作成済みです。

Hosted Agent の **Log stream** に `Monitoring Metrics Publisher` または `Forbidden` が表示される
場合は、デプロイ直後のロール反映を数分待ってから1回だけ再実行します。解消しない場合は
デプロイコマンドの出力を講師へ渡してください。

## クリーンアップ

### `destroy.sh` が失敗した

表示された原因を修正して、同じコマンドを再実行します。

```bash
./scripts/destroy.sh
```

Terraform の状態ファイルと `.workshop/` はクリーンアップ完了の確認に必要です。手動で削除しないでください。
Cloud Shell の storage / HOME image も、`destroy.sh` が成功するまで削除しません。
Cloud Shell storage はこのスクリプトの削除対象ではなく、
[環境ガイドの終了手順](environments/cloud-shell.md#stop)で最後に扱います。
削除直後の一覧反映には時間差があるため、スクリプトは残存確認を有限回繰り返します。
途中で失敗して環境情報が残っていれば、Foundry アカウントの削除後でも同じコマンドで再開できます。

### Toolbox / Skill の参照が原因で削除できない

`destroy.sh` は Portal で作成した Toolbox / Skills の個別削除を自動化していません。
エラーがこれらの参照を示す場合は、講師と対象を確認し、ハンズオン用プロジェクト内だけで
次の順に操作します。

1. **Build > Agents > contoso-travel-assistant > Playground** の **Tools** で、
   `contoso-travel-toolbox-mcp` の **Actions > Remove** を選び、**Save** します。

![Lab 9 でハンズオン用の MCP 接続だけを Remove する](../images/lab08-remove-toolbox-connection.png)

![Lab 9 で接続を外した後に Save する](../images/lab08-save-disconnected-agent.png)

2. **Build > Tools > Toolboxes** で `contoso-travel-toolbox` の行にポインターを重ね、
   表示された **… > Delete** を選び、
   確認画面の名前を確認して削除します。

![Lab 9 で対象 Toolbox の操作メニューから Delete](../images/lab08-delete-toolbox-menu.png)

![Lab 9 で削除対象の名前を確認する](../images/lab08-confirm-delete-toolbox.png)

3. **Skills** で、他の Toolbox が参照していない `travel-estimation` と
   `preapproval-simulation` を削除します。**確認画面が出ない場合があるため、
   Delete を選ぶ前に名前を確認してください。**

![Lab 9 の Skills タブで travel-estimation を削除する](../images/lab08-delete-skill-menu.png)

![Lab 9 で preapproval-simulation も名前を確認して削除する](../images/lab08-delete-second-skill.png)

4. ブラウザーを再読み込みして対象が消えたことを確認し、`./scripts/destroy.sh` を再実行します。

![Lab 9 でこの演習の2つだけだった場合は Add your first skill と表示される](../images/lab08-skills-deleted.png)

削除画面が利用できない場合は講師へ連絡し、SDK での削除を確認してから再実行してください。

## 戻る

[Lab 0 — 全体像と進め方](../../labs/00-overview.md)

# 参加者向けトラブルシューティング

該当する症状だけを確認してください。Subscription scope の対応が必要な場合は
[管理者向けトラブルシューティング](../admin/troubleshooting.md)へ進みます。

## Preflight / setup

### Owner role がない

Subscription と resource group 名、`az account show` の user を確認します。
Role 付与直後は反映に数分かかることがあります。解消しない場合は管理者へ連絡します。

### Resource provider / quota で fail する

参加者は変更できません。`preflight.sh` の出力を管理者へ渡してください。

### Search の `InsufficientResourcesAvailable`

指定 region で新しい Azure AI Search service を作成できません。別 region で setup を
再実行します。

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --location swedencentral
```

### Setup が途中で失敗した

同じ command を再実行します。Terraform state、Azure resource、`.workshop/` を手動で
削除しないでください。Setup は作成済み resource を確認して続行します。

### `.workshop/context.json` がない

Setup が最後まで完了していません。`./scripts/setup.sh ...` を再実行します。

## Portal

### 教材と画面が違う

- `https://ai.azure.com` を開いている
- Foundry **new** を使っている
- `.workshop/context.json` と同じ account / project を開いている
- Portal の表示言語が English である

を確認します。

### Foundry IQ を選んでも knowledge base がない

Agent 画面から先に追加しようとしています。
**Build > Knowledge > Create knowledge base** で knowledge base を作成してから、
Agent の **Knowledge > Add > Foundry IQ** に戻ります。

### Foundry IQ の model を選べない

Portal の model picker が対応する deployment を選びます。このハンズオンでは
`.workshop/context.json` の `primary_model_deployment_name` を使います。
通常は `gpt-5.6-luna` です。Optimizer 用の `gpt-5.5` と取り違えないでください。

## Citation link

### Citation が Search service のトップを開く

Index に標準の retrievable `url` field が入っていない状態です。最新の repository で
setup を再実行し、data bootstrap を更新します。

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>"
```

直らない場合は、Azure AI Search の `contoso-travel-policy` と
`contoso-travel-approval` index で `url` field が retrievable かを管理者へ
確認してもらいます。

## Toolbox Portal

### Toolbox、OpenAPI、Skill の追加画面が見つからない

[Lab 4](../../labs/04-tools-toolbox.md) のスクリーンショットと比較します。
対象は Web の Foundry (new) Portal です。**Build > Tools > Create toolbox** の
**Included > + Add** に **Add tool** と **Add skill** があります。
OpenAPI は **Select a tool > Custom > OpenAPI tool**、
Skill は **Select a skill > Configured > Add skill > Upload skill** です。

項目がない場合は、対象 project と権限を確認し、講師へ画面を共有してください。
Toolbox の SDK Notebook は補助用で、Skills の作成・利用まで代替するものではありません。

### OpenAPI の server がない／接続先が違う

`/openapi.json` をそのまま貼るのではなく、
`.venv/bin/python scripts/prepare_toolbox_assets.py` を実行し、
`.workshop/toolbox/travel-ops.openapi.json` を使います。
自分の context の API endpoint が `servers` に設定されます。
JSON 全体を貼り付け、code fence は含めません。

### Browser のアップロードでファイルが見えない

Codespace と手元の PC は別のファイルシステムです。VS Code Explorer の **Download** で
ZIP または各 `SKILL.md` を手元へ保存してからアップロードします。
ZIP は `SKILL.md` が直下にある、生成済みのものを使ってください。

### Toolbox は公開できたが Agent から接続できない

Toolbox への認証は Entra ID/RBAC です。OpenAPI mock の **Anonymous** と混同しません。
UI の keyless 接続が利用できない場合は、公開後に
`.venv/bin/python scripts/connect_toolbox.py` を実行します。
新しい Toolbox は作らず、既存の Knowledge を保持して接続だけを追加します。
403 が続く場合は project と呼び出し identity の Foundry User 権限を講師へ確認します。

### Skill を追加したのに手順が反映されない

Toolbox の公開済み version に Skill が含まれること、参照先 Skill の version、
利用クライアントの MCP Resources／Skill provider 対応を確認します。
新しい会話または再接続で読み込み記録を確認し、API の成功だけを Skill の成功としません。
既存の Lab 7 workflow は Skill provider を含みません。
Skill を Agent の instructions にコピーする代替は、Toolbox 経由の利用とは区別してください。

## Toolbox Notebook

以下は任意の SDK 学習・補助経路だけのトラブルシューティングです。

### `Python (Foundry Workshop)` kernel がない

Codespace を rebuild します。急ぐ場合は terminal で次を実行します。

```bash
.venv/bin/python -m ipykernel install \
  --user \
  --name foundry-workshop \
  --display-name "Python (Foundry Workshop)"
```

### `context file not found`

Lab 1 の setup を完了し、repository 内の
`notebooks/04-create-toolbox.ipynb` を開いてください。

### OpenAPI の取得が timeout する

Container App の cold start 中です。Health check 後に該当 cell を再実行します。

```bash
curl -s "https://$(jq -r '.terraform_outputs.travel_api_fqdn.value' \
  .workshop/context.json)/health"
```

### Toolbox の作成が 403 になる

Role 反映に数分かかることがあります。少し待って cell を再実行します。解消しない場合は
Lab 1 の preflight 出力とともに管理者へ連絡します。

## Evaluation / Optimizer

### Synthetic data を生成できない

`Unable to create data source configuration from item schema` が表示される場合が
あります。Lab 5 は **Existing dataset** の `contoso-travel-eval-live-subset` を使ってください。
一覧に無い場合は Lab 1 の setup を同じ引数で再実行します。

### Evaluation が終わらない

**Evaluations** 一覧で status を確認し、数分後に refresh します。同じ run を重複して
submit しないでください。

### Optimizer が candidate を生成しない

`.workshop/context.json` の `optimizer_model_deployment_name` の値を選んでいるか確認します。
Criteria は built-in evaluator ではなく **Contoso Travel Rubric** を選択します。
Service error の場合は run を増やさず講師へ連絡します。

### 評価モデルと Agent のモデルが違う

この教材では意図した設定です。回答する Agent と Foundry IQ は `gpt-5.6-luna`、
回答を採点する LLM judge と改善案を作る Optimizer は `gpt-5.5` を使います。
Lab 6 の **Evaluation model** と **Optimization model** は、どちらも
`optimizer_model_deployment_name` の値を選択します。

## Hosted Agent

### `Python (Foundry Hosted Agent)` kernel がない

Codespace を rebuild します。急ぐ場合は terminal で次を実行します。

```bash
src/hosted-agent/.venv/bin/python -m ipykernel install \
  --user \
  --name foundry-hosted-agent \
  --display-name "Python (Foundry Hosted Agent)"
```

### Notebook の model call が 404 になる

`.workshop/context.json` が現在の環境のものか確認し、Notebook を restart して上から
再実行します。

### Hosted Agent deploy が timeout / failed になる

**Build > Agents** で `contoso-travel-hosted-planner` の status と build error を確認します。
Source を変更せずに deploy command を何度も実行しないでください。

## Trace

### Trace が表示されない

Agent を 1 回実行し、数分待って対象 agent の **Traces** を開き直します。
Application Insights connection は setup で作成済みです。

Hosted Agent の **Log stream** に `Monitoring Metrics Publisher` または `Forbidden` が表示される
場合は、deploy 直後の role 反映を数分待ってから 1 回だけ再実行します。解消しない場合は
deploy command の出力を講師へ渡してください。

## Cleanup

### `destroy.sh` が失敗した

表示された原因を修正して、同じ command を再実行します。

```bash
./scripts/destroy.sh
```

Terraform state と `.workshop/` は cleanup 完了の確認に必要です。手動で削除しないでください。

## 戻る

[Lab 0 — 全体像と進め方](../../labs/00-overview.md)

# 参加者向けトラブルシューティング

## RG 作成 / template 読み込み

- Azure Portal の account / directory / subscription を確認します。
- **Resource groups > Create** で自分専用 RG を手動作成してから template を開きます。
- **Deploy a custom template > Build your own template in the editor > Load file** で
  管理者が配布した `infra/azuredeploy.json` 本体を読み込みます。GitHub の HTML ページを
  JSON として保存していないか確認します。
- template の **Resource group** は作成済み RG を選択。**Create new** は使いません。
- RG 作成権限と RG 内の Owner 相当権限を別々に管理者へ確認します。

## Deployment / bootstrap の失敗

- RG の **Deployments** と該当 deployment の詳細で失敗した resource を確認。
  Deployment Scripts の **Overview / Logs** で初期化のどの段階で失敗したかを確認します。
- model version、GlobalStandard SKU、quota、Policy、GHCR digest、公開済み `sourceRevision`
  を管理者へ確認します。capacity は予約されていません。
- 403 は対象 participant object ID、bootstrap identity、role scope、反映待ちを区別します。
  管理者による redeployment は `participantObjectIdOverride` に元の参加者を指定します。
- 実行中の deployment を重複送信しません。同じ RG・入力での再実行は診断後に行い、
  `bootstrapRunId` は意図的に bootstrap を再実行するときだけ変更します。
- Azure の deployment はトランザクションではありません。失敗後に部分的な resources が
  残る場合があります。別 RG を増やす前に管理者へ相談します。
- 一時 ACI / Storage と診断情報の保持には期限（`P1D`）があります。
  非秘密の error code / operation を早めに管理者へ伝えます。

**停止条件を回避しません。** リージョン・モデル・SKU・security baseline の変更、
runtime Owner、public Blob、account key への切り替えは対処ではありません。
bootstrap / validation が失敗したまま Lab 2 に進まず、以前の ZIP を今回の成功と扱いません。

## Private ZIP download

- deployment 全体の **Succeeded** と bootstrap `status = complete` を確認します。
- outputs の `storage_account_name` と同じ Storage account を開きます。
- **Storage browser > Blob containers > workshop-files**、
  **Microsoft Entra user account** を選び、`foundry-workshop-files.zip` を **Download**。
- 認証が Access key の場合は **Switch to Microsoft Entra user account** を選択します。
- 403 は participant の Storage Blob Data Contributor と管理プレーン参照権限を確認。
  権限反映後に画面を更新します。SAS / 公開 container / account key で回避しません。
- ZIP が空・展開不能、`source_revision` が違う、context の `setup_status` が `complete` でない
  場合は使用せず、管理者へ bootstrap outputs と照合してもらいます。

`.workshop/download/foundry-workshop-files.zip` は Azure 側の生成パスです。
Portal にこのパスを入力するのではなく、private Blob 一覧から download します。

## Foundry Portal

- account / project は `.workshop/context.json` の `resource_outputs.<key>.value` に合わせます。
- connection は `contoso-travel-search` / `contoso-travel-knowledge-lab-mcp` /
  `contoso-travel-appinsights`。後ろの 2 つは **Project Managed Identity** です。
- Search は Basic、indexes は `contoso-travel-policy` / `contoso-travel-approval` です。
- 403 は scope / principal と propagation を確認し、broad role や key で回避しません。

## 引用リンク

Direct search の URL が Search service 自体を指している場合は、bootstrap の source revision と
index の `source_url` を管理者に確認してもらいます。公開済み commit にある合成規程が正本です。
Foundry IQ の `mcp://searchindex/...` は内部引用 ID の場合があります。通常の Web URL として
開けることではなく、Trace の文書 ID / category と教材の根拠文書を照合してください。

## Lab 4 assets

展開済み `portal-assets/travel-estimation.zip` と `portal-assets/preapproval-simulation.zip`
を PC から upload します。`portal-assets/travel-ops.openapi.json` の全 JSON を
**OpenAPI 3.0+ schema** に貼り付けます。この schema field は file upload ではありません。
`servers[0].url` が自分の Travel Ops API であることを確認します。

## 評価と最適化

`gpt-5.5` は Foundry IQ / evaluation / optimizer 共通の必須 deployment です。
In progress の run は再送しません。429 / timeout と score の Fail、保護機能による
`content_filter` を区別し、Trace / error details を確認します。Guardrail を弱めません。
**No supported optimization model** など対応状況の問題は管理者へ共有し、
別モデル追加や参考用 simulated assets を成功の代用にしません。

## Azure ML

- template が作成した workspace を選びます。Compute は Lab 7 にだけ作成します。
- `Standard_DS3_v2`、**Idle shutdown** enabled を確認。
- ZIP ではなく展開済み最上位 folder を **Notebooks > User files** へ **Upload folder**。
  `.workshop/context.json` を含む構成を崩しません。
- `notebooks/00-azureml-setup.ipynb` は **Python 3.10 - SDK v2**。
- setup が作る 2 kernels は **Python (Foundry Workshop)** と
  **Python (Foundry Hosted Agent)**。Labs 7/8 は後者です。
- kernel 作成失敗は setup Notebook output を確認し、解決後に page refresh。
  device code / token を Notebook に保存しません。

## Cleanup

1. Azure ML から必要な Notebook を **Export**。
2. Notebook の cleanup cell で Hosted Agent / versions を削除。
3. Compute instance を **Stop**、次に **Delete**。
4. Azure Portal の **Resource groups** で専用 RG 名と中の resources を確認。
5. **Delete resource group** で RG と resources をまとめて削除。
6. 一覧を更新し、対象 RG が削除されたことを確認。

削除が失敗したら **Activity log**、resource lock、deny assignment、残った Compute /
Hosted version を管理者と確認します。既存の共有 resource や他人の RG は削除しません。
**deployment history の削除は resources の削除ではありません。**
詳細は [Lab 9](../../labs/09-observability-cleanup.md) に従います。

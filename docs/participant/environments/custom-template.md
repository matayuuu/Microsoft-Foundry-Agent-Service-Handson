# Azure Portal — Custom template と教材の受け取り

このガイドは [Lab 1](../../../labs/01-setup.md) の準備・成功条件・再実行境界をまとめたものです。
参加者はブラウザーと PC のファイル操作だけで準備します。所要時間は新経路で未計測です。

## 実行順序

1. Azure Portal の **Resource groups > Create** で、Japan East に専用 RG を **1 個手動作成**。
2. 作成完了後に **Deploy a custom template > Build your own template in the editor > Load file**。
3. 管理者から受け取った
   [infra/azuredeploy.json](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/azuredeploy.json)
   を
   upload して **Save**。作成済み RG を選択し、**Create new** は使いません。
4. 管理者確認済みパラメーターで **Review + create > Create**。
5. Deployment Scripts の初期化と validation を含め、deployment 全体の成功を待ちます。
6. Azure ML backing Storage の **Storage browser > Blob containers > workshop-files** で
   **Microsoft Entra user account** を使い、`foundry-workshop-files.zip` を **Download**。
7. PC に 1 回取得して展開。Labs 2〜6 の Foundry Portal へ進みます。

RG は template の前提で、template が作る対象ではありません。Azure ML Compute instance も
template の対象外です。**Lab 7** の開始時に **Standard_DS3_v2** + **Idle shutdown** で
作成します。その後、最上位 folder を **Notebooks > User files** へ upload します。

## パラメーターと公開物

`location = japaneast`。`primaryModelVersion` / `evaluationModelVersion` /
`embeddingModelVersion` は、固定モデルと GlobalStandard SKU について管理者が確認した
version を入力します。`travelApiImageRef` は検証済み GHCR `@sha256:`、
`sourceRevision` は公開済みの小文字 40 桁 commit SHA を使います。

`participantObjectIdOverride` は空欄なら root deployer の object ID を使用します。
代理 deployment や別実行者の redeployment では**元の参加者本人の Entra object ID**を
明示し、bootstrap identity や代理管理者へ置き換えません。
`bootstrapRunId` は意図した初期化の再実行時だけ変更します。

標準の公開入口は管理者確認済みファイルを **Load file** する方法です。
`infra/` は教材 ZIP に含めません。上のリンクは GitHub の `dev-custom-template` 開発ブランチ
なので、管理者が公開を確認するまでは利用可能と扱わず、管理者から JSON を受け取ります。
未公開 template URL や `main` の存在しない artifact を前提にしません。
管理者の事前確認は capacity の予約ではありません。リージョン・モデル fallback はありません。

## 成功条件

- RG の **Deployments** で bootstrap を含む全体が **Succeeded**
- Deployment Scripts の検証が全て `pass`、出力の `status = complete`
- outputs の Storage account / container / blob / `source_revision` / `sha256` が揃う
- private container の ZIP が PC で正常に展開できる

失敗後にリソースが残る場合があります。成功 gate を通っていない古い ZIP や部分結果を
今回の配布物と扱いません。同じ RG・入力での再実行は管理者と診断後に行います。
一時 ACI / Azure Files Storage は成功時 cleanup、失敗時は `P1D` 保持。
専用 bootstrap identity と scoped grants は最終 RG cleanup まで保持します。

## ZIP と認証の境界

- Blob container `workshop-files` は private。公開リンク、account key、SAS は配布しません。
- Storage browser の認証は **Microsoft Entra user account**。必要なら
  **Switch to Microsoft Entra user account** を選びます。
- 参加者には RG 内の管理プレーン参照と Storage Blob Data Contributor が必要です。
- AML Storage は `allowBlobPublicAccess: false`、`defaultToOAuthAuthentication: true`。
  Shared Key は workspace 互換性のため維持しますが、ZIP の取得には使いません。
- 生成側の `.workshop/download/foundry-workshop-files.zip` には、
  `Microsoft-Foundry-Agent-Service-Handson` という最上位 folder を 1 つ格納します。
- `.workshop/context.json` の `resource_outputs.<key>.value`、live `portal-assets/`、
  `notebooks/`、Hosted source / 必要な scripts / tests を同じ folder のまま維持します。
- `setup_status = complete` と `source_revision` を確認します。秘密情報や認証キャッシュは
  含めません。
- `bundle-manifest.json` の `source_revision` と各ファイルの hash を維持します。
  bootstrap outputs の `sha256` は ZIP 全体の hash です。

## 最後の cleanup

**Export → Hosted Agent / versions 削除 → Compute Stop / Delete →
Azure Portal Delete resource group → 削除完了確認**。
RG 内の標準リソースは RG とまとめて削除します。deployment history の削除は
resource の削除ではありません。詳細は [Lab 9](../../../labs/09-observability-cleanup.md)。

## 参考

- [Deploy templates with Azure Portal](https://learn.microsoft.com/azure/azure-resource-manager/templates/deploy-portal)
- [Authorize Blob data operations in Azure Portal](https://learn.microsoft.com/azure/storage/blobs/authorize-data-operations-portal)
- [Download a block blob](https://learn.microsoft.com/azure/storage/blobs/storage-quickstart-blobs-portal#download-a-block-blob)
- [Azure ML 実行環境](azure-ml.md)

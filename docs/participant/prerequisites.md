# 参加者向け前提条件

## Azure account / permissions

- workshop 用 Azure account と subscription
- Azure Portal の **Resource groups > Create** で専用 RG を **1 個手動作成**できる権限
- 作成後の RG 内で resource の deployment / 削除と scoped role assignments を管理できる
  **Owner 相当権限**。RG 作成の権限と RG 内の RBAC 管理権限は別に確認します
- [Azure Portal](https://portal.azure.com)、[Microsoft Foundry Portal](https://ai.azure.com)、
  [Azure Machine Learning Studio](https://ml.azure.com) への access
- Storage browser に必要な管理プレーン参照権限と、対象 Storage の
  **Storage Blob Data Contributor**（template が参加者へ付与）

production subscription、既存の共有 workload RG、共有 account は使いません。
runtime managed identity に subscription-wide role を付けません。
管理者による代理 deployment / redeployment では `participantObjectIdOverride` に
**利用する参加者本人の Entra object ID**を指定してもらいます。

## 管理者から受け取るもの

- 確認済み `infra/azuredeploy.json` と専用 RG 名
- `location = japaneast`
- `primaryModelVersion`、`evaluationModelVersion`、`embeddingModelVersion` の確認済み値
- GHCR `@sha256:` 付き `travelApiImageRef`
- 公開済み commit の小文字 40 桁 hex `sourceRevision`
- 意図した再試行以外では変更しない `bootstrapRunId`

ローカル CLI は参加者の provisioning に不要です。
**RG を手動作成した後に** **Deploy a custom template > Build your own template in the editor >
Load file** を開き、作成済み RG を選択します。手順は
[Custom template guide](environments/custom-template.md) と [Lab 1](../../labs/01-setup.md) に従います。

## Quota / policy

管理者が **参加者の subscription** の Japan East で、次を確認している必要があります。

- `gpt-5.6-luna` 40K TPM、`gpt-5.5` 100K TPM、
  `embedding` / `text-embedding-3-small` 40K TPM（GlobalStandard）
- Azure AI Search **Basic**、Container Apps、monitoring、Azure ML workspace / Storage / Key Vault
- Deployment Scripts、専用 bootstrap identity、一時 ACI / Azure Files Storage
- **Lab 7** の `Standard_DS3_v2` Compute instance quota
- public endpoints と必要な outbound HTTPS、組織 Policy の適合

model catalog の表示や管理者側の成功は、自分の quota や capacity の予約ではありません。
不足時は停止して連絡します。別リージョン・モデル・SKU へ切り替えて続行しません。
Cosmos DB、Agent capability host、ACR、private networking は core の対象外です。

## PC / browser / handoff

- current English UI labels を表示できる desktop browser
- Storage browser の **Microsoft Entra user account** で private container `workshop-files` の
  `foundry-workshop-files.zip` を **Download** し、PC で展開できる
- `Microsoft-Foundry-Agent-Service-Handson` folder の `.workshop/context.json` を含む
  全体を、Lab 7 で **Notebooks > User files** へ **Upload folder** できる
- `portal-assets/*.zip` を Foundry Portal の file picker で選択できる
- `portal-assets/travel-ops.openapi.json` 全体を text editor からコピーできる

ZIP は private なまま配布します。SAS、account key、公開 Blob link は不要です。
AML Storage は Shared Key の互換性を維持しますが、ブラウザーの教材取得には Entra ID を使います。
Compute は Lab 7 まで作成せず、開始時に **Standard_DS3_v2** と **Idle shutdown** を指定します。

## Data / authentication / billing

教材の合成データだけを使います。実在する社員、顧客、予約、経費、契約、credential を
Portal、Web Search、Notebook、evaluation、trace に入力しません。Azure ML の認証で
device code が必要な場合は本人だけが認証画面へ入力し、共有・撮影しません。

モデル、Search、Hosted Agent、Storage、一時 bootstrap resources、Compute は課金対象です。
Lab 9 の **Export → Hosted cleanup → Compute Stop / Delete → Delete resource group →
削除完了確認** を実施できることを確認します。deployment history の削除だけでは resources は残ります。

## 次へ

[Lab 1 — Custom template と教材 download](../../labs/01-setup.md)

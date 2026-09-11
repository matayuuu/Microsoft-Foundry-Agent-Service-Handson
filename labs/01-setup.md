# Lab 1 — Custom template と教材 download

## ゴール

Azure Portal で専用 workload resource group を **1 個手動作成してから**、custom template
を実行します。Azure 側の Deployment Scripts が初期化・検証・教材作成まで完了したことを
確認し、private Storage の ZIP を Microsoft Entra ID で PC に 1 回 download・展開します。
参加者の事前準備にローカル CLI は不要です。この経路の所要時間は未計測です。

## 始める前に

- [参加条件](../docs/participant/prerequisites.md) と管理者指定の subscription / RG 名を確認。
- 管理者から、確認済みの
  [infra/azuredeploy.json](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/azuredeploy.json)
  ファイルと
  当日用パラメーターを受け取ります。ブラウザーに JSON が表示された場合は、HTML ではなく
  JSON 本体を PC に保存してください。
- テンプレートと、その bootstrap が取得する公開済み source revision の組合せは
  管理者が確認します。未公開ファイルへのリンク、未確認モデルバージョンや image digest
  を推測して使いません。
- RG の手動作成権限と、作成後の RG 内で scoped role assignments を作成できる
  **Owner 相当権限**が必要です。既存の共有・production RG は使用しません。

`infra/azuredeploy.json` は教材 ZIP の収録ファイルではありません。上のリンクは GitHub の
`dev-custom-template` 開発ブランチです。管理者は公開状態を確認して JSON を配布します。
未公開の場合は管理者からファイルを受け取り、`main` に同じ artifact があるとは仮定しません。

## 1. Azure Portal で専用 resource group を手動作成する

1. [Azure Portal](https://portal.azure.com) で account、directory、subscription を確認。
2. **Resource groups > Create** を開きます。
3. **Subscription** は管理者指定のもの、**Resource group** は自分専用の名前、
   **Region** は **Japan East** を選びます。
4. **Review + create > Create** を選びます。
5. 作成完了後、**Resource groups** から対象を開き、subscription、名前、location を再確認。

この workshop で手動作成する workload RG は **この 1 個だけ**です。
**この作成が完了してから**次へ進みます。テンプレート自身は RG を作りません。

## 2. 作成後に custom template を開き、JSON を読み込む

1. Azure Portal の検索から **Deploy a custom template** を開きます。
2. **Build your own template in the editor > Load file** を選びます。
3. PC の `infra/azuredeploy.json` を読み込み、**Save** を選択します。
4. **Subscription** と **Resource group** に、手順 1 で作成した RG を選びます。
   この画面の **Create new** は使いません。

手動の **Load file** が標準経路です。テンプレートを保存しただけでは deployment は始まりません。

## 3. 管理者確認済みパラメーターを入力して実行する

UI の表示名と JSON の parameter key を照合します。モデル名と capacity は固定です。

| Parameter key | 入力 |
|---|---|
| `location` | `japaneast`（Japan East） |
| `primaryModelVersion` | 管理者が `gpt-5.6-luna` / GlobalStandard 40K TPM で確認した version |
| `evaluationModelVersion` | 管理者が `gpt-5.5` / GlobalStandard 100K TPM で確認した version |
| `embeddingModelVersion` | 管理者が `text-embedding-3-small` / GlobalStandard 40K TPM で確認した version |
| `travelApiImageRef` | 管理者検証済みの GHCR image reference。`@sha256:` digest 必須 |
| `sourceRevision` | 公開済み教材 commit の小文字 40 桁 hex SHA。branch 名は入力しない |
| `participantObjectIdOverride` | 本人の初回 deployment は空欄で root deployer の object ID を使用。代理 deployment / 別実行者の redeployment は**利用する参加者本人の Entra object ID**を明示 |
| `bootstrapRunId` | 管理者指定値を維持。初期化を意図的にやり直す場合だけ変更 |

1. **Review + create** を選び、validation と対象 RG / パラメーターを確認。
2. **Create** を選択し、deployment の完了を待ちます。同じ deployment を重複送信しません。

管理者の quota / capacity 確認は予約ではありません。不足や Policy により失敗した場合は
停止して管理者へ連絡します。リージョン、モデル、SKU、image の mutable tag への
自動・手動 fallback で通しません。

## 4. bootstrap を含む成功を確認する

テンプレートは次を作成します。

- Foundry resource / project `contoso-travel`、Basic Agent Setup
- Luna 40K TPM（`gpt-5.6-luna`）、GPT-5.5 100K TPM（`gpt-5.5`）、embedding 40K TPM
- Azure AI Search **Basic**、Application Insights / Log Analytics、Container Apps Travel Ops API
- Azure ML workspace、Storage、Key Vault、scoped RBAC / connections
- bootstrap 専用 user-assigned managed identity と Deployment Scripts

Azure ML Compute instance は作成しません。**Lab 7** 開始時に作成します。
public endpoints と既存サービスの system identities を使い、Foundry / Search の
local auth は無効です。Cosmos DB、Agent capability host、ACR、private networking は追加しません。

`contoso-travel-search` は AAD Search resource connection です。
`contoso-travel-knowledge-lab-mcp` と `contoso-travel-appinsights` は
**Project Managed Identity** を使います。runtime identity に subscription role は付けません。

Deployment Scripts は専用 identity で、2 Search indexes の seed、evaluation dataset /
rubric 準備、resource / participant RBAC / API / Search の validation、
live OpenAPI / Skill assets と教材 ZIP の生成を順に実行します。
Prompt Agent、Foundry IQ knowledge base、Toolbox の作成と評価実行は後続 Lab の学習対象です。

1. RG の **Deployments** で、初期化を含む deployment 全体が **Succeeded** であることを確認。
2. Deployment Scripts の **Overview / Logs** と deployment の **Outputs** を確認。
   bootstrap の出力は `status = complete`、`container_name = workshop-files`、
   `blob_name = foundry-workshop-files.zip`、実際の `source_revision` と `sha256` を含みます。
3. validation の全 check が `pass` であることを確認します。
   リソースが作成されたことだけを初期化成功とみなしません。

一時 ACI / Azure Files Storage は `OnSuccess` で削除され、失敗時は `P1D` の有限保持です。
bootstrap identity と scoped grants は再実行のため RG 削除まで残ります。
失敗した deployment は自動 rollback ではなく、部分的なリソースが残り得ます。
失敗時は [トラブルシューティング](../docs/participant/troubleshooting.md) に進み、
新規 ZIP の成功扱いや無制限の再実行はしません。

## 5. Storage browser で private ZIP を 1 回 download する

1. deployment の outputs で `storage_account_name` を確認し、同じ RG の Storage account を開く。
2. **Storage browser > Blob containers > workshop-files** を開く。
3. 認証方式が **Microsoft Entra user account** であることを確認。
   表示が Access key なら **Switch to Microsoft Entra user account** で切り替えます。
4. private container 内の `foundry-workshop-files.zip` を選び、**Download**。
5. PC の download 完了を確認。正常時はこの ZIP を **1 回だけ**取得します。

403 の場合は account / participant object ID / scoped data role の反映を確認してもらいます。
account key、SAS、公開 container、直接の公開 Blob URL へ切り替えません。
Storage は `allowBlobPublicAccess: false`、`defaultToOAuthAuthentication: true` です。
Azure ML の互換性のため Shared Key は維持されますが、教材の取得には使いません。

生成側の ZIP パスは `.workshop/download/foundry-workshop-files.zip` です。
これは Azure 側の packaging path であり、Portal の download 欄へ入力するパスではありません。

## 6. PC で展開し、handoff を確認する

最上位 folder が `Microsoft-Foundry-Agent-Service-Handson` であることを確認します。
隠し folder の `.workshop` を含め、次の構成を維持します。

```text
Microsoft-Foundry-Agent-Service-Handson/
  bundle-manifest.json
  .workshop/context.json
  portal-assets/portal-values.json
  portal-assets/travel-ops.openapi.json
  portal-assets/travel-estimation.zip
  portal-assets/preapproval-simulation.zip
  labs/
  notebooks/00-azureml-setup.ipynb
  notebooks/07-agent-framework-harness.ipynb
  notebooks/08-hosted-agent.ipynb
  src/hosted-agent/
  scripts/
  tests/
```

`.workshop/context.json` を text editor で開き、`provisioning_method = azure-custom-template`、
`setup_status = complete`、`source_revision` が配布された SHA と一致することを確認。
値は必ず **`resource_outputs.<key>.value`** から読みます。
`bundle-manifest.json` の `source_revision` も同じ SHA であることを確認します。
manifest は各収録ファイルの hash を持ちます。bootstrap outputs の `sha256` は **ZIP 全体**の
hash なので、必要に応じて管理者が取得した ZIP の hash と照合します。
token、credential、`.env`、認証キャッシュを教材として追加しません。

Labs 2〜6 は Foundry Portal で進めます。Lab 4 はこの `portal-assets/` を使用します。
Azure ML への folder upload と kernel 準備は Lab 7 です。

## 完了チェック

- RG を手動作成後に template を開き、同じ既存 RG へ deploy した
- bootstrap と validation を含む deployment が成功し、`status = complete`
- private `workshop-files` から Entra ID で ZIP を 1 回 download・展開した
- `.workshop/context.json` の `resource_outputs.<key>.value` と revision を確認した
- Compute はまだ作成していない

## 次の Lab

[Lab 2 — Prompt Agent](02-prompt-agent.md)

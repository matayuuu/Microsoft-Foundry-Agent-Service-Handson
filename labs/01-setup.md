# Lab 1 — Cloud Shell provisioning と download（10〜15分）

## ゴール

永続化済み Azure Cloud Shell Bash で workload resource group を 1 個作り、Terraform
provisioning、bootstrap、validation を完了します。最後に生成された ZIP を PC へ 1 回だけ
download し、直ちに Cloud Shell を終了します。

**10〜15分**が participant target です。**8〜10分**は準備済み/warm の best case です。
初回 Cloud Shell の Storage 作成と mount 確認はこの Lab に含めますが、計測はその完了後に
開始します。

## 0. 初回 Cloud Shell Storage と永続 clouddrive を準備

Azure Portal で Cloud Shell を初めて開いた場合は、次の標準 UI だけを使います。

1. **Bash** を選択。
2. **Mount storage account** を選択。
3. workshop subscription を選び、**Apply**。
4. **We will create a storage account for you** を選び、**Next**。
5. Cloud Shell が専用 Storage resource group、Storage account、Azure Files share を
   自動作成し、Bash prompt が表示されるまで待つ。

advanced settings で既存 storage を手入力しません。作成と mount が完了してから
10〜15分の計測を開始します。

既に Cloud Shell Storage がある場合は新しく作り直さず、既存の Azure Files-backed
`~/clouddrive` を再利用します。現在の Cloud Shell では `$HOME` のうち `clouddrive` の外側は
session-local です。次の provisioning を始める前に `clouddrive` が正常に mount されている
ことを確認します。

> [!CAUTION]
> **Azure Files mount に失敗した、`clouddrive` が read-write CIFS mount ではない、または
> ephemeral session と表示された場合は停止してください。** provisioning を開始せず、
> 講師/管理者へ連絡します。repository、`.workshop`、Terraform state を `clouddrive` の
> 外側へ置かないでください。

![Mount storage account と subscription を選択する実画面](../docs/images/lab01-cloud-shell-storage.png)

![Cloud Shell が Storage account を作成する実画面](../docs/images/lab01-cloud-shell-create-storage.png)

## 1. Azure Cloud Shell Bash と subscription を確認

Section 0 から続く Cloud Shell **Bash**、または再度開いた Bash で、作成または再利用した
healthy persistent `~/clouddrive` が mount されていることを確認します。Cloud Shell の既定
subscription が workshop subscription とは限らないため、講師指定の ID を設定し、Azure CLI
の既定 context を明示的に切り替えます。

```bash
SUBSCRIPTION_ID="<講師指定の subscription ID>"

az account set --subscription "$SUBSCRIPTION_ID"

az account show \
  --query "{subscription:id,name:name,user:user.name}" \
  --output table
```

表示された `subscription` が `SUBSCRIPTION_ID` と一致しない場合は続行しません。
`SUBSCRIPTION_ID` 変数を設定しただけでは Azure CLI の既定 context は変わらないため、
`az account set` を省略しません。token、device code、credential を出力・共有しません。

正しい account/subscription を確認後、この Bash session で使う残りの値を設定します。

```bash
RESOURCE_GROUP="<講師指定のリソース グループ名>"
LOCATION="japaneast"
```

`RESOURCE_GROUP` の placeholder は、講師から指定された workshop 専用 name に置き換えます。

## 2. workload resource group を 1 個作る

同じ Cloud Shell Bash で Azure CLI を実行します。

```bash
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --subscription "$SUBSCRIPTION_ID" \
  --query "{resourceGroup:name,location:location,state:properties.provisioningState}" \
  --output table
```

resourceGroup が `$RESOURCE_GROUP`、location が `japaneast`、state が `Succeeded` である
ことを確認します。この Lab で作る workload resource group はこの 1 個だけです。

Cloud Shell storage resource group は workload resource group とは別 lifecycle です。
初回 UI が作成する storage を workload resource group 内へ移動しません。

## 3. repository を永続 clouddrive へ shallow clone

repository、`.workshop`、Terraform state を session 間で保持するため、Azure Files-backed
`clouddrive` の下へ clone します。`~/Microsoft-Foundry-Agent-Service-Handson` など
`clouddrive` の外側へ clone しません。

```bash
cd ~/clouddrive
git clone --depth 1 --branch main --single-branch \
  https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson.git
cd Microsoft-Foundry-Agent-Service-Handson
```

既に `~/clouddrive/Microsoft-Foundry-Agent-Service-Handson` がある場合は、講師が指定した
revision であることを確認し、新しい clone を重ねません。

## 4. 軽量 provisioning environment

```bash
bash scripts/setup-cloud-shell.sh &&
  source scripts/activate-cloud-shell.sh
```

最初の command は built-in Python 3.12 を使う provisioning-only virtual environment を
session-local `$HOME/.cache` に準備します。repository と Terraform state は `clouddrive` に残ります。
新しい Cloud Shell session ではこの command を再実行します。成功メッセージに
**No Jupyter, notebook kernels, Hosted Agent environment, Graphviz, or web preview was
installed** と表示されます。

storage validation が失敗したら、その安全な拒否を回避しません。`clouddrive` の外側へ
repository や state を作らず、ここで停止します。最初の command が失敗した場合は
`source scripts/activate-cloud-shell.sh` や `scripts/setup.sh` を実行しません。

## 5. Terraform provisioning

```bash
./scripts/setup.sh \
  --subscription "$SUBSCRIPTION_ID" \
  --resource-group "$RESOURCE_GROUP"
```

plan に自分の workload resource group だけが表示されることを確認して承認します。
処理中は同じ command を再送しません。Terraform は次を作成します。

- Foundry resource / project `contoso-travel` と Basic Agent Setup
- Luna 40K TPM、GPT-5.5 100K TPM、embedding 40K TPM
- Azure AI Search、monitoring、Container Apps Travel Ops API
- scoped RBAC と managed-identity connections
- Azure ML workspace、Storage、Key Vault、workspace-based Application Insights

Azure ML Compute instance は作成しません。Lab 7 で必要になった時点で作成します。
Travel Ops API image は setup が immutable digest を解決して pin し、mutable tag へ
fallback しません。public endpoints と system identities を使い、Foundry/Search の local
authentication は無効です。Cosmos DB、Agent capability host、ACR、private networking は
追加しません。

connections は direct Search／knowledge source 用の `contoso-travel-search`、
Foundry IQ MCP 用の `contoso-travel-knowledge-lab-mcp`、trace 用の
`contoso-travel-appinsights` です。後ろの 2 つは **Project Managed Identity** を使います。
Terraform が作る scoped RBAC:

| Principal | Scope | Roles |
|---|---|---|
| Participant | Foundry account / project | Foundry User; Foundry Project Manager |
| Participant | Search / monitoring | Search Service Contributor; Search Index Data Contributor; Log Analytics Reader; Privileged Monitoring Data Reader |
| Project MI | Foundry / Search / monitoring | Foundry User; both Search contributor roles; Monitoring Metrics Publisher; Log Analytics Reader; Privileged Monitoring Data Reader |
| Search MI | Foundry account | Cognitive Services OpenAI User |

setup は 2 Search indexes を seed し、evaluation assets を準備し、resources を検証し、
live OpenAPI / Skill assets と canonical `resource_outputs` context を作成します。

成功時は terminal の **Environment validation report** が **Overall status: pass** となり、
resource、RBAC、Travel Ops API、2 Search indexes の全 check が `pass` になります。画像では
なく、実行した terminal の結果を確認してください。

成功時は次のファイルが 1 個だけ download 対象として表示されます。

```text
.workshop/download/foundry-workshop-files.zip
```

ZIP には non-secret context、Portal assets、Notebooks、Hosted Agent source が含まれます。
Terraform state、token、`.env`、credential は含まれません。

## 6. 1 回だけ download して exit

1. Cloud Shell toolbar の **Manage files > Download**。
2. setup output に表示された
   `.workshop/download/foundry-workshop-files.zip` の absolute path を入力。
3. PC への download 完了を確認。
4. Terminal で直ちに実行:

```bash
exit
```

![Manage files から Download を選択する実画面](../docs/images/lab01-cloud-shell-download.png)

Cloud Shell で ZIP を展開したり、Notebook、Jupyter、Graphviz、web preview、Hosted
environment を起動したりしません。`exit` により tenant slot を解放します。

## 7. PC で展開

download した ZIP を PC で展開し、最上位 folder に `.workshop/context.json`、
`portal-assets/`、`labs/`、`notebooks/`、`src/` があることを確認します。
Labs 2〜6 は Foundry Portal で進め、Lab 4 はこの `portal-assets/` を使います。

## 完了チェック

- persistent `clouddrive` validation が pass
- Terraform / bootstrap / validation が成功
- `.workshop/context.json` の key が `resource_outputs`
- PC に ZIP を 1 回 download・展開
- Cloud Shell で `exit` 済み

## 次の Lab

[Lab 2 — Prompt Agent](02-prompt-agent.md)

# Azure Cloud Shell — provisioning / download only

Azure Cloud Shell Bash は Lab 1 の provisioning と 1 回の ZIP download、Lab 9 の destroy
だけに使います。Notebook、Jupyter、Graphviz、web preview、Hosted Agent environment は
実行しません。

## 必須の persistent clouddrive

初回起動では Cloud Shell の標準 UI で **Bash**、**Mount storage account**、workshop
subscription、**Apply**、**We will create a storage account for you**、**Next** の順に選び、
Storage account と Azure Files share を自動作成させます。Bash prompt が表示されたら
Azure Files-backed `~/clouddrive` を正常に mount できることを確認します。既存 storage が
ある場合は新規作成せず再利用します。repository、`.workshop`、Terraform state は
`clouddrive` 配下に置きます。`clouddrive` 外の `$HOME` と provisioning-only virtual
environment は session-local です。

Storage 作成と mount 確認は Lab 1 に含まれますが、10〜15分の計測はその完了後に開始します。
詳細は Microsoft Learn の
[Get started with Azure Cloud Shell using persistent storage](https://learn.microsoft.com/azure/cloud-shell/get-started/new-storage)
を参照してください。

> [!CAUTION]
> Azure Files mount failure、ephemeral session、`clouddrive` の read-only/non-CIFS mount の
> いずれかなら**停止**します。`setup-cloud-shell.sh` の refusal を回避せず、provisioning
> しません。

## Lab 1 commands

Cloud Shell の既定 subscription が workshop subscription とは限りません。変数を設定する
だけでは Azure CLI の既定 context は変わらないため、`az account set` を省略しません。

```bash
SUBSCRIPTION_ID="<講師指定の subscription ID>"
az account set --subscription "$SUBSCRIPTION_ID"
az account show \
  --query "{subscription:id,name:name,user:user.name}" \
  --output table
RESOURCE_GROUP="<講師指定のリソース グループ名>"
LOCATION="japaneast"
az group create \
  --name "$RESOURCE_GROUP" \
  --location "$LOCATION" \
  --subscription "$SUBSCRIPTION_ID" \
  --query "{resourceGroup:name,location:location,state:properties.provisioningState}" \
  --output table
cd ~/clouddrive
git clone --depth 1 --branch main --single-branch \
  https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson.git
cd Microsoft-Foundry-Agent-Service-Handson
bash scripts/setup-cloud-shell.sh &&
  source scripts/activate-cloud-shell.sh &&
  ./scripts/setup.sh \
    --subscription "$SUBSCRIPTION_ID" \
    --resource-group "$RESOURCE_GROUP"
```

`setup-cloud-shell.sh` は provisioning-only dependencies だけを session-local
`$HOME/.cache` に用意します。setup 完了後、**Manage files > Download** で次を PC へ
1 回取得します。

```text
.workshop/download/foundry-workshop-files.zip
```

download 完了直後に `exit` します。

## Lab 9 return

同じ persistent `clouddrive` repository、`.workshop`、Terraform state を再利用します。
Python virtual environment は session-local なので setup を再実行します。

```bash
cd ~/clouddrive/Microsoft-Foundry-Agent-Service-Handson
bash scripts/setup-cloud-shell.sh &&
  source scripts/activate-cloud-shell.sh &&
  ./scripts/destroy.sh
```

activation が stale / missing、state がない、`clouddrive` を検証できない場合は destroy を
推測で進めず、troubleshooting を確認します。workload resource group の削除確認後に
`exit` します。

## Storage lifecycle

Cloud Shell storage は workload resource group の外です。Lab 9 の destroy では削除されません。
専用 storage だった場合だけ、workload cleanup 成功後、組織 policy と管理者の許可に従って
別途削除します。既存共有 storage や他用途の file share を削除しません。

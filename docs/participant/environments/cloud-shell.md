# Azure Cloud Shell — provisioning / download only

Azure Cloud Shell Bash は Lab 1 の provisioning と 1 回の ZIP download、Lab 9 の destroy
だけに使います。Notebook、Jupyter、Graphviz、web preview、Hosted Agent environment は
実行しません。

## 必須の persistent HOME

初回起動では Cloud Shell の標準 UI で **Bash**、**Mount storage account**、workshop
subscription、**Apply**、**We will create a storage account for you**、**Next** の順に選び、
Storage account と Azure Files share を自動作成させます。Bash prompt が表示されたら
Azure Files-backed persistent HOME を正常に mount できることを確認します。既存 storage が
ある場合は新規作成せず再利用します。repository、`.venv`、`.workshop`、Terraform state は
persisted Unix HOME 配下に置き、`clouddrive` 直下には置きません。

Storage 作成と mount 確認は Lab 1 に含まれますが、10〜15分の計測はその完了後に開始します。

> [!CAUTION]
> Azure Files mount failure、HOME backing image の未検出、ephemeral session、read-only mount
> のいずれかなら**停止**します。`setup-cloud-shell.sh` の refusal を回避せず、provisioning
> しません。current rehearsal でも mount failure を検出して安全に拒否したため、これは
> 想定された protection です。

## Lab 1 commands

```bash
cd ~
git clone --depth 1 --branch main --single-branch \
  https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson.git
cd Microsoft-Foundry-Agent-Service-Handson
bash scripts/setup-cloud-shell.sh
source scripts/activate-cloud-shell.sh
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>"
```

`setup-cloud-shell.sh` は provisioning-only dependencies だけを用意します。setup 完了後、
**Manage files > Download** で次を PC へ 1 回取得します。

```text
.workshop/download/foundry-workshop-files.zip
```

download 完了直後に `exit` します。

## Lab 9 return

同じ persistent HOME、同じ repository、同じ `.workshop` と Terraform state を再利用します。

```bash
cd ~/Microsoft-Foundry-Agent-Service-Handson
source scripts/activate-cloud-shell.sh
./scripts/destroy.sh
exit
```

activation が stale / missing、state がない、HOME を検証できない場合は destroy を推測で
進めず、troubleshooting を確認します。

## Storage lifecycle

Cloud Shell storage は workload resource group の外です。Lab 9 の destroy では削除されません。
専用 storage だった場合だけ、workload cleanup 成功後、組織 policy と管理者の許可に従って
別途削除します。既存共有 storage や他用途の HOME を削除しません。

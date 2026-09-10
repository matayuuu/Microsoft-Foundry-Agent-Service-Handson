# 参加者向け前提条件

## Azure account

- workshop subscription と Azure account
- Azure Portal で workload resource group を 1 個作成・削除できる権限
- その resource group 内で Terraform resources と scoped role assignments を管理できる
  Owner 相当権限
- [Azure Portal](https://portal.azure.com)、[Microsoft Foundry Portal](https://ai.azure.com)、
  [Azure ML Studio](https://ml.azure.com) への access

production subscription、共有 workload resource group、共有 account は使いません。

## Cloud Shell persistent storage

Azure Cloud Shell Bash の初回起動時は標準 UI の **Mount storage account** と
**We will create a storage account for you** を使い、persistent Storage を自動作成させます。
既存 storage がある場合は再利用します。どちらも Azure Files-backed persistent HOME が
正常に mount されたことを確認してから provisioning を始めます。作成と mount の手順は
Lab 1 に含めますが、10〜15分の計測はその完了後に開始します。

> [!CAUTION]
> Azure Files mount failure、HOME backing image を確認できない、ephemeral session、
> read-only mount の場合は Lab 1 を開始しません。安全な refusal を回避せず、管理者へ
> 連絡してください。`clouddrive` の存在だけでは永続 HOME の証明になりません。

repository、`.workshop`、Terraform state を保持できる空き容量と、GitHub / package sources /
GHCR への HTTPS access が必要です。

## Quota / policy

Japan East で次を作成できることを管理者が確認済みである必要があります。

- `gpt-5.6-luna` 40K TPM
- `gpt-5.5` 100K TPM
- `embedding` (`text-embedding-3-small`) 40K TPM
- Azure AI Search Basic、Container Apps、Azure ML workspace backing resources
- Lab 7 の `Standard_DS3_v2` Compute instance

model catalog の表示だけでは quota を証明しません。private networking、Cosmos DB、
Agent capability host、ACR は core workshop の scope 外です。

## PC / browser

- Cloud Shell の **Manage files > Download** で ZIP を保存・展開できる
- 展開した folder を Azure ML **User files** へ upload できる
- `portal-assets/*.zip` を Foundry Portal file picker で選択できる
- current English UI labels を表示できる desktop browser

## Data / authentication / billing

教材の合成データだけを使います。実在する社員、顧客、予約、経費、契約、credential を
Portal、Web Search、Notebook、evaluation、trace に入力しません。device code は本人だけが
認証画面へ入力し、共有・撮影しません。

Azure resources、persistent storage、models、Search、evaluation、Hosted Agent は課金対象です。
Lab 9 で Compute、Terraform resources、workload resource group を削除できることを確認します。

## 次へ

[Cloud Shell provisioning guide](environments/cloud-shell.md)

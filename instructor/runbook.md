# Instructor runbook

## Capacity planning

Azure Cloud Shell の tenant limit は既定 **20 concurrent users** です。既存利用と承認済み上限を
含めて開催可能性を判断します。participant 手順には capacity scheduling を記載しません。

Lab 1 target は 10〜15分、8〜10分は prepared/warm best case です。rehearsal reference:
Cloud Shell start 35.5秒、shallow clone 1.55秒、provisioning-only venv initial install
18.85秒、prior Terraform + bootstrap 6分42秒。初回 Cloud Shell の標準 UI による Storage
作成は Lab 1 に記載しますが、計測は mount 確認後に開始します。

## Before the event

1. 初回 participant は標準 UI に Cloud Shell Storage を自動作成させ、全 participant の
   Azure Files-backed `clouddrive` を mount/reconnect test。
2. repository/state が `clouddrive` 配下にあり、session-local `$HOME` のみにないことを確認。
3. current rehearsal の mount failure と safe ephemeral refusal を再現し、Azure resources が
   作成されないことを確認。
4. required providers、Storage shared-key/public access policy、Key Vault RBAC を確認。
5. Japan East で Luna 40K、GPT-5.5 100K、embedding 40K、Search Basic、
   `Standard_DS3_v2` capacity を実 deployment で確認。
6. GitHub、GHCR、package sources、Azure endpoints への HTTPS を確認。
7. budget / alert、cleanup owner、incident path を決める。

## Lab 1 rehearsal

- Azure CLI で workload RG を 1 個だけ作成。
- `clouddrive` へ shallow clone → `setup-cloud-shell.sh` → source activation → `setup.sh`。
- Terraform creates Foundry/models/Search/monitoring/API/RBAC/connections/Azure ML workspace,
  but no Compute.
- bootstrap seeds two indexes/evaluation assets and validates resources.
- exactly one `.workshop/download/foundry-workshop-files.zip`。
- **Manage files > Download** once、download completion、immediate `exit`。
- ZIP excludes state/credentials and includes `resource_outputs`, live `portal-assets`, notebooks/source。

Lab 1 の screenshot は resource group、Cloud Shell storage、single download、validation だけを
使います。automated Foundry/Search/Container/RBAC/model creation の手動 UI screenshot は
使いません。

## Labs 2–6

すべて Foundry Portal で実施します。Lab 4 の Skill ZIP / OpenAPI JSON は PC に展開した
`portal-assets/` を使います。Cloud Shell を開き直さず、Azure ML Compute もまだ作りません。
evaluation は 7 synthetic rows、optimizer candidate は 1。実行中の run を再送しません。

## Labs 7–8

Terraform-created Azure ML workspace を開き、`Standard_DS3_v2` + Idle shutdown の Compute
を作成。展開済み top-level folder を **User files** へ upload。
`notebooks/00-azureml-setup.ipynb` を **Python 3.10 - SDK v2** で実行して 2 kernels を作り、
Labs 7/8 は **Python (Foundry Hosted Agent)** を使用します。

Lab 7 は plain / Harness Agent、Lab 8 は intake / policy / reviewer sequential workflow。
Lab 8 は Lab 7 session state に依存しません。

## Incident boundaries

- mount/home validation failure は hard stop。symlink、一時 storage、fresh clone で回避しない。
- secret/device code/real data の共有を止め、組織 incident process を使う。
- quota/Policy failure で model/security baseline を変更しない。
- state を失った participant は parent resources を Portal で先に削除しない。

## Cleanup roll call

participant ごとに:

1. Notebook Export。
2. Hosted Agent / versions delete。
3. Compute Stop、Delete。
4. same persistent `clouddrive` repository/state。
5. setup rerun、source activation、`./scripts/destroy.sh`。
6. workload RG empty を確認。
7. Portal **Delete resource group**、Cloud Shell `exit`。
8. Cloud Shell storage は dedicated + policy permitted の場合だけ別 lifecycle で処理。

browser close、Cloud Shell exit、Compute Stop だけを cleanup 完了扱いにしません。

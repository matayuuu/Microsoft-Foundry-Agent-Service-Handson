# 参加者向けトラブルシューティング

## Cloud Shell storage validation が失敗

> [!CAUTION]
> **provisioning を開始しません。** Azure Files mount failure、ephemeral HOME、
> backing image 未検出、read-only mount は安全な stop condition です。現在の rehearsal
> でも mount failure を検出し、script が Azure 変更前に拒否しました。

- 初回起動なら標準 UI の **Mount storage account** による自動作成が完了したか確認。
- Cloud Shell storage settings と Azure Files share の状態を管理者に確認。
- Storage `publicNetworkAccess` / `allowSharedKeyAccess` を組織 policy と照合。
- repository は persisted HOME 配下、`clouddrive` 直下ではないことを確認。
- 一時 folder、別 shell、symlink で check を回避しない。
- `.workshop` / Terraform state を削除して再試行しない。

## `setup-cloud-shell.sh` / activation

- Azure Cloud Shell **Bash** であることを確認。
- built-in Python 3.12、Terraform 1.10+、`az`、`jq`、`curl`、`git` が必要。
- 各新規 terminal で repository に移動し
  `source scripts/activate-cloud-shell.sh`。
- readiness marker が stale の場合は persistent HOME の同じ repository で
  `bash scripts/setup-cloud-shell.sh` を再実行。

Jupyter、Graphviz、Hosted Agent dependencies、web preview を追加しません。

## setup / Terraform

- `az account show` が指定 subscription/account か確認。
- plan scope が専用 workload resource group 内だけか確認。
- provider、quota、Policy、role assignment failure は管理者へ共有。
- running command を重複実行しない。
- model catalog の表示を quota 成功とみなさない。
- failure 後も `.workshop/terraform-inputs.json` と state を保持して同じ setup を再実行。

## download

setup が表示する absolute path の
`.workshop/download/foundry-workshop-files.zip` だけを
**Manage files > Download** で 1 回取得します。空/不完全なら `exit` 前に setup output を
確認します。成功後は直ちに `exit`。Cloud Shell で展開や Notebook 実行をしません。

## Foundry Portal

- account/project は setup output の names と一致させます。
- `.workshop/context.json` は `resource_outputs` を持つことを確認。
- connection は `contoso-travel-search` / `contoso-travel-knowledge-lab-mcp` /
  `contoso-travel-appinsights`。
- 403 は role scope/principal と propagation を確認し、broad role や key で回避しない。
- evaluation / optimizer が In progress の間は再送しない。

## Lab 4 assets

PC に展開した `portal-assets/travel-estimation.zip` と
`portal-assets/preapproval-simulation.zip` を upload します。
`portal-assets/travel-ops.openapi.json` は text editor で開き、JSON 全体を Portal の
**OpenAPI 3.0+ schema** field へ貼り付けます。schema field は file upload ではありません。

## Azure ML

- Terraform-created workspace を選ぶ。
- Compute は `Standard_DS3_v2`、Idle shutdown enabled。
- ZIP ではなく展開済み最上位 folder を **User files** へ upload。
- `notebooks/00-azureml-setup.ipynb` は built-in **Python 3.10 - SDK v2**。
- Labs 7/8 は **Python (Foundry Hosted Agent)**。
- kernel 作成失敗時は setup Notebook output を確認し、page refresh。Cloud Shell に戻って
  Notebook を実行しない。

## Cleanup

1. Azure ML から必要な Notebook を Export。
2. Hosted Agent / data-plane children を削除。
3. Compute instance を Stop、次に Delete。
4. 同じ persistent Cloud Shell HOME / repository / state を開く。
5. `source scripts/activate-cloud-shell.sh`、`./scripts/destroy.sh`。
6. workload resource group が空であることを確認し、Azure Portal で Delete。
7. `exit`。

`destroy.sh` が `Application Insights Smart Detection` action group の削除を表示する場合が
あります。これは Azure が Application Insights とともに自動作成した resource で、正常な
cleanup の一部です。

state や persistent HOME が見つからない場合は、推測で parent resources を先に消さず
管理者へ連絡します。Cloud Shell storage は別 lifecycle です。

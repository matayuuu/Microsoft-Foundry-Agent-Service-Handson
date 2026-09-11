# Azure ML — Labs 7〜8 の準備

**Lab 7 の開始時にだけ**実施します。Lab 1 で作成されたワークスペースと、PC に展開した教材を使います。

## 1. Compute を作る

1. [Azure ML Studio](https://ml.azure.com) で自分のワークスペースを開きます。
2. **Compute > Compute instances > New** を選びます。
3. **Virtual machine type = CPU**、サイズ **Standard_DS3_v2** を選びます。
4. **Idle shutdown** を有効にし、**30 minutes** に設定して作成します。

## 2. 教材フォルダーをアップロードする

**Notebooks > User files > Upload folder** で、展開済みの最上位フォルダー
`Microsoft-Foundry-Agent-Service-Handson` を選びます。
ZIP のままではなく、隠しフォルダー `.workshop` を含む全体をアップロードしてください。
`notebooks/`、`src/`、`scripts/`、`tests/` の配置は変えません。

## 3. カーネルを準備する

1. `notebooks/00-azureml-setup.ipynb` を **Python 3.10 - SDK v2** で開き、セルを上から実行します。
2. 画面を更新し、次の 2 つが選べることを確認します。
   - **Python (Foundry Workshop)**
   - **Python (Foundry Hosted Agent)**
3. **Labs 7〜8 は Python (Foundry Hosted Agent)** を選びます。

エラーのセルを飛ばさないでください。再起動後は、必要なセルを上から実行し直します。

## 4. 認証が必要な場合

Azure ML の **Terminal** で実行し、管理者指定のサブスクリプションを選びます。

```bash
az login --use-device-code
az account set --subscription "<subscription-id>"
```

認証コードやトークンは、ノートブックに保存したり他の人へ共有したりしません。

準備ができたら [Lab 7](../../../labs/07-agent-framework-harness.md) へ進みます。
終了時の保存・削除は [Lab 9](../../../labs/09-observability-cleanup.md) に従ってください。

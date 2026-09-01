# Lab 1 — 環境構築（20分）

## ゴール

割り当てられた既存 resource group に、ハンズオン用の Foundry project と関連 resource
を構築します。

## 事前に用意する値

| 値 | 入手先 |
|---|---|
| `<subscription-id>` | 講師または管理者 |
| `<resource-group>` | 講師または管理者 |

詳しい条件は
[参加者向け前提条件](../docs/participant/prerequisites.md)を確認してください。

## 1. Azure にサインインする

Codespace の terminal で実行します。

```bash
az login --use-device-code
az account show --query "{subscriptionId:id, user:user.name}" -o table
```

表示された subscription が、割り当てられたものと一致することを確認します。

## 2. 事前確認を実行する

```bash
./scripts/preflight.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>"
```

`overall_status` が `pass` なら次へ進みます。`fail` の場合は setup を実行せず、
[トラブルシューティング](../docs/participant/troubleshooting.md#preflight--setup)を確認してください。

## 3. 環境を構築する

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>"
```

この処理は再実行できます。途中で失敗した場合も Terraform state や
`.workshop/` を手動で削除しないでください。

Azure AI Search の作成で `InsufficientResourcesAvailable` が表示された場合だけ、
別 region を指定して同じ setup を再実行します。

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --location swedencentral
```

## 4. 完了を確認する

成功時は account、project、Travel Ops API と `.workshop/context.json` が表示されます。
Lab 5 / 6 で使う合成 dataset と rubric evaluator も、この setup で登録されます。

```bash
jq -r '
  .terraform_outputs
  | {
      account: .ai_services_account_name.value,
      project: .foundry_project_name.value,
      search: .search_service_name.value,
      travel_api: .travel_api_fqdn.value
    }
' .workshop/context.json

curl -s "https://$(jq -r '.terraform_outputs.travel_api_fqdn.value' \
  .workshop/context.json)/health"
```

`"status":"ok"` が返れば構築完了です。

1. setup の出力にある `https://ai.azure.com` を開きます。
2. 表示された account と project を選びます。
3. Portal の表示言語を **English** にします。

## 次の Lab

[Lab 2 — Prompt Agent](02-prompt-agent.md)

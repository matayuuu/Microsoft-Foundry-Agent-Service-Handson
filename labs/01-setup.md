# Lab 1 — 環境構築（20分）

## 前提

このハンズオンの参加者向け前提条件は
[docs/participant/prerequisites.md](../docs/participant/prerequisites.md) に
まとまっています。要点だけ再掲すると:

- 参加者に必要なのは `az login` と、**既存の** resource group への **Owner** ロールだけです。
  resource group の作成・削除、resource provider 登録、subscription 単位の quota/policy
  変更は一切行いません（行う必要もありません）。
- subscription ID・resource group 名・`--travel-api-image-ref` の値は、ワークショップの
  管理者から個別に受け取ります。**このファイルにはその値を書きません** — 常にご自身が
  受け取った値をコマンドに渡してください。
- 管理者側の前提条件（resource provider 登録、model quota）が完了していることが前提です。
  完了していない場合は、このファイルの次のセクションにある `preflight.sh` が失敗します。

前提条件の詳細や「困ったら」の連絡先は上記ページに従い、ここでは実行手順と検証に集中します。

## 1. サインイン

```bash
az login --use-device-code
az account show --query "{subscriptionId:id, name:name, user:user.name}" -o table
```

表示された `subscriptionId` が、管理者から受け取ったものと一致することを確認してください。

## 2. `preflight.sh`（読み取り専用の事前確認）

```bash
./scripts/preflight.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  [--location eastus2]
```

このスクリプトは何も変更しません。実施する確認は:

- 指定した resource group に対して、あなたの identity が実際に Owner を持っているか。
- 指定した region（既定 `eastus2`。要件を満たさない場合は `swedencentral` に自動フォールバック）
  に必要な resource provider が登録済みで、必要な model quota/capacity が十分にあるか。
- Lab 6 の Agent Optimizer で使う、実際に利用可能な `gpt-5` 系 model のバージョンを発見する
  （後続の `setup.sh` はこの発見結果をそのまま使うため、バージョンを推測する必要はありません）。

**終了コードが 0 以外の場合は `setup.sh` に進まないでください。** 報告された詳細を読み、
subscription 単位の問題を指している場合は
[管理者向けトラブルシューティング](../docs/admin/troubleshooting.md)へ、
参加者側の問題（Owner ロール不足など）の場合は
[参加者向けトラブルシューティング](../docs/participant/troubleshooting.md)へ進んでください。

## 3. `setup.sh`（構築）

`preflight.sh` が成功したら、実際の構築を行います。

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --travel-api-image-ref "<ghcr-image-ref>@sha256:<digest>" \
  [--location eastus2]
```

このコマンドは 1 回の実行で次の 5 ステップを順に行います（途中で失敗しても再実行可能です。
`terraform apply` は同じ状態に収束し、データ投入は id ベースの merge-or-upload なので
二重投入されません）。

1. `preflight.sh` を再実行し、`overall_status` が `fail` なら中断します。
2. `infra/` に対して `terraform init` / `plan` / `apply`（`--auto-approve` を渡さない限り、
   apply 前に確認プロンプトが出ます）。
3. `scripts/bootstrap_data.py` で `data/manifest.json` の内容を Azure AI Search に投入します。
4. `scripts/validate_environment.py` で構築結果を検証します。
5. 非機密の `.workshop/context.json` と `.workshop/.env` を書き込み、Portal リンクを表示します。

成功すると、次のような出力が表示されます（値は環境ごとに異なります）。

```text
Setup complete.

Foundry portal:   <foundry_portal_url>
  Account:        <ai_services_account_name>
  Project:        <foundry_project_name>
  (No officially confirmed direct deep-link URL format was found; open the
  portal above and select the account/project by name.)

Travel Ops API:   https://<travel_api_fqdn>

Non-secret context written to:
  .workshop/context.json
  .workshop/.env
```

> [!NOTE]
> Foundry portal への直接ディープリンク URL 形式は公式に確認できていないため、
> `setup.sh` は portal のトップ URL と account/project 名だけを表示します。portal を開いたら
> 表示された account 名・project 名を自分で選択してください。

## 4. リソースと link の検証

以降の Lab では、参加者固有の値（resource group 名、subscription ID、生成された FQDN、
ハッシュ付きリソース名など）を本文に決め打ちしません。代わりに、必ず自分の
`.workshop/context.json` を参照します。

```bash
jq '.terraform_outputs | keys' .workshop/context.json
```

以下のキーが揃っていることを確認してください（`infra/outputs.tf` が定義する全 output）。

| キー | 用途 |
|---|---|
| `resource_group_name` / `location` | 構築先 resource group と region |
| `ai_services_account_name` / `ai_services_endpoint` | Foundry account（AIServices） |
| `openai_endpoint` | embedding 呼び出しに使う Azure OpenAI v1 endpoint |
| `foundry_project_name` / `foundry_project_id` / `foundry_project_endpoint` | Foundry project。`foundry_project_endpoint` は Lab 4/5 の SDK スクリプトがそのまま使う完全な URL です |
| `primary_model_deployment_name` / `optimizer_model_deployment_name` / `embedding_model_deployment_name` | Lab 2〜6 で使う model deployment 名 |
| `search_service_name` / `search_service_endpoint` | Lab 3 で使う Azure AI Search |
| `storage_account_name` / `rag_container_name` | RAG ソースドキュメントの格納先 |
| `log_analytics_workspace_name` / `application_insights_name` / `application_insights_id` | Lab 8 の観測性 |
| `search_connection_name` / `storage_connection_name` / `application_insights_connection_name` | Foundry project に張られた connection 名 |
| `travel_api_fqdn` | Lab 4 の Travel Ops API |
| `foundry_portal_url` | Foundry portal のトップ URL |

続けて、実際に Portal と API を開いて確認します。

```bash
# Travel Ops API のヘルスチェック(架空データのみを返す、認証不要の公開エンドポイント)
curl -s "https://$(jq -r '.terraform_outputs.travel_api_fqdn.value' .workshop/context.json)/health"
```

`{"status":"ok", ...}` のような応答が返れば成功です。次に、`foundry_portal_url` を
ブラウザで開き、`ai_services_account_name` と `foundry_project_name` に一致する
account/project が実際に portal 上に存在することを目視で確認してください。

## 5. うまくいかないとき

- `preflight.sh` / `setup.sh` が途中で失敗した場合は、そのまま同じコマンドで再実行できます。
- 参加者側で解決できない失敗（quota、resource provider 登録など）は
  [参加者向けトラブルシューティング](../docs/participant/troubleshooting.md) と
  [管理者向けトラブルシューティング](../docs/admin/troubleshooting.md) を確認してください。

## 次のステップ

[Lab 2 — Prompt Agent](02-prompt-agent.md) に進んでください。

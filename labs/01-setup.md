# Lab 1 — 環境構築（20分）

## ゴール

参加者向け前提条件で作成したresource groupに、ハンズオン用のFoundry projectと関連resource
を構築します。

## 事前に用意する値

| 値 | 入手先 |
|---|---|
| `<subscription-id>` | 講師または管理者 |
| `<resource-group>` | 参加者向け前提条件で自分が作成したworkload用RG |

詳しい条件は
[参加者向け前提条件](../docs/participant/prerequisites.md)を確認してください。

## 1. 実行環境を選んで準備する

次の **どちらか一方**のガイドを完了し、このページの手順 2 に戻ります。
前提条件のページですでに準備した場合は、同じ環境を開き直してください。

| 実行環境 | 準備するもの |
|---|---|
| [GitHub Codespaces](../docs/participant/environments/codespaces.md) | 従来の devcontainer、VS Code、Azure CLI サインイン |
| [Azure Cloud Shell Bash + JupyterLab](../docs/participant/environments/cloud-shell.md) | 自分専用の永続ストレージ、rootless の Python 3.13、ブラウザーの JupyterLab |

**ここから先は共通です。** 選んだ環境の repository root の Terminal でコマンドを実行します。
Lab 7 / 8 も同じ Notebook を使い、Cloud Shell 専用の CLI 演習には置き換えません。
root `.venv` と Hosted Agent 用 `.venv` は依存が異なるため、統合しないでください。

## 2. 事前確認を実行する

サインイン済みのAzure CLIで、対象subscriptionを明示します。
表示されたIDとユーザーが前提条件でRGを作成したアカウントと一致することを確認してから
preflightを実行します。

```bash
az account set --subscription "<subscription-id>"
az account show --query "{subscriptionId:id, user:user.name}" -o table
```

```bash
./scripts/preflight.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>"
```

`overall_status` が `pass` なら次へ進みます。`fail` の場合は setup を実行せず、
[トラブルシューティング](../docs/participant/troubleshooting.md#事前確認とセットアップ)を確認してください。

## 3. 環境を構築する

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>"
```

この処理は再実行できます。途中で失敗した場合も Terraform state や
`.workshop/` を手動で削除しないでください。
Cloud Shell の一時セッションや、永続化を確認できない保存先では実行しません。
実行環境を終了しても作成した Azure resources は残るため、削除は Lab 9 で行います。

Azure AI Search の作成で `InsufficientResourcesAvailable` が表示された場合だけ、
別 region を指定して同じ setup を再実行します。推奨順は **Japan East**（既定）、
**Australia East**、**Central US** です。

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --location australiaeast
```

3 region の dedicated Basic がすべて作成できない場合は、Serverless Developer preview を試します。

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --location japaneast \
  --ai-search-serverless
```

Serverless は従量課金で、preview 中は SLA がありません。2026-09-09 に取得した公式情報では
2026-09-13 から課金開始予定です。本番用途ではなく、このハンズオンの小規模データでだけ使います。

## 4. 完了を確認する

成功時は account、project、Travel Ops API と `.workshop/context.json` が表示されます。
Lab 5 / 6 で使う合成 dataset と rubric evaluator も、この setup で登録されます。
ここで作る Foundry project、Search、モデルは、Lab 7 のコード演習と Lab 8 の Hosted
workflow でも同じものを再利用します。

```bash
jq -r '
  .terraform_outputs
  | {
      account: .ai_services_account_name.value,
      project: .foundry_project_name.value,
      search: .search_service_name.value,
      search_pricing_model: .search_pricing_model.value,
      travel_api: .travel_api_fqdn.value
    }
' .workshop/context.json

curl -s "https://$(jq -r '.terraform_outputs.travel_api_fqdn.value' \
  .workshop/context.json)/health"
```

`"status":"ok"` が返れば構築完了です。

## 5. Foundry Portal を開く

1. 選んだ実行環境のタブを残し、別のタブで [Microsoft Foundry](https://ai.azure.com) を開きます。
2. **Sign in** が表示された場合は、Azure CLI と同じ Azure account でサインインします。
3. 画面上部に **New Foundry**（新しい Foundry）の切り替えがある場合はオンにします。
   すでに新しい画面を開いている場合は、そのまま自分の project を確認します。

![画面上部の New Foundry をオンにする](../docs/images/lab01-new-foundry-toggle.png)

## 6. 自分の project を選択する

1. **Select a project to continue**（プロジェクトを選択して続行）の選択欄を開きます。
2. 手順 4 に表示された **account と project の組み合わせ**を選択します。
   一覧の **resource** が自分の account 名と一致することを確認してください。
3. **Let's go**（出発進行）を選択します。
4. 初回の案内画面が表示されたら **Close**（閉じる）で閉じます。

setup 済みの project を使います。見つからない場合は account、directory、
setup の完了結果を確認してください。

## 完了チェック

- `preflight.sh` が3モデルすべてについて `pass` し、Travel Ops API の応答が `ok` になった
- `.workshop/context.json` が作られ、自分の account / project 名を確認できた
- Foundry (new) で自分の project を開ける

`gpt-5.5` は Foundry IQ でも使う必須モデルです。3モデルのいずれかが失敗した場合は、
解決済みリージョンが出るまでクォータとモデル提供状況を確認します。

## 次の Lab

[Lab 2 — Prompt Agent](02-prompt-agent.md)

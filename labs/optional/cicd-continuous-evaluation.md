# 選択ラボ — CI/CD と継続的評価（設計ドキュメントのみ、ワークフローは同梱しません）

## この文書の位置づけ

このラボは、`infra/`（Terraform）・Hosted Agent デプロイ・継続的評価を GitHub Actions で
自動化する場合の**設計指針とサンプル YAML の抜粋**を提供します。

> [!IMPORTANT]
> 本リポジトリには、このラボの内容を実行する `.github/workflows/*.yml` は**含まれません**。
> 以下のコードブロックはすべて**ドキュメントとしてのサンプル**であり、コピーしてそのまま
> 有効化すると実際に Azure リソースへデプロイが走ります。有効化する前に、必ず自分の
> フォーク・自分の resource group・自分のレビューを経てください。本ラボの目的は「安全な
> 設計を理解すること」であり、「今すぐ CI/CD を有効化すること」ではありません。

## 1. 設計原則

1. **クライアントシークレットを使わない。** GitHub Actions から Azure への認証は、必ず
   **OpenID Connect (OIDC) + Microsoft Entra federated identity credential** を使います。
   `AZURE_CLIENT_SECRET` のような長期秘密情報を GitHub Secrets に保存する設計は採用しません
   （AGENTS.md の非交渉制約「参加者は `az login` で認証し、クライアントシークレットを要求
   しない」という本編の方針と一貫させます）。
2. **最小権限。** サービスプリンシパルには、対象の resource group スコープでのみ、必要な
   ロール（例: Contributor）を割り当てます。サブスクリプションスコープやテナントスコープの
   ロールは付与しません。
3. **段階的なゲート。** `terraform plan` → 人間のレビュー → `terraform apply` → Hosted
   Agent デプロイ → 継続的評価、の順に、失敗したら後続ジョブに進まないゲートを設けます。
4. **読み取り専用ジョブと変更ジョブを分離する。** Pull request 時は `plan` と評価のみを実行し、
   実際の `apply`・Hosted Agent デプロイは保護されたブランチへの push、または手動承認済みの
   environment に限定します。

## 2. Microsoft Entra 側の設定（federated identity credential）

GitHub Actions のワークフロー実行時、GitHub の OIDC プロバイダーが発行する JWT を、
Microsoft Entra のアプリ登録に事前登録した **federated identity credential** と突き合わせる
ことで、クライアントシークレットなしに短命なアクセストークンを取得します。

| 設定項目 | 値の例 |
|---|---|
| Issuer | `https://token.actions.githubusercontent.com` |
| Subject（ブランチ限定の例） | `repo:<org>/<repo>:ref:refs/heads/main` |
| Subject（GitHub Environment 限定の例、推奨） | `repo:<org>/<repo>:environment:production` |
| Audience | `api://AzureADTokenExchange` |

> [!NOTE]
> Subject を GitHub **Environment** に紐づける方式（`environment:<name>`）を使うと、GitHub
> 側の environment protection rules（必須レビュアーなど）と Azure 側の認可を連動させられる
> ため、ブランチ名だけで絞るより推奨されます。

アプリ登録には、対象 resource group スコープの Contributor ロールのみを割り当てます。
サブスクリプションスコープのロール割り当ては行いません（AGENTS.md 「Participant automation
may write only inside the existing resource group」という制約と同じ考え方です）。

## 3. サンプルワークフロー抜粋（ドキュメントのみ、`.github/workflows/` には配置していません）

### 3.1 Terraform plan（pull request 時、読み取り専用）

> [!IMPORTANT]
> CI では `infra/backend.remote.tf.example` を基に remote state を構成し、
> `scripts/admin-preflight.sh` で確認した model version、image digest、既存 RG など
> `infra/variables.tf` の必須値を GitHub Environment の `TF_VAR_*` として渡します。
> 以下は job の責任分界を示す抜粋であり、環境別入力を省略してそのまま実行する
> 完成 workflow ではありません。

```yaml
# サンプル抜粋。このリポジトリの .github/workflows/ には存在しません。
name: terraform-plan-sample
on:
  pull_request:
    paths: ["infra/**"]

permissions:
  id-token: write   # OIDC トークン取得に必要
  contents: read

jobs:
  plan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: hashicorp/setup-terraform@v3
      - uses: azure/login@v3
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - name: terraform init & plan
        working-directory: infra
        run: |
          terraform init
          terraform plan -out=tfplan
      - uses: actions/upload-artifact@v4
        with:
          name: terraform-plan
          path: infra/tfplan
```

`secrets.AZURE_CLIENT_ID` などは、クライアントシークレットではなく、federated identity
credential を設定したアプリ登録の client ID・tenant ID・subscription ID です（値そのものは
機密ではありませんが、リポジトリ変数ではなく Secrets に置くことが推奨されます）。

### 3.2 Terraform apply（保護された environment 経由、人間の承認あり）

```yaml
# サンプル抜粋。このリポジトリの .github/workflows/ には存在しません。
jobs:
  apply:
    needs: plan
    environment: production   # GitHub 側で required reviewers を設定しておく
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: hashicorp/setup-terraform@v3
      - uses: azure/login@v3
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - uses: actions/download-artifact@v4
        with:
          name: terraform-plan
          path: infra
      - working-directory: infra
        run: |
          terraform init
          terraform apply -auto-approve tfplan
      - name: Build non-secret SDK context
        shell: bash
        run: |
          mkdir -p .workshop
          outputs=$(terraform -chdir=infra output -json)
          jq -n \
            --arg subscription_id "${{ secrets.AZURE_SUBSCRIPTION_ID }}" \
            --arg resource_group_name "${{ vars.AZURE_RESOURCE_GROUP }}" \
            --argjson terraform_outputs "$outputs" \
            '{subscription_id: $subscription_id, resource_group_name: $resource_group_name, terraform_outputs: $terraform_outputs}' \
            > .workshop/context.json
      - uses: actions/upload-artifact@v4
        with:
          name: workshop-context
          path: .workshop/context.json
```

### 3.3 Hosted Agent デプロイゲート

```yaml
# サンプル抜粋。このリポジトリの .github/workflows/ には存在しません。
jobs:
  deploy-hosted-agent:
    needs: apply
    environment: production
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: azure/login@v3
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - uses: actions/download-artifact@v4
        with:
          name: workshop-context
          path: .workshop
      - run: python -m pip install -e ".[dev]"
      - name: Deploy hosted agent version
        run: python scripts/deploy_hosted_agent.py --output json
```

このジョブは本編の `scripts/deploy_hosted_agent.py` をそのまま呼び出すだけで、CI/CD 固有の
新しいデプロイ経路を作りません。既存スクリプトの冪等性（バージョン単位の immutable
デプロイ、bounded polling）はそのまま CI/CD からも活かされます。先行する apply job は
`scripts/setup.sh` が生成した非秘密の `.workshop/context.json` を
`actions/upload-artifact` で `workshop-context` として渡す必要があります。

### 3.4 継続的評価ゲート

```yaml
# サンプル抜粋。このリポジトリの .github/workflows/ には存在しません。
jobs:
  continuous-evaluation:
    needs: deploy-hosted-agent
    runs-on: ubuntu-latest
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.13"
      - uses: azure/login@v3
        with:
          client-id: ${{ secrets.AZURE_CLIENT_ID }}
          tenant-id: ${{ secrets.AZURE_TENANT_ID }}
          subscription-id: ${{ secrets.AZURE_SUBSCRIPTION_ID }}
      - uses: actions/download-artifact@v4
        with:
          name: workshop-context
          path: .workshop
      - run: python -m pip install -e ".[dev]"
      - name: Run evaluation against the current dataset
        run: python scripts/run_evaluation.py --output json > evaluation-result.json
      - name: Fail the pipeline on regression
        run: |
          python - <<'PY'
          import json, sys
          with open("evaluation-result.json") as f:
              result = json.load(f)
          counts = result["result_counts"]
          total = counts["total"] or 0
          passed = counts["passed"] or 0
          pass_rate = passed / total if total else 0
          if pass_rate < 0.8:
              print(f"Evaluation pass rate {pass_rate:.0%} below threshold; failing pipeline.")
              sys.exit(1)
          PY
```

継続的評価ジョブは本編 [Lab 5](../05-evaluation.md) の `scripts/run_evaluation.py` をそのまま
呼び出し、`--output json` が返す `result_counts.total`/`result_counts.passed` から算出した
合格率がしきい値を下回った場合にパイプラインを失敗させるゲートの例です。実際のフィールド名は
`run_evaluation.py` の `format_report()` の出力に対応しています。しきい値は
[Lab 5](../05-evaluation.md) で定義される合格基準に合わせて調整してください。

## 4. 何をこのラボが「作らない」か

- `.github/workflows/*.yml` の実ファイル（本ラボはドキュメントのみ）。
- 新しい Azure リソース（federated identity credential の設定は Microsoft Entra 側の
  アプリ登録に対する変更であり、本リポジトリの Terraform の scope 外）。
- クライアントシークレットを使ういかなる認証経路。

実際にこの設計を採用する場合は、まず自分のフォークで `workflow_dispatch` トリガーのみの
`plan` ジョブから始め、レビューを経てから `apply` 系ジョブを追加することを推奨します。

## 公式参照

- [Authenticate to Azure from GitHub Actions by OpenID Connect](https://learn.microsoft.com/azure/developer/github/connect-from-azure-openid-connect)
- [About security hardening with OpenID Connect (GitHub Docs)](https://docs.github.com/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect)
- [Configuring OpenID Connect in Azure (GitHub Docs)](https://docs.github.com/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-azure)

## 関連リンク

- [選択ラボ index](README.md)
- [本編 Lab 5 — 評価](../05-evaluation.md)
- [本編 Lab 7 — Hosted Agent デプロイ](../07-hosted-multi-agent.md)
- [instructor runbook](../../instructor/runbook.md)

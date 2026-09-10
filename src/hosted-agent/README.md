# Contoso Travel Hosted Agent

Lab 8 の Microsoft Agent Framework sequential workflow:

```text
intake_agent -> policy_agent -> reviewer_agent
```

`policy_agent` だけが Foundry IQ で合成規程を検索します。Lab 7 の Harness、Toolbox、Skills、
Travel Ops API は deployed workflow に含みません。実際の予約・申請・承認・精算は行いません。

## Azure ML workflow

Lab 1 の single download ZIP を PC で展開し、Lab 7 で Terraform-created Azure ML workspace
の **User files** へ upload します。`notebooks/00-azureml-setup.ipynb` を built-in
**Python 3.10 - SDK v2** で実行後、Labs 7/8 は **Python (Foundry Hosted Agent)** を使用。

設定は `.workshop/context.json` の canonical `resource_outputs` から読みます。Cloud Shell
では Hosted Agent environment、Notebook、deploy を実行しません。

deploy は `notebooks/08-hosted-agent.ipynb` の cell から行います。cleanup は parent Foundry
resource の destroy より先です。

```bash
conda run --name foundry-hosted-agent python scripts/delete_hosted_agent.py \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --output json
```

source remote build、model、Foundry IQ、Hosted runtime、telemetry は課金対象です。
request / trace には合成データだけを入力し、credential を保存しません。

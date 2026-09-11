# Contoso Travel Hosted Agent

Lab 8 の Microsoft Agent Framework sequential workflow:

```text
intake_agent -> policy_agent -> reviewer_agent
```

`policy_agent` だけが Foundry IQ で合成規程を検索します。Lab 7 の Harness、Toolbox、Skills、
Travel Ops API は deployed workflow に含みません。実際の予約・申請・承認・精算は行いません。

## Azure ML workflow

Lab 1 の custom template / Deployment Scripts 完了後、private `workshop-files` container から
Entra ID で download した ZIP を PC で展開します。Lab 7 に template-created Azure ML workspace
で **Standard_DS3_v2** + **Idle shutdown** の Compute を作成し、最上位
`Microsoft-Foundry-Agent-Service-Handson` folder を **Notebooks > User files** へ upload します。
`notebooks/00-azureml-setup.ipynb` を built-in
**Python 3.10 - SDK v2** で実行後、Labs 7/8 は **Python (Foundry Hosted Agent)** を使用。

設定は `.workshop/context.json` の canonical `resource_outputs.<key>.value` から読みます。
hidden `.workshop`、source、scripts、Notebook が実行する tests の相対位置を保ちます。

deploy は `notebooks/08-hosted-agent.ipynb` の cell から行います。必要な成果物を Export し、
Hosted Agent / versions の cleanup を完了してから Compute を Stop / Delete、
Azure Portal の Delete resource group で専用 RG を削除します。
deployment history の削除だけでは resources は消えません。

```bash
conda run --name foundry-hosted-agent python scripts/delete_hosted_agent.py \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --output json
```

source remote build、model、Foundry IQ、Hosted runtime、telemetry は課金対象です。
request / trace には合成データだけを入力し、credential を保存しません。

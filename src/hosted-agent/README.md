# Contoso Travel Hosted Agent

Lab 8 の Microsoft Agent Framework sequential workflow:

```text
intake_agent -> policy_agent -> reviewer_agent
```

`policy_agent` だけが Foundry IQ で合成規程を検索します。
Lab 7 の Harness、Toolbox、Skills、Travel Ops API は deployed workflow に含みません。
実際の予約・申請・承認・精算は行いません。

## Notebook workflow

1. Lab 1 の初期化後、[Codespaces](../../docs/participant/environments/codespaces.md) または
   [ローカル Dev Container](../../docs/participant/environments/local-dev-container.md) を開きます。
2. コンテナーの Terminal で Azure CLI にサインインし、
   `notebooks/00-setup.ipynb` を **Python (Foundry Workshop)** で実行します。
   subscription ID / RG 名から `.workshop/context.json` が作成されます。
3. [`notebooks/08-hosted-agent.ipynb`](../../notebooks/08-hosted-agent.ipynb) を
   **Python (Foundry Hosted Agent)** で実行します。設定は `resource_outputs.<key>.value` から読みます。

Notebook・source・scripts は同じリポジトリ内のものを使います。
管理用は Python 3.12 の `foundry-workshop` venv、Hosted 用は Python 3.13 の
`foundry-hosted-agent` venv です。どちらもコンテナー内のチェックアウト外に準備されます。

## Deploy / cleanup

Notebook の **DEPLOY** 確認後にソースコード ZIP を生成し、Foundry の source remote build へ渡します。
deploy / delete は Hosted カーネルから管理用 interpreter
（`WORKSHOP_MANAGEMENT_PYTHON`、未指定時は `~/.venvs/foundry-workshop/bin/python`）を呼び出します。

成果物を保存し、削除セルの対象を確認して、表示された **Agent 名**を入力してください。
Hosted Agent / versions の削除後に Codespace を停止・削除し、
Azure Portal で自分の専用 RG を削除します。詳しくは [Lab 9](../../labs/09-observability-cleanup.md) を参照します。
deployment history の削除だけでは resources は消えません。

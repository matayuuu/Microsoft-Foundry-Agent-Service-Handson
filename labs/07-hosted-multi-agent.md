# Lab 7 - シンプルな Sequential Hosted Agent（45分）

## ゴール

Microsoft Agent Framework の `FoundryChatClient.as_agent()` で3つの agent を作り、
`SequentialBuilder` で順番につなぎます。その後、ローカル実行した同じコードを
Microsoft Foundry の Hosted Agent として source deploy します。

```text
policy_agent -> planner_agent -> reviewer_agent
```

> [!IMPORTANT]
> この workflow は架空の社内規程を使う学習用シミュレーションです。実際の予約や承認は
> 行いません。最終回答には必ず「実際の予約・承認ではない」旨を含めます。

> [!WARNING]
> Workflow Designer は 2026-12-01 に廃止予定です。本 Lab は後継の
> Microsoft Agent Framework をコードから利用します。各 agent の呼び出しには
> model token の料金が発生します。入力には合成データだけを使用してください。

## 1. コードを読む

`src/hosted-agent/workflow.py` の中心部分は次の構造です。

```python
chat_client = FoundryChatClient(
    project_endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    model=os.environ["FOUNDRY_MODEL"],
    credential=DefaultAzureCredential(),
)

policy_agent = chat_client.as_agent(
    name="policy_agent",
    instructions="依頼を読み、規程上の注意点を整理する...",
)
planner_agent = chat_client.as_agent(
    name="planner_agent",
    instructions="規程確認を踏まえて出張案と概算を作る...",
)
reviewer_agent = chat_client.as_agent(
    name="reviewer_agent",
    instructions="案をレビューし、最終回答を返す...",
)

workflow = SequentialBuilder(
    participants=[policy_agent, planner_agent, reviewer_agent]
).build()
```

確認ポイントは3つだけです。

1. 3つの agent は同じ `FoundryChatClient` と model deployment を使います。
2. `SequentialBuilder` に並べた順に実行され、後続 agent は前の回答を読めます。
3. workflow の最終出力は最後の `reviewer_agent` の回答です。

`main.py` はこの workflow を `workflow.as_agent()` で1つの agent として包み、
`ResponsesHostServer` で公開するだけです。

## 2. ローカル環境を設定する

Lab 1 の setup が完了し、`.workshop/context.json` が存在することを確認します。

```bash
cd src/hosted-agent
source .venv/bin/activate
cp .env.example .env
```

`.env` に次の2値を設定します。

```bash
jq -r '.terraform_outputs.foundry_project_endpoint.value' \
  ../../.workshop/context.json
jq -r '.terraform_outputs.primary_model_deployment_name.value' \
  ../../.workshop/context.json
```

```dotenv
FOUNDRY_PROJECT_ENDPOINT=https://<account>.services.ai.azure.com/api/projects/<project>
FOUNDRY_MODEL=<primary_model_deployment_name>
PORT=8088
```

ローカルでは `DefaultAzureCredential` が `az login` のセッションを使います。
Hosted Agent では同じコードが managed identity を使うため、secret は不要です。

## 3. workflow を直接実行する

```bash
python workflow.py
```

`workflow.py` 内の `SAMPLE_REQUEST` が次の1行で実行されます。

```python
result = await workflow.run(SAMPLE_REQUEST)
```

最終回答に次が含まれることを確認します。

- 規程確認
- 食事・宿泊の概算
- 次に行うこと
- 実際の予約・承認ではないという注意書き

model の文章は実行ごとに多少変わります。

## 4. Responses protocol で実行する

1つ目のターミナル:

```bash
python main.py
```

2つ目のターミナル:

```bash
curl -s http://localhost:8088/responses \
  -H "content-type: application/json" \
  -d '{"input":"2026年9月10日から11日まで、東京から大阪へ1名で社内レビューに行きます。座席クラスは economy です。規程確認と概算を作ってください。"}' \
  | jq
```

`output_text` は `reviewer_agent` の最終回答です。サーバーを停止するには
1つ目のターミナルで `Ctrl+C` を押します。

## 5. 自動テストを実行する

```bash
cd ../..
src/hosted-agent/.venv/bin/python -m pytest \
  tests/contract/hosted_agent -q
```

テストは Azure 接続だけを fake に差し替え、実際の `SequentialBuilder` で次を確認します。

- agent が `policy_agent`、`planner_agent`、`reviewer_agent` の順で作られる
- 前の agent の回答が次の agent に渡る
- Hosted Agent と同じ `workflow.as_agent()` が reviewer の最終回答を返す
- 最終回答にシミュレーションの注意書きが含まれる

## 6. Hosted Agent として deploy する

repository root の `.venv` を使います。

```bash
.venv/bin/python scripts/deploy_hosted_agent.py --output json
```

このスクリプトは:

1. `src/hosted-agent/` を zip 化します。
2. `FOUNDRY_MODEL` を Terraform output から自動設定します。
3. Python 3.13 の source remote build を開始します。
4. immutable な Hosted Agent version が `active` になるまで有限時間で待ちます。

Docker、ACR、別の `azd auth login` は不要です。

## 7. Portal で確認する

出力された account、project、agent、version を使って Foundry portal の Agents 画面を
開きます。Playground から同じ依頼を送り、次を確認します。

- 応答がストリーミングされる
- trace に `policy_agent`、`planner_agent`、`reviewer_agent` の3つの model call が並ぶ
- 最後の回答が reviewer によって整理されている

## 8. 変更して再 deploy する

たとえば `workflow.py` の `REVIEWER_AGENT_INSTRUCTIONS` に、回答を表形式にする指示を
追加します。

```bash
src/hosted-agent/.venv/bin/python -m pytest \
  tests/contract/hosted_agent -q
.venv/bin/python scripts/deploy_hosted_agent.py --output json
```

再 deploy ごとに新しい immutable version が作成されます。Playground で新旧 version
を切り替え、instructions の違いが最終回答へ反映されることを確認します。

## 9. Cleanup

```bash
./scripts/destroy.sh
```

`destroy.sh` は Hosted Agent version を削除してから Terraform resource を破棄し、
既存 resource group 自体は残します。

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| `FOUNDRY_PROJECT_ENDPOINT` / `FOUNDRY_MODEL` がない | `.env.example` をコピーし、Lab 1 の context から値を設定します。 |
| model 呼び出しが 404 | `FOUNDRY_MODEL` が実際の deployment 名か確認します。 |
| port 8088 が使用中 | `.env` の `PORT` を別の値へ変更します。 |
| deploy が timeout | Portal で version 状態を確認し、必要なら `--timeout` を増やします。 |
| version が `failed` | version の build log と Application Insights trace を確認します。 |

## 次のステップ

[Lab 8 - Observability・governance・cleanup](08-observability-cleanup.md) に進みます。

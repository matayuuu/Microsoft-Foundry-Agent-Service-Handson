# Lab 7 — Agent Framework の Hosted Agent（40分）

## ゴール

Microsoft Agent Framework の sequential workflow を Notebook で実行し、
同じ source を Hosted Agent として Microsoft Foundry に deploy します。

```text
policy_agent -> planner_agent -> reviewer_agent
```

最後に model を使わない `SimulationNoticeExecutor` が、simulation の注意書きを保証します。

> [!IMPORTANT]
> この workflow は学習用 simulation です。予約や承認は行いません。

## 1. Notebook で workflow を実行する

1. VS Code Explorer で
   [`notebooks/07-hosted-agent.ipynb`](../notebooks/07-hosted-agent.ipynb)
   を開きます。
2. 右上の kernel picker で **Python (Foundry Hosted Agent)** を選択します。
3. 説明を読み、上から 1 cell ずつ実行します。

Notebook では次を確認します。

1. `.workshop/context.json` から endpoint と model を取得
2. `policy_agent`、`planner_agent`、`reviewer_agent` の責務
3. `SequentialBuilder` の workflow を 1 回実行
4. 決定的な最終チェックで simulation 注意書きを検証
5. Azure を呼ばない contract test を実行

## 完了チェック

- 最終回答に「規程確認」「概算」「次のアクション」がある
- 最後に「実際の予約・承認ではありません」と明示される
- Contract test が pass する

## 2. Hosted Agent を deploy する

Notebook を閉じ、repository root の terminal で実行します。

```bash
.venv/bin/python scripts/deploy_hosted_agent.py --output json
```

Script は次を自動で行います。

1. `src/hosted-agent/` を package
2. `primary_model_deployment_name` を環境変数へ設定
3. Python 3.13 の source remote build を開始
4. Hosted Agent の runtime identity に Application Insights の送信権限を付与
5. `active` または `failed` になるまで有限時間で待機

Docker、ACR、追加の sign-in は不要です。

次の値が返れば deploy 完了です。

```json
{
  "agent_name": "contoso-travel-hosted-planner",
  "status": "active"
}
```

## 3. Portal で実行する

1. Microsoft Foundry Portal で **Build > Agents** を開きます。
2. `contoso-travel-hosted-planner` を選択します。
3. **Details** を開き、**Status** が **Running**、
   **Responses protocol** が **Active** であることを確認します。
4. **Playground** に戻り、次を送ります。

```text
2026年9月10日から11日まで、東京から大阪へ1名で社内レビューに行きます。
座席クラスは economy です。規程確認と概算を作ってください。
```

## 完了チェック

- 応答が最後まで返る
- 最終回答が reviewer によって整理されている
- 実際の予約・承認ではないことが明記される

![Hosted Agent の Playground](../docs/images/lab07-hosted-agent-playground.png)

初回は Hosted Agent の起動に時間がかかります。**Log stream** が動いている間は再送しません。

Hosted Agent の trace は次の Lab で確認します。

## 次の Lab

[Lab 8 — Observability と cleanup](08-observability-cleanup.md)

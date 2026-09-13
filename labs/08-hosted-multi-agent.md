# Lab 8 — 通常 Agent の sequential workflow を Hosted Agent にする（30分）

## ゴール

Microsoft Agent Framework の通常 Agent を 3 つ作り、順番に処理する workflow として
Microsoft Foundry に deploy します。

```text
intake_agent -> policy_agent -> reviewer_agent
```

| Agent | 担当 | 接続する機能 |
|---|---|---|
| `intake_agent` | 旅程と質問を整理する | model |
| `policy_agent` | 社内規程を検索し、文書 ID と出典を整理する | model + Foundry IQ |
| `reviewer_agent` | 元の依頼と根拠を照合し、最終回答に整える | model |

Lab 7 の Harness Agent は独立した演習です。この workflow には入れず、
通常 Agent の役割分担、引き継ぎ、Hosted deployment を確認します。

> [!WARNING]
> Notebook の model / Foundry IQ 呼び出し、source remote build、Hosted Agent の稼働には
> 料金が発生します。処理中の cell や Hosted Agent の依頼を再送しないでください。

## 1. Notebook で通常 Agent と workflow を確認する

Lab 1 の初期化と、Lab 7 の共通環境・`notebooks/00-setup.ipynb` を完了してから始めます。

1. Codespaces またはローカル Dev Container の VS Code で
   [`notebooks/08-hosted-agent.ipynb`](../notebooks/08-hosted-agent.ipynb) を開きます。
2. kernel に **Python (Foundry Hosted Agent)** を選択します。
   `foundry-hosted-agent` venv（Python 3.13）を使います。
3. 説明を読み、上から 1 cell ずつ実行します。エラーの cell を飛ばしません。

環境の操作は [Codespaces の共通手順](../docs/participant/environments/codespaces.md#共通手順)、
ローカルの前提条件は [Dev Container ガイド](../docs/participant/environments/local-dev-container.md)を参照してください。

Notebook は次の順に進みます。

1. `.workshop/context.json` の `resource_outputs.<key>.value` から model、Search、Foundry IQ の接続先を読む
2. 3 つの通常 Agent を作る
3. `SequentialBuilder` で実行順を固定する
4. `WorkflowViz` と Graphviz で実際の graph を表示する
5. 合成の規程質問を実行し、途中回答と reviewer の最終回答を比較する
6. Azure を使わない contract test を実行する

Graphviz が使える場合、次の 3 participant が順に接続された SVG が表示されます。

```text
intake_agent -> policy_agent -> reviewer_agent
```

Notebook だけ `intermediate_output_from="all_other"` を使い、intake と policy の途中回答を
表示します。deploy する workflow は reviewer の最終回答だけを返します。

### 実行結果を確認する

標準の合成依頼では、東京から大阪への国内出張について、食事日当、宿泊上限、精算期限を
根拠付きで確認します。費用見積もりや予算計算は行いません。

実行記録で次を確認してください。

- 実行順が `intake_agent` → `policy_agent` → `reviewer_agent`
- `policy_agent` だけが `knowledge_base_retrieve` を実行
- 規程の文書 ID、文書名、引用または source URL が残っている
- 最終回答に **依頼の整理 / 規程確認 / 次のアクション** がある
- Toolbox、Skill、`tool_search`、`call_tool`、Travel Ops API は実行されていない
- 実際の予約・承認・精算を行っていないと明記されている

Lab 7 の session、todo、memory、出力は引き継ぎません。Lab 3 の Foundry IQ が準備済みなら、
Lab 7 の Agent 実行を省略していても Lab 8 を開始できます。
共通 Dev Container、Azure CLI サインイン、`00-setup.ipynb` の準備は必須です。

## 2. Hosted Agent を deploy する

Notebook と contract test を確認後、同じ Notebook の **Python (Foundry Hosted Agent)**
kernel で管理用コマンドの準備セルと deploy cell を実行し、確認欄に **DEPLOY** と入力します。
表示された subscription / RG を確認してから実行してください。
セルは `WORKSHOP_MANAGEMENT_PYTHON` が指す管理用 `foundry-workshop` venv（Python 3.12）を
呼び出すため、Hosted SDK と混在させません。
Lab 1 の template を再実行する操作ではありません。

Script が `src/hosted-agent/` のソースコード ZIP を作成し、Python 3.13 の source remote build、
実行用 identity への必要な権限付与、状態確認を行います。ZIP を手作業で作る必要はありません。
build は Foundry 側で行われ、参加者用 ACR の作成は不要です。
認証切れの場合は [共通のサインイン手順](../docs/participant/environments/codespaces.md#共通手順)に戻ります。
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
3. **Details** で **Status = Running**、
   **Responses protocol = Active** を確認します。
4. **Playground** に戻り、前の会話があれば **New chat** を選択します。
5. 次を入力して **Send** を押します。

```text
2026年9月10日から11日まで、東京から大阪へ1名で社内レビューに行きます。
座席クラスは economy です。国内出張の食事日当、宿泊上限、精算期限を、
規程の文書IDまたはリンク付きでまとめてください。費用見積もり、予約、申請、
承認、精算は行わないでください。
```

初回は Hosted Agent の起動に時間がかかります。Log stream が動いている間は再送しません。
deploy 直後の最初の呼び出しだけ Search の `403` になった場合は、role assignment の反映を
待って同じ依頼を再送してください。新しい version は作り直しません。

## 完了チェック

- Hosted Agent の応答が最後まで返る
- `intake_agent` → `policy_agent` → `reviewer_agent` の順で処理される
- `policy_agent` の Trace に `knowledge_base_retrieve` がある
- 規程値と出典が Foundry IQ の結果に沿っている
- Toolbox / Skills / Travel Ops API を呼んでいない
- 実際の予約・承認・精算ではないことが明記されている

次の Lab で Prompt Agent と Hosted workflow の Trace を比較します。

## 終了時の削除

Trace の比較と成果物の保存後、同じ Notebook の削除セルで対象を確認し、
表示された **Agent 名**（`contoso-travel-hosted-planner`）を確認欄に入力します。
削除も管理用 `foundry-workshop` venv で実行されます。Hosted Agent と全 versions の削除を確認してから、
Codespace、専用 RG の順に片付けます。具体的な操作は [Lab 9](09-observability-cleanup.md) に従ってください。

## 次の Lab

[Lab 9 — Trace の比較と cleanup](09-observability-cleanup.md)

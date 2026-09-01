# Lab 4 — Travel Ops API の Toolbox（30分）

## ゴール

Python Notebook で Travel Ops API の Toolbox を作り、Prompt Agent から
出張費用の見積もり API を呼び出します。

## 1. Notebook を開く

1. VS Code Explorer で
   [`notebooks/04-create-toolbox.ipynb`](../notebooks/04-create-toolbox.ipynb)
   を開きます。
2. 右上の kernel picker で **Python (Foundry Workshop)** を選択します。
3. Notebook の説明を読み、上から 1 cell ずつ実行します。

Notebook では次を順に確認できます。

1. `.workshop/context.json` の読み込み
2. `az login` を使う Foundry client の作成
3. 実際の Travel Ops API から OpenAPI 3.1 定義を取得
4. `travel_ops_api` tool の定義
5. `contoso-travel-toolbox` の作成または更新
6. default Toolbox に tool が含まれることの確認
7. keyless MCP connection `contoso-travel-toolbox-mcp` の作成
8. Foundry IQ を残したまま Prompt Agent へ接続

最後の cell に次が表示されれば完了です。

```text
Toolbox ready: travel_ops_api
Connection ready: contoso-travel-toolbox-mcp
Toolbox connection ready.
```

同じ Notebook を再実行しても、OpenAPI 定義が変わっていなければ既存 Toolbox を再利用します。

## 2. Portal で接続結果を確認する

1. Microsoft Foundry Portal で
   **Build > Agents > contoso-travel-assistant** を開きます。
2. **Tools** に `contoso-travel-toolbox-mcp` が表示されることを確認します。
3. **Knowledge** に Lab 3 の knowledge base が残っていることを確認します。

表示されない場合は Portal で手作業せず、Notebook の最後の 2 cell を再実行します。

## 3. Tool call を確認する

**Playground** で次の質問を送ります。

```text
東京からニューヨークへ2026-07-10〜2026-07-15の出張で、
ビジネスクラス利用を前提に費用見積もりを出してください。
```

Activity / trace で tool call を開きます。

## 完了チェック

- `travel_ops_api___createTripEstimate` が呼び出されている
- `origin_city=Tokyo`、`destination_city=New York` が渡されている
- `start_date=2026-07-10`、`end_date=2026-07-15` が渡されている
- `cabin_class=business` が渡されている
- 合計が `781,000円` である
- 最終回答が API の結果を使い、予約や承認ではないことを明示している

> [!NOTE]
> この API は合成データだけを返す決定的な mock です。実際の予約、見積もり、
> 事前承認は行いません。

Notebook でエラーになった場合は
[Toolbox のトラブルシューティング](../docs/participant/troubleshooting.md#toolbox-notebook)
を確認してください。

## 次の Lab

[Lab 5 — Portal で Agent evaluation](05-evaluation.md)

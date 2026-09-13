# Lab 5 — Portal で Agent evaluation（15分）

## ゴール

Microsoft Foundry Portal で、Lab 1 の Deployment Scripts が登録した合成 test data を使い
`contoso-travel-assistant` を end-to-end で評価します。

Lab 4 までで作った Agent に同じ質問集を実行し、**回答と tool の使い方から改善点を見つけます。**

回答する Agent と、回答を採点するモデルは別の役割です。このハンズオンでは
Agent に `gpt-5.6-luna`、設定可能な LLM judge（採点役）に `gpt-5.5` を使います。

> [!WARNING]
> Agent invocation と LLM evaluator には料金が発生します。
> この Lab では 7 件の合成データに限定します。

Lab 4 の MCP 自動承認設定まで保存した Agent を使います。

## 1. Evaluation を作成する

1. 対象 project の左 navigation で **Build > Evaluations** を開きます。
2. **Create** を選択します。

3. **Target** は **Agent** にし、右側で `contoso-travel-assistant` の行を選択します。
   Hosted Agent や Model を選ばないでください。
4. **Version** の選択欄で、Lab 4 までの変更を保存した最新の version を **1 つだけ**
   選びます。

![評価する Agent の最新 version を1つ選択する](../docs/images/lab05-agent-version.png)

5. 対象 Agent と version を確認して **Next** を押します。

6. **Scope** は **Individual turns** にして **Next** を押します。
7. **Frequency** は **One time** にして **Next** を押します。定期実行は作りません。

## 2. 合成 dataset を選択する

1. **Data** で **Existing dataset** を選択します。
2. `contoso-travel-eval-live-subset` を選択し、**Next** を選択します。

![合成 dataset の選択](../docs/images/lab05-data-selection.png)

この dataset は Lab 1 の Python adapter が `data/eval/live_subset.jsonl` から登録した架空データです。
新しいデータは生成せず、登録済みの 7 件を使います。

## 3. Field mapping を設定する

**Field mapping** では、dataset の列を表す `item.*` と、Evaluation 実行時に Agent から
取得する `sample.*` を evaluator の標準フィールドへ割り当てます。

1. Lab 1 のデプロイの **Outputs > resourceOutputs** で
   `evaluation_model_deployment_name.value` が `gpt-5.5` であることを確認します。
2. **Judge model** で **Deployments > gpt-5.5** を選択します。
   初期選択が `gpt-5.6-luna` なら変更してください。`gpt-5.5` が表示されない場合は、
   Lab 1 の model deployment を管理者に確認してから続行します。
3. 各フィールドが次の値になっていることを確認します。

| Field | Mapping | 内容 |
|---|---|---|
| **Query** | `{{item.query}}` | dataset に保存された質問 |
| **Response** | `{{sample.output_text}}` | Agent がこの実行で生成する最終回答 |
| **Context** | **Not available** | この dataset には固定の `context` 列がないため、そのままにする |
| **Ground truth** | `{{item.ground_truth}}` | 正解例がある行の期待回答 |
| **Tool calls** | `{{sample.tool_calls}}` | Agent がこの実行で行った tool call |
| **Tool definitions** | `{{sample.tool_definitions}}` | Agent が利用できる tool の定義 |


4. **Next** を選択します。

## 4. Agent の入力を確認する

1. **Configure agents** で `contoso-travel-assistant` の **Configure** を選択します。

2. **User prompt** が `{{item.query}}` であることを確認します。
   違っていればこの値を入力し、**Save** を押します。
3. **Next** を選択します。

## 5. Criteria を選択する

1. 初期選択の評価器から **TaskAdherence** と **TaskCompletion** だけを残します。
   不要なチップの **×** で外せます。**Quality** と **Safety** の評価器は、
   それぞれの **Remove all** でまとめて外して構いません。
2. Lab 1 で登録した、このハンズオン専用の custom evaluator
   **[Contoso Travel Rubric](../docs/participant/contoso-travel-rubric.md)** を追加します。
3. 最終的に、次の **3 つ**が選択されていることを確認します。

| Evaluator | 確認すること |
|---|---|
| **TaskAdherence** | instructions と依頼に従ったか |
| **TaskCompletion** | 必要な内容を回答したか |
| **Contoso Travel Rubric** | 出張・経費規程に沿い、必要な引用、適切な tool 利用、対象範囲と安全上の制約を満たしたか |

ToolSelection / ToolInputAccuracy / ToolCallAccuracy は追加しません。
ここで評価器を外しても、Agent の Guardrail は変更されません。

## 6. 評価器ごとの入力を設定する

手順 3 の Field mapping は共通の初期値です。ここでは各 evaluator のチップを開き、
次の値を設定して、それぞれ **Update** を押します。

| Evaluator | Judge model | Query | Response |
|---|---|---|---|
| **TaskAdherence** | `gpt-5.5` | `{{item.query}}` | `{{sample.output_items}}` |
| **TaskCompletion** | `gpt-5.5` | `{{item.query}}` | `{{sample.output_text}}` |
| **Contoso Travel Rubric** | `gpt-5.5` | `{{item.query}}` | `{{sample.output_items}}` |

`sample.output_text` は最終回答だけ、`sample.output_items` は最終回答と直接記録された
tool call を評価器へ渡します。

**TaskAdherence** の **Tool definitions** は `{{sample.tool_definitions}}` のままにします。
表にない項目は既定値から変更しません。

![TaskAdherence の Response は output_items にする](../docs/images/lab05-task-adherence-mapping.png)

3 つの evaluator をすべて **Update** したら、**Next** を選択します。

## 7. Evaluation を実行する

1. **Review** の Evaluation name に `contoso-travel-portal-eval` を入力します。
2. Target が `contoso-travel-assistant` の 1 version、dataset が指定の合成データ、
   Frequency が One time、Judge model が `gpt-5.5`、評価器が上の 3 つであることを確認します。
3. **Submit** を選択します。

4. Evaluation detail の status が **Completed** または **Partial** になるまで待ちます。
   7 件では通常数分かかります。**In progress** の間は同じ run を再送しません。
5. 結果を開きます。**Partial** は一部を採点できなかった状態なので、次の手順で
   **Error** の内容を確認します。

## 8. 結果を読む

実行一覧の `contoso-travel-assistant` を開き、**Overall metric results** と
**Detailed metrics result** を確認します。

**Overall metric results** は評価器ごとの集計、**Detailed metrics result** は質問ごとの結果です。
詳細の表は横にスクロールして、質問・回答・score・reason・右端の **Error** を見比べます。
Conversation ID が表示される行は、そのリンクから会話や tool 呼び出しをたどれます。

理由が省略されている場合は、そのセルにポインターを重ねて少し待つと全文を読めます。

少なくとも 1 行で、質問・回答・規程・採点理由を照合してください。
モデルの採点が正しいとは限りません。reason と実際の Trace が食い違う場合も、その不一致を記録します。

| 結果 | 読み方 |
|---|---|
| **Pass / Fail** と reason | 回答や tool 利用の改善点を確認する |
| 攻撃文の行で `content_filter` | 保護機能による遮断として記録する。Guardrail を弱めて通さない |
| `429`・タイムアウトなどの **Error** | 採点結果と区別し、[トラブルシューティング](../docs/participant/troubleshooting.md#評価と最適化)で原因を解消する |

Tool が必要な row では Conversation / Trace を開き、`tool_search` / `call_tool` が選んだ tool と、
`createTripEstimate` など実際に実行された operation の引数・出力を確認します。

**Completed / Partial でも、全行を正常に採点できたとは限りません。** Error の内容まで確認します。

## 完了チェック

- 7 件の synthetic query が実行されている
- 採点できた行で Evaluator ごとの pass / fail が表示される
- Error がある場合、保護機能による遮断と、未解消の実行エラーを区別できる
- Tool が必要な row で、選ばれた tool と実 operation の引数・出力を確認できる
- Fail の row で evaluator の reason を確認できる

次の Lab では同じ dataset と、登録済みの **Contoso Travel Rubric** を使います。

詳細は
[Run evaluations from the Microsoft Foundry portal](https://learn.microsoft.com/azure/foundry/how-to/evaluate-generative-ai-app)
を参照してください。

## 次の Lab

[Lab 6 — Agent Optimizer](06-optimization.md)

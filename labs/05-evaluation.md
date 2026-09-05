# Lab 5 — Portal で Agent evaluation（15分）

## ゴール

Microsoft Foundry Portal で、setup 済みの合成 test data を使い
`contoso-travel-assistant` を end-to-end で評価します。Lab 本編では Python を使いません。

> [!WARNING]
> Agent invocation と LLM evaluator には料金が発生します。
> この Lab では 7 件の合成データに限定します。

## 1. Evaluation を作成する

1. 対象 project の左 navigation で **Build > Evaluations** を開きます。
2. **Create** を選択します。
3. **Target** で **Agent** を選び、`contoso-travel-assistant` を選択してから **Next** を選択します。
4. **Scope** で **Individual turns** を選び、**Next** を選択します。
5. **Frequency** で **One time** を選び、**Next** を選択します。

## 2. 合成 dataset を選択する

1. **Data** で **Existing dataset** を選択します。
2. `contoso-travel-eval-live-subset` を選択し、**Next** を選択します。

![合成 dataset の選択](../docs/images/lab05-data-selection.png)

この dataset は setup が `data/eval/live_subset.jsonl` から登録した架空データです。
通常は schema が一致するため **Field mapping** は自動で完了します。画面が開いた場合だけ、
dataset の `query` を `query` に割り当てて **Next** を選択します。
Portal の **Synthetic generation** preview は、2026-09-01 の keyless 構成では空の
item schema を作る場合があるため、本編では使いません。

## 3. Agent の入力を確認する

1. **Configure agents** で `contoso-travel-assistant` の **Configure** を選択します。
2. **USER > Prompt** に `{{item.query}}` を入力し、**Save** を選択します。
3. **Next** を選択します。

![Dataset の query を Agent へ渡す](../docs/images/lab05-agent-prompt.png)

`item.query` は dataset の `query` column です。Agent の instructions は変更しません。

## 4. Criteria を選択する

**Criteria** では、次の 4 つだけを残して **Next** を選択します。

| Evaluator | 確認すること |
|---|---|
| **TaskAdherence** | instructions と依頼に従ったか |
| **TaskCompletion** | 必要な内容を回答したか |
| **ToolSelection** | 必要な tool を選んだか |
| **ToolInputAccuracy** | tool へ正しい値を渡したか |

Evaluator を増やすほど実行時間と料金が増えます。この Lab では 4 つに限定します。

## 5. 実行する

1. **Review** の Evaluation name に `contoso-travel-portal-eval` を入力します。
2. Target、dataset、criteria を確認します。
3. **Submit** を選択します。
4. Evaluation detail の run が **Completed** になるまで待ちます。

7 件では通常数分かかります。**In progress** の間は同じ run を再送しません。

## 6. 結果を読む

完了した run を開き、**Overall metric results** と **Detailed metrics result** を確認します。

![Evaluation の結果](../docs/images/lab05-evaluation-results.png)

## 完了チェック

- 7 件の synthetic query が実行されている
- Evaluator ごとの pass / fail が表示される
- Tool が必要な row で tool call と入力値を確認できる
- Fail の row で evaluator の reason を確認できる

Fail は異常ではありません。改善点を見つけることが評価の目的です。
次の Lab では同じ dataset と、setup 済みの **Contoso Travel Rubric** を使います。

操作ラベルは 2026-09-01 時点の Foundry (new) を基準にしています。詳細は
[Run evaluations from the Microsoft Foundry portal](https://learn.microsoft.com/azure/foundry/how-to/evaluate-generative-ai-app)
を参照してください。

## 次の Lab

[Lab 6 — Agent Optimizer](06-optimization.md)

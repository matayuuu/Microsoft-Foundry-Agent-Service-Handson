# Lab 6 — Agent Optimizer（20分）

## ゴール

Lab 5 と同じ評価データを使って Prompt Agent の構成候補を生成し、
baseline より良い候補だけを agent に反映します。

改善前の **baseline** と、生成された **candidate** を同じ質問集・採点基準で比較し、
変更内容と結果から採用を判断します。

> [!WARNING]
> Agent と tool を dataset の各行で繰り返し実行するため、
> model と外部 tool の料金が発生します。

## 1. Optimization wizard を開く

1. **Build > Agents > contoso-travel-assistant** を開きます。
2. **Optimize** tab を選択します。
3. 初回は **Optimize my agent**、2 回目以降は **Create optimization run** を選択します。

## 2. Target を設定する

Lab 1 のデプロイの **Outputs > resourceOutputs** で、
`optimizer_model_deployment_name` と `evaluation_model_deployment_name` の値を確認します。
このハンズオンでは、どちらも `gpt-5.5` です。

**Target** step で次を設定します。

| 項目 | 値 |
|---|---|
| Version | Lab 4 までの変更を保存した最新の version |
| Optimization model | `optimizer_model_deployment_name` の値（`gpt-5.5`） |
| Max candidates | `1` |
| Evaluation model | `evaluation_model_deployment_name` の値（`gpt-5.5`） |
| Compare across models | Off |

両方のモデルに **gpt-5.5** を選びます。`gpt-5.6-luna` と `embedding` は選びません。
候補数はトークン消費を抑えるため **1** に限定します。

設定を確認して **Next** を押します。

![対象 version、2つのモデル、候補数、モデル比較 Off を設定する](../docs/images/lab06-target-settings.png)


## 3. Dataset を選択する

1. **Data** では **Select dataset and criteria** を選択します。
   初期選択の **Generate data** は使いません。質問集を新たに生成する必要はありません。

![Select dataset and criteria に切り替える](../docs/images/lab06-existing-data.png)

2. 右側の一覧で `contoso-travel-optimizer-live-subset` の行にチェックを付けます。
   `skill_...` のデータは選びません。
3. **Next** を選択します。

この dataset は Lab 5 と同じ 7 件の質問に、Optimizer が必要とする参照回答
（`ground_truth`）をすべて設定したものです。

## 4. Criteria を選択する

1. **Criteria** で、Lab 1 が登録した
   **[Contoso Travel Rubric](../docs/participant/contoso-travel-rubric.md)** を選択します。
2. ほかの評価器は追加せず、**Next** を選択します。

この評価器は、規程への準拠、引用、Tool の利用、対象範囲と安全性の 4 項目で回答を採点します。
実際に選ばれた Tool とその引数・出力は、候補ごとの Conversation / Trace で確認します。

![Optimizer の custom rubric 選択](../docs/images/lab06-optimizer-criteria.png)

## 5. Cost estimate を確認して実行する

**Review** で Agent、dataset、モデル、候補数、評価器と **Estimated cost** を確認し、
**Submit** を選択します。見積もりの **Maximum** は請求額の上限ではありません。

## 6. Candidate を比較する

Run detail の status が **Succeeded** になるまで待ちます。同じ run を再送しないでください。

1. **Improvement**、**Baseline**、**Best score** を比較します。
2. **Candidate results** の **View changes** で変更前後を確認し、**Close** で閉じます。
3. 表の右端の **Score details** にある `evalrun_...` のリンクを開きます。
   確認したい candidate の行を選んでください。

**Max candidates = 1** では、生成した候補 1 つに baseline を加えた 2 行が表示される場合があります。

`system_prompt` の変更と回答を読み、次を確認します。

- 不足情報を確認する指示や、予約・承認を実行したと誤認させない指示が残っている
- 規程の金額・承認条件・処理日数が指示文へ書き写され、検索結果より優先される構成になっていない
- 正しい回答ができていた質問で、不要な確認質問が増えていない
- 参照していない出典や、実行していない tool の結果を作らせていない
- `tool_search` / `call_tool` と downstream operation のどちらかを隠す変更になっていない
- 見積もり依頼で `createPreapproval`、Web Search、Code Interpreter を不要に呼んでいない

Evaluation run を開いたら、**Detailed metrics result** のスコア横の詳細ボタン
（**View rubric details**）を選びます。

観点ごとの重み・スコア・理由を確認し、**Done** で閉じて比較画面へ戻ります。
少数の質問による評価なので、点数が上がっても、内容や安全性が悪化していれば採用しません。
小さなスコア差だけで改善を判断することも避けてください。

採用できる改善案がなくても、ここまで比較できればこの Lab の目的は達成しています。
その場合は次の「反映する」を飛ばし、Lab 7 へ進みます。

## 7. 改善した candidate を反映する

明確に改善した candidate がある場合だけ実行します。

1. **Promote candidate** を選択します。
2. Best candidate と baseline の score 差、変更内容を再確認します。
3. 確認ダイアログの **Promote to agent version** を選択します。

**Promoted** の表示を確認します。
Agent に戻り、モデルが `gpt-5.6-luna`、Knowledge と Toolbox の接続が残っていることを
確認します。Toolbox 側では Code Interpreter、Web Search、2 つの Skills、既存の
policies/guardrail、Tool Search On が残っていることも確認します。Skills は Lab 7 用に
登録・公開を維持しますが、Prompt Agent が利用した証拠は `load_skill` または
`resources/read` の Trace がある場合だけです。次の Lab 7 の Harness Agent は共有 factory の
Skill provider で Skills を読み込み、その実行記録を確認します。

**New chat** で Lab 3 / 4 の質問を試し、規程確認と
`tool_search → call_tool → createTripEstimate` が引き続き動作するか確認してください。

詳細は
[Quickstart: Optimize a prompt agent](https://learn.microsoft.com/azure/foundry/agents/quickstarts/quickstart-optimize-prompt-agent)
を参照してください。

## 次の Lab

[Lab 7 — Agent Framework で Agent と Harness Agent を作る](07-agent-framework-harness.md)

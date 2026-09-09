# Lab 6 — Agent Optimizer（20分）

## ゴール

Agent Optimizer が `gpt-5.6-luna` を最適化モデルとして受け付ける環境では、
Lab 5 と同じ評価データを使って Prompt Agent の構成候補を生成し、
baseline より良い候補だけを agent に反映します。対応していない環境では
互換性ゲートを確認し、別モデルを追加せず参考結果で比較方法を学びます。

改善前の **baseline** と、生成された **candidate** を同じ質問集・採点基準で比較し、
変更内容と結果から採用を判断します。

> [!WARNING]
> Agent と tool を dataset の各行で繰り返し実行するため、
> model と外部 tool の料金が発生します。

## 0. 評価条件を確認する

Lab 5 を実行できた場合は、`sample.output_items` / `sample.tool_calls`、Conversation、Trace の
メモを確認します。Sol をデプロイできず Lab 5 をスキップしていても、Optimizer の
互換性ゲートは確認できます。ここでは process evaluator を使わず、登録済みの
task-level rubric だけで比較するためです。downstream call が `sample.tool_calls` に
flatten されるとは仮定しません。

## 使用する値

```bash
jq -r '
  .terraform_outputs
  | {
      evaluation_model: .primary_model_deployment_name.value,
      optimization_model: .primary_model_deployment_name.value
    }
' .workshop/context.json
```

## 1. Optimization model の互換性を確認する

1. **Build > Agents > contoso-travel-assistant** を開きます。
2. **Optimize** tab を選択します。
3. 次の表示を確認します。

| 表示 | 対応 |
|---|---|
| **No supported optimization model** | `gpt-5.6-luna` が現在の Agent Optimizer の最適化モデルに未対応です。下記のスキップ手順へ進む |
| **Create optimization run** があり、Optimization model に `gpt-5.6-luna` を選択できる | セクション2以降を実行する |

2026-09-09 時点の
[Agent Optimizer の対応モデル](https://learn.microsoft.com/azure/foundry/agents/concepts/agent-optimizer-overview#models)
には `gpt-5.6-luna` が含まれません。Japan East の実環境でも
**No supported optimization model** が表示されることを確認しています。
この表示はクォータ不足ではなく、機能とモデルの互換性によるものです。

### Luna が未対応の場合

1. **Deploy a model** は選択せず、`gpt-5`、`gpt-5-mini`、`Phi-4`、`model-router` などを
   追加しません。Sol も選択しません。
2. Codespace で
   `instructor/completed-run-assets/optimizer-run.simulated.json` を開きます。
3. baseline と candidate の score、`instructions_diff_summary_ja` を比較し、
   「すべての候補が baseline を下回る場合は現状維持」という判断基準を確認します。
4. この Lab の live 実行を省略し、[Lab 7](07-agent-framework-harness.md) へ進みます。

この分岐により、Sol を Lab 5 の judge 以外へ流用せず、ほかの LLM を Luna に統一する
モデル方針を維持します。将来 Luna が対応モデルへ追加された場合だけ、以下を実行します。

## 2. Optimization wizard を開く

1. **Create optimization run** を選択します。

## 3. Target を設定する

**Target** step で次を設定します。

| 項目 | 値 |
|---|---|
| Version | Lab 4 までの変更を保存した最新の version |
| Optimization model | `primary_model_deployment_name` の値（通常 `gpt-5.6-luna`） |
| Max candidates | `1` |
| Evaluation model | `primary_model_deployment_name` の値（通常 `gpt-5.6-luna`） |
| Compare across models | Off |

両方のモデルに **gpt-5.6-luna** を選びます。`gpt-5.6-sol` と `embedding` は選びません。
候補数はトークン消費を抑えるため **1** に限定します。

設定を確認して **Next** を押します。

![対象 version、2つのモデル、候補数、モデル比較 Off を設定する](../docs/images/lab06-target-settings.png)

**Optimization model** は改善案を作る役、**Evaluation model** は回答を採点する役です。
この演習では両方に同じ `gpt-5.6-luna` deployment を選びます。
評価対象の Agent 自体は `gpt-5.6-luna` のままで、ここでは変更しません。

## 4. Dataset を選択する

1. **Data** では **Select dataset and criteria** を選択します。
   初期選択の **Generate data** は使いません。質問集を新たに生成する必要はありません。

![Select dataset and criteria に切り替える](../docs/images/lab06-existing-data.png)

2. 右側の一覧で `contoso-travel-eval-live-subset` の行にチェックを付けます。
   `skill_...` のデータは選びません。
3. **Next** を選択します。

`Insufficient traces` が表示されても、既存 dataset を選ぶこの手順では
トレースを増やすための追加実行は不要です。

live subset は常に 7 件で、明確に無関係な out-of-scope case を含みます。Web Search と
Code Interpreter を呼ぶ case は含まれないため、process evaluator の限定対応に影響されません。
現在情報を Web Search で調べる master case は、固定 fact ではなく出典 URL と取得日時を
task-level/custom rubric/Trace で確認する対象であり、Optimizer の live subset には追加しません。

## 5. Criteria を選択する

**Criteria** では、setup が登録したカスタム評価器 **Contoso Travel Rubric** の行に
チェックを付け、**Next** を選択します。この演習では、ほかの評価器は追加しません。

この rubric は回答と期待する振る舞いを task-level で比較します。Tool Search の
`tool_search` / `call_tool` の選択と、その内側の実 operation の正確さを 1 つの process score
として扱いません。候補ごとの Conversation / Trace で 2 層を確認します。Code Interpreter や
Web Search を使う別 dataset に ToolInputAccuracy 等を適用しないでください。

![Optimizer の custom rubric 選択](../docs/images/lab06-optimizer-criteria.png)

## 6. Cost estimate を確認して実行する

**Review** で Agent、dataset、モデル、候補数、評価器と **Estimated cost** を確認し、
**Submit** を選択します。見積もりの **Maximum** は請求額の上限ではありません。

## 7. Candidate を比較する

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

## 8. 改善した candidate を反映する

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

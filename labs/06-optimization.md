# Lab 6 — Agent Optimizer（20分）

## ゴール

Lab 5 と同じ評価データを使って Prompt Agent の構成候補を生成し、
baseline より良い候補だけを agent に反映します。

**Baseline** は改善前の Agent、**candidate** は改善案です。
Optimizer が指示文などの候補を作り、同じ質問集・採点基準で比較します。
自動で作られた候補を必ず採用するのではなく、変更内容と結果を読んで判断します。

> [!WARNING]
> Agent と tool を dataset の各行で繰り返し実行するため、
> model と外部 tool の料金が発生します。

## 使用する値

```bash
jq -r '
  .terraform_outputs
  | {
      evaluation_model: .optimizer_model_deployment_name.value,
      optimization_model: .optimizer_model_deployment_name.value
    }
' .workshop/context.json
```

## 1. Optimization wizard を開く

1. **Build > Agents > contoso-travel-assistant** を開きます。
2. **Optimize** tab を選択します。
3. 初回は **Optimize my agent**、2 回目以降は **Create optimization run** を選択します。

## 2. Target を設定する

**Target** step で次を設定します。

| 項目 | 値 |
|---|---|
| Agent version | 既定で選択される最新の保存内容 |
| Optimization model | `optimizer_model_deployment_name` の値（通常 `gpt-5.5`） |
| Max candidates | `2` |
| Evaluation model | `optimizer_model_deployment_name` の値（通常 `gpt-5.5`） |
| Compare across models | Off |

設定後、**Dataset** へ進みます。

**Optimization model** は改善案を作る役、**Evaluation model** は回答を採点する役です。
この演習では両方に同じ `gpt-5.5` deployment を選びます。
評価対象の Agent 自体は `gpt-5.6-luna` のままで、ここでは変更しません。

## 3. Dataset を選択する

1. `contoso-travel-eval-live-subset` を選択します。
2. **Next** を選択します。

## 4. Criteria を選択する

**Criteria** では、setup が登録したカスタム評価器 **Contoso Travel Rubric** を
選択し、**Next** を選択します。この演習では、ほかの評価器は追加しません。

![Optimizer の custom rubric 選択](../docs/images/lab06-optimizer-criteria.png)

## 5. Cost estimate を確認して実行する

**Review** で次を確認します。

- Agent と dataset
- Evaluation / optimization model
- Candidate 数
- Evaluator
- **Estimated cost**

見積もりの表示を待ちます。これは上限ではありません。
内容を確認して **Submit** を選択します。

## 6. Candidate を比較する

Run detail の status が **Succeeded** になるまで待ちます。実行中は
**Working on iteration 1 of 1** と表示されます。同じ run を再送しないでください。

1. **Improvement**、**Baseline**、**Best score** を比較します。
2. **Candidate results** の **View changes** で変更前後を確認します。
3. Candidate の evaluation run を開き、rubric の score と reason を確認します。

![Optimizer の candidate 比較](../docs/images/lab06-optimizer-results.png)

Score 差が `0.03` 未満なら noise の可能性があります。すべての candidate が baseline より
低い場合は、現在の agent を維持してください。

採用できる改善案がなくても、ここまで比較できればこの Lab の目的は達成しています。
その場合は次の「反映する」を飛ばし、Lab 7 へ進みます。

## 7. 改善した candidate を反映する

明確に改善した candidate がある場合だけ実行します。

1. **Promote candidate** を選択します。
2. Best candidate と baseline の score 差、変更内容を再確認します。
3. 確認ダイアログの **Promote to agent version** を選択します。

**Promoted** の表示を確認します。参加者が version 番号を記録する必要はありません。

詳細は
[Quickstart: Optimize a prompt agent](https://learn.microsoft.com/azure/foundry/agents/quickstarts/quickstart-optimize-prompt-agent)
を参照してください。

## 次の Lab

[Lab 7 — Agent Framework の Hosted Agent](07-hosted-multi-agent.md)

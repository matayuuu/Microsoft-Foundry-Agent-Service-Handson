# Lab 8 — Observability と cleanup（10分）

## ゴール

Prompt Agent と Hosted Agent の trace を確認し、ハンズオンで作成した Azure resources
を削除します。

Trace は、**1 回の依頼がどの順番で処理されたかをたどる記録**です。
回答だけでは分からない検索・tool 呼び出し・各 agent の処理を確認します。
確認が終わったら、費用が発生し続けないようにリソースを片付けます。

## 1. Trace を開く

1. Microsoft Foundry Portal で **Build > Agents** を開きます。
2. 対象 agent を選択します。
3. 上部の **Traces** tab を選択します。

Application Insights connection は Lab 1 の setup で作成済みです。
Trace が見えない場合は数分待って browser を再読み込みします。

## 2. Prompt Agent の trace を確認する

`contoso-travel-assistant` の **Traces** で、Lab 4〜6 で質問した実行の行を選択します。
対象の version と実行時刻を確認してください。操作方法は
[Lab 3 の検索 trace](03-rag-foundry-iq.md#6-回答の根拠を確認する)、
[Lab 4 の API 呼び出し](04-tools-toolbox.md#7-api-の実行と-skill-の利用を区別して確認する)
でも確認できます。

- Model の input / output と token 数
- Foundry IQ の retrieval
- `travel_ops_api` の tool call と引数
- 各 span の latency と status

## 3. Hosted Agent の trace を確認する

1. `contoso-travel-hosted-planner` の **Traces** で、Lab 7 の実行時刻に対応する
   **Trace ID** を選択します。再デプロイしている場合は、上部の Version も確認します。

2. 詳細画面を右上の拡大ボタンで広げ、**Trajectories** の **Find in trace** に
   `invoke_agent` と入力します。
3. `policy_agent`、`planner_agent`、`reviewer_agent` が順番に並び、成功していることを確認します。

![invoke_agent で絞り込み、3つの担当と処理時間を確認する](../docs/images/lab08-hosted-agent-trace.png)

先頭の名前なしの `invoke_agent` はホストの受付処理です。
出張を検討する担当は、名前が付いた上の **3 agent** です。

4. `reviewer_agent` を選択し、**Input + Output** の **Output** を読みます。
   Lab 7 の最終回答と、航空券を含まない小計・シミュレーションの注意文を見比べます。

5. **Find in trace** を `workflow.run` に変更し、workflow 全体も成功していることを確認します。
   検索欄を空に戻せば全 span に戻ります。必要に応じて **Graph view** でも構造を確認できます。

## 完了チェック

- `policy_agent`、`planner_agent`、`reviewer_agent` の model call が順番に表示される
- 最後の output が reviewer の回答になっている
- `workflow.run` と 3 つの `invoke_agent` が **Success** になっている

Cold start の最初に state store の `GET` が 1 回だけ `404` になり、直後の `POST` が
**Success** になる場合があります。これは state store の新規作成確認であり、
workflow の失敗ではありません。

Trace には prompt、response、tool の引数が保存されます。実データや secret を入力しないで
ください。詳細は
[Set up tracing](https://learn.microsoft.com/azure/foundry/observability/how-to/trace-agent-setup)
を参照してください。

## 4. Cleanup を実行する

repository root の terminal で実行します。

```bash
./scripts/destroy.sh
```

確認画面で対象 resource を確認し、削除を承認します。

`destroy.sh` は Hosted Agent を削除した後、Foundry project / account を含む Terraform
管理 resources を削除します。**割り当てられた resource group 自体は削除しません。**

## Cleanup の完了チェック

- Command が exit code `0` で終了する
- Workshop 管理 resource が resource group に残っていない
- Cleanup 成功後に `.workshop/` の生成 context が削除される

失敗した場合は Terraform state や `.workshop/` を手動で消さず、
[cleanup troubleshooting](../docs/participant/troubleshooting.md#cleanup)を確認して
同じ command を再実行してください。

## 5. Codespace を停止する

Azure の cleanup が完了したら、Codespace の稼働も止めます。
**Codespace を停止するだけでは Azure resources は削除されません。**
必ず上の cleanup の完了を先に確認してください。

1. 残しておきたい Notebook などの作業を保存します。
2. **Ctrl+Shift+P**（macOS は **Cmd+Shift+P**）で Command Palette を開きます。
3. `Codespaces: Stop Current Codespace` と入力し、同名の項目を選択します。

![Command Palette から Codespaces: Stop Current Codespace を選択する](../docs/images/lab08-stop-codespace.png)

4. 停止処理が終わり、**Codespace is stopped** と表示されることを確認します。
   **Stopping codespace...** の表示が続く場合は、ブラウザーを再読み込みして確認します。

5. **Restart codespace** は押さず、ブラウザーのタブを閉じます。

## 完了

これでハンズオンは終了です。

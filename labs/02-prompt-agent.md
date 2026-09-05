# Lab 2 — Prompt Agent（10分）

## ゴール

Microsoft Foundry Portal で、後続 Lab の knowledge と tool を接続する Prompt Agent
`contoso-travel-assistant` を作成します。

Prompt Agent は、**モデルと指示文を組み合わせたアシスタント**です。この Lab では
「何をする担当か」を設定します。社内規程を調べる機能は Lab 3、費用を計算する機能は
Lab 4 で追加します。

## 始める前に

Lab 1 の setup が完了し、自分の Foundry project を開いていることを確認します。
以後、同じ `contoso-travel-assistant` を編集して機能を追加します。
Lab ごとに別の Agent を作る必要はありません。

## 使用する値

```bash
jq -r '
  .terraform_outputs
  | {
      project: .foundry_project_name.value,
      model: .primary_model_deployment_name.value
    }
' .workshop/context.json
```

## 1. Prompt Agent を作成する

1. Microsoft Foundry Portal で対象 project を開きます。
2. 上部の **Build** を開き、**Agents** tab を選択します。
3. **New agent** から **Build an agent** を選択します（この UI ではそのまま Agent name 入力画面に遷移します）。
4. 次を設定します。

   | 項目 | 値 |
   |---|---|
   | Name | `contoso-travel-assistant` |
   | Model | `primary_model_deployment_name` の値 |

通常、Model に選ぶ deployment 名は **`gpt-5.6-luna`** です。
モデルカタログから別のモデルをデプロイするのではなく、Lab 1 で作成済みの
deployment を選びます。名前が見つからない場合は、対象 project と setup の完了を
確認してください。

## 2. Instructions を設定する

**Instructions** に次を貼り付けます。

```text
あなたは Contoso 社の社内向け出張・経費アシスタントです。
出張・経費に関する質問へ、日本語で簡潔に回答してください。

接続された knowledge または tool がある場合は、必ずそれを使って確認してください。
規程を参照した回答には出典を付け、確認できない値は推測しないでください。
Travel Ops tool の都市名には、Tokyo、Osaka、New York のような英語の canonical name を
渡してください。
予約や承認を実行したとは表現せず、シミュレーションであることを明示してください。
```

**Save** を選択します。

Instructions は **Agent が毎回守る役割・回答方針**で、利用者がその都度送る質問とは
別です。コードブロックの本文だけをコピーし、囲みのバッククォートは貼り付けません。

## 完了チェック

- Agents の一覧に `contoso-travel-assistant` が表示される
- Agent の model と instructions が保存されている
- Knowledge と Tools はまだ空である

この Lab では Playground の確認は行いません。続けて knowledge を接続します。

## 次の Lab

[Lab 3 — Azure AI Search と Foundry IQ](03-rag-foundry-iq.md)

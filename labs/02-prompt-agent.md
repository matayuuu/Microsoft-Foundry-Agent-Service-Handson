# Lab 2 — Prompt Agent（10分）

## ゴール

Microsoft Foundry Portal で、後続 Lab の knowledge と tool を接続する Prompt Agent
`contoso-travel-assistant` を作成します。

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

## 完了チェック

- Agents の一覧に `contoso-travel-assistant` が表示される
- Agent の model と instructions が保存されている
- Knowledge と Tools はまだ空である

この Lab では Playground の確認は行いません。続けて knowledge を接続します。

## 次の Lab

[Lab 3 — Azure AI Search と Foundry IQ](03-rag-foundry-iq.md)

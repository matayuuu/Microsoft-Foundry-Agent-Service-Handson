# Lab 2 — Prompt Agent（20分）

## ゴール

Microsoft Foundry portal で、**意図的に最小限の指示しか与えていない** baseline
Prompt Agent `contoso-travel-assistant` を作成し、version 1 として固定します。
この agent には、まだ Foundry IQ の knowledge base も Toolbox も接続しません
（Lab 3・Lab 4 で追加します）。何もつなげていない状態でどこまで答えられるか／
答えられないかを Playground で観察することが、このラボの目的です。

## 重要な用語の整理

`data/schemas/eval_case.schema.json` と `data/eval/live_subset.jsonl` に出てくる
`v1_expected_outcome` / `v2_expected_outcome` は、Foundry portal 上の実際の
version 番号（1, 2, 3, ...）とは**別物の概念的なラベル**です。

- `v1` = このラボで作る「素の baseline agent」（知識源なし・tool なし）の想定結果
- `v2` = Lab 3（Foundry IQ）と Lab 4（Toolbox）まで積み上げた「改善後の agent」の想定結果

Foundry portal 上では、agent を保存するたびに新しい version（1, 2, 3, ...）が
不変（immutable）に作成されます。このラボで作る baseline は portal 上では
**version 1** になりますが、Lab 3／Lab 4 で追加した後の agent は portal 上では
version 2・3 などになります — eval データの `v2_expected_outcome` は、その中で
最終的に Lab 5 の評価対象にする version を指しています。

## 1. Prompt Agent を作成する

Microsoft Foundry portal で、`.workshop/context.json` の `foundry_project_name`
に一致する project を開き、Agents（または同等のメニュー）から新しい Prompt Agent
を作成します。

- **名前**: `contoso-travel-assistant`
- **model deployment**: `.workshop/context.json` の `primary_model_deployment_name`
  出力（既定 `primary`、`gpt-4.1`）
- **knowledge source / tool**: このラボでは何も追加しません

## 2. Baseline instructions（日本語、そのままコピーして使用）

次のテキストを、そのまま agent の instructions（システムプロンプト）欄に貼り付けてください。
意図的に、根拠の明示・引用形式・対応範囲外の質問への振る舞い・ツール利用方針などを
一切指定していません。

```text
あなたは Contoso 社の社内向け出張・経費アシスタントです。
社員から出張や経費に関する質問を受けたら、日本語で分かりやすく回答してください。
```

> [!IMPORTANT]
> この instructions を Lab 5・Lab 6 より前に書き換えないでください。Lab 6 の
> Agent Optimizer は、この baseline を出発点として改善案を提案します。書き換えて
> しまうと、後続ラボでの before/after 比較が成立しなくなります。

## 3. Playground で試す

保存すると Playground でチャットできるようになります。`data/eval/live_subset.jsonl`
から、次のような性質の異なる質問を 2〜3 件試してみてください（実際の文言は
JSONL を開いて確認してください — 例えば `category: "direct_policy_fact"` の
単純な事実確認と、`category: "multi_hop"` の複数文書にまたがる質問、
`category: "out_of_scope"` の対応範囲外の質問）。

観察ポイント:

- 知識源がないため、具体的な金額や日数などの規程の数字は**根拠なく推測（ハルシネーション）
  するか、「わかりません」と答えるかのどちらか**になりやすいはずです。
- 複数文書にまたがる質問（`multi_hop`）や、ツール呼び出しが必要な質問
  （`category: "tool_choice"`、例えば日当計算や見積もり）には、根本的に対応できません
  — まだ knowledge base も Toolbox も接続していないためです。
- 対応範囲外の質問（`category: "out_of_scope"`）や安全性に関わる質問
  （`category: "safety"`）に対して、明確な線引きをせず答えてしまう可能性があります。

これらの弱点は Lab 3〜Lab 6 で段階的に改善していきます。今の時点では**直す必要は
ありません** — Lab 5 の評価で数値として可視化することが目的です。

## 4. Versioning を確認する

Prompt Agent の version 一覧画面で、たった今保存した version（portal 上の番号を
メモしておいてください）が一覧に表示されることを確認します。Foundry の Prompt Agent
は保存のたびに新しい不変の version を作るため、この後 Lab 3・Lab 4 で knowledge
source や tool を追加すると、それぞれ新しい version が積み上がっていきます。
Lab 6 で Agent Optimizer が新しい version 候補を提案した際も、この version 履歴の
中に並びます。

## 次のステップ

[Lab 3 — Azure AI Search と Foundry IQ](03-rag-foundry-iq.md) に進んでください。

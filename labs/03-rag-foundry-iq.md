# Lab 3 — Azure AI Search と Foundry IQ（35分）

## ゴール

構築済みの Azure AI Search index `contoso-travel-policy`
（`data/manifest.json` の規程文書 10 件がすでに投入済みです）を使って、まず
Prompt Agent に**直接** Azure AI Search をアタッチする方法を体験し、次に
**Foundry IQ** の knowledge source / knowledge base を同じ index の上に作成して、
単純検索と agentic retrieval の違いを比較します。

> [!WARNING]
> **Preview**: Foundry IQ の agentic retrieval（knowledge base 経由のマルチホップ検索）
> は、Microsoft Foundry portal / Azure portal のどちらの画面から使った場合でも、
> 現時点では preview 機能です（[feature-support-matrix.md](../docs/feature-support-matrix.md)
> 参照）。挙動やコスト計算方法は今後変わる可能性があります。

## 1. index を直接アタッチする（改善前: 単純検索）

Prompt Agent `contoso-travel-assistant` の編集画面で、knowledge source として
Azure AI Search を追加します。

- **connection**: `.workshop/context.json` の `search_connection_name` 出力
- **index**: `contoso-travel-policy`

保存すると新しい version が作られます。Playground で、単一の規程文書だけで
答えられる質問（`data/eval/live_subset.jsonl` の `category: "direct_policy_fact"`、
例えば日帰り出張の日当額）を試してください。今度は具体的な数字を、出典（citation）
付きで返せるはずです。

次に、複数の規程文書にまたがる質問（`category: "multi_hop"`、例えば「国際線
ビジネスクラス利用の飛行時間条件と、必要な承認者」）を試してください。単純な
Azure AI Search 検索は 1 回のクエリで最も関連度の高い断片を返すため、
2 つの条件のうち片方しか拾えない、あるいは根拠文書を統合できないことがあります
— これが `v1_failure_mode` に書かれている挙動です。

## 2. Foundry IQ の knowledge source / knowledge base を作る

同じ既存 index の上に、Foundry IQ の knowledge source を新規作成します。

- **knowledge source の種類**: Azure AI Search（既存 index を参照）
- **参照する index**: `contoso-travel-policy`（新しい index やコネクションを
  作る必要はありません — すでにある index をそのまま参照します）

knowledge source を作成したら、それを束ねる knowledge base を作成します。

- **query planner model**: `.workshop/context.json` の
  `primary_model_deployment_name`（`gpt-4.1`）
- **reasoning effort**: **low**（コストと待ち時間を抑えるため。
  [costs-and-cleanup.md](../docs/costs-and-cleanup.md) の推奨値）

作成した knowledge base を、`contoso-travel-assistant` の新しい version に
knowledge source として接続します（Step 1 で直接アタッチした Azure AI Search
index の代わりに、knowledge base を使う version です）。

## 3. Direct 検索 と Agentic 検索 の比較

同じ multi-hop の質問を、今度は knowledge base 経由（agentic retrieval）の
version で試してください。Playground の応答に付随する **activity log**
（またはそれに相当する検索過程の表示）を開き、次を確認します。

- 何回クエリが発行されたか（1 回の単純検索ではなく、複数回の計画的な検索に
  分解されているはず)。
- 各ステップでどの根拠文書がヒットしたか。
- 最終回答の **citation** が、`data/eval/live_subset.jsonl` の
  `expected_citations`（例: `policy-flights-001`, `policy-approval-process-001`)
  に対応する複数の文書を含んでいるか。

Step 1（直接 index アタッチ）の応答と比較し、citation の完全性・正確性の違いを
observe してください。

## 4. 注意事項

- 本ラボで扱う index・knowledge source・knowledge base はすべて既存の
  `contoso-travel-policy` index を参照するだけです。新しい index を作成したり、
  Azure AI Search の構成を変更したりする必要はありません（Terraform が既に
  構築済みです）。
- Agentic retrieval は Azure AI Search の retrieval トークンと、query planner
  model のトークンの両方を消費します。reasoning effort を `low` に保ってください。
- Portal でできる操作は上記の通りです。この Lab で Toolbox や外部ツールの話は
  出てきません（Lab 4 の範囲です）。

## 次のステップ

[Lab 4 — Tools・Toolbox](04-tools-toolbox.md) に進んでください。

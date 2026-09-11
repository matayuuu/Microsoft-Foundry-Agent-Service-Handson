# Lab 7 — Agent Framework で Agent と Harness Agent を作る（45分）

## ゴール

これまで Portal で育てた `contoso-travel-assistant` と同じ情報源を、Python から作る
Microsoft Agent Framework の Agent でも利用します。

Notebook で次の 2 つを順に作ります。

1. **通常の Agent**: Lab 3 の Foundry IQ だけを接続し、Agent をコードで作る最小構成を学ぶ
2. **Harness Agent**: Foundry IQ を残したまま、Lab 4 の Toolbox tools と Skills を追加し、
   複雑な依頼を plan / todos / execute に分解して処理する

Lab 4 で公開した Skills は、この Lab で初めて `load_skill` により本文を読み込みます。
Toolbox へ登録しただけの状態と、Agent が実際に利用した状態の違いを実行記録で確認します。

> [!IMPORTANT]
> この Lab は Notebook 上で Agent をローカル実行しますが、モデル推論、Foundry IQ、
> Toolbox tools、Web Search は Azure 上のサービスを呼び出します。教材の合成データだけを
> 入力し、secret、顧客情報、個人情報を送信しないでください。

> [!WARNING]
> モデル、Foundry IQ、Code Interpreter、Web Search の利用には料金が発生します。
> Harness Agent の loop には反復上限を設定しています。同じ cell を結果待ちの間に再実行
> しないでください。既定の 40K TPM deployment で急な連続呼び出しを避けるため、model call
> の間に最大 20 秒ほど待つことがあります。

## 通常の Agent と Harness Agent

どちらも、Agent Framework の通常の `Agent` として `run()` できます。
違いは、組み立て時に追加される実行支援機能です。

| 構成 | この Lab で確認すること |
|---|---|
| `Agent(...)` | client、instructions、tools を明示して作る最小構成 |
| `create_harness_agent(...)` | 通常の Agent に mode、todos、memory、Skills、loop を組み合わせる factory |

`create_harness_agent` は decorator、別の Azure resource、multi-agent workflow ではありません。
複雑な作業を 1 つの Agent 内で管理しやすくした構成です。複数 Agent を明示的につなぐ方法は
次の Lab 8 で、通常 Agent だけを使って扱います。

## 1. Azure ML を準備して Notebook を開く

1. **この Lab の開始時に初めて** [Azure ML 実行環境](../docs/participant/environments/azure-ml.md)
   に従い、Lab 1 の custom template が作成した workspace を開きます。
2. **Standard_DS3_v2** Compute instance を **Idle shutdown** 有効で作成します。
3. Lab 1 の private ZIP を PC に展開した最上位 `Microsoft-Foundry-Agent-Service-Handson`
   folder を **Notebooks > User files > Upload folder** へ upload。
   `.workshop/context.json`、`scripts/`、`notebooks/`、`src/`、必要な `tests/` を含む構成を保ちます。
4. `notebooks/00-azureml-setup.ipynb` を built-in **Python 3.10 - SDK v2** で実行し、
   2 kernels を作成します。
5. Azure ML Studio の **Notebooks > User files** で
   [`notebooks/07-agent-framework-harness.ipynb`](../notebooks/07-agent-framework-harness.ipynb)
   を開きます。
6. kernel に **Python (Foundry Hosted Agent)** を選択します。
   `foundry-hosted-agent` Conda environment を指すことを確認します。
   root の **Python (Foundry Workshop)** は選びません。
7. 説明を読み、上から 1 cell ずつ実行します。エラーの cell を飛ばしません。

Notebook は download bundle 内の `.workshop/context.json` の `resource_outputs.<key>.value` を読みます。
接続先や model deployment を
手入力する必要はありません。認証には Azure ML Terminal で行った `az login --use-device-code` を使い、API key や
client secret は使いません。
Notebook を保存しても、実行中の session、todos、memory が保存されるわけではありません。
kernel を再起動した場合は接続セルから必要なセルを順番に再実行し、plan の確認もやり直します。

## 2. Foundry IQ を使う通常の Agent

Notebook 前半では、次の部品を順に作ります。

```text
FoundryChatClient
  + instructions
  + Foundry IQ MCP tool
  = travel_policy_agent
```

- `FoundryChatClient` は model に質問を送る client
- `instructions` は Agent の担当と回答方針
- `MCPStreamableHTTPTool` は Lab 3 の knowledge base を呼ぶ接続
- `Agent` は上の部品を一つにまとめ、`run()` できる実行単位

Lab 3 と同じ複数規程の質問を送り、`knowledge_base_retrieve` と citation を確認します。
この時点では Toolbox を渡していないため、費用計算や Web Search はできません。

## 3. Toolbox と Skills を使う Harness Agent

Notebook 後半では、同じ Foundry IQ に次を追加します。

```text
Foundry IQ
  + Lab 4 Toolbox
      - tool_search / call_tool
      - Travel Ops OpenAPI
      - Code Interpreter
      - Web Search
      - travel-estimation Skill
      - preapproval-simulation Skill
  + plan / execute mode
  + todos / bounded loop
  = travel_harness_agent
```

`FoundryToolbox` は Toolbox の tool を MCP 経由で読み込みます。
`toolbox.as_skills_provider()` は Skills の名前と説明を提示し、必要な Skill の本文だけを
`load_skill` で遅延読み込みします。全 Skill の本文を毎回 prompt に入れる方式ではありません。

Harness Agent が自動追加できる Web Search は無効にします。Web Search も含め、Lab 4 の
すべての callable tool が Toolbox の Tool Search を通るようにするためです。

## 4. plan mode で複合依頼を分解する

Notebook が作る合成依頼には、規程確認、費用見積もり、予算比較、現在の公開情報、
事前承認シミュレーションが含まれます。

最初の実行は **plan mode** です。ここではすぐに最終回答を作らず、`todos_add` で作業を
小さく分け、計画を提示します。

表示された計画を読み、次を確認します。

- Foundry IQ で社内規程と承認手続きを調べる
- `travel-estimation` Skill を読み、見積もり tool の使い方を確認する
- Travel Ops API で deterministic な費用見積もりを取得する
- Code Interpreter で予算との差額と消化率を計算する
- 明示的に依頼された現在情報だけ Web Search で調べる
- `preapproval-simulation` Skill を読み、合成の承認シミュレーションを実行する

計画に不要な処理や、実際の予約・承認が含まれていないことも確認します。

## 5. execute mode で todos を完了する

計画確認の次の cell で、同じ `AgentSession` を **execute mode** に切り替えます。
session を作り直さないため、plan mode で作成した todos が残ります。

execute mode では、未完了 todo がある間だけ Harness Agent を再実行します。
反復回数には上限があり、tool エラーを成功として扱いません。

Notebook に表示される実行記録で、少なくとも次を確認します。

1. `knowledge_base_retrieve` で社内規程を取得
2. `load_skill` で該当 Skill の本文を取得
3. `tool_search` で必要な tool schema を発見
4. `call_tool` で選択した tool を実行
5. Travel Ops / Code Interpreter / Web Search の結果を todos ごとに反映
6. `todos_complete` で未完了項目がなくなる

Tool Search は「複雑な依頼を分解する機能」ではありません。候補 tool を必要時に発見して
context を節約する機能です。依頼の分解と進捗管理は Harness の mode、TodoProvider、
session、loop が担当します。

## 完了チェック

- 通常の `Agent(...)` を client / instructions / tools から作成し、Foundry IQ の回答を確認した
- `create_harness_agent(...)` も通常の Agent を返す factory だと説明できる
- 通常 Agent には Foundry IQ だけ、Harness Agent には Foundry IQ + Toolbox + Skills がある
- plan mode で複合依頼が todos に分解され、確認後に同じ session を execute mode へ切り替えた
- `load_skill` と Skill resource の読み込みを確認した
- `tool_search`、`call_tool`、選択された実 tool の順を確認した
- 未完了 todos がなくなり、失敗した tool を成功として扱っていない
- 最終回答が社内規程、API 結果、現在の外部情報を出典と取得時点付きで区別している
- 実際の予約・承認ではないことが明記されている

## Lab 7 を飛ばして Lab 8 を行う場合

Lab 8 は、この Notebook の session、todos、memory、出力を引き継ぎません。
Lab 8 は `intake_agent`、`policy_agent`、`reviewer_agent` という通常 Agent の
sequential workflow です。Lab 3 の Foundry IQ が準備できていれば、経験者は
Lab 7 の Agent 実行を省略して Lab 8 へ進めます。ただし、この Lab の環境準備
（Compute、folder upload、`00-azureml-setup.ipynb`、2 kernels）は省略できません。

連続して受講する場合は、この Lab で単一 Agent 内の仕組みを観察してから、Lab 8 で
複数の通常 Agent に役割を分ける構成と比較してください。

## 参考資料

- [Microsoft Agent Framework — Agent Harness](https://learn.microsoft.com/agent-framework/concepts/harness)
- [Microsoft Agent Framework — Agent Skills](https://learn.microsoft.com/agent-framework/agents/skills)
- [Microsoft Agent Framework — Microsoft Foundry Toolbox](https://learn.microsoft.com/agent-framework/integrations/by-component/tools/foundry-toolbox)
- [Microsoft Foundry — Foundry IQ](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq)

## 次の Lab

[Lab 8 — 通常 Agent の sequential workflow](08-hosted-multi-agent.md)

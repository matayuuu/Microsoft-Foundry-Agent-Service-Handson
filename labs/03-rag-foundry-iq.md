# Lab 3 — Azure AI Search と Foundry IQ（35分）

## ゴール

利用条件と承認手続きを分けた 2 つの規程 index を使い、取得できた根拠の範囲と
回答品質を比較します。

1. **Azure AI Search tool**: 利用条件をまとめた検索用データ（index）だけを直接検索
2. **Foundry IQ knowledge base**: 質問を分解し、利用条件と承認手続きの 2 つの検索先
   （source）を横断検索

たとえば「ビジネスクラスに乗れるか」と「誰にどの順番で承認してもらうか」は、
別の規程に書かれています。同じ質問を 2 つの検索方法で試し、**回答の根拠が増えること**
を確認します。文書を検索して回答の根拠にする仕組みを RAG と呼びます。

> [!WARNING]
> 検索とモデルの呼び出しには料金が発生します。教材の合成データと質問例を使います。

## 使用する値

```bash
jq -r '
  .terraform_outputs
  | {
      search_service: .search_service_name.value,
      search_connection: "contoso-travel-search",
      direct_search_index: "contoso-travel-policy",
      approval_search_index: "contoso-travel-approval",
      knowledge_model: .optimizer_model_deployment_name.value
    }
' .workshop/context.json
```

## 1. Azure AI Search tool を接続する

1. **Build > Agents** から `contoso-travel-assistant` を開きます。
2. **Tools > Add > Add tools** を選択します。

![Tools の Add から Add tools を選ぶ](../docs/images/lab03-add-tools.png)

3. **Configured** の **Azure AI search** を選び、**Add tool** を選択します。

![Azure AI search を選んで追加する](../docs/images/lab03-select-ai-search.png)

4. **Azure AI Search connection** を開き、`search_service_name` の値
   （`srch-fdyws-...`）を選択します。**Connect to new resource** は使いません。

![接続欄で自分の Search service を選択する](../docs/images/lab03-search-connection.png)

`contoso-travel-search` は project connection 名です。この選択欄では
service 名が表示されるため、`search_service_name` と見比べてください。

5. `contoso-travel-policy` の行の丸い選択ボタンを選び、**Add** を押します。
   `contoso-travel-approval` はまだ選びません。

![policy index を選択する](../docs/images/lab03-ai-search-picker.png)

6. Agent に戻ったら **Select a search index** が `contoso-travel-policy` であることを
   確認し、**Save** を選択します。

![接続した index を確認して保存する](../docs/images/lab03-search-attached.png)

## 2. Direct search と citation を確認する

**Playground > New chat** で、次の質問を送ります。

```text
東京から大阪へ日帰り出張する場合、食事の日当はいくらですか?
```

回答の金額と引用を確認し、[日当・食事規程](../data/policies/04-per-diem-meals.md)と見比べます。
Search service のトップ URL が開く場合は
[citation のトラブルシューティング](../docs/participant/troubleshooting.md#citation-link)
を確認してください。

この確認後、もう一度 **New chat** を選び、複数 source の根拠が必要な
比較用質問を送ります。

```text
片道12時間の国際線を出発2日前にビジネスクラスで予約したいです。
直前予約として添付が必要なもの、ビジネスクラスの承認者と順序、
申請に使う機能名、申請から承認完了までの標準最大営業日数をまとめてください。
```

次の 4 項目について、回答に値があるかだけでなく、対応する citation があるかを記録します。

| 確認項目 | 根拠文書 |
|---|---|
| 直前予約で添付するもの | [フライト規程](../data/policies/02-flights.md) |
| 承認者と順序 | [承認プロセス規程](../data/policies/09-approval-process.md) |
| 申請に使う機能 | [承認プロセス規程](../data/policies/09-approval-process.md) |
| 標準最大所要期間 | [承認プロセス規程](../data/policies/09-approval-process.md) |

`contoso-travel-policy` にはフライト規程が含まれますが、承認プロセス規程は
`contoso-travel-approval` に分けてあります。今は前者だけを接続しています。
回答に値が書かれていても、対応する資料で裏付けられなければ未取得として記録します。

画面の **AI Quality** の数値だけで合否を決めず、この表の 4 項目と根拠を使って
比較します。

## 3. Foundry IQ knowledge base を作成する

Agent に接続する前に、**Build > Knowledge** で knowledge base を作成します。

1. 左 navigation の **Build > Knowledge** を開きます。
2. **Connection** に `contoso-travel-search` を選択します。
3. **Create a knowledge base** を選択します。

![Knowledge で Search 接続を選び、knowledge base を作成する](../docs/images/lab03-knowledge-home.png)

4. **Basic configuration** を次のように設定します。

   | 項目 | 値 |
   |---|---|
   | Name | `contoso-travel-knowledge-lab` |
   | Chat completions model | `optimizer_model_deployment_name` の値（通常 `gpt-5.5`） |
   | Retrieval reasoning effort | **Medium** |
   | Output mode | **Extractive data** |

   ![Foundry IQ knowledge base の基本設定](../docs/images/lab03-knowledge-base.png)

**Chat completions model** は **Deployments** の `gpt-5.5` を選びます。
**Retrieval reasoning effort** は初期値の Minimal から **Medium** に変更します。
**Description** と **Retrieval instructions** は、この演習では空のままで構いません。

5. **Knowledge sources (Foundry IQ) > Add sources > Azure AI Search Index** を選択します。

6. ダイアログを次のように設定し、**Create** を選択します。

   | 項目 | 値 |
   |---|---|
   | Name | `travel-rules-source-lab` |
   | Description | `出張の利用条件、フライト・宿泊・日当・領収書などの規程。承認手続きは別の source を参照する。` |
   | Select search index | `contoso-travel-policy` |

   ![Azure AI Search Index を knowledge source にする](../docs/images/lab03-knowledge-source.png)

7. もう一度 **Add sources > Azure AI Search Index** を選び、次を追加します。

   | 項目 | 値 |
   |---|---|
   | Name | `approval-workflow-source-lab` |
   | Description | `事前承認の申請機能、承認者と順序、標準処理日数を確認するための規程。` |
   | Select search index | `contoso-travel-approval` |

両方の source で **Advanced (optional)** は変更しません。

8. 2 つの source が一覧にあることを確認して、**Save knowledge base** を選択します。

![2つの source を確認して knowledge base を保存する](../docs/images/lab03-save-knowledge-base.png)

9. 一覧で `contoso-travel-knowledge-lab` の Status が **Active** になるまで待ちます。

Agent の **`gpt-5.6-luna`** は最終回答を作り、knowledge base の **`gpt-5.5`** は
どこをどう検索するかを考えます。後者は評価・Optimizer 用の deployment と共有します。
**Extractive data** を選ぶことで、knowledge base は取得した原文を返し、最終回答は
Prompt Agent が作成します。

**Medium** では検索結果が不十分な場合に追加の検索を行います。

## 4. Knowledge base を agent に接続する

1. **Build > Agents > contoso-travel-assistant** に戻ります。
2. 比較条件を揃えるため、**Tools** の **Azure AI Search** で
   **Actions > Remove** を選び、**Save** します。

![直接検索の tool だけを Remove し、その後 Agent を Save する](../docs/images/lab03-remove-direct-search.png)

Search service や index を削除する操作ではありません。接続方法だけを切り替えます。

3. **Knowledge** の一覧から `contoso-travel-knowledge-lab` を開きます。
4. **Use in an agent > contoso-travel-assistant** を選択します。
5. Agent 画面の **Knowledge** に knowledge base が表示されることを確認します。
   この操作で自動保存される場合があります。**Save** が有効なら押し、無効ならそのまま
   次へ進みます。

## 5. Agentic retrieval を確認する

Playground で **New chat** を選び、同じ質問を送ります。Direct search の回答が
会話履歴から混入しないよう、必ず新しい会話で比較してください。

```text
片道12時間の国際線を出発2日前にビジネスクラスで予約したいです。
直前予約として添付が必要なもの、ビジネスクラスの承認者と順序、
申請に使う機能名、申請から承認完了までの標準最大営業日数をまとめてください。
```

## 6. 回答の根拠を確認する

回答末尾の **根拠資料** に、フライト規程と承認プロセス規程が含まれることを確認します。
category はそれぞれ `flights` と `approval_process` です。追加の FAQ などが
含まれていても構いません。

Search index 型の Foundry IQ では、引用が `mcp://searchindex/...` という内部識別子で
表示されることがあります。これは通常の Web URL ではないため、ブラウザーで直接
開けることを成功条件にはしません。元資料は上の比較表の文書リンクから確認できます。

1. **Traces** で今回の **Trace ID** を開きます。
2. **Trajectories > Find in trace** で `knowledge_base_retrieve` を検索し、
   該当する処理の **Input + Output** を開きます。
3. **Input** の質問と、**Output** に含まれる `flights` / `approval_process` の文書を確認します。
   取得した文書と回答を見比べ、手順 2 で記録した結果と比較してください。

## 完了チェック

- 4 項目すべてが正しく、Direct search より根拠付き回答数が増えている
- 引用と根拠資料に、フライト規程と承認プロセス規程が含まれる
- Traces の `knowledge_base_retrieve` 出力に `flights` と `approval_process` の文書がある

<details>
<summary>回答後の確認ポイント</summary>

国内日帰りの食事日当は `1,500円` です。比較用質問は次の 4 項目を確認します。

| 確認項目 | 規程に基づく内容 |
|---|---|
| 直前予約で添付するもの | Contoso Expense にマネージャーの承認コメントを添付 |
| 承認者と順序 | マネージャー、次に部門 VP |
| 申請に使う機能 | `事前承認リクエスト` |
| 標準最大所要期間 | 4 営業日 |

期待する比較結果は、Direct search が原則 1/4、Foundry IQ が 4/4 です。生成文の表現は
変動しても、根拠文書を index 間で分離しているため citation coverage で同じ判定ができます。

</details>

背景仕様は
[What is Foundry IQ?](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq)、
[Connect Agents to Foundry IQ](https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect)、
[Retrieval reasoning effort](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-set-retrieval-reasoning-effort)、
[MCP の応答形式](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve#review-the-mcp-response)
を参照してください。

## 次の Lab

[Lab 4 — Travel Ops API の Toolbox](04-tools-toolbox.md)

# Lab 3 — Azure AI Search と Foundry IQ（35分）

## ゴール

利用条件と承認手続きを分けた 2 つの規程 index を使い、取得できた根拠の範囲と
回答品質を比較します。

1. **Azure AI Search tool**: 利用条件の index だけを直接検索
2. **Foundry IQ knowledge base**: 質問を分解し、2 つの source を横断検索

> [!WARNING]
> Microsoft Foundry Portal から作成する Foundry IQ の agentic retrieval は preview です。
> 実行ごとに Search と query-planning model の料金が発生します。

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
3. **Azure AI search** を選び、**Add tool** を選択します。
4. Search service の選択画面が表示された場合は
   `search_service_name` の値（例: `srch-fdyws-...`）を選択します。
5. **Select a search index** で `contoso-travel-policy` を選択します。

   ![Azure AI Search の index 選択](../docs/images/lab03-ai-search-picker.png)

   `contoso-travel-search` は project connection 名です。Agent の tool picker で
   service 名を求められた場合は、connection 名ではなく `search_service_name` を使います。

6. **Save** を選択します。

## 2. Direct search と citation を確認する

**Playground** で **New conversation** を選び、次の質問を送ります。

```text
東京から大阪へ日帰り出張する場合、食事の日当はいくらですか?
```

回答が `1,500円` で、引用が表示されることを確認します。引用を開くと、
この repository の `data/policies/04-per-diem-meals.md` が表示されます。
Search service のトップ URL が開く場合は
[citation のトラブルシューティング](../docs/participant/troubleshooting.md#citation-link)
を確認してください。

この確認後、もう一度 **New conversation** を選び、複数 source の根拠が必要な
比較用質問を送ります。

```text
片道12時間の国際線を出発2日前にビジネスクラスで予約したいです。
直前予約として添付が必要なもの、ビジネスクラスの承認者と順序、
申請に使う機能名、申請から承認完了までの標準最大営業日数をまとめてください。
```

次の 4 項目について、回答に値があるかだけでなく、対応する citation があるかを記録します。

| 確認項目 | 正解 | 根拠文書 |
|---|---|---|
| 直前予約で添付するもの | マネージャーの承認コメント | フライト規程 |
| 承認者と順序 | マネージャー、次に部門 VP | 承認プロセス規程 |
| 申請に使う機能 | `事前承認リクエスト` | 承認プロセス規程 |
| 標準最大所要期間 | 4 営業日 | 承認プロセス規程 |

`contoso-travel-policy` にはフライト規程が含まれますが、承認プロセス規程は
`contoso-travel-approval` に分けてあります。Direct search には前者しか接続していないため、
直前予約の添付要件と承認者名は取得できても、承認順序、申請機能、SLA の正式な根拠は
取得できません。値を推測して回答した場合も、承認プロセス規程の citation がなければ
未取得として数えます。

## 3. Foundry IQ knowledge base を作成する

> [!IMPORTANT]
> Agent の **Knowledge > Add** から先に **Foundry IQ** を選んでも、knowledge base が
> まだ無いため何も表示されません。最初に **Build > Knowledge** で作成します。

1. 左 navigation の **Build > Knowledge** を開きます。
2. **Connection** に `contoso-travel-search` を選択します。
3. **Create a knowledge base** を選択します。
4. **Basic configuration** を次のように設定します。

   | 項目 | 値 |
   |---|---|
   | Name | `contoso-travel-knowledge-lab` |
   | Chat completions model | `optimizer_model_deployment_name` の値 |
   | Retrieval reasoning effort | **Medium** |
   | Output mode | **Extractive data** |

   ![Foundry IQ knowledge base の基本設定](../docs/images/lab03-knowledge-base.png)

5. **Knowledge sources (Foundry IQ) > Add sources > Azure AI Search Index** を選択します。
6. ダイアログを次のように設定し、**Create** を選択します。

   | 項目 | 値 |
   |---|---|
   | Knowledge source name | `travel-rules-source-lab` |
   | Search index | `contoso-travel-policy` |

   ![Azure AI Search Index を knowledge source にする](../docs/images/lab03-knowledge-source.png)

7. もう一度 **Add sources > Azure AI Search Index** を選び、次を追加します。

   | 項目 | 値 |
   |---|---|
   | Knowledge source name | `approval-workflow-source-lab` |
   | Search index | `contoso-travel-approval` |

8. **Save knowledge base** を選択します。
9. 一覧で `contoso-travel-knowledge-lab` の Status が **Active** になるまで待ちます。

`primary` の `gpt-4.1` は Prompt Agent では利用できますが、2026-09-01 時点の
Portal の knowledge-base model picker では対象外です。この Lab では Portal が
サポートする `optimizer` の `gpt-5` deployment を使います。
**Extractive data** を選ぶことで、knowledge base は取得した原文を返し、最終回答は
Prompt Agent が作成します。

**Medium** は初回結果を semantic classifier で評価し、不十分な場合だけ query plan を
修正して最大 1 回再検索します。初回で十分と判定された場合は再検索されないため、
2 回目の検索が Activity に無くても失敗ではありません。この Lab の再現性は再検索の
発生有無ではなく、物理的に分けた 2 source から 4 項目の根拠を取得できたかで判定します。
Low より latency と model/Search の token 使用量が増える点にも注意してください。

## 4. Knowledge base を agent に接続する

1. **Build > Agents > contoso-travel-assistant** に戻ります。
2. 比較条件を揃えるため、**Tools** の **Azure AI Search** で
   **Actions > Remove** を選び、**Save** します。
3. `contoso-travel-knowledge-lab` の詳細画面へ戻ります。
4. **Use in an agent > contoso-travel-assistant** を選択します。
5. Agent 画面の **Knowledge** に knowledge base が表示されたら、**Save** を選択します。

## 5. Agentic retrieval を確認する

Playground で **New conversation** を選び、同じ質問を送ります。Direct search の回答が
会話履歴から混入しないよう、必ず新しい会話で比較してください。

```text
片道12時間の国際線を出発2日前にビジネスクラスで予約したいです。
直前予約として添付が必要なもの、ビジネスクラスの承認者と順序、
申請に使う機能名、申請から承認完了までの標準最大営業日数をまとめてください。
```

## 完了チェック

- 4 項目すべてが正しく、Direct search より根拠付き回答数が増えている
- 直前予約について、Contoso Expense にマネージャーの承認コメントを添付すると回答する
- 承認順序が「マネージャー、次に部門 VP」になっている
- `事前承認リクエスト` と「標準最大 4 営業日」が含まれる
- フライト規程と承認プロセス規程の 2 つの citation がある
- Activity の `knowledge_base_retrieve` に `travel-rules-source-lab` と
  `approval-workflow-source-lab` が表示される

期待する比較結果は、Direct search が原則 1/4、Foundry IQ が 4/4 です。生成文の表現は
変動しても、根拠文書を index 間で分離しているため citation coverage で同じ判定ができます。

操作ラベルは 2026-09-04 時点の Foundry (new) を基準にしています。
背景仕様は
[What is Foundry IQ?](https://learn.microsoft.com/azure/foundry/agents/concepts/what-is-foundry-iq)、
[Connect Agents to Foundry IQ](https://learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect)、
[Retrieval reasoning effort](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-set-retrieval-reasoning-effort)
を参照してください。

## 次の Lab

[Lab 4 — Travel Ops API の Toolbox](04-tools-toolbox.md)

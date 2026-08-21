# 選択ラボ — Fabric IQ（Contoso 出張・経費データを Fabric で公開する）

## この文書の位置づけ

このラボは**本編 3 時間 50 分に含まれません**。[architecture.md](../../docs/architecture.md)
の方針どおり、本ハンズオンの Terraform（`infra/`）は Microsoft Fabric の容量・ワークスペース・
ontology・data agent を一切作成しません。ここで説明する手順は、**別途 Fabric 容量とワーク
スペースを持つ組織**が、本編の Contoso 出張・経費シナリオを Fabric IQ 経由で Foundry agent に
つなぐ場合の**設計と接続手順**です。実際に手を動かす場合は、この文書の前提条件をすべて満たす
Fabric 管理者と一緒に進めてください。

> [!WARNING]
> **Preview**: Fabric IQ は現時点で public preview です。SLA なしで提供され、本番ワークロード
> には推奨されません。接続すると、モデルのトークン課金とは別に料金が発生し、データが Azure の
> コンプライアンス境界の外に送信される場合があります。責任は利用者側にあります
> （[Fabric IQ 公式ドキュメント](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq)
> の Warning 節）。

## 1. ゴール

`contoso-travel-assistant`（本編 Lab 2〜6 で使った Prompt Agent）に、Azure AI Search の
`contoso-travel-policy` index（規程文書、本編 Lab 3）とは別に、**Fabric IQ** を経由して
「Contoso の出張・経費**実績データ**（架空）」を問い合わせられるようにします。Lab 3 の
Foundry IQ が「規程文書に対する agentic retrieval」だったのに対し、Fabric IQ は
「Fabric 上の構造化データ（ontology・semantic model・data agent）に対する自然言語アクセス」
である違いを体験することが目的です。

## 2. 前提条件（すべて必須。resource group Owner だけでは不足します）

> [!IMPORTANT]
> 本編の参加者権限（既存 resource group の **Owner**）は、Fabric IQ の準備には**一切使えません**。
> Fabric IQ が必要とするのは Fabric テナント・容量・ワークスペース側の権限であり、Azure
> resource group の権限とは別系統です。以下はすべて、本編とは別の Fabric 管理者が事前に
> 準備しているという前提で読んでください。

### 2.1 呼び出すすべてのユーザーに Fabric ライセンスが必要

Fabric IQ を Foundry agent 経由で呼び出す**すべてのユーザー**（開発者だけでなく、agent を
使うエンドユーザー全員）が、問い合わせ対象の Fabric item にアクセスできる
[Microsoft Fabric ライセンス](https://www.microsoft.com/microsoft-fabric)を持っている必要が
あります。「agent の呼び出し元の資格情報でアクセス制御される」という Fabric の仕組み上、
ライセンス不足のユーザーは agent 経由でも Fabric データにアクセスできません。

### 2.2 有償 Fabric 容量（F2 以上）または Power BI Premium（P1 以上）

Fabric data agent を使う場合は、**有償の F2 以上の Fabric 容量**、または **Microsoft Fabric
が有効化された Power BI Premium P1 以上の容量**の上に公開されている必要があります。
無償の Fabric トライアル容量や、Fabric が無効な Power BI 容量では動作しません。

### 2.3 リージョン: 「Power BI のみ」の地域では利用不可

Fabric IQ は、その地域で **Power BI のみが Fabric ワークロードとして提供されている**場合は
利用できません。Fabric のフルスタック（lakehouse、eventhouse、OneLake など）が提供されている
リージョンの Fabric ワークスペースが必要です。ワークスペースの地域が対象かどうかは
[Microsoft Fabric region availability](https://learn.microsoft.com/fabric/admin/region-availability#power-bi)
で確認してください。

### 2.4 公開済みの Fabric item（ontology・Fabric data agent・Power BI semantic model のいずれか）

問い合わせ対象は次のいずれかで、**あらかじめ公開（publish）済み**である必要があります。

| Fabric item | 用途 | 追加要件 |
|---|---|---|
| **Ontology** | エンティティ・プロパティ・関係性に基づく質問 | — |
| **Power BI semantic model** | メジャー・階層に基づく分析的な質問 | 複雑なメジャー推論には `gpt-5.4` や `opus 4.7` 等の新しいモデルを推奨 |
| **Fabric data agent** | 会話形式の Q&A、長時間実行のクエリ | 有償 F2 以上または Power BI Premium P1 以上の容量上に公開済み。テナント設定で cross-geo processing/storage が必要な場合は有効化。data agent とそのデータソースは**同一リージョンの容量**上にあること |

さらに、呼び出し元ユーザーまたはサービスプリンシパルが、対象の item と各データソースへの
**読み取り権限**を Fabric 側で持っている必要があります。

### 2.5 Azure RBAC ロール（Foundry 側）

| ロール | 対象 | 用途 |
|---|---|---|
| **Foundry User** | 開発者本人、agent の実行時 identity、OAuth フローに関わるユーザー identity | Fabric IQ ツールを使う agent の作成・実行 |
| **Foundry Project Manager** | 接続を作成する担当者 | Fabric IQ エンドポイントへの Foundry connection 作成 |

これらは本編 Lab 4/5 と同じ Foundry project 上のロールですが、`infra/rbac.tf` は Fabric IQ
connection 用のロールを付与しません。本ラボを行う場合は、Fabric 管理者と Foundry project
管理者が individually にロールを付与する必要があります。

### 2.6 認証方式: managed OAuth と BYO（Bring Your Own）Entra app の違い、および admin consent

Fabric IQ への接続には、item の種類ごとに次の認証方式があります。

| Fabric item | 最初のクエリで使える認証 |
|---|---|
| Ontology | BYO Entra app または managed OAuth connection 経由の delegated user authentication |
| Power BI semantic model | 同上 |
| Fabric data agent | Foundry connection 経由は BYO Entra app または managed OAuth。data agent の MCP エンドポイントに**直接**アクセスするクライアントに限り、user token または service-principal token も使用可 |

- **Managed OAuth**: Foundry が Entra アプリ登録と同意フローを代行して管理する方式です。
  セットアップは速い一方、テナントによっては「マルチテナントアプリへの同意」を許可する
  ポリシーが必要になる場合があります。
- **BYO Entra app**: 組織自身が Entra アプリ registration を作成し、delegated permission を
  設定した上で、テナント管理者が **admin consent** を明示的に許可する方式です。組織のアプリ
  ガバナンスに従いたい場合はこちらを選びます。

どちらの方式でも、初回セットアップ時にテナント管理者による同意（またはテナントのユーザー
同意ポリシーの確認）が必要になり得ます。resource group Owner ロールはこの同意を代替しません。

### 2.7 Foundry Toolkit（VS Code 拡張機能）

[Visual Studio Code](https://code.visualstudio.com/) と
[Foundry Toolkit for Visual Studio Code](https://code.visualstudio.com/docs/intelligentapps/overview#_install-and-setup)
をインストールしておくと、Toolbox 経由で Fabric IQ ツールを追加する UI フローが使えます
（後述）。

## 3. Contoso シナリオでの適用イメージ（架空・本リポジトリでは構築しません）

Fabric 管理者がすでに次を準備している状況を想定します（すべて架空のデータで、本リポジトリの
`data/` とは別に Fabric ワークスペース上へ手動で作られたものです）。

- Fabric ワークスペース `contoso-travel-fabric-ws`（フル Fabric スタックが提供されるリージョン、
  有償 F2 以上の容量）。
- ontology `ContosoTravelOntology`。エンティティ `Employee`・`Trip`・`ExpenseReport` と、
  それぞれの関係性（`Employee` が複数の `Trip` を持つ、など）を OneLake 上の lakehouse に
  バインドしたもの。
- 公開済みの Fabric data agent `contoso-expense-fabric-agent`。上記 ontology を基盤にした
  会話型 Q&A エンドポイント。

この状態に対して、`contoso-travel-assistant` から次のような**架空のプロンプト**で問い合わせる
デモを想定します。

- 「先週、経費規程の日当上限を超えて申請された Trip の件数は？」
- 「今四半期、承認待ちのままになっている経費申請を部署別に集計して」

いずれも Contoso 社内の合成データに関する質問であり、実在の従業員・経費情報は一切含みません。

## 4. 接続手順（概念。実施は Fabric 管理者と一緒に）

### 4.1 Fabric IQ サーバー URL を確認する

Fabric item の種類ごとに MCP エンドポイントの URL パターンが異なります。

| Fabric item | `server_url` パターン |
|---|---|
| Power BI semantic model | `https://api.fabric.microsoft.com/v1/mcp/fabricaihub/integrations/m365` |
| Ontology | `https://api.fabric.microsoft.com/v1/mcp/dataPlane/workspaces/{workspaceId}/items/{itemId}/ontologyEndpoint` |
| Fabric data agent | `https://api.fabric.microsoft.com/v1/mcp/workspaces/{workspaceId}/dataagents/{dataAgentId}/agent` |

`{workspaceId}` / `{itemId}` / `{dataAgentId}` は Fabric portal で対象の item を開いた際の
ブラウザ URL から取得します。

### 4.2 Foundry Toolkit で Toolbox 経由に追加する（推奨パターン）

本編 Lab 4 と同様、Fabric IQ ツールも**直接 agent に追加するのではなく Toolbox 経由**にすると、
複数の agent での再利用や、認証情報・バージョン・ポリシーの一元管理がしやすくなります
（[公式ドキュメントの Tip](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq)）。

1. Foundry Toolkit の **My Resources > Tools** から Toolbox を作成または開く。
2. **Add tools** → **Configured** タブ → **Fabric IQ (OneLake Catalog)** を選択。
   Fabric IQ の接続自体（Ontology 用の OAuth 接続など）は Foundry Toolkit からは直接
   作成できないため、先に Foundry portal でその接続を作成してから Toolkit に戻ります。
3. **Publish**（新規 Toolbox）または **Save Changes**（既存 Toolbox）。

### 4.3 SDK で確認する場合（参考。本編スクリプトは変更しません）

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, FabricIQPreviewTool
from azure.identity import DefaultAzureCredential

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=FOUNDRY_PROJECT_ENDPOINT, credential=credential) as project_client,
):
    tool_payload = FabricIQPreviewTool(
        project_connection_id=FABRIC_IQ_PROJECT_CONNECTION_ID,
        require_approval="never",
    )
    agent = project_client.agents.create_version(
        agent_name="contoso-travel-assistant-fabriciq-demo",
        definition=PromptAgentDefinition(
            model=PRIMARY_MODEL_DEPLOYMENT_NAME,  # .workshop/context.json の primary_model_deployment_name
            instructions="Fabric IQ を使って Contoso の出張・経費実績に関する質問に答えてください。",
            tools=[tool_payload],
        ),
    )
```

`FABRIC_IQ_PROJECT_CONNECTION_ID` は Fabric 管理者と Foundry Project Manager が事前に作成した
connection の完全なリソース ID です。本編の `.workshop/context.json` にはこの値は含まれません
（本編の Terraform は Fabric connection を作らないためです）。このコードは**参考実装**であり、
`scripts/` 配下には追加しません — 実行する場合は自分のスクラッチファイルとして保存してください。

## 5. 検証する

1. Fabric item へのアクセス権を持つユーザーで、上記の架空プロンプトを Playground から送り、
   ontology の用語（`Trip`、`ExpenseReport` など）を使った質問に、Fabric 側のデータに基づく
   応答が返ることを確認します。
2. 同じ質問を、Fabric item へのアクセス権を**持たない**ユーザーで試し、権限がない場合は
   結果が返らない（または拒否される）ことを確認します。これは Fabric 側の permission
   enforcement が実際に効いていることの確認であり、Foundry 側でアクセス制御を作り込んで
   いるわけではないことを理解する目的です。

## 6. Cleanup（本編の `destroy.sh` の対象外）

- Fabric IQ 用に作成した Foundry connection と、それを使った agent version は、Foundry
  project 内のオブジェクトなので、本編と同様 Foundry portal または SDK
  （`project_client.agents.delete_version(...)`）から削除できます。
- Fabric ワークスペース側の ontology・data agent・容量そのものは、Fabric 管理者が Fabric
  portal から個別に削除・凍結してください。本リポジトリの `./scripts/destroy.sh` は
  Fabric 側のリソースを一切認識しません。

## 7. データ境界とコストの再確認

> [!WARNING]
> Fabric IQ に接続すると、コストが発生し、データが Azure のコンプライアンス境界の外に
> 送信される場合があります。データがどの境界を越えるか、組織のコンプライアンス・地理的
> 境界にどう影響するかを判断し、必要な許可・境界・承認を得るのは利用者の責任です
> （[公式ドキュメントの Warning 節](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq)）。
> 本ラボで送ってよいのは、架空の Contoso シナリオに関するプロンプトのみです。

## 公式参照

- [Connect agents to Microsoft Fabric with Fabric IQ (preview)](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/fabric-iq)
- [Fabric IQ overview](https://learn.microsoft.com/fabric/iq/overview)
- [Ontology overview](https://learn.microsoft.com/fabric/iq/ontology/overview)
- [Fabric data agent concept](https://learn.microsoft.com/fabric/data-science/concept-data-agent)
- [Microsoft Fabric region availability](https://learn.microsoft.com/fabric/admin/region-availability#power-bi)
- [Curate intent-based toolbox in Foundry](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox)

## 関連リンク

- [選択ラボ index](README.md)
- [本編 Lab 3 — Azure AI Search と Foundry IQ](../03-rag-foundry-iq.md)（Foundry IQ との違いの比較対象）
- [本編 Lab 4 — Tools・Toolbox](../04-tools-toolbox.md)

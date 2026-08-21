# 選択ラボ — Work IQ（Microsoft 365 データへの接続、架空プロンプトのみ）

## この文書の位置づけ

このラボは**本編 3 時間 50 分に含まれません**。Work IQ は Foundry agent から
Microsoft 365 Copilot の Work IQ を呼び出す機能で、**呼び出したユーザー本人の
Microsoft 365 権限とデータ**にアクセスします。本リポジトリは実在の Microsoft 365 テナント
データを一切保持・参照しないため、このラボは**設計・接続手順の説明**にとどめ、実際に試す
場合は必ず**自分自身の、許可されたテナント・アカウント**で、架空のプロンプトのみを使って
ください。

> [!WARNING]
> **Public preview**: Work IQ は public preview 機能で、SLA なしで提供され、本番ワークロード
> には推奨されません。接続すると、モデルのトークン課金とは別に料金が発生し、データが Azure の
> コンプライアンス境界の外に送信される場合があります
> （[公式ドキュメントの Warning 節](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq)）。
>
> 本ラボの手順・サンプルプロンプトは**すべて架空**です。実在の同僚のメール・会議・ファイルを
> 対象にした操作を、他者の許可なく行わないでください。

## 1. ゴール

`contoso-travel-assistant` に Work IQ ツールを追加し、「自分自身の」架空の Microsoft 365
コンテキスト（例: 自分宛のメール、自分のカレンダー）に対する自然言語の問い合わせを、
Agent-to-Agent（A2A）プロトコル経由で Work IQ に委譲する仕組みを理解します。

## 2. 前提条件（resource group Owner だけでは不足します）

> [!IMPORTANT]
> Work IQ のテナント初期設定は **Microsoft Entra Global Administrator** の 1 回限りの作業です。
> 本編の参加者権限（既存 resource group の Owner）では代替できません。すでに組織で Work IQ
> connection が用意されている場合は、この節の「テナント初期設定」は読み飛ばして
> 「agent へ追加する」節から進めてください。

### 2.1 商用要件: 課金方式ごとの違い

| 接続経路 | 要件の種類 | 要件 |
|---|---|---|
| A2A・REST・MCP 経由の Work IQ API | **従量課金** | [Copilot Credits の従量課金](https://learn.microsoft.com/microsoft-365-copilot/usage-based-billing-overview-copilot-credits) を有効化。コネクタライセンスは不要 |
| コネクタ経由の Microsoft 365 ツール（Teams、Word、Outlook Calendar/Mail、SharePoint、OneDrive など） | **コネクタライセンス** | 選択したコネクタごとの前提条件を確認。呼び出す各ユーザーに [Microsoft 365 Copilot ライセンス](https://www.microsoft.com/microsoft-365-copilot/pricing/individuals) が必要な場合がある |

「Work IQ Chat」（A2A エンドポイント経由）と、それ以外の個別コネクタ（Copilot Chat、Teams、
Word、Outlook Calendar/Mail、Microsoft 365 user profile、SharePoint、OneDrive）とで、課金・
ライセンスの性質が異なる点に注意してください。

### 2.2 Azure RBAC ロール（Foundry 側）

| ロール | 対象 | 用途 |
|---|---|---|
| **Foundry User** | 開発者本人、agent の実行時 identity、OAuth フローに関わるユーザー identity | Work IQ ツールを使う agent の作成・実行 |
| **Foundry Project Manager** | 接続を作成する担当者 | Work IQ エンドポイントへの Foundry connection 作成 |

### 2.3 テナント初期設定（1 回限り、Global Administrator が実施）

組織で最初の Work IQ connection を作る際、Global Administrator は次を行います。

1. Work IQ サービスプリンシパルをテナントにプロビジョニングする。
2. delegated 権限 `WorkIQAgent.Ask` に対する**テナント全体の admin consent** を許可する。

> [!NOTE]
> Global Administrator ロールは、この初期設定のためだけに
> [Microsoft Entra Privileged Identity Management (PIM)](https://learn.microsoft.com/entra/id-governance/privileged-identity-management/pim-configure)
> で**ジャストインタイムに有効化**し、設定完了後は**非活性化**することが推奨されます。
> 日常的に Work IQ を使うユーザーはこのロールを必要としません。

この初期設定が完了していれば、以降は Foundry User + Foundry Project Manager ロールを持つ
開発者が、Work IQ connection を作成し、agent に追加できます。

### 2.4 委任ユーザーコンテキスト（delegated user context）と On-Behalf-Of（OBO）

Work IQ へのリクエストは、**呼び出したユーザー本人の Microsoft 365 権限**の範囲でのみ実行
されます。Foundry は A2A プロトコル経由でリクエストを Work IQ に転送し、認証は
**On-Behalf-Of (OBO)** フローを使うため、agent 自身の identity ではなく、サインインしている
ユーザーの delegated 権限で実行されます。これにより、Work IQ は常にユーザー本人が Microsoft
365 上で閲覧できる範囲のメール・会議・ファイル・チャットにしかアクセスできません。

### 2.5 Foundry Toolkit / Node.js 前提条件

- **Foundry Toolkit**: [Visual Studio Code](https://code.visualstudio.com/) と
  [Foundry Toolkit for Visual Studio Code](https://code.visualstudio.com/docs/intelligentapps/overview#_install-and-setup)
  をインストールしておくと、Toolbox 経由で Work IQ を追加する UI フローが使えます。
- **JavaScript SDK を使う場合**: Node.js **22 以上**、`@azure/ai-projects` **2.4.0 以上**、
  `@azure/identity` が必要です（Python SDK を使う場合は `azure-ai-projects>=2.3.0` で足ります）。

### 2.6 直接 A2A 呼び出しをする場合

Work IQ は A2A プロトコルの **v1.0** と **v0.3** の両方をサポートします。新規実装では
`A2A-Version: 1.0` ヘッダーを送って v1 のメソッド名を使うことが推奨されます（ヘッダー省略時は
v0.3 として扱われます）。時刻に関連するリクエストには位置情報のメタデータを含め、常に
delegated user authentication を使用してください。

## 3. データ・コンプライアンスに関する重要な警告

> [!WARNING]
> - Work IQ に接続すると、コストが発生し、データが Azure のコンプライアンス境界の外に送信
>   される場合があります。データがどの境界を越えるか、組織のコンプライアンス・地理的境界に
>   どう影響するかを判断し、必要な許可・境界・承認を得るのは利用者の責任です。
> - 本ラボで送ってよいのは、**自分自身が実際にアクセス権を持つ、かつ許可された範囲**の
>   架空・業務上問題のないプロンプトのみです。他者のメール・会議・ファイルの内容を、本人の
>   同意なしに要約・引用させる操作は行わないでください。
> - 本リポジトリの Contoso データ（`data/`）は Microsoft 365 とは無関係な、規程文書・経費・
>   旅程の合成データです。Work IQ の応答に Contoso の合成データが混ざることはありません
>   （Work IQ は Microsoft 365 テナントのデータのみを扱います）。

## 4. Contoso シナリオでの適用イメージ（架空プロンプト例）

Work IQ 自体は実データにアクセスする機能のため、本ラボで使ってよいプロンプトは、
「自分自身の実際のメール・カレンダー」に対する**一般的な操作の例**にとどめます（Contoso の
架空の出張申請に関連する文脈だけを添えた、実データ照会の例）。

- 「直近の Contoso 出張申請に関するメールを要約して」
- 「今週、出張の承認待ちになっている会議はある？」

これらは Work IQ の一般的な使い方を示すためのテンプレートであり、実行結果は実際にサインイン
したユーザー自身の Microsoft 365 データに基づきます。実行する場合は、必ず自分自身のテスト
アカウントか、許可を得たアカウントで行ってください。

## 5. agent へ追加する

### 5.1 Foundry Toolkit（推奨パターン）

1. Foundry Toolkit の **My Resources > Tools** から **+ Add Toolbox**。
2. **Build a Custom Toolbox** タブでツールボックス名・説明を入力。
3. **Add tools** → **Work IQ** を選択。
4. **Add the Work IQ Tool** で使いたい Microsoft 365 Copilot データを選択します。
   **Work IQ Chat** は A2A エンドポイント経由、それ以外（Copilot Chat、Teams、Word、Outlook
   Calendar/Mail、Microsoft 365 user profile、SharePoint、OneDrive）は MCP エンドポイント
   経由で接続されます。
5. 選択した各オプションについて、既存の connection を選ぶか **Create new connection** を選択。
6. **Add** → **Publish**。

### 5.2 SDK で確認する場合（参考。本編スクリプトは変更しません）

```python
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, WorkIQPreviewTool
from azure.identity import DefaultAzureCredential

with (
    DefaultAzureCredential() as credential,
    AIProjectClient(endpoint=FOUNDRY_PROJECT_ENDPOINT, credential=credential) as project_client,
):
    tool_payload = WorkIQPreviewTool(project_connection_id=WORK_IQ_PROJECT_CONNECTION_ID)
    agent = project_client.agents.create_version(
        agent_name="contoso-travel-assistant-workiq-demo",
        definition=PromptAgentDefinition(
            model=PRIMARY_MODEL_DEPLOYMENT_NAME,
            instructions="Work IQ を使って、ユーザー自身の Microsoft 365 コンテキストに関する質問に答えてください。",
            tools=[tool_payload],
        ),
    )
```

このコードは**参考実装**であり、`scripts/` 配下には追加しません。`WORK_IQ_PROJECT_CONNECTION_ID`
は Global Administrator のテナント初期設定完了後に、Foundry Project Manager が作成した
connection の完全なリソース ID です。

## 6. Cleanup（本編の `destroy.sh` の対象外）

- Work IQ 用に作成した agent version・Foundry connection は Foundry project 内のオブジェクトの
  ため、Foundry portal または SDK（`project_client.agents.delete_version(...)`）から削除
  できます。
- テナント全体の Work IQ サービスプリンシパル・admin consent は組織単位の設定です。個々の
  ワークショップ参加者が削除すべきものではなく、組織のテナント管理者の判断に委ねてください。

## 公式参照

- [Connect agents to Microsoft 365 with Work IQ (preview)](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/work-iq)
- [Work IQ API overview](https://learn.microsoft.com/microsoft-365/copilot/extensibility/work-iq-api-overview)
- [Usage-based billing overview (Copilot Credits)](https://learn.microsoft.com/microsoft-365-copilot/usage-based-billing-overview-copilot-credits)
- [Microsoft Entra Privileged Identity Management](https://learn.microsoft.com/entra/id-governance/privileged-identity-management/pim-configure)
- [Curate intent-based toolbox in Foundry](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox)

## 関連リンク

- [選択ラボ index](README.md)
- [A2A・Routines・Publish](a2a-routines-publish.md)（Work IQ が使う A2A プロトコルの詳細）
- [本編 Lab 4 — Tools・Toolbox](../04-tools-toolbox.md)

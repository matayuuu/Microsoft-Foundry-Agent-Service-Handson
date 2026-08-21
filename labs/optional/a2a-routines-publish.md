# 選択ラボ — A2A・Routines・Teams/M365 publish（プレビュー機能）

## この文書の位置づけ

このラボは、Foundry agent を外部から呼び出す・自動でトリガーする・Teams や Microsoft 365 に
公開する、3 つの独立したプレビュー機能を扱います。いずれも本編には含まれておらず、
**すべて preview** です。安全のため、外部 agent との通信は本ラボ内でホストするローカルの
モック（simulated）で代替し、実在の外部サービスや秘密情報を扱いません。

> [!WARNING]
> 本ラボのコード例・手順は、実際の Microsoft Entra アプリ登録・実際の Bot Service リソース
> ・実際の Teams への公開を行うものではありません。すべて「これから何をどう設定するか」の
> 説明と、ローカルで完結する simulated なやり取りの例です。実施する場合は組織のセキュリティ
> ・コンプライアンス担当者の承認を得てください。

## 1. Incoming A2A（agent を外部から呼び出し可能にする、preview）

### 1.1 前提条件

| 項目 | 要件 |
|---|---|
| プロトコル | agent が **Responses プロトコル**を実装していること（[Advanced Hosted Agent](advanced-hosted-agent.md) 参照）。prompt agent は標準で Responses に対応済み |
| Azure ロール | **Foundry User** |
| ネットワーク | project の public network access が有効であること（無効な場合は A2A ではなく REST API + 別のネットワーキング手順が必要） |
| 対象 | prompt agent、および Responses プロトコルを実装した hosted agent |

> [!NOTE]
> **Foundry agent 同士**の委任には A2A は不要です。同じ Foundry project 内の複数 agent を
> 連携させたい場合は、本編 [Lab 7](../07-hosted-multi-agent.md) が使う Microsoft Agent
> Framework の workflow、または prompt agent の connected agents 機能を使ってください。
> A2A は **Foundry の外にある agent**（他プラットフォーム、他ベンダーの agent）との相互運用
> のための preview プロトコルです。

### 1.2 有効化の概念フロー

1. Foundry portal または SDK で、公開したい agent（例: 本編の
   `contoso-travel-assistant`）に対して A2A を有効化する。
2. Foundry が **agent card**（agent の能力・エンドポイント・認証方式を記述したメタデータ）
   を生成する。
3. 呼び出し側の外部 agent は、agent card を取得してからリクエストを送る。

### 1.3 安全な simulated 外部 agent（このラボ専用、実際の通信なし）

以下は、外部 agent が A2A 経由で呼び出す際にどのようなリクエスト形状になるかを示す
**参考疑似コード**です。`https://example-invalid.contoso-lab.invalid` は意図的に**解決不能な
架空ドメイン**にしてあり、実行してもどこにも接続されません。実際の A2A エンドポイントに
接続する場合は、必ず自分の Foundry project の agent card から得た本物のエンドポイントと
資格情報を使ってください。

```python
# 参考疑似コード。実行しても外部通信は発生しません（ドメインが解決不能なため）。
SIMULATED_EXTERNAL_AGENT_CARD = {
    "name": "contoso-partner-demo-agent",
    "endpoint": "https://example-invalid.contoso-lab.invalid/a2a",
    "protocolVersion": "1.0",
    "note": "This is a fictional agent card for lab illustration only.",
}


def simulated_a2a_call(prompt: str) -> dict:
    """外部 agent への A2A 呼び出しがどう構成されるかを示すだけの関数。実際には送信しない。"""
    return {
        "request_would_be_sent_to": SIMULATED_EXTERNAL_AGENT_CARD["endpoint"],
        "headers": {"A2A-Version": "1.0"},
        "body_preview": {"input": prompt},
        "status": "SIMULATED — no network call performed",
    }
```

### 1.4 バージョン

A2A は v1.0（推奨、`A2A-Version: 1.0` ヘッダーを送信）と v0.3（ヘッダー省略時の既定）の
両方をサポートします。新規実装では v1.0 を明示的に指定することが推奨されます。

## 2. Routines（preview）

### 2.1 概要

Routine は、**1 つのトリガーに対して 1 つのアクション**を紐づける自動化の仕組みです。
Workflow（本編 Lab 7 の Agent Framework）が扱う複雑な分岐・複数 agent の連携とは異なり、
Routine は次のようなシンプルな自動化に向いています。

| トリガーの種類 | 例 |
|---|---|
| タイマー（1 回限り） | 「明日 9:00 に一度だけ、未承認の出張申請一覧を要約して投稿する」 |
| 定期スケジュール | 「毎週月曜 9:00 に、先週の Contoso 出張精算サマリーを生成する」 |
| イベント | 「GitHub issue が作成されたら、内容を要約してコメントする」 |

### 2.2 Contoso シナリオでの架空の例

```text
トリガー: 毎週金曜 17:00（定期スケジュール）
アクション: contoso-travel-assistant を呼び出し、
  「今週承認された Contoso 出張申請の件数と合計金額を要約してください」
  というプロンプトを実行する
```

これは**架空の設定例**であり、実データに対して実行するものではありません。実行結果の履歴は
Foundry portal 上の run history で確認できます。preview 機能のため、対応するトリガー種別・
アクション種別は今後変わる可能性があります。

### 2.3 使い分けの目安

- 単純な「決まった時刻に決まった 1 つのプロンプトを実行する」「特定イベントで 1 アクション
  を起動する」だけなら **Routines**。
- 複数 agent のオーケストレーション、条件分岐、人間の承認ステップを含む場合は、引き続き
  本編の **Agent Framework workflow**（[Lab 7](../07-hosted-multi-agent.md)）を使う。

## 3. Teams・Microsoft 365 への publish（preview）

### 3.1 前提条件

| 項目 | 要件 |
|---|---|
| プロトコル | agent が Responses プロトコルを実装（Activity プロトコルへは自動でブリッジされる） |
| Azure ロール（RG スコープ） | **Azure Bot Service Contributor**（`Microsoft.BotService/botServices/write` と `channels/write` を含む。Contributor や Owner でも足りる） |
| Foundry ロール | **Foundry User** |
| ネットワーク | project の public network access が有効であること |
| 組織全体への公開 | Microsoft 365 / Teams 管理者による**組織の管理者承認**（Teams admin center 経由） |

> [!IMPORTANT]
> 「個人で試す（自分だけがインストールできる状態にする）」ことと、「組織の全員が使える状態
> にする」ことは別の話です。後者には Microsoft 365 / Teams 管理者の承認が必要です。本ラボの
> 参加者権限（resource group Owner）だけでは、組織全体への公開はできません。

### 3.2 概念フロー

1. Foundry portal で agent を選び、**Channels** から Teams / M365 Copilot を選択して bot
   registration を作成する（この操作に Azure Bot Service Contributor 権限が必要）。
2. 個人アカウントでのテスト利用であれば、生成された Teams アプリのマニフェストを
   sideload してすぐに試せる。
3. 組織全体に配布する場合は、Teams admin center から組織の承認を申請する。

本ラボでは、実際の bot registration や Teams アプリの発行は行いません。上記フローの
「どのロールが何を承認するか」を理解することが目的です。

## 4. データ・セキュリティ上の注意

- 本節で扱った 3 つの機能はいずれも **preview** であり、SLA の対象外です。
- 本ラボのコード・設定例は実際の外部通信・実際の Azure リソース作成を伴いません。
- 実際に有効化する場合は、[docs/costs-and-cleanup.md](../../docs/costs-and-cleanup.md) の
  コスト方針と、組織のデータガバナンス方針の両方を確認してください。

## 公式参照

- [Enable incoming Agent-to-Agent (A2A) requests](https://learn.microsoft.com/azure/foundry/agents/how-to/enable-agent-to-agent-endpoint)
- [Routines in Foundry Agent Service (preview)](https://learn.microsoft.com/azure/foundry/agents/concepts/routines)
- [Publish an agent to Microsoft 365 Copilot and Microsoft Teams](https://learn.microsoft.com/azure/foundry/agents/how-to/publish-copilot)
- [Hosted agents in Foundry Agent Service](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents)

## 関連リンク

- [選択ラボ index](README.md)
- [Advanced Hosted Agent](advanced-hosted-agent.md)（Responses/Activity プロトコルの詳細）
- [Work IQ](work-iq.md)（Work IQ 自体が A2A + OBO を使う実例）
- [本編 Lab 7 — Agent Framework workflow](../07-hosted-multi-agent.md)

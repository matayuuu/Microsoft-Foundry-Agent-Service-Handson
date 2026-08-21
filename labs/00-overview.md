# Lab 0 — 全体像とルール（10分）

## このハンズオンについて

これは Microsoft Foundry Agent Service の主要機能を、1つの架空シナリオ
「Contoso 社内出張・経費支援」を通して体験する 3 時間 50 分のハンズオンです。
Contoso は**実在しない架空の企業**であり、本ハンズオンで使用する規程文書、
経費データ、旅程データ、評価用の質問と回答はすべて**合成データ**です。実在の
人物・企業・経費・予約情報は一切含まれません。

対象は Microsoft Foundry の **new**（プロジェクトベースの新しい Foundry）です。
検索結果や過去のブログ記事で見かける「Azure AI Studio」「Foundry classic」
（hub ベースの旧体験）の画面とはメニュー構成が異なります。作業中に見ている
画面が想定と違う場合は、[トラブルシューティング](../docs/participant/troubleshooting.md)
を確認してください。

## 全体ライフサイクルマップ

[README](../README.md) のアジェンダに対応する、Lab とファイルの対応表です。

| 時間 | Lab | 内容 | 主な操作面 |
|---|---|---|---|
| 00:00-00:10 | Lab 0 | オープニングと全体アーキテクチャ（このファイル） | ドキュメントのみ |
| 00:10-00:30 | Lab 1 | Codespaces + Terraform によるワンコマンド構築 | ターミナル |
| 00:30-00:50 | Lab 2 | Prompt Agent（baseline v1） | Portal |
| 00:50-01:25 | Lab 3 | Azure AI Search と Foundry IQ | Portal |
| 01:25-01:35 | 休憩 | — | — |
| 01:35-02:10 | Lab 4 | Tools・Tool Catalog・Toolbox | Portal + Toolkit + SDK |
| 02:10-02:35 | Lab 5 | Agent evaluation | SDK + Portal |
| 02:35-02:55 | Lab 6 | Agent Optimizer とバージョン比較 | Portal |
| 02:55-03:40 | Lab 7 | Agent Framework workflow の Hosted Agent 配布 | Codespaces + SDK |
| 03:40-03:50 | Lab 8 | Observability・governance・cleanup | Portal + ターミナル |

Lab 7（Hosted Agent／Microsoft Agent Framework）は別ワークストリームが執筆します。
本ファイル群では Lab 8 から参照するのみで、内容には立ち入りません。

各 Lab で作成・変更するオブジェクトの「所有者」は次の通りです（詳細は
[architecture.md](../docs/architecture.md) の resource ownership 表）。

| オブジェクト | 所有者 | ライフサイクル |
|---|---|---|
| Foundry account/project・model deployment・Search・Storage・App Insights | Terraform | `setup.sh` / `destroy.sh`（Lab 1／Lab 8） |
| Search index のドキュメント | bootstrap adapter | `setup.sh` 内で idempotent に投入済み |
| Prompt Agent・Foundry IQ knowledge base | 参加者（Portal） | Lab 2〜Lab 6。親 project 削除時に削除 |
| Toolbox version・evaluation run | Python SDK（Lab 4／Lab 5 のスクリプト） | Lab 内で作成。明示的な削除 API がある範囲で `destroy.sh` が削除を試みる |
| Hosted Agent とその version | Python SDK（Lab 7） | Lab 7 で作成。Terraform destroy の前に削除 |

## Microsoft Foundry の GA / Preview / 廃止予定

本ハンズオンで扱う機能の現状（2026-08-21 時点、
[feature-support-matrix.md](../docs/feature-support-matrix.md) より抜粋）です。
Preview 表記は今後変わり得るため、実際のポータル表示と
[公式ドキュメント](https://learn.microsoft.com/azure/foundry/)を都度確認してください。

| 機能 | 状態 | この Lab での扱い |
|---|---|---|
| Prompt Agent の作成・バージョン管理・Playground | GA | Lab 2、Portal で実施 |
| Azure AI Search を Agent にアタッチ | GA | Lab 3、index/connection は構築済み |
| Foundry IQ Knowledge Base（agentic retrieval） | **Preview** | Lab 3、Portal での agentic retrieval は preview |
| Toolbox（v1 作成・Web Search・Code Interpreter） | GA | Lab 4、Toolkit で v1 作成 |
| OpenAPI ツールを Toolbox に追加 | GA（Portal 非対応・SDK のみ） | Lab 4、`scripts/create_toolbox.py` で v2 作成 |
| Tool Search | **Preview** | Lab 4 で簡単に紹介のみ |
| Agent 評価の実行（任意データセット） | GA（Portal 非対応・SDK のみ） | Lab 5、SDK 実行・結果は Portal で閲覧 |
| Prompt Agent Optimizer | **Preview** | Lab 6、Portal ウィザード |
| Hosted Agent／Agent Framework workflow | GA | Lab 7 |
| Prompt/Hosted トレース（Application Insights 連携） | GA | Lab 8 |
| Workflow Designer | **2026-12-01 に廃止予定** | 本編では使用しません（Lab 7 が Agent Framework を使う理由） |
| Fabric IQ／Work IQ | Agent config 経由の追加機能 | **本編外**（追加ライセンス・管理者同意が必要） |

## Portal / Toolkit / SDK の境界

設計方針は **Portal-first**: Portal でできない操作だけ Foundry Toolkit または
Python SDK を使います。

| 操作 | Portal | Toolkit | Python SDK/REST |
|---|---:|---:|---:|
| Prompt Agent 作成・バージョン・テスト | ○ | ○ | ○ |
| Toolbox **v1** 作成 | × | ○ | ○ |
| Toolbox に OpenAPI ツール追加（v2） | × | × | ○（Lab 4） |
| 任意データセットでの評価実行 | × | — | ○（Lab 5） |
| Foundry IQ Knowledge Base 作成 | ○ | — | ○ |
| Prompt Agent Optimizer | ○ | — | サービス管理 |

この境界は今後のポータル更新で変わり得ます。本ハンズオンの手順が「Portal ではできない」
と書いている操作について、実際のポータルで新しく対応している場合は
[トラブルシューティング](../docs/participant/troubleshooting.md)にフィードバックしてください。

## 課金とデータ境界に関する重要な注意

> [!WARNING]
> - **Web Search** はエージェント構成から呼び出すたびに、外部の Web グラウンディング
>   サービスへクエリを送信し、モデルのトークン課金とは別の料金が発生します。本ハンズオン
>   で送信してよいのは、Lab 4 で示す**架空の Contoso シナリオに関するプロンプトのみ**です。
>   実際の個人情報や機密情報を Web Search に渡さないでください。
> - **Code Interpreter** はセッションごとに追加料金が発生します。
> - Azure AI Search・model 推論・embedding・評価 judge・Agent Optimizer はすべて
>   トークン／時間課金です。詳細は [costs-and-cleanup.md](../docs/costs-and-cleanup.md)
>   を参照してください。
> - 本ハンズオンで作成するリソースは resource group の外に一切書き込みません。
>   終了後は必ず Lab 8 の手順で `./scripts/destroy.sh` を実行してください。

## 次のステップ

[Lab 1 — 環境構築](01-setup.md) に進んでください。

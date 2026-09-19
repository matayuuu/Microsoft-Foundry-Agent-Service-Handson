# 本編の対応範囲

[開発者向けガイド](README.md) / [ハンズオンの構成](architecture.md)

教材の変更時に、本編の固定構成と付録の追加要件を区別するための一覧です。
サービス全体の提供状況ではなく、このハンズオンが採用している範囲を示します。

## 環境作成と共通教材

| 項目 | 本編の構成 |
|---|---|
| 専用 RG | テンプレートを開く前に、参加者が Azure Portal で 1 個手動作成します。 |
| テンプレート | `infra/azuredeploy.json` を読み込み、Subscription と既存 RG を選びます。他は確認済みのリリース既定値を使います。 |
| 初期化 | Deployment Scripts が Search のデータ、評価データ・評価基準を準備して検証します。 |
| 成功判定 | デプロイ全体が成功し、`workshopContext.setup_status = complete` になったことを確認します。 |
| 共通教材 | GitHub の `assets/skills/*.zip` と `assets/openapi/travel-ops.openapi.json`。`servers[0].url` だけを `travelApiBaseUrl` に変更します。 |
| Portal の演習 | Labs 2〜6 を Foundry Portal で実施します。 |

## Notebook と認証

| 項目 | 本編の構成 |
|---|---|
| 実行環境 | 基本は GitHub Codespaces。ローカルの VS Code / Docker でも同じ Dev Container を使います。 |
| 依存関係 | 作成後処理がチェックアウトの外に仮想環境を分けて準備します。Azure へのログインや環境作成は行いません。 |
| 初期設定カーネル | Python (Foundry Workshop)、Python 3.12、`foundry-workshop`。 |
| Labs 7〜8 のカーネル | Python (Foundry Hosted Agent)、Python 3.13、`foundry-hosted-agent`。 |
| 認証 | Notebook の前にコンテナー内で本人が Azure CLI へサインインします。GitHub / Portal の認証とは別です。 |
| 接続情報 | `00-setup.ipynb` がサブスクリプション ID と RG 名から成功した ARM 出力を取得し、`.workshop/context.json` に保存します。スキーマは `2.0`、構造は `resource_outputs.<key>.value` です。 |
| Hosted Agent の管理 | ソースコードのリモートビルドを使います。管理用仮想環境から確認入力付きでデプロイ・削除します。 |

## サービスと終了処理

| 項目 | 本編の構成 |
|---|---|
| リージョン・モデル | Japan East / GlobalStandard。固定モデルと容量は [管理者向けのモデル利用枠](../../docs/admin/prerequisites.md#モデルの利用枠) を参照します。 |
| Search | Basic。初期データを持つ 2 インデックスを使います。 |
| 接続 | Search は AAD リソース接続、MCP と Application Insights は Project Managed Identity。[接続名と設定](../../infra/README.md#接続スキーマの例外) はインフラ説明を参照します。 |
| ID・ネットワーク | システム割り当て ID、初期化専用 ID、対象を限定した RBAC、公開エンドポイント。Foundry / Search のローカル認証は無効です。 |
| 監視・API | Log Analytics / Application Insights と、Container Apps の Travel Ops API。 |
| 終了処理 | 保存・エクスポート → Hosted Agent の全バージョン削除 → Codespace の停止・削除 → Portal で専用 RG を削除 → 削除完了の確認。 |

環境固有のアーカイブ配布、Cosmos DB、Agent capability host、ACR、プライベートネットワークは本編に含めません。
リージョン・モデルの自動切り替え、実際の予約・承認・支払いも行いません。
配布条件は [管理者向け前提条件](../admin/prerequisites.md)、
終了処理は [費用と片付け](../participant/costs-and-cleanup.md) を参照してください。

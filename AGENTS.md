# 開発エージェント向けガイド

## プロジェクトの概要

日本語の Microsoft Foundry Agent Service ハンズオンです。
環境作成には Azure Portal のカスタムテンプレートを使い、Codespaces とローカルで
同じ Dev Container を共有します。画面の英語 UI ラベルは正式表記を維持します。

## AI開発ガイド

文書の言語方針と実環境検証の判断基準は、
[Copilot 向け開発指示](.github/copilot-instructions.md) に従います。
構成・設計・実装ごとの資料は [開発者向けガイド](docs/development/README.md) を参照します。

## ディレクトリと検証の入口

作業ルートは、この `AGENTS.md` と `Makefile` がある Git リポジトリです。
親フォルダーの作業用ファイルや依存関係を、このリポジトリの構成に含めません。

| 場所 | 役割 |
|---|---|
| `src/travel-api/` | Python 3.12 の FastAPI。HTTP adapter → application → domain の依存方向 |
| `src/hosted-agent/` | Python 3.13 の Hosted Agent。起動処理とワークフロー |
| `scripts/`、`scripts/lib/` | 管理・初期化処理と共通の接続情報・実行環境処理 |
| `notebooks/` | 参加者の操作入口。SDK 環境と管理操作を分離 |
| `infra/` | Bicep 正本、生成 ARM、パラメーター例 |
| `data/`、`assets/` | 合成教材・スキーマ・Skill ソースと生成 ZIP / OpenAPI |
| `tests/unit/`、`tests/contract/`、`tests/runtime/` | 単体・契約テスト、初期化イメージの検証 |
| `.devcontainer/`、`.github/workflows/` | 共通開発環境、検証 CI と API イメージの公開 |
| `docs/`、`labs/`、`instructor/` | 読者別の資料、演習、講師の受入条件 |

セットアップと検証コマンドの実行場所・環境は
[開発者向けガイド](docs/development/README.md#初めて開発する場合) を正本とします。
`make` の手順は Dev Container 内の Bash 用です。Windows ホストの Python や
リポジトリ内の `.venv` を、管理用・Hosted 用の両環境と同一視しません。
対象別の規約は [AI設定の一覧](docs/development/README.md#ai設定の責務) から確認します。

## 責務の分担

- Azure Portal では、参加者がテンプレートの実行前に専用リソースグループ（RG）を
  1 個手動作成し、テンプレートでその既存 RG を選択します。
- Bicep / ARM は、Foundry アカウント・プロジェクト、固定モデル、Search、監視基盤、
  Container Apps API、対象を限定した RBAC・接続を管理します。
  RG、Azure ML ワークスペース、恒久的な演習用 Storage / Key Vault は作成しません。
- Deployment Scripts は専用のユーザー割り当て ID で Python の初期化処理を実行し、
  Search データと評価教材を準備・検証して、秘密を含まない ARM の接続情報を返します。
- GitHub は共通 Skill ZIP、OpenAPI テンプレート、Notebook、Python ソースを保持します。
- Foundry Portal は Prompt Agent、Foundry IQ、Toolbox、評価、最適化、トレースの操作に使います。
- Codespaces / ローカル Dev Container は Labs 7〜8 の Notebook と Hosted Agent の操作に使います。
- 接続情報の正規キーは `.workshop/context.json` の `resource_outputs` です。

## 環境作成で守る条件

- Bicep を正本とし、生成した Portal 用 ARM JSON もコミット対象に含めます。
- 全パラメーターにリリース既定値を設定し、参加者はサブスクリプションと既存 RG だけを選びます。
  本人がデプロイする場合、参加者 ID の上書き値は空欄にします。
- Terraform / Cloud Shell による環境作成、片付け、代替実装は追加しません。
- 管理者が確認したモデルバージョンと、固定したソース・イメージのリビジョンを使います。
  リリース時は Bicep の既定値、パラメーター例、文書を同時更新します。
  容量やポリシーの問題ではデプロイを停止し、別リージョン・モデルへ自動で切り替えません。
- 対象参加者のオブジェクト ID を RBAC と検証へ渡します。初期化用マネージド ID と参加者は別です。
  初期化処理が Microsoft Graph でサインイン中のユーザーを検索する方法は使いません。
- 初期化は冪等にし、再試行回数を制限し、デプロイ上で失敗を確認できるようにします。
- 環境固有の参加者用 ZIP や Blob による受け渡しは追加しません。
  共通 Skill ZIP と Hosted 用ソースコードアーカイブは、それぞれの API 形式に必要です。
- 初期化の成功後にだけ、完了済みで秘密を含まない接続情報を公開します。
- Deployment Scripts の一時的な ACI / Storage は成功時に片付け、失敗時の保持期間を制限します。
  初期化専用 ID と対象を限定した権限は、演習環境を削除するまで維持します。

## 開発環境で守る条件

- Codespaces とローカルの VS Code / Docker で同じ Dev Container を使います。
- Python 3.12 の管理環境と Python 3.13 の Hosted SDK 環境を分離します。
- コンテナーの仮想環境はリポジトリの外に置き、ホストの `.venv` を上書きしません。
- 作成後処理は依存関係とカーネルの準備に限定し、Azure の認証や環境作成を行いません。
- 本人の Azure CLI サインイン後、`notebooks/00-setup.ipynb` がサブスクリプション ID と RG 名から
  成功したデプロイを読み取り、`.workshop/context.json` を保存します。
- Labs 7〜8 は **Python (Foundry Hosted Agent)** を使います。
- 管理操作は Hosted SDK ではなく、管理用インタープリターを明示的に呼び出します。
- 共通 OpenAPI はサーバー URL だけを本人の API エンドポイントへ置き換えます。

## サービスの固定条件

- Foundry プロジェクトは `contoso-travel`、構成は Basic Agent Setup です。
- モデル名・容量・接続名の正本は [Bicep](infra/main.bicep) です。
  数値は [管理者向けのモデル利用枠](docs/admin/prerequisites.md#モデルの利用枠)、
  接続名と認証方式は [接続スキーマ](infra/README.md#接続スキーマの例外) を確認します。
  推測で値を変更せず、リリース時は関連する生成物・文書も同期します。
- 公開エンドポイント、システム割り当て ID、対象を限定した RBAC を使い、
  Foundry / Search のローカル認証は無効にします。
- 専用のユーザー割り当て ID は、デプロイ時の初期化にだけ使います。
- Cosmos DB、Agent capability host、ACR、プライベートネットワークは本編に含めません。

## 安全性と終了処理

合成データだけを使い、資格情報、トークン、デバイスコード、状態ファイルを公開しません。
Notebook の保存、Hosted Agent のバージョン削除、検証用 Codespace の停止・削除の後、
Azure Portal で専用 RG を削除して完了を確認します。
デプロイ履歴の削除ではリソースは消えません。無関係なローカルコンテナー、データ、環境は削除対象外です。

旧実装のファイルを撤去する際も、既存ユーザーの状態、キャッシュ、無関係な Azure リソースを保持します。
旧ツールの廃止後も資格情報・状態ファイルの除外設定を維持します。
参加者向け文書に容量割り当ての調整手順を含めません。

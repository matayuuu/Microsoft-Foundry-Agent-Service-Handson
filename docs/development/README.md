# 開発者向けガイド

このハンズオンの教材・コード・環境構成を変更する方に向けた資料です。
参加方法は [ハンズオンの README](../../README.md)、開催準備は
[講師向けガイド](../../instructor/README.md) を参照してください。

## 初めて開発する場合

### 1. 共通 Dev Container を開く

ローカルでは [Dev Container の前提条件](../../docs/participant/environments/local-dev-container.md)
を満たした上でリポジトリを clone し、VS Code でルートを開いて
**Dev Containers: Reopen in Container** を実行します。
Codespaces を使う場合は、対象ブランチを選んで **Code > Codespaces** から作成します。
以下のコマンドは、どちらもコンテナー内の Bash で、リポジトリのルートから実行します。

`postCreateCommand` が依存関係と 2 つのカーネルを準備するまで待ちます。
ダウンロード失敗時の再実行は `make setup` です。
既存環境の管理対象・互換性に関するエラーは、削除して回避せず
[共通開発コンテナー](../../.devcontainer/README.md#作成後処理と復旧) に従って確認します。
この段階で Azure のサインインや Lab 1 の環境作成は不要です。

### 2. 管理用・Hosted 用環境を確認する

```bash
"$WORKSHOP_MANAGEMENT_PYTHON" -c "import sys, azure.ai.projects, travel_api; assert sys.version_info[:2] == (3, 12)"
"$WORKSHOP_HOSTED_PYTHON" -c "import sys, agent_framework, agent_framework_foundry_hosting; assert sys.version_info[:2] == (3, 13)"
"$WORKSHOP_MANAGEMENT_PYTHON" -m jupyter kernelspec list
```

先頭の 2 コマンドが終了コード 0 で完了し、最後の一覧に `foundry-workshop` と
`foundry-hosted-agent` があることを確認します。管理操作に Hosted 用の Python を代用しません。

### 3. 変更前のローカル検証を行う

```bash
make lint
make test
make test-hosted
make assets-check
make shell-validate
```

これらは Azure リソースの作成・認証を伴わない検証です。
`make test` は管理用環境、`make test-hosted` は Hosted 用環境で実行します。
失敗や依存関係不足によるスキップがあれば、変更前の状態として確認し、成功扱いにしません。

ARM と Bicep の一致を確認するには、CI と同じコンパイラーを準備します。
初回のインストールは配布元への通信を伴います。

```bash
az bicep install --version v0.46.1
make bicep-validate
```

準備後は `make validate` で上記の検証をまとめて実行できます。
コンテナーイメージのビルド・起動確認など、ローカルの `make validate` に含まれない検証は
[CI のワークフロー](../../.github/workflows/validate.yml) でも確認してください。

### 4. 必要な実環境検証を分けて実施する

参加者の操作、接続、デプロイ動作を確認する場合は、対象・課金・本人認証の了承を得て、
[講師向けrunbook](../../instructor/runbook.md) の受入条件に従います。
リリース前の全 Lab の確認は、ローカルテストや CI の成功で代替しません。

## 構成と変更方針

| 資料 | 確認する内容 |
|---|---|
| [ハンズオンの構成](architecture.md) | サービスの責務、通信経路、認証、教材と接続情報の受け渡し |
| [本編の対応範囲](feature-support-matrix.md) | 本編の固定構成と、付録に分ける機能 |
| [AI向け開発規則](../../.github/copilot-instructions.md) | 日本語方針、文書の正本、実環境検証の判断基準 |
| [開発エージェント向けガイド](../../AGENTS.md) | 実装の責務、環境・サービスの制約、安全上の条件 |

## 実装ごとの資料

| 資料 | 確認する内容 |
|---|---|
| [インフラ実装ガイド](../../infra/README.md) | Bicep、生成 ARM、初期化処理、権限、再実行・削除 |
| [共通開発コンテナー](../../.devcontainer/README.md) | Python 環境とカーネル、作成後処理、依存関係 |
| [Travel Ops API](../../src/travel-api/README.md) | API 契約、ローカル実行、テスト、コンテナーの公開 |
| [Hosted Agent](../../src/hosted-agent/README.md) | ワークフロー、Notebook、デプロイと削除 |
| [共通教材](../../assets/README.md) | Skill ZIP と OpenAPI の正本、再生成・検証 |

実装に隣接する README はその場所で維持します。横断的な構成・設計・開発知識は
`docs/development/` に集約し、人とAIが同じ正本を参照します。
AIに常時適用する短い規則は `.github/copilot-instructions.md` に置きます。
参加者・管理者向けの操作説明は `docs/participant/`・`docs/admin/`、
講師の開催・検証手順は `instructor/` が正本です。

## AI設定の責務

| 設定 | 役割 |
|---|---|
| [AGENTS.md](../../AGENTS.md) | ディレクトリの地図、検証入口、環境とサービスの固定条件 |
| [共通Instructions](../../.github/copilot-instructions.md) | 文書の正本、変更・テスト・安全性・完了条件 |
| [Python](../../.github/instructions/python.instructions.md) | 管理用・API・Hosted の実行環境、型、依存方向、I/O 境界 |
| [テスト](../../.github/instructions/testing.instructions.md) | 単体・契約・ランタイム検証と外部 I/O の分離 |
| [CI](../../.github/instructions/ci.instructions.md) | ワークフローと Makefile の整合、検証と公開の権限分離 |
| [インフラ](../../.github/instructions/infra.instructions.md) | Bicep・生成 ARM・初期化の変更条件 |
| [Notebook](../../.github/instructions/notebooks.instructions.md) | カーネル、管理操作、保存内容と Lab の整合 |
| [GitHub Copilot app](../../.github/github-app.yml) | 上記の正本への案内。自動実行スクリプトは設定しません |

パス別 Instructions は各ファイルの `applyTo` に一致する変更に適用します。
GitHub Copilot app の設定は内容を確認して承認するまで適用されません。
親フォルダーではなく、この Git リポジトリをプロジェクトとして開いて使います。
設定ファイルの存在と、各クライアント・セッションでの読み込み確認は区別してください。

既存の pytest、Ruff、コンテナー検証、Bicep の生成物検証を再利用します。
専用の静的型検査は現行の Makefile / CI にはありません。型注釈や Ruff の検査を
静的型検査の代替として報告しません。
独立した責務を増やさないため、追加の Custom Agent、リポジトリ固有 Skill、
Hooks / MCP、重複する設計文書は置きません。

## 変更対象と確認先

変更した種類に応じて、正本と関連文書・生成物を同じ変更に含めます。
表の検証は作業中の確認先です。提出前には `make validate` と CI の結果を確認します。

| 変更対象 | 正本 | 同時に更新・確認するもの | 作業中の検証 |
|---|---|---|---|
| 文書・配置・案内 | 読者に対応する既存の Markdown | README、資料一覧、相対リンク、英語版 README。Lab の受入条件が変わる場合は runbook | 管理用 Python で `tests/contract/test_labs_links_contract.py` と `tests/contract/test_optional_labs_links_contract.py` |
| モデル・権限・初期化・テンプレート | [main.bicep](../../infra/main.bicep) と [初期化スクリプト](../../scripts/bootstrap_custom_template.py)・[実行ラッパー](../../scripts/bootstrap-custom-template.sh) | パラメーター例、生成 ARM、[インフラ説明](../../infra/README.md)、[管理者の配布条件](../../docs/admin/prerequisites.md)。公開済みのソース・イメージを先に確認 | `make bicep-build` → `make bicep-validate`。管理用 Python で `tests/contract/test_custom_template_contract.py` と `tests/unit/test_bootstrap*` |
| API・規程・共通教材 | [API ソースの案内](../../src/travel-api/README.md)、[規程データ（例）](../../data/policies/01-general-policy.md)、[Skill ソース（例）](../../data/skills/travel-estimation/SKILL.md) | [生成ツール](../../scripts/build_common_assets.py) による共通 ZIP / OpenAPI、関連 Lab、公開イメージのダイジェスト | 管理用 Python で `tests/unit/travel_api`、`tests/contract/travel_api`、`tests/unit/data`、`tests/contract/data`。`make assets` → `make assets-check` |
| Notebook・Harness・Hosted ワークフロー | [Lab 8 の Notebook](../../notebooks/08-hosted-agent.ipynb)、[Hosted ソースの案内](../../src/hosted-agent/README.md) | Labs 7〜8、カーネルの指定、runbook。必要に応じて公開するソースのリビジョン | `make test-hosted`。管理用 Python で `tests/contract/test_notebooks_contract.py` |
| Dev Container・依存関係 | [コンテナー設定](../../.devcontainer/devcontainer.json)、[環境準備スクリプト](../../scripts/setup_dev_environment.py)、各コンポーネントの依存定義 | コンテナーの README、参加者向け環境ガイド、CI の実行環境 | 管理用 Python で `tests/unit/test_setup_dev_environment.py` と `tests/contract/test_devcontainer_contract.py`。CI でコンテナーのビルドと両カーネルを確認 |

例えば文書を変更した場合は、コンテナー内で次を実行します。

```bash
"$WORKSHOP_MANAGEMENT_PYTHON" -m ruff check .
"$WORKSHOP_MANAGEMENT_PYTHON" -m ruff format --check .
"$WORKSHOP_MANAGEMENT_PYTHON" -m pytest -q tests/contract/test_labs_links_contract.py tests/contract/test_optional_labs_links_contract.py
```

整形確認は変更した Python ファイルだけでなく、Markdown 内のコード例も含むリポジトリ全体を対象にします。
履歴資料 `cloud-shell.md` だけは原文保持のため、
[pyproject.toml](../../pyproject.toml) で Ruff の自動整形から除外しています。
現行文書・コードの整形確認や、履歴資料の冒頭にある現行手順へのリンク確認は維持します。

モデル名・容量・接続名などの固定値は Bicep を正本とします。
人が読む数値一覧はインフラ説明と管理者の配布条件で維持し、AGENTS・構成概要・対応範囲はそこへ参照を張ります。
検証コマンドの正本は [Makefile](../../Makefile)、自動実行の正本は
[検証ワークフロー](../../.github/workflows/validate.yml) です。

実環境の受入条件と全 Lab の通し検証は [講師向けrunbook](../../instructor/runbook.md) を参照します。
静的検証の成功、実環境で確認した結果、未実施の範囲を分けて報告してください。

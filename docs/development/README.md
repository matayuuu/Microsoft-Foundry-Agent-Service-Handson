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
| [文書・画像](../../.github/instructions/documentation.instructions.md) | 入力値と成功条件の説明、実画面と構成図、出典・編集元・掲載画像の整合 |
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

## AIと進める変更

AIへの依頼は、この Git リポジトリ内の変更を単位に進めます。
ローカルの開発履歴は不足や判断理由を探す材料であり、現行仕様や検証結果の正本ではありません。

1. **到達点を決める。** 変更の目的・対象・非対象、ローカル検証までか実環境検証までかを確認します。
   現在のブランチと未コミット差分を読み、共有作業や進行中の変更を保護します。
   親フォルダーの作業ファイルを追加したり、依頼なしにブランチを切り替えたりしません。
2. **根拠を照合する。** 対象の実装・テスト・現在の文書を読みます。
   履歴を参照する場合はユーザーの決定と当時のAgentの報告を区別し、後の決定による撤回も確認します。
   未確認の製品仕様や過去の成功報告を、そのまま現在の要件・対応状況にしません。
3. **変更をつなぐ。** [変更対象と確認先](#変更対象と確認先) から、同時に更新する文書・生成物・テストを選びます。
   例えば Python の対応範囲は依存定義、CI、コンテナーで照合し、モデルの変更は用途別の対応を確認します。
   既存の検証で足りる場合は再利用し、新しい検査には壊した入力を拒否するテストも用意します。
4. **結果を分けて確認する。** 変更に対応する最小の検査から始め、必要な全体検証へ進みます。
   実行環境・コマンド・対象 revision・件数・スキップと未実施範囲を区別します。
   実環境では [runbook](../../instructor/runbook.md#実環境検証の範囲) を使い、
   待機の打ち切りを SDK のタイムアウトと混同せず、依頼された範囲を独断で縮小しません。
5. **再発防止だけを残す。** 実装と照合できた規則は対象の Instructions、設計の理由は既存の構成文書、
   検査できる不変条件はテストに反映します。会話ログのコピーや、一度の失敗を一般化した禁止事項は増やしません。
   実行証跡は秘密・個人情報を除いてリポジトリ外に保持し、次の開発者に必要な恒久情報だけを共有します。

過去の課金・認証・デプロイ・削除・push・mergeへの了承は、今回の操作への了承ではありません。
変更の提出方法と完了判定は [変更の提出と完了判定](#変更の提出と完了判定) に従います。

## 変更対象と確認先

変更した種類に応じて、正本と関連文書・生成物を同じ変更に含めます。
表の検証は作業中の確認先です。提出前には `make validate` と CI の結果を確認します。

| 変更対象 | 正本 | 同時に更新・確認するもの | 作業中の検証 |
|---|---|---|---|
| 文書・配置・案内 | 読者に対応する既存の Markdown | README、資料一覧、相対リンク、英語版 README。Lab の受入条件が変わる場合は runbook | 管理用 Python で `tests/contract/test_labs_links_contract.py` と `tests/contract/test_optional_labs_links_contract.py` |
| AI向け指示 | `AGENTS.md`、共通・パス別 Instructions | このガイドの一覧、適用対象、参照先。会話履歴ではなく現行の実装と照合 | 管理用 Python で `tests/contract/test_labs_links_contract.py`。利用するクライアントでも検出と適用対象を確認 |
| 構成図・画面画像 | [構成図の編集元](architecture.md#構成図の編集)、実際の UI | 編集用ファイル、掲載 PNG、日英 README、関連 Lab、[出典](../images/ATTRIBUTION.md)。旧図は現行の正本に戻さない | 管理用 Python で `tests/contract/test_architecture_diagrams_contract.py` と文書リンク検査。掲載画像と編集用ファイルの表示は別に目視確認 |
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
文書リンク検査には共通・パス別 Instructions の相対リンクと Markdown の見出しも含めます。
パス別 Instructions は YAML frontmatter と開発者ガイドからの導線も検査します。
クライアントによる指示の検出・適用や、本文に記載した製品動作の実証を代替する検査ではありません。

モデル名・容量・接続名などの固定値は Bicep を正本とします。
人が読む数値一覧はインフラ説明と管理者の配布条件で維持し、AGENTS・構成概要・対応範囲はそこへ参照を張ります。
検証コマンドの正本は [Makefile](../../Makefile)、自動実行の正本は
[検証ワークフロー](../../.github/workflows/validate.yml) です。

実環境の受入条件と全 Lab の通し検証は [講師向けrunbook](../../instructor/runbook.md) を参照します。
静的検証の成功、実環境で確認した結果、未実施の範囲を分けて報告してください。

## 変更の提出と完了判定

ブランチ・提出先・PRの利用は依頼と既存運用を確認します。
commit、push、PR作成、merge、公開は別の操作であり、AI設定の更新だけでは実行しません。
共有ファイルはステージ直前にも再読し、依頼外の変更を混ぜません。

| 段階 | 確認する根拠 |
|---|---|
| ローカル変更 | 対象の差分、検証した環境・コマンド・件数。依存不足によるスキップ、未実施、失敗を成功に数えません。 |
| PR・リモート CI | 対象 head SHA と対応する run、[検証ワークフロー](../../.github/workflows/validate.yml) の必要な job・step の成功、必要なレビュー。別 revision の成功や、インストール失敗後のスキップで代替しません。 |
| merge・配布 | merge後の SHA、配布するソース・イメージの revision と公開結果。APIの公開は [専用ワークフロー](../../.github/workflows/publish-travel-api.yml) と承認範囲に従います。 |
| 実環境・通し検証 | 同一 revision の Lab・実行環境ごとの結果、再デプロイ、cleanup。過去の画像、登録済みデータ、simulated fixture、CI成功を完走の証拠にしません。 |

PRを使う場合は対象のブランチルール・required checks・レビュー条件を確認し、承認された場合だけmergeします。
ルールを読み取れない場合は不明とし、この文書やCIファイルを追加しただけで設定済みとは扱いません。
報告ではローカルの変更、ローカルのコミット、リモートへの反映を区別します。
依頼に含まれない後続段階は対象外、依頼に含まれるが実施できない段階は未完了として、必要な確認を示します。

# 共通開発コンテナー

[開発者向けガイド](../docs/development/README.md) / [参加者向けの共通手順](../docs/participant/environments/codespaces.md#共通手順)

Codespaces とローカルの **Dev Containers: Reopen in Container** は、この設定を共有します。
ホストの Python 環境、資格情報ディレクトリ、Docker ソケットはマウントしません。
Jupyter サーバーの起動やポートの自動転送も行いません。

## Python 環境とカーネル

| 実行環境 | Terminal と Notebook に渡すインタープリター | カーネル |
|---|---|---|
| Python 3.12 | `WORKSHOP_MANAGEMENT_PYTHON=/home/vscode/.venvs/foundry-workshop/bin/python` | Python (Foundry Workshop) |
| Python 3.13 | `WORKSHOP_HOSTED_PYTHON=/home/vscode/.venvs/foundry-hosted-agent/bin/python` | Python (Foundry Hosted Agent) |

変数は `containerEnv` で定義しているため、VS Code と `devcontainer exec` の両方で引き継がれます。
Terminal の有効化スクリプトには依存しません。

## 作成後処理と復旧

作成後処理は `python3.12 scripts/setup_dev_environment.py` を実行します。
`python3.12` と `python3.13` の両方を確認し、分離した依存関係と開発ツールを導入した後、
`pip check`、SDK バージョンの確認、2 つのユーザーカーネルの登録を行います。
Azure へのサインインやリソースの操作は行いません。

依存関係のダウンロードに失敗した場合は、同じコマンドを再実行してください。
この処理が管理する作成途中の仮想環境は準備を続行できます。
管理対象外または互換性のない環境・カーネルはエラーにし、削除・上書きしません。
配置を変える場合は、2 つの変数へチェックアウト外の絶対パスを明示します。
末尾はそれぞれ対応する `<kernel-name>/bin/python` にしてください。

## イメージと依存関係の更新

[公式 Python イメージの定義](https://github.com/devcontainers/images/blob/main/src/python/manifest.json)
にある `3.2.3-3.13-bookworm` を Linux amd64 / arm64 で使います。
[Python Feature](https://github.com/devcontainers/features/blob/main/src/python/devcontainer-feature.json)
は固定した Python 3.12 を `/usr/local/python` に追加し、イメージにある
`/usr/local/bin/python3.13` を維持します。Feature に定義されたオプションだけを使います。

イメージ、Features、Azure CLI、Graphviz、開発ツールはリリースバージョンを固定しています。
Python 依存関係の範囲は既存のプロジェクト定義を正本とし、推移的依存を固定する lockfile とは区別します。
固定値はまとめて更新し、教材のリリース前に両アーキテクチャでコンテナー全体のビルドを確認してください。

## 初回の利用

コンテナーの Terminal で本人がサインインした後、管理用カーネルで `notebooks/00-setup.ipynb` を実行します。
Labs 7〜8 は Hosted 用カーネルへ切り替えます。

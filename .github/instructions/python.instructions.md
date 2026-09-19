---
description: 管理スクリプト、Travel Ops API、Hosted Agent の Python 規約。
applyTo: "**/*.py,**/pyproject.toml,**/requirements*.txt"
---

# Python の変更

- 書式・import・lint の正本は [ルートの pyproject.toml](../../pyproject.toml) です。
  名前は既存の `snake_case` / `PascalCase` に合わせ、Ruff と競合する書式規則を追加しません。
- Python の対応範囲は各 manifest に従います。管理用の標準実行環境は 3.12、
  Travel Ops API は 3.12、Hosted Agent は 3.13 です。ルートの Ruff は `py310` を対象とするため、
  管理スクリプト全体を Hosted 専用の構文・SDK に揃えません。
- 変更する関数の引数・戻り値には、既存の型と整合する型注釈を付けます。
  外部 JSON は使用前に検証し、安易な `Any` や型検査の抑制で不整合を隠しません。
- Travel Ops API の依存方向は HTTP adapter → application → domain です。
  HTTP やフレームワークの型を domain に持ち込まず、業務例外から HTTP 応答への変換は
  adapter で行います。詳細は [API の README](../../src/travel-api/README.md) を確認します。
- Hosted の起動処理は薄く保ち、Agent 定義とワークフローを既存のモジュールへ置きます。
  SDK・環境変数の契約は [Hosted の README](../../src/hosted-agent/README.md) と
  [requirements.txt](../../src/hosted-agent/requirements.txt) を確認します。
- 接続情報・実行環境の処理は `scripts/lib/` の既存ヘルパーを再利用します。
  I/O はテストで差し替えられる境界へ置き、予期した例外だけを扱います。
  再試行は回数を制限し、失敗を空値や成功結果へ変換しません。
- 依存とカーネルの準備には既存の
  [共通開発環境](../../.devcontainer/README.md) を使い、管理用と Hosted 用を混在させません。
  環境準備以外のスクリプトから依存の自動インストールを追加しません。

参考: [Python の型注釈](https://docs.python.org/3.12/library/typing.html)。
型注釈や Ruff の成功だけを、専用の静的型検査に合格した証拠にはしません。

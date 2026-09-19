---
description: 単体・契約・ランタイム検証の配置、外部 I/O 分離、結果の扱い。
applyTo: "tests/**"
---

# テストの変更

- `tests/unit/` は関数・業務ロジック・失敗処理、`tests/contract/` は API、教材、
  Notebook、テンプレートなどの整合を検証します。既存の `conftest.py` と fixture を再利用します。
- Python テストは `test_*.py` / `test_*` と pytest を使います。
  変更する契約の期待値を明示し、実装と同じ計算をコピーしただけのテストにしません。
- `tmp_path`、`monkeypatch`、既存の FakeRunner / SDK fake を使い、
  Azure、認証、ネットワーク、subprocess を必要な境界で分離します。
  単体・契約テストから実環境へ接続しません。
- 正常系に加え、無効入力、外部処理の失敗、再試行上限など変更に関係する条件を検証します。
  検証ロジックには、意図的に壊した入力を拒否するケースを含めます。
- Hosted のテストは専用 Python 3.13 環境でも実行します。
  管理環境で SDK 不足によりスキップされた結果や fake の成功で、この検証を代替しません。
- `tests/runtime/` のコンテナー検証と実環境の通し検証は、単体・契約テストと区別します。
  `integration` marker は対象環境の用意や課金操作の了承を意味しません。
- 実行したテスト数・スキップ・失敗を確認し、0 件や無条件の成功で検証を成立させません。
  実行環境と入口は [開発者向けガイド](../../docs/development/README.md) を参照します。

参考: [pytest の monkeypatch](https://docs.pytest.org/en/stable/how-to/monkeypatch.html)。

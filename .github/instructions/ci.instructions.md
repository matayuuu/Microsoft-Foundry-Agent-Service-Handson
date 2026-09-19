---
description: GitHub Actions と Makefile の検証入口・環境・権限を保守する規約。
applyTo: ".github/workflows/*.yml,.github/workflows/*.yaml,Makefile"
---

# CI と検証入口の変更

- [validate.yml](../workflows/validate.yml) と [Makefile](../../Makefile) を再利用します。
  同じ責務の pipeline を増やさず、検証コマンドの変更は
  [開発者向けガイド](../../docs/development/README.md) と整合させます。
- 管理用 Python 3.12、Hosted 用 Python 3.13、Bicep、初期化用イメージ、
  Dev Container、API コンテナーの検証を区別します。
  runtime・依存定義・作業ディレクトリの対応を崩さず、ローカルと CI で検証内容を揃えます。
- Bicep のコンパイラー更新は生成 ARM と一致検証への影響を確認します。
  cache のキー・参照先は、そのジョブが使用する実在の依存定義に合わせます。
- 通常の検証は `contents: read` を基本とし、不要な権限・秘密情報・
  checkout の credential 永続化を追加しません。
  外部 PR のコードに書き込み権限を渡す `pull_request_target` は使いません。
- [API 公開ワークフロー](../workflows/publish-travel-api.yml) は検証 CI と別の責務です。
  公開用の権限や push 処理を検証へ移さず、構成更新の確認のために公開を起動しません。
- Action の追加・更新では公式の release / tag と必要な runner を確認します。
  架空の SHA、失敗を隠す `continue-on-error`、テスト 0 件を許す設定を追加しません。
- CI 定義の静的確認、ローカル同等検証、リモート CI の成功を区別して報告します。

参考: [GitHub Actions の安全な利用](https://docs.github.com/en/actions/reference/security/secure-use)。

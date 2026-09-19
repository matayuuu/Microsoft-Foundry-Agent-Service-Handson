---
description: 参加者用 Notebook のカーネル、管理操作、保存内容を維持する規約。
applyTo: "notebooks/*.ipynb"
---

# Notebook の変更

- [共通開発コンテナー](../../.devcontainer/README.md) と
  [Hosted Agent の README](../../src/hosted-agent/README.md) を先に確認します。
  Labs 7〜8 は **Python (Foundry Hosted Agent)** を使い、
  管理操作には管理用インタープリターを明示します。
- 接続情報は既存の `.workshop/context.json` と `scripts/lib/` の処理を使います。
  サブスクリプション、RG、エンドポイントをセルに固定しません。
- 再利用可能な処理は既存の `scripts/` または `src/hosted-agent/` に置き、
  Notebook は参加者の入力・操作・結果確認の入口として保ちます。
- セルの出力・例外・metadata に認証情報や実環境固有値を保存しません。
  不要な実行出力や実行番号の変更を持ち込まず、無関係なセル ID・metadata を維持します。
- 対応する Lab、カーネル指定、Notebook 契約テスト、Hosted テストを確認します。
  参加者の操作や受入条件を変えた場合は [講師向け runbook](../../instructor/runbook.md) も更新します。
- セル実行は認証・課金・デプロイ・削除を伴い得ます。
  静的な Notebook 検証と実環境の通し実行を区別し、保存確認だけで成功を主張しません。

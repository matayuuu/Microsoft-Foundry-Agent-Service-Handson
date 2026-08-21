# completed-run-assets — SIMULATED / REFERENCE フォールバック資料

## これは何か

Lab 5（評価）・Lab 6（Optimizer）・Lab 7（Hosted Agent デプロイ）の live 実行が、
preview 機能の不安定さやネットワーク・quota の事情で当日時間内に完了しない場合に、
講師が画面共有して「本来この形の結果が返ってくる」と説明するための**参考資料**です。

> [!WARNING]
> このディレクトリの JSON ファイルは、**実際に Microsoft Foundry 上で実行された結果では
> ありません**。すべて `asset_status` フィールドで `"SIMULATED"` または `"REFERENCE"` と
> 明示されており、値（ID・スコア・URL）はすべて架空です。参加者に対して「これは実際の
> 実行結果です」と説明しないでください。
>
> 含まれる識別子（`eval-id` 等）・URL はすべて意図的に非現実的な形式
> （`SIMULATED-...`、`.invalid` ドメインなど）にしてあり、実在の Azure リソース ID・
> サブスクリプション ID・テナント ID・秘密情報は一切含まれません。

## ラベルの意味

| `asset_status` | 意味 |
|---|---|
| `SIMULATED` | 実際にはどの Foundry 環境でも実行しておらず、スクリプト・ドキュメントに書かれた出力形状をもとに、講師が手作業で作成した架空の値 |
| `REFERENCE` | 実行結果そのものではなく、フィールドの意味・構造を説明するための参考情報（値は例示） |

すべてのファイルに `disclaimer_ja` フィールドがあり、「これは実際の Foundry 実行結果では
ない」旨の日本語の注記が入っています。

## ファイル一覧

| ファイル | 対応する Lab | スキーマ |
|---|---|---|
| [evaluation-run.simulated.json](evaluation-run.simulated.json) | [Lab 5](../../labs/05-evaluation.md) | [schemas/evaluation-run.schema.json](schemas/evaluation-run.schema.json) |
| [optimizer-run.simulated.json](optimizer-run.simulated.json) | [Lab 6](../../labs/06-optimization.md) | [schemas/optimizer-run.schema.json](schemas/optimizer-run.schema.json) |
| [hosted-agent-deploy.simulated.json](hosted-agent-deploy.simulated.json) | [Lab 7](../../labs/07-hosted-multi-agent.md) | [schemas/hosted-agent-deploy.schema.json](schemas/hosted-agent-deploy.schema.json) |

`tests/contract/test_completed_run_assets_contract.py`（本タスクで追加）が、各 JSON ファイル
がそのスキーマに準拠していること、`asset_status` が `SIMULATED`/`REFERENCE` のいずれかで
あること、`disclaimer_ja` が空でないこと、秘密情報らしき文字列（`sk-`、`AccountKey=` など）
や実在しそうな GUID 形式の ID を含まないことを検証します。

## 使い方（講師向け）

1. 該当する Lab の live 実行を試みる。
2. 時間内に完了しない、またはエラーが解消できない場合のみ、このディレクトリの該当ファイルを
   開き、画面共有する。
3. 「これはシミュレーションです」と口頭で明示したうえで、フィールドの意味を
   [runbook.md](../runbook.md) の該当節に沿って説明する。
4. 参加者には、実際の実行は各自の時間がある時に試すよう案内する。

## 関連リンク

- [instructor/README.md](../README.md)
- [instructor/runbook.md](../runbook.md)

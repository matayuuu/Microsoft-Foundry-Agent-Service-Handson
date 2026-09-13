# 管理者向けトラブルシューティング

## Template / quota / Policy

- 手動作成した専用 RG を選択し、`infra/azuredeploy.json` 本体を **Load file** で読み込んだか確認します。
- RG の **Deployments / Activity log** で失敗した operation、provider registration、lock、
  Policy、Japan East の固定モデルと Search Basic の利用枠を確認します。
- Bicep と生成 JSON の一致、確認済みモデル・image・source の既定値を
  [配布ガイド](prerequisites.md)と照合します。別リージョン・モデルに切り替えません。

## Bootstrap

1. Deployment Scripts の **Overview / Logs** で、source 取得、依存関係、
   Search seed、評価データ・rubric の準備、validation のどこが失敗したかを特定します。
2. `participantObjectIdOverride` と対象参加者、role scope を確認します。
   bootstrap identity と参加者は別です。403 を広い権限の追加で回避しません。
3. 同じ RG と確認済み入力で修復します。初期化を意図的に再実行する場合だけ `bootstrapRunId` を変更します。
4. 全体が **Succeeded** になり、`workshopContext.setup_status = complete` と
   `source_revision` が一致することを確認します。

失敗時に自動 rollback されるとは限りません。以前の成功を今回の成功とみなさず、
部分リソースも確認します。ログの保持・再試行・一時実行基盤の詳細は
[infra/README.md](../../infra/README.md) を参照してください。

## GitHub assets / Notebook

| 症状 | 確認すること |
|---|---|
| assets が取得できない | 配布参照先が公開され、bootstrap / 共通教材の revision が互換か |
| Skill を登録できない | PC の ZIP を選び、直下に `SKILL.md` があるか |
| OpenAPI が別 API を呼ぶ | `servers[0].url` が本人の `travelApiBaseUrl` と一致するか |
| カーネルが出ない | Dev Container の post-create が成功したか。既存のホスト環境を変更しない |
| CLI 認証エラー | Notebook と同じコンテナーで本人が Azure CLI にサインインしたか |
| context 取得が失敗 | subscription / RG、成功した schema `2.0` の `workshopContext`、読み取り権限を確認 |
| deployment 候補が複数 | 対象を確認してから、管理者が `configure_workshop.py --deployment <name>` を指定。推測しない |
| context の対象違い | 別環境の設定を上書きせず、現在の checkout と目的の環境を確認 |

操作は [Codespaces の共通手順](../participant/environments/codespaces.md#共通手順)を使います。
API key、手動 token の注入、認証情報の共有で代替しません。

## Cleanup failure

[Lab 9](../../labs/09-observability-cleanup.md) の順に、保存、Hosted Agent versions の削除、
Codespace の停止・削除を確認してから、Azure Portal で本人の専用 RG を削除します。
削除中は再送せず、失敗時は **Activity log**、lock、deny assignment を確認します。
**Resource groups** 一覧から消えたことまで確認し、deployment history の削除だけで完了にしません。

## 検証結果の扱い

実 UI の検証では Azure Portal、Foundry Portal、Codespaces / VS Code の操作結果を確認します。
CI、SDK 単体の成功や simulated JSON を、未実施の UI 操作の成功とみなしません。
アカウント固有の情報・私的証跡は repository に保存しません。

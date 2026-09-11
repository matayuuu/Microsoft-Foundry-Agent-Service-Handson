# 困ったとき

初期化が失敗したら Lab 2 へ進まず、エラー内容を管理者へ伝えてください。
実行中の処理を繰り返さず、認証コード・トークン・キーは共有しません。

| 症状 | 最初に確認すること |
|---|---|
| RG を作成できない | アカウント、サブスクリプション、作成権限。共有 RG で代用しません |
| テンプレートを読み込めない | 管理者指定の `azuredeploy.json` 本体か確認。HTML ページは読み込めません |
| デプロイ・初期化が失敗する | RG の **Deployments** と Deployment Scripts の **Logs** を確認。リージョン・モデルを変えず、管理者へ連絡 |
| ZIP の取得が 403 になる | **Storage browser** の認証を **Microsoft Entra user account** に変更。解決しなければ対象の権限を管理者に確認 |
| ZIP が見つからない・展開できない | 初期化の `status = complete` と、非公開の `workshop-files` を確認。以前の ZIP で続行しません |
| モデルや接続先が見つからない | `.workshop/context.json` にある自分のプロジェクトを開いているか確認 |
| Azure ML のカーネルが表示されない | [準備ガイド](environments/azure-ml.md)の設定ノートブックを完了し、画面を更新 |
| RG を削除できない | [Lab 9](../../labs/09-observability-cleanup.md) の順序と **Activity log** を確認。ロックなどは管理者へ相談 |

ZIP の取得に公開リンク、SAS、アカウントキーは使いません。

## Lab 4 のファイル

Skill は PC の `portal-assets/` 内にある ZIP をアップロードします。
`travel-ops.openapi.json` は内容全体を **OpenAPI 3.0+ schema** に貼り付けます。
この欄はファイルのアップロードではありません。

## 引用リンク

検索結果の URL が Search 自体を開く場合は、`source_url` を管理者に確認してもらいます。
Foundry IQ の `mcp://searchindex/...` は内部の引用 ID です。
Web ページとして開くのではなく、**Traces** の文書 ID と教材の規程を照合します。

## 評価と最適化

**In progress** の間は再送しません。429・タイムアウトと、評価結果の **Fail** は区別します。
`content_filter` は保護機能による遮断です。Guardrail を弱めず、エラー内容を管理者へ共有します。
**No supported optimization model** と表示された場合も、別モデルを追加せず確認を依頼します。

[準備に戻る：Lab 1](../../labs/01-setup.md)

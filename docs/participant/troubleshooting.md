# 困ったとき

初期化が失敗したら Lab 2 へ進まず、エラー内容を管理者へ伝えてください。
実行中の処理を繰り返さず、認証コード・トークン・キーは共有しません。

| 症状 | 最初に確認すること |
|---|---|
| RG を作成できない | アカウント、サブスクリプション、作成権限。共有 RG で代用しません |
| テンプレートを読み込めない | 管理者指定の `azuredeploy.json` 本体か確認。HTML ページは読み込めません |
| デプロイ・初期化が失敗する | RG の **Deployments** と Deployment Scripts の **Logs** を確認。リージョン・モデルを変えず、管理者へ連絡 |
| モデルや接続先が見つからない | Lab 1 の **Outputs > resourceOutputs** にある自分のプロジェクトを開いているか確認 |
| Codespace を作れない | GitHub アカウント、利用枠、組織の Codespaces ポリシーを確認 |
| カーネルが表示されない | **Select Kernel > Jupyter Kernel...** を確認。そこにもない場合は post-create の完了と[準備ガイド](environments/codespaces.md)を確認 |
| Notebook の出力が省略される | **Output is truncated** の **scrollable element** を選ぶ。セルを再実行して確認しない |
| Notebook で認証エラー | コンテナーの Terminal で Azure CLI にサインインしたか確認。Portal のログインだけでは使えません |
| 初回設定で対象が見つからない・曖昧になる | subscription ID / RG 名と **Succeeded** の deployment を確認。複数候補は管理者へ相談し、推測で選びません |
| 接続先の不一致で初回設定が止まる | 既存の `.workshop/context.json` と今回の対象を確認。別環境の設定を上書きして続けません |
| RG を削除できない | [Lab 9](../../labs/09-observability-cleanup.md) の順序と **Activity log** を確認。ロックなどは管理者へ相談 |

## Lab 4 のファイル

Skill は [Lab 4 の GitHub リンク](../../labs/04-tools-toolbox.md)から PC に保存した ZIP を
アップロードします。直下に `SKILL.md` がある ZIP を使い、Markdown 単体は選びません。
`travel-ops.openapi.json` は `servers[0].url` を **Outputs > travelApiBaseUrl** に置換してから、
JSON 全体を **OpenAPI 3.0+ schema** に貼り付けます。
404 や HTML が表示される場合は、リンク先と保存したファイルを管理者へ確認します。

## 引用リンク

Lab 2 は Azure AI Search の **Actions > Parameters** で **Search type = Semantic**、
**Retrieved documents = 5** を確認します。回答の金額だけでなく、適用条件と根拠資料も照合します。
検索結果の URL が Search 自体を開く場合は、`source_url` を管理者に確認してもらいます。
Foundry IQ の `mcp://searchindex/...` は内部の引用 ID です。
Web ページとして開くのではなく、**Traces** の文書 ID と教材の規程を照合します。
Portal の回答に `cite` の内部記号がそのまま残る場合は、引用表示の不一致として記録し、
**Traces** の取得文書と元資料を確認します。検索設定だけで表示が直るとは限らず、成功扱いにしません。

## 評価と最適化

**In progress** の間は再送しません。429・タイムアウトと、評価結果の **Fail** は区別します。
`content_filter` は保護機能による遮断です。Guardrail を弱めず、エラー内容を管理者へ共有します。
**No supported optimization model** と表示された場合も、別モデルを追加せず確認を依頼します。

[準備に戻る：Lab 1](../../labs/01-setup.md)

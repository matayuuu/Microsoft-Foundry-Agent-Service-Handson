# 管理者向けトラブルシューティング

## Template validation / published source

先に手動作成した専用 RG が選択され、正しい `infra/azuredeploy.json` が **Load file** で
読み込まれたか確認します。Bicep と生成 JSON の不一致、HTML の誤保存、未公開
`sourceRevision`、不正な model version / GHCR digest を切り分けます。
branch 名や mutable tag、未確認の version を代替値にしません。

## Provider / quota / Policy

RG の **Deployments** と **Activity log** で provider registration、deny assignment、
resource lock、SKU restriction を確認します。Japan East の 3 固定モデル / GlobalStandard、
Search Basic、ACI、AML workspace / `Standard_DS3_v2` の各 quota は別に確認します。
一つの subscription の成功は他の subscription の capacity を証明しません。
事前確認は予約ではなく、不足時は deployment が失敗するのが正しい動作です。

一時 ACI が使う Azure Files / Shared Key、package download の outbound HTTPS、
Deployment Scripts の対応 runtime と組織 Policy を照合します。
public Blob、別リージョン / モデル、認証設定の緩和へ黙って切り替えません。

## RBAC / identity

`participantObjectIdOverride`、context の `participant_object_id`、role scope と
role definition ID を照合します。bootstrap UAMI は実行主体で、参加者ではありません。
代理 deployment / redeployment の場合も元の参加者 ID を明示します。
runtime に subscription roles や Owner を追加せず、反映待ちの bounded retry と恒久的な
403 を区別します。重複 assignment で解決しません。

## Deployment Scripts / 部分失敗

1. 失敗 deployment の resource details と、Deployment Scripts の **Overview / Logs** を確認。
2. source 取得、dependency preparation、Search seed、evaluation assets、validation、
   Portal assets、ZIP、Blob upload のどこが失敗したかを特定します。
3. 診断情報は保持期限 `P1D` 内に確認。秘密情報を含めず error code と対象 operation を記録。
4. 同じ専用 RG と確認済み入力で修復・再実行します。意図的に bootstrap をやり直す場合だけ
   `bootstrapRunId` を変更。部分リソースを放置して別 RG を増やしません。
5. deployment / bootstrap の成功、validation の全 `pass`、private ZIP の
   `source_revision` / `sha256` / `setup_status = complete` を改めて照合。

失敗は自動 rollback ではありません。リソースやデータが残る場合があります。
成功済み ZIP が残っていても、失敗した今回の deployment の配布物とはみなしません。
retention 後は script resource が消えることもあるため、再実行の冪等性を確認します。
bootstrap UAMI と grants は script の cleanup で消える前提にせず、最終 RG cleanup まで保持します。

## Storage browser の 403 / ZIP 不一致

- outputs の Storage account と private container `workshop-files` を開いているか確認。
- **Microsoft Entra user account** を選択しているか、必要なら
  **Switch to Microsoft Entra user account** で切り替えたか確認。
- 対象参加者の Storage Blob Data Contributor と Portal 管理プレーン参照権限を確認。
- `allowBlobPublicAccess: false` と OAuth default を維持。
  Azure ML 互換性に必要な Shared Key 設定は変更しません。
- Blob の revision / hash と manifest、context、live API endpoint を照合します。
  SAS / account key / anonymous download を迂回路にしません。

## Azure ML / cleanup failure

Notebook Export → Hosted Agent / versions cleanup → Compute **Stop / Delete** を確認してから、
Azure Portal で専用 RG の **Delete resource group** を実行します。
標準 resources は RG とまとめて削除します。

削除が進行中なら再送しません。失敗なら **Activity log**、lock、deny assignment、
Compute / Hosted version を調べ、所有者と承認済みの修復を行います。
deployment history の削除だけで完了にせず、**Resource groups** 一覧から対象 RG が
消えたことと、失敗がないことを確認します。他の RG や共有 resources は対象外です。

## E2E 証跡

テンプレート契約テスト、直接 CLI / REST / SDK の成功、simulated / reference JSON を
Portal UI の成功とみなしません。実 E2E は Playwright が実 Portal / Foundry / Azure ML の
UI で確認した結果、download ファイル、Notebook 出力を記録し、未実施・阻害項目を明示します。
アカウント固有情報と私的証跡は repository に保存しません。

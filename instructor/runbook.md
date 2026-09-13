# Instructor runbook

## Before the event

1. [管理者前提条件](../docs/admin/prerequisites.md)に従い、権限、Japan East の固定モデル、
   Search Basic、Codespaces の利用枠・ポリシーを確認します。
2. 同ガイドの公開チェックを済ませたテンプレートと教材の参照先、専用 RG 名を配布します。
   参加者にモデル version・image digest・source SHA の手入力は求めません。
3. ローカル参加者には [Dev Container の前提条件](../docs/participant/environments/local-dev-container.md)を案内します。
4. 予算・alert、cleanup の担当、失敗時の連絡先を決めます。

## Rehearsal — 実 UI で確認すること

以下は検証項目です。Azure / Codespaces の作成前に対象・課金・本人認証を確認します。
実行結果と未実施の範囲は repository 外に記録し、CI や simulated JSON で UI の成功を代替しません。
画像を追加する場合は、実画面で確認した公開可能な範囲だけを使います。

### Lab 1

1. Azure Portal **Resource groups > Create** で専用 RG を **1 個手動作成**し、完了を確認。
2. **Deploy a custom template > Build your own template in the editor > Load file** で
   `infra/azuredeploy.json` を読み込み、**Save** 後に作成済み RG を選択。
3. Subscription / RG 以外は既定値。本人の実行は **Participant Object Id Override** が空欄、
   **Bootstrap Run Id** が `1` のまま **Review + create > Create**。
4. Search seed、評価データ・rubric、validation を含む全体が **Succeeded**、
   `workshopContext.setup_status = complete` になることを確認。
5. `resourceOutputs`、`travelApiBaseUrl`、`foundryPortalUrl` が本人の環境を指すことを確認。
6. 同じ RG・参加者での再デプロイと、意図した `bootstrapRunId` 更新を確認。
   重複データを増やさず、失敗は明示されることを確認。

### Labs 2–6

同じ Prompt Agent を拡張します。Lab 4 は GitHub の共通 Skill ZIP を PC からアップロードし、
共通 OpenAPI の `servers[0].url` だけを本人の `travelApiBaseUrl` に変更します。
Prompt Agent / Search、OpenAPI / Skill、登録済み評価データなど代表操作を確認します。
評価は 7 件、optimizer candidate は 1。実行中の処理を再送しません。

### Labs 7–8

1. [Codespaces ガイド](../docs/participant/environments/codespaces.md)の
   **Code > Codespaces** から作成し、post-create と教材の配置を確認。
2. コンテナーの Terminal で本人が Azure CLI にサインイン。
   GitHub / Portal のログインと別であることを説明。
3. `notebooks/00-setup.ipynb` を **Python (Foundry Workshop)** で実行。
   subscription ID / RG 名から schema `2.0` の `.workshop/context.json` が作られることを確認。
4. Labs 7/8 を **Python (Foundry Hosted Agent)** で実行。
   Lab 7 は plain / Harness、Lab 8 は intake / policy / reviewer の sequential workflow。
5. Lab 8 の deploy / delete が確認入力を要求し、管理用 venv で実行されることを確認。
6. ローカルでも clone → **Dev Containers: Reopen in Container** → 同じ共通手順を確認。

Lab 8 は Lab 7 の session state には依存しませんが、環境準備は必要です。

## Incident boundaries

- 初期化失敗時は次の Lab へ進まず、同じ RG の診断・修復を行います。
- 403 は bootstrap と参加者の identity / scope を区別します。広い runtime role を追加しません。
- quota / Policy failure で model / region / security baseline を変更しません。
- 認証が本人操作を要求したら本人に引き継ぎます。コード・token の共有や代行保存は行いません。
- 対処は [管理者トラブルシューティング](../docs/admin/troubleshooting.md)を参照します。

## Cleanup roll call

参加者ごとに [Lab 9](../labs/09-observability-cleanup.md) の順で確認します。

1. Notebook・結果を保存・Export。
2. Hosted Agent と全 versions の削除を確認。
3. Codespace を停止・削除。ローカルは教材のコンテナーだけ停止。
4. Azure Portal で本人の subscription / 専用 RG 名を照合。
5. **Delete resource group** を実行し、一覧から RG が消えたことを確認。

Deployment history の削除では resources は消えません。他人・共有環境は対象外です。

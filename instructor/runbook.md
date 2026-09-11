# Instructor runbook

## Before the event

1. participant ごとの専用 workload RG 名を決め、Portal で RG を作る権限と、
   作成後の RG 内の Owner 相当権限を確認。
2. [管理者前提条件](../docs/admin/prerequisites.md) に従い、Japan East の固定 3 models /
   version / GlobalStandard / quota、Search Basic、public endpoints / local auth policy を確認。
3. Deployment Scripts、UAMI、ACI quota、一時 Azure Files Storage の Shared Key /
   network Policy、GitHub / GHCR / package sources への到達性を確認。
4. Lab 7 用 **Standard_DS3_v2** の利用可否・quota と **Idle shutdown** を確認。
5. `travelApiImageRef` の実 digest と公開済み 40 桁 `sourceRevision` を確認。
   実行ソース、引用 URL、manifest の revision を一致させる。
6. `infra/main.bicep` と一致する生成済み `infra/azuredeploy.json`、管理者確認済み
   model version parameters を配布。未公開 artifact や存在しない `main` URL を使わない。
7. 代理 deployment / redeployment は `participantObjectIdOverride` に対象参加者を指定。
   `bootstrapRunId` は意図的な retry の場合だけ変更する。
8. budget / alert、cleanup owner、失敗時の連絡先を決める。

確認は capacity の予約ではありません。参加者と講師の subscription を区別し、
不足時に別リージョン・モデルへ切り替えません。
Lab 1 の新経路の所要時間は未計測です。実 Portal rehearsal の結果なしに時間を約束しません。

## Lab 1 rehearsal checklist — 実 UI で確認すること

以下は確認計画であり、実施済みの証跡ではありません。
Playwright で実際の Azure Portal を操作し、結果と阻害事項を別途記録します。

> [!NOTE]
> passkey や MFA で本人操作が必要な場合は認証を引き継ぎ、完了するまで E2E を停止します。
> 実施結果と未実施の範囲は repository 外の rehearsal 記録に残します。
> ローカル契約テストや参考資料を、未実施の Portal 操作の成功証拠にしません。

1. **Resource groups > Create** で専用 RG を **1 個手動作成**して完了を確認。
2. **その後** **Deploy a custom template > Build your own template in the editor > Load file**
   から JSON を upload。**Save** 後に作成済み RG を選択し、**Create new** は使わない。
3. 確認済みパラメーターで **Review + create > Create**。RG と Compute を template が
   作らないこと、固定の resources と scoped RBAC / connections を確認。
4. Deployment Scripts の 2 indexes seed、evaluation assets、validation、live Portal assets、
   ZIP publication を含め deployment 全体が **Succeeded**、bootstrap `status = complete`。
5. **Storage browser > Blob containers > workshop-files** で
   **Microsoft Entra user account**（必要なら **Switch to Microsoft Entra user account**）を使用し、
   private `foundry-workshop-files.zip` を **Download** で PC に 1 回取得。
6. ZIP を展開し、最上位 folder `Microsoft-Foundry-Agent-Service-Handson`、
   `.workshop/context.json` の `resource_outputs.<key>.value` と `setup_status = complete`、
   source revision / hash、live `portal-assets/`、notebooks / Hosted source / tests を確認。
7. 同じ RG / 設定の redeployment と、意図した `bootstrapRunId` 更新の再試行を UI で確認。
   参加者 ID の維持、重複 resources / data が増えないこと、失敗が明示されることを確認。

生成側の ZIP path は `.workshop/download/foundry-workshop-files.zip` です。
private Blob を raw URL / SAS / key で取得した結果を Storage browser 成功の代わりにしません。
一時 ACI / Azure Files Storage は `OnSuccess`、失敗保持は `P1D`。
bootstrap UAMI と scoped grants は RG cleanup まで残ります。

新 UI の screenshot は実画面を確認し、アカウント固有情報を除いて公開可能なものだけを使います。
架空 screenshot、別の操作画面の転用、simulated / reference JSON は実 E2E 証跡にしません。
parameter file、認証情報、私的 E2E 証跡は repository へ保存しません。

## Labs 2–6

Foundry Portal で同じ Prompt Agent を拡張します。Lab 4 の Skill ZIP / live OpenAPI JSON は
PC に展開した `portal-assets/` を使います。Compute はまだ作りません。
evaluation は 7 synthetic rows、optimizer candidate は 1。実行中の run を再送しません。
実 E2E では Prompt Agent / Search 質問、OpenAPI / Skill の入力、評価アセットの参照など
代表操作を確認します。全 Lab の完走を確認したと表現しません。

## Labs 7–8

**Lab 7** に template-created Azure ML workspace を開き、
**Standard_DS3_v2** + **Idle shutdown** の Compute を作成。
展開済み top-level folder を **Notebooks > User files > Upload folder** で upload。
`notebooks/00-azureml-setup.ipynb` を **Python 3.10 - SDK v2** で実行し、
**Python (Foundry Workshop)** / **Python (Foundry Hosted Agent)** を作成します。
Labs 7/8 は **Python (Foundry Hosted Agent)** を使います。

Lab 7 は plain / Harness Agent、Lab 8 は intake / policy / reviewer sequential workflow。
Lab 8 は Lab 7 の session state には依存しませんが、環境準備は省略できません。
実 E2E は Azure ML の実 UI で upload / cell 実行 / 最小限の Hosted 起動・呼出しを確認します。
ローカル SDK の成功を Notebook UI の成功とみなしません。

## Incident boundaries

- bootstrap failure は hard stop。部分 resources が残るため、診断後に同じ RG で修復します。
- 403 は bootstrap と participant の identity / scope を区別。broad runtime role を付けません。
- quota / Policy failure で model / region / security baseline を変更しません。
- Private ZIP の失敗を public Blob、SAS、account key で回避しません。
- device code / token / real data の共有を止め、組織 incident process に従います。
- 実 E2E が阻害された場合は blocker と未実施範囲を記録し、simulated 結果で埋めません。

## Cleanup roll call

participant ごとに:

1. Notebook / safe results を **Export**。
2. Hosted Agent / versions を削除し、deleted / not found を確認。
3. Compute **Stop**、**Delete**、一覧から削除を確認。
4. Azure Portal で専用 workload RG の subscription / 名前 / resources を照合。
5. **Delete resource group** で RG と resources をまとめて削除。
6. **Resource groups** 一覧から消え、削除失敗がないことを確認。

Deployment history を削除しても resources は消えません。browser close、Compute Stop、
一時 script cleanup だけを workshop cleanup 完了と扱いません。
private ZIP の AML Storage、bootstrap identity / grants、失敗時の残存 supporting resources も
対象 RG 内で確認します。他人や共有環境の resources は削除しません。

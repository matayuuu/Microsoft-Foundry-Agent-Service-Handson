# Instructor guide

本編は Azure Portal の **RG 手動作成 → custom template → Azure 側 bootstrap →
private ZIP download**、Microsoft Foundry Portal、Azure ML Studio の単一参加者経路です。

開催前に [runbook](runbook.md)、[参考結果](completed-run-assets/README.md)、
[管理者向け前提条件](../docs/admin/prerequisites.md)、
[費用と cleanup](../docs/costs-and-cleanup.md) を確認します。

## Responsibilities

- participant ごとの subscription、専用 RG 名、RG 作成権限と RG 内 Owner 相当権限を確認
- Japan East の固定モデル version / GlobalStandard / quota、Search Basic、
  ACI / AML Compute / Storage Policy を事前確認
- 検証済み `travelApiImageRef` の digest、公開済み `sourceRevision`、
  Bicep と一致する `infra/azuredeploy.json` を配布
- 代理 deployment / redeployment は `participantObjectIdOverride` に元の参加者 ID を指定
- **Resource groups > Create** の完了後に template を開く順序を確認
- bootstrap / validation 完了、Storage browser の **Microsoft Entra user account**、
  private `workshop-files` の 1 回の **Download** を確認
- Labs 2〜6 と、PC の live `portal-assets` handoff を確認
- Lab 7 の **Standard_DS3_v2** + **Idle shutdown**、**User files** の folder upload、
  setup Notebook と 2 kernels を確認
- data boundary、simulation、authentication、billing warnings を説明
- Export → Hosted Agent / versions → Compute Stop / Delete → **Delete resource group** →
  削除完了まで確認

Lab 1 の新経路の所要時間は未計測です。管理者確認は capacity 予約ではありません。
実 Portal E2E は Playwright の実 UI 操作で検証し、実施済みと未実施を区別します。
simulated assets を deployment、evaluation、download、cleanup の成功証拠にしません。
アカウント固有情報・私的 E2E 証跡は repository に置きません。

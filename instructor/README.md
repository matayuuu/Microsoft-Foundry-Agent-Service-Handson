# Instructor guide

本編は Azure Portal + provisioning-only Azure Cloud Shell Bash + Microsoft Foundry Portal +
Azure ML Studio の hybrid participant path です。

開催前に [runbook](runbook.md)、
[completed-run-assets](completed-run-assets/README.md)、
[管理者向け前提条件](../docs/admin/prerequisites.md)、[費用と cleanup](../docs/costs-and-cleanup.md)
を確認します。

## Responsibilities

- participant ごとの alias、subscription、workload resource group naming を決める
- Cloud Shell persistent `clouddrive` mount / reconnect / free space を事前検証
- providers、model/Search/Compute capacity、Policy、network を rehearsal
- lightweight Cloud Shell setup、Terraform/bootstrap、single ZIP download、immediate exit を確認
- Foundry Portal Labs 2〜6 と PC `portal-assets` handoff を確認
- Lab 7 の Azure ML Compute/upload/setup Notebook と 2 kernels を確認
- data boundary、simulation、authentication、billing warnings を説明
- Lab 9 の Compute deletion、same-state destroy、empty RG、Portal deletion を確認

production/shared workload resources、broad runtime roles、real data、shared credentials を
participant path に混在させません。

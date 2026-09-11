# 管理者向けトラブルシューティング

## Cloud Shell mount failure

ephemeral refusal を解除しません。初回起動なら標準 UI の Storage 自動作成が完了したかを
確認し、Azure Files share、Cloud Shell storage settings、`clouddrive` の CIFS/read-write
mount、Storage firewall/shared-key policy を確認します。修復後、再接続して `clouddrive`
の書込みと再読込みを検証します。participant の workload provisioning はそれまで停止します。

## Provider / quota / Policy

Activity log と deployment details で provider registration、deny assignment、resource lock、
SKU restriction を確認します。model catalog 表示や単独 participant の成功だけで全体 capacity
を判断しません。別 model や security baseline への変更で回避しません。

## RBAC propagation

principal object ID、scope、role definition ID を確認します。legacy role label は ID で照合。
反映待ちに重複 assignment や runtime Owner を追加しません。

## Terraform recovery

participant の persistent `clouddrive` にある repository、`.workshop/terraform-inputs.json`、state を
保持します。partial failure の resource inventory と state recovery output を確認して setup
または destroy を再実行します。state を失ったまま Portal で parent resource を先に削除しません。

## Azure ML Compute blocks destroy

participant に Notebook export 後、Compute instance の Stop と Delete を完了させます。
Compute deletion を確認してから Terraform destroy を再実行します。

## Residual resources

destroy 後に workload RG inventory、Activity log、locks を確認します。空になった workload
resource group は participant が Azure Portal で削除します。Cloud Shell storage は別の
owner/lifecycle として扱います。

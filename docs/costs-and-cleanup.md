# 費用と cleanup

## 課金対象

- Cloud Shell persistent Azure Files storage
- Foundry model inference、evaluation、optimizer、Hosted Agent
- Azure AI Search、Container Apps、Application Insights / Log Analytics
- Azure ML workspace backing resources と稼働中 Compute instance
- Code Interpreter / Web Search など利用した tools

Cloud Shell compute は利用料金の対象外でも、persistent storage と workload resources は
課金されます。browser close、Cloud Shell `exit`、Compute Stop は resource deletion では
ありません。

## Cost controls

- Cloud Shell は provisioning/download 後すぐ `exit`。
- Terraform は Compute を作成しない。
- Compute は Lab 7 直前に作り、`Standard_DS3_v2` + Idle shutdown。
- evaluation は 7 synthetic rows、optimizer candidate は 1。
- In progress の run / model call を重複送信しない。
- 管理者は budget / alert と全 participant inventory を準備。

## Cleanup order

1. Azure ML User files から必要な Notebook / result を Export。
2. Hosted Agent versions / agent と data-plane children を削除。
3. Compute instance を Stop、次に Delete。
4. 同じ persistent `clouddrive` repository / Terraform state を再開。
5. `bash scripts/setup-cloud-shell.sh` で session-local environment を再作成。
6. `source scripts/activate-cloud-shell.sh`、`./scripts/destroy.sh`。
7. workload RG が空であることを確認。
8. Azure Portal で workload RG を Delete。
9. Cloud Shell で `exit`。

> [!WARNING]
> state を削除・移動してから destroy しません。Compute が残ったまま workspace を削除しません。
> cleanup 完了は workload RG の削除確認までです。

Cloud Shell storage は別 lifecycle です。dedicated storage で、workload cleanup が成功し、
組織 policy が許可する場合だけ別途削除します。shared/existing storage や他用途の file share
は削除しません。

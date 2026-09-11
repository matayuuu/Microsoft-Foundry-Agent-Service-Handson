# Lab 9 — Observability と cleanup（20分）

## ゴール

Prompt / Hosted Agent traces を比較し、**Export → Hosted Agent / versions 削除 →
Azure ML Compute Stop / Delete → Azure Portal で専用 RG 削除 → 削除完了確認**の順に
完全に cleanup します。ブラウザーを閉じるだけでは resources は残ります。

## 1. Trace を比較

Foundry Portal の **Build > Agents > Traces** で Lab 4 と Lab 8 の実行を開きます。

- Prompt Agent: Foundry IQ、`tool_search`、`call_tool`、選択された実 tool
- Hosted Agent: `intake_agent` → `policy_agent` → `reviewer_agent`
- `policy_agent` だけの `knowledge_base_retrieve`
- latency、status、token usage、reviewer output

trace には prompt、response、tool arguments が残ります。secret や実データを入力していない
ことを再確認します。

## 2. Export と Hosted Agent cleanup

Azure ML **User files** から必要な Notebook / safe result を PC へ **Export** します。
token、credential、個人の環境識別情報を含む context や認証出力は共有しません。

**Python (Foundry Hosted Agent)** で Lab 8 Notebook の cleanup cell を実行します。
同じ環境の Azure ML Terminal を使う場合は、同梱の `delete_hosted_agent.py` を実行できます。

```bash
conda run --name foundry-hosted-agent python scripts/delete_hosted_agent.py \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --output json
```

自分が作成した全 Hosted Agent versions と agent が deleted / not found になったことを確認します。
成功前に parent Foundry resource を削除しません。Lab 8 を行っていない場合も、対象の
Hosted Agent が存在しないことを確認して次へ進みます。

## 3. Compute を Stop / Delete

Azure ML Studio の **Compute > Compute instances** で対象 instance を選びます。

1. **Stop** を選び、status **Stopped** まで待つ。
2. **Delete** を選び、Compute が一覧から消えるまで待つ。

必要な成果物を Export せずに Compute / workspace を削除しません。
Compute を作成していない場合は、対象 workspace の一覧に存在しないことを確認します。
Stop だけでは Storage や他の Azure resources は削除されません。

## 4. Azure Portal で専用 resource group を削除

1. Azure Portal の **Resource groups** から、Lab 1 で手動作成した **自分の専用 RG** を開く。
2. subscription と RG 名を照合し、表示される resources が今回の workshop 用だけであることを確認。
3. **Delete resource group** を選ぶ。
4. 確認欄へその RG 名を入力し、**Delete** で確定する。

Foundry、Search、Container Apps、monitoring、AML backing Storage / Key Vault、
bootstrap identity と scoped grants は **RG とまとめて削除**します。
初期化失敗後に一時 ACI / Azure Files Storage が残っている場合も対象 RG 内を確認します。
resources が表示されていること自体は、RG 削除を妨げる条件ではありません。
共有 resource や他人の resource が見つかった場合だけ、削除前に管理者へ確認します。

![Delete resource group を選択する Microsoft Learn の画面例](../docs/images/lab09-delete-resource-group.png)

この画像は一般的な UI の参考であり、今回の deployment や削除を実行した証拠ではありません。

> [!IMPORTANT]
> **Deployments の履歴（deployment history / deployment record）を削除しても、
> deploy された resources は削除されません。**
> cleanup は必ず **Delete resource group** と、その削除完了確認まで行います。

## 5. 削除完了を確認

- **Resource groups** 一覧を更新し、対象 RG が消えたことを確認します。
- 削除通知と **Activity log** を確認し、失敗・進行中を完了とみなしません。
- 削除失敗の場合は lock、deny assignment、未削除の Compute / Hosted version を
  管理者と確認。既存の保護設定を勝手に外したり、別の RG を削除したりしません。
- 講師へ、自分の workload RG の削除完了を報告します。追加演習の resources がある場合は
  その所有者と別途 cleanup を確認します。

Deployment Scripts の `OnSuccess` は一時 supporting resources の cleanup であり、
Foundry や Search の削除ではありません。bootstrap identity / grants はここで RG と削除します。

## 完了チェック

- Prompt / Hosted traces を比較した
- 必要な Notebook / safe result を Export した
- Hosted Agent / versions が削除済み、または存在しない
- Compute が Stop / Delete 済み、または存在しない
- Azure Portal の Delete resource group で専用 RG を削除した
- RG が一覧から消え、削除失敗がないことを確認した

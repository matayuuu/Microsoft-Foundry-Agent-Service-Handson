# Lab 9 — トレースの比較と片付け（20分）

## 1. トレースを比較する

Foundry Portal の **Build > Agents > Traces** で、Lab 4 と Lab 8 の実行を開きます。

- Prompt Agent：`tool_search` → `call_tool` → 実際のツール呼び出しを確認。
- Hosted Agent：`intake_agent` → `policy_agent` → `reviewer_agent` と、
  `policy_agent` の `knowledge_base_retrieve` を確認。
- 応答、所要時間、トークン使用量を比較します。

## 2. 成果物を保存し、Hosted Agent を削除する

1. Azure ML の **User files** から、必要なノートブックと結果を PC へ **Export** します。
2. Lab 8 のノートブックを **Python (Foundry Hosted Agent)** で開き、削除セルを実行します。
3. Hosted Agent と全 versions が削除済み、または存在しないことを確認します。

## 3. Compute を停止・削除する

Azure ML Studio の **Compute > Compute instances** で、自分の対象を選びます。

1. **Stop** を選び、**Stopped** まで待ちます。
2. **Delete** を選び、一覧から消えたことを確認します。

Compute を作成していない場合は、この手順は不要です。

## 4. 専用 RG を削除する

1. Azure Portal の **Resource groups** で、Lab 1 で作成した自分の RG を開きます。
2. サブスクリプションと RG 名を確認し、**Delete resource group** を選びます。
3. 確認欄に RG 名を入力し、**Delete** で確定します。残るリソースも RG とまとめて削除します。
4. **Resource groups** の一覧を更新し、RG が消えたことを確認して完了です。

**デプロイ履歴の削除では、リソースは消えません。**
削除に失敗したら **Activity log** を確認し、管理者へ連絡してください。

> [!IMPORTANT]
> 削除するのは **自分の専用 RG だけ**です。必要な成果物の Export と、
> Hosted Agent・Compute の削除を済ませてから RG を削除してください。

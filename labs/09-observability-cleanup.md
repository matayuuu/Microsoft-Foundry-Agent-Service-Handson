# Lab 9 — トレースの比較と片付け（20分）

## 1. トレースを比較する

Foundry Portal の **Build > Agents > Traces** で、Lab 4 と Lab 8 の実行を開きます。

- Prompt Agent：`tool_search` → `call_tool` → 実際のツール呼び出しを確認。
- Hosted Agent：`intake_agent` → `policy_agent` → `reviewer_agent` と、
  `policy_agent` の `knowledge_base_retrieve` を確認。
- 応答、所要時間、トークン使用量を比較します。

## 2. 成果物を保存し、Hosted Agent を削除する

1. VS Code の **File > Save All** で保存します。Codespaces では、必要なノートブックと結果を
   Explorer の **Download...** で PC へ保存（Export）します。
2. Lab 8 のノートブックを **Python (Foundry Hosted Agent)** で開き、削除セルの対象を確認して
   表示された **Agent 名**（`contoso-travel-hosted-planner`）を入力します。
   セルは管理用 `foundry-workshop` venv で削除を実行します。
3. Hosted Agent と全 versions が削除済み、または存在しないことを確認します。

## 3. Codespace を停止・削除する

[Your codespaces](https://github.com/codespaces) で、この教材の Codespace を確認します。

1. 対象の **… > Stop codespace** を選び、停止を確認します。
2. 保存・Export が済んでいることを再確認して **… > Delete** を選びます。
3. 一覧から消えたことを確認します。停止だけではストレージが残ります。

ローカル Dev Container の場合は、ファイルを保存してこの教材のコンテナーを停止します。
他のコンテナー、volume、ホストの Python 環境は削除しません。

## 4. 専用 RG を削除する

1. Azure Portal の **Resource groups** で、Lab 1 で作成した自分の RG を開きます。
2. サブスクリプションと RG 名を確認し、**Delete resource group** を選びます。
3. 確認欄に RG 名を入力し、**Delete** で確定します。残るリソースも RG とまとめて削除します。
4. **Resource groups** の一覧を更新し、RG が消えたことを確認して完了です。

**デプロイ履歴の削除では、リソースは消えません。**
削除に失敗したら **Activity log** を確認し、管理者へ連絡してください。

> [!IMPORTANT]
> 削除するのは **自分の専用 RG だけ**です。必要な成果物の Export と、
> Hosted Agent・Codespace の削除を済ませてから RG を削除してください。

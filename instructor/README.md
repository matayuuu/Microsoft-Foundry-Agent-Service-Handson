# Instructor guide

本編は **専用 RG の手動作成 → custom template / 初期化 → Foundry Portal →
GitHub Codespaces** の順です。ローカル参加者も同じ Dev Container を使います。

開催前に [runbook](runbook.md)、[参考結果](completed-run-assets/README.md)、
[管理者向け前提条件](../docs/admin/prerequisites.md)、
[費用と cleanup](../docs/costs-and-cleanup.md) を確認します。

## 確認すること

- 参加者の subscription、専用 RG 名、作成・削除・role assignment の権限
- 固定モデル / Search Basic の利用枠と、既定値設定済みテンプレート
- RG の作成完了後にテンプレートを開き、Subscription / 作成済み RG だけを選ぶ順序
- Search・評価データの準備と validation の成功、`workshopContext.setup_status = complete`
- Lab 4 の GitHub Skill ZIP、共通 OpenAPI と本人の `travelApiBaseUrl`
- Codespaces / Dev Container の準備、本人の Azure CLI サインイン、`00-setup.ipynb` と 2 カーネル
- 保存 → Hosted Agent versions → Codespace 停止・削除 → 専用 RG の削除確認

本編の安全上の注意を開始時に説明してください。
実 UI の操作結果と参考資料を区別し、simulated assets を成功証拠にしません。

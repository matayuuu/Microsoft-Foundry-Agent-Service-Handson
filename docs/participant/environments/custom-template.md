# 環境準備ガイド

**操作は [Lab 1](../../../labs/01-setup.md) の順に進めてください。**

専用 RG を 1 個手動作成 → 作成済み RG にテンプレートを実行 →
データ投入・検証の成功を確認 → Foundry Portal、という流れです。
`workshopContext.setup_status` が `complete` になるまで次の Lab へ進みません。

テンプレートでは **Subscription** と作成済みの **Resource group** だけを選び、
その他は既定値のまま進めます。本人のデプロイでは **Participant Object Id Override** は空欄です。

| 確認したいこと | 参照先 |
|---|---|
| 参加前に必要なもの | [参加条件](../prerequisites.md) |
| 画面操作と初期化の確認 | [Lab 1](../../../labs/01-setup.md) |
| 共通 Skill ZIP と OpenAPI | [Lab 4](../../../labs/04-tools-toolbox.md) |
| テンプレートの既定値 | [管理者向けガイド](../../admin/prerequisites.md) |
| エラーへの対処 | [トラブルシューティング](../troubleshooting.md) |
| ノートブックの準備（標準） | [Codespaces](codespaces.md) |
| ローカルで受講する場合 | [同じ Dev Container を使う](local-dev-container.md) |
| 終了時の片付け | [Lab 9](../../../labs/09-observability-cleanup.md) |
| 詳細な構成・権限 | [infra/README.md](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/README.md) |

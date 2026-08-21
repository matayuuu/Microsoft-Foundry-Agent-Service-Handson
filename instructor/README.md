# 講師向け資料（instructor materials）

このディレクトリは、Microsoft Foundry Agent Service ハンズオン（3 時間 50 分、
[Lab 0〜Lab 8](../labs/00-overview.md)）を進行する**講師専用**の資料です。参加者向けの
`labs/` `docs/participant/` とは独立しており、参加者に配布する必要はありません。

> [!IMPORTANT]
> このディレクトリの資料は、本編のセットアップ（`./scripts/setup.sh`）・Terraform
> （`infra/`）・コアスクリプトを一切変更しません。ここにある JSON/Markdown は、当日の
> live デモが preview 機能の不安定さなどで失敗した場合に**代替として提示するための
> 参考資料**であり、実際に Foundry 上で発生したデータではありません
> （詳細は [completed-run-assets/README.md](completed-run-assets/README.md)）。

## 中身

| ファイル/ディレクトリ | 内容 |
|---|---|
| [runbook.md](runbook.md) | 3 時間 50 分の進行台本。事前準備、区切りごとのチェックポイント、デモ用プロンプト、コスト・データ境界の注意喚起の読み上げ文、live 実行が難しい場合の切り替え判断、cleanup 確認手順 |
| [completed-run-assets/](completed-run-assets/README.md) | Optimizer・評価・Hosted Agent デプロイの live 実行が難しい場合に提示する、明示的に **SIMULATED**（模擬）または **REFERENCE**（参考構造）とラベル付けされた JSON/Markdown 資料 |

## 使い方

1. イベントの数日前に [runbook.md](runbook.md) の「0. 事前準備」を実施し、
   `admin-preflight.sh` の結果と、参加者数に応じた model quota を確認します。
2. 当日は [runbook.md](runbook.md) の時間割に沿って進行し、各区切りのチェックポイントで
   参加者の進捗を確認します。
3. Optimizer（Lab 6）や評価（Lab 5）、Hosted Agent デプロイ（Lab 7）で live 実行が
   時間内に完了しない・preview 機能が不安定などの理由で難しい場合は、
   [completed-run-assets/](completed-run-assets/README.md) の該当資料を画面共有し、
   「本来ならこの形の結果が返ってくる」という参考として説明します。
4. イベント終了後は [runbook.md](runbook.md) の「cleanup 確認」節に従い、
   `./scripts/destroy.sh` の実行結果を確認します。

## 関連リンク

- [labs/00-overview.md](../labs/00-overview.md) — 参加者向けの全体像
- [labs/optional/README.md](../labs/optional/README.md) — 選択ラボ index
- [docs/admin/prerequisites.md](../docs/admin/prerequisites.md)
- [docs/admin/troubleshooting.md](../docs/admin/troubleshooting.md)
- [docs/costs-and-cleanup.md](../docs/costs-and-cleanup.md)

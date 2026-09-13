# 参加前に用意するもの

## アカウントと PC

- 管理者指定の Azure アカウントとサブスクリプション。
- 専用 RG の作成・削除権限と、その RG 内でロール割り当てができる **Owner 相当の権限**。
- 英語の画面表示を使える PC のブラウザー。
- [GitHub Codespaces](https://github.com/codespaces) を利用できる GitHub アカウントと利用枠。
- Lab 4 用の Skill ZIP・OpenAPI JSON を PC に保存できること。

標準の Codespaces 経路では、PC への CLI・Docker・Python のインストールは不要です。
Azure と Codespaces の利用枠・組織ポリシーは管理者に確認してもらいます。

## 管理者から受け取るもの

- 自分専用の RG 名。
- 既定値を設定済みの `azuredeploy.json` ファイル。
  モデルのバージョンやハッシュを自分で調べて入力する必要はありません。
  既定値の詳細は[管理者向けガイド](../admin/prerequisites.md)を参照してください。

## 開始する

[Lab 1](../../labs/01-setup.md) に従い、Azure Portal で RG を **1 個手動作成した後**、
作成済み RG にテンプレートを実行します。**Subscription** と **Resource group** 以外は
既定値のまま進めます。Notebook の準備は Lab 7 の
[Codespaces ガイド](environments/codespaces.md)で行います。

| 使う画面 | 用途 |
|---|---|
| [Azure Portal](https://portal.azure.com) | 環境作成、初期化の確認、RG の削除 |
| [Microsoft Foundry Portal](https://ai.azure.com) | Labs 2〜6 |
| GitHub / Codespaces | 共通教材、Labs 7〜8 の Notebook |

ローカルで実施する場合は、[Dev Container の前提条件](environments/local-dev-container.md)を確認してください。
利用時の安全上の注意は [README](../../README.md)、終了手順は [Lab 9](../../labs/09-observability-cleanup.md) にまとめています。

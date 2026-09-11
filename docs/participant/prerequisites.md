# 参加前に用意するもの

## アカウントと PC

- 管理者指定の Azure アカウントとサブスクリプション。
- 専用 RG の作成・削除権限と、その RG 内でロール割り当てができる **Owner 相当の権限**。
- 英語の画面表示を使える PC のブラウザー。
- ZIP のダウンロード・展開と、フォルダーのアップロードができること。

準備にローカル CLI のインストールは不要です。Azure の利用枠は管理者に確認してもらいます。

## 管理者から受け取るもの

- 自分専用の RG 名。
- `azuredeploy.json` ファイルと、確認済みの入力値。
  詳細は[管理者向けガイド](../admin/prerequisites.md)を参照してください。

## 開始する

[Lab 1](../../labs/01-setup.md) に従い、Azure Portal で RG を **1 個手動作成した後**、
作成済み RG にテンプレートを実行します。Azure ML Compute は Lab 7 まで作成しません。

| 使う画面 | 用途 |
|---|---|
| [Azure Portal](https://portal.azure.com) | 環境作成、教材の取得、RG の削除 |
| [Microsoft Foundry Portal](https://ai.azure.com) | Labs 2〜6 |
| [Azure ML Studio](https://ml.azure.com) | Labs 7〜8 |

> [!IMPORTANT]
> 合成データだけを使い、認証情報を共有しないでください。利用には料金が発生します。
> 終了時は [Lab 9](../../labs/09-observability-cleanup.md) で **自分の専用 RG だけ**を削除します。

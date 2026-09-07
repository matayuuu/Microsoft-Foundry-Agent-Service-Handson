# 参加者向け前提条件

ハンズオンで使うアカウントと **GitHub Codespaces** を準備します。
Azure へのサインイン・事前確認・環境作成は [Lab 1](../../labs/01-setup.md) で行います。

## 必要なもの

| 必要なもの | 確認すること |
| --- | --- |
| GitHub アカウント | GitHub Codespaces を利用できる |
| Azure アカウント | Azure にサインインできる |
| Azure サブスクリプション ID | 管理者から受け取っている |
| 既存のリソースグループ（RG）名 | 管理者から割り当てられ、その RG の **Owner** ロールがある |

**作業は割り当てられた RG 内だけで行います。** 権限が足りない場合は管理者に連絡してください。

## 手元の PC と Codespace を区別する

**GitHub Codespaces は、ブラウザーで使える開発環境です。**
教材用の Python、Azure CLI、Terraform、Foundry Toolkit は Codespace に用意されるため、
PC へのインストールは不要です。Docker、API キー、クライアントシークレットも準備不要です。

| 場所 | 用途 |
| --- | --- |
| 手元の PC | ブラウザーを開く。アップロード用の素材を保存する |
| Codespace | Explorer で教材を開き、Terminal でコマンドを実行する。Lab 7 の Notebook もここで開く |
| Foundry Portal（別タブ） | **Foundry (new)** でエージェントの設定・会話・評価・実行履歴を確認する |

**本編の `bash` コマンドはすべて Codespace の Terminal で実行します。**
PC の PowerShell / Terminal や Azure Cloud Shell は使いません。

## Codespace を開いて準備する

1. 講師が指定した GitHub リポジトリとブランチを開きます。
2. ファイル一覧の上で **Code → Codespaces** を選択します。
3. 指定のブランチで **Create a codespace on …**（画像では右上の **＋**）を選択します。演習用の Codespace がある場合は、同じリポジトリ・ブランチのものを開き直します。
4. ブラウザーに VS Code が開いたら、初期化が終わるまで待ちます。

![Codespaces パネル右上の ＋ が新しい Codespace の作成ボタン](../images/lab00-create-codespace.png)

**Running postCreateCommand** は準備中の表示です。
エラーが出たら先へ進まず、[トラブルシューティング](troubleshooting.md)を確認してください。

フォルダーを信頼するか尋ねられたら、講師指定のリポジトリであることを確認して
**Trust Folder & Continue** を選択します。無関係なフォルダーは信頼しないでください。

## 管理者が事前に行うこと

リソースプロバイダーの登録、モデルのクォータ・容量の確認、参加者への RG の **Owner** ロール付与は、
サブスクリプション管理者が行います。詳細は[管理者向け前提条件](../admin/prerequisites.md)を参照してください。


## 準備完了のチェック

- [ ] Codespace で VS Code が開き、初期化が完了している
- [ ] 自分用のサブスクリプション ID と既存 RG 名が分かる
- [ ] Azure アカウントでサインインできる

> [!WARNING]
> **Codespaces と Azure の利用には料金が発生します。** 実際の個人情報・顧客情報は使わず、教材の合成データだけを使ってください。
> 終了時は [Lab 8](../../labs/08-observability-cleanup.md) のクリーンアップを行い、Codespace を停止します。
> **Codespace を閉じるだけでは Azure リソースは削除されません。**

## 次のステップ

[Lab 0 — 全体像と進め方](../../labs/00-overview.md)

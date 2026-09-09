# 参加者向け前提条件

ハンズオンで使うアカウントと実行環境を準備します。
**GitHub Codespaces** または **Azure Cloud Shell Bash + JupyterLab** を最初に選び、
[Lab 1](../../labs/01-setup.md) の共通の事前確認・環境作成へ進みます。
Lab 2〜9 は同じ教材、Lab 7 / 8 は同じ Notebook です。

## 必要なもの

| 必要なもの | 確認すること |
| --- | --- |
| Azure アカウント | Azure にサインインできる |
| Azure サブスクリプション ID | 個人検証用、または講師・管理者から受け取っている |
| サブスクリプションの権限 | 教材workload用RGとCloud Shell専用RG / Storageを作成できる。個人・sandbox subscriptionの **Owner**、または作成後のworkload用RGで **Owner** になれる同等の権限 |
| 教材workload用RGの名前 | 講師の命名規則に従う自分専用の一意名。例: `rg-foundry-handson-<受講者ID>` |

40名が1つの共有subscriptionでOwnerになると、互いのRGへアクセスできるため、
可能なら受講者ごとのsandbox subscriptionを使います。共有subscriptionを使う場合は、
管理者が許可範囲と終了後の棚卸し方法を明示してください。

## 教材workload用のリソースグループを作成する

Cloud ShellのStorage作成とは別に、最初に教材のAzure resourcesを置くRGを作ります。

1. [Azure portal](https://portal.azure.com/)に、上記の権限を持つアカウントでサインインします。
2. 上部の検索で **Resource groups** を開き、**Create** を選択します。
3. **Subscription** にハンズオン対象のsubscriptionを選択します。
4. **Resource group** に講師の命名規則に従った自分専用名を入力します。
5. **Region** は講師指定の値を選びます。通常は`Japan East`です。
   これはRG metadataの保存先で、後から作る各resourceのlocationを固定する値ではありません。
6. **Review + create > Create**を選びます。
7. 作成したRGを開き、**Resources**が0件であることを確認します。
8. **Access control (IAM) > View my access**で、このRGに対する**Owner**が有効であることを確認します。

このRG名をLab 1の`<resource-group>`に使います。`setup.sh`は新しいRGを作らず、
このRG内だけに教材workloadを作成します。Cloud Shellの初回画面が自動作成する
Storage用RGは別物なので、同じ名前にしたり教材workloadの出力先にしたりしません。

## 実行環境を選ぶ

| 経路 | 追加の前提条件 | 次に開くガイド |
|---|---|---|
| GitHub Codespaces | Codespaces を利用できる GitHub アカウント | [Codespaces の準備](environments/codespaces.md) |
| Azure Cloud Shell Bash + JupyterLab | 個人検証、または受講者が Cloud Shell 専用 RG / Storage を作成できるサブスクリプションレベルの権限を持つこと。Cloud Shell、Terminal の HTTPS / WebSocket、Jupyter preview の HTTPS、教材・パッケージ配布先への通信許可 | [Cloud Shell の準備](environments/cloud-shell.md) |

Cloud Shell では初回画面の **We will create a storage account for you** を標準にします。
Cloud Shell が新しい専用 RG、Storage account、Azure Files share を作成します。
組織が新しい RG の作成を許可しない場合だけ、管理者が用意した既存 Storage を選択します。
公開リポジトリの取得に GitHub アカウントは不要ですが、GitHub への通信許可は必要です。
**No storage account required** の一時セッションでは Terraform を実行しません。
会社で Codespaces が禁止されていても、Cloud Shell や配布先の利用が自動的に許可されるわけではありません。

## 手元の PC と実行環境を区別する

どちらの経路もブラウザーで使い、PC への Python / Azure CLI / Terraform のインストールは不要です。
Codespaces は devcontainer、Cloud Shell は教材の準備スクリプトで必要なツールをそろえます。
Docker、API キー、クライアントシークレットも本編では準備不要です。

| 場所 | 用途 |
| --- | --- |
| 手元の PC | ブラウザーを開く。アップロード用の素材を保存する |
| 選んだ実行環境 | Terminal でコマンドを実行する。ファイルブラウザーで教材と同じ Lab 7 / 8 の Notebook を開く |
| Foundry Portal（別タブ） | **Foundry (new)** でエージェントの設定・会話・評価・実行履歴を確認する |

**本編の `bash` コマンドは、選んだ環境の repository root の Terminal で実行します。**
PC の PowerShell / Terminal へ貼り付けないでください。
Portal のファイル選択画面は手元の PC を参照し、リモート環境のファイルは直接選べません。
Lab 4 の素材は環境ガイドの **Download** 手順で PC に保存してからアップロードします。

## 管理者が事前に行うこと

リソースプロバイダーの登録、モデルのクォータ・容量の確認、参加者への RG の **Owner** ロール付与は、
サブスクリプション管理者が行います。詳細は[管理者向け前提条件](../admin/prerequisites.md)を参照してください。

Cloud Shell を使う場合は `Microsoft.CloudShell` / `Microsoft.Storage` の登録、ストレージの
権限・ポリシー、通信条件も事前確認します。**tenant あたり既定20同時ユーザー**を超える開催は、
管理者から Azure Support へ事前に相談します。参加者は provider 登録や `--apply` を実行しません。

## 準備完了のチェック

- [ ] 選んだ環境ガイドの準備が完了し、Terminal とファイルブラウザーを開ける
- [ ] Python 3.13 の2つの環境と、`Python (Foundry Workshop)` / `Python (Foundry Hosted Agent)` を区別できる
- [ ] 自分用のサブスクリプション ID と、作成したworkload用RG名が分かる
- [ ] 作成直後のworkload用RGが空で、自分のOwnerが有効になっている
- [ ] Azure アカウントでサインインできる
- [ ] Cloud Shell の場合は、専用 RG / Storage を自動作成できる権限、または管理者が割り当てた既存 Storage がある
- [ ] Cloud Shell の場合は永続ストレージを接続し、ガイドどおり再接続後の教材ファイルの保持を確認した

> [!WARNING]
> **Codespaces と Azure の利用には料金が発生します。** 実際の個人情報・顧客情報は使わず、教材の合成データだけを使ってください。
> Cloud Shell の計算環境は無料ですが、Storage account / Azure Files と教材の Azure 利用は有料です。
> 終了時は [Lab 9](../../labs/09-observability-cleanup.md) のクリーンアップ後、環境ガイドの終了手順に従います。
> **ブラウザーや Cloud Shell を閉じるだけでは Azure リソースもストレージも削除されません。**

## 次のステップ

[Lab 0 — 全体像と進め方](../../labs/00-overview.md)を確認済みなら、
[Lab 1 — 環境構築](../../labs/01-setup.md)へ進んでください。

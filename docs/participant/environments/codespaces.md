# GitHub Codespaces — Labs 7〜8 の準備

ブラウザーで実施する標準手順です。PC への Docker・Python のインストールは不要です。
[Lab 1](../../../labs/01-setup.md) の初期化を完了し、Codespaces を利用できる GitHub アカウントを用意します。

## 1. Codespace を作成する

1. [教材リポジトリ](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/tree/dev-custom-template)
   を開き、ブランチが `dev-custom-template` であることを確認します。
2. **Code > Codespaces** を開き、作成ボタン
   （**Create codespace on dev-custom-template** または **＋**）を選びます。
3. ブラウザー版 VS Code が開き、Dev Container の作成と `postCreateCommand` の完了を待ちます。
4. Explorer に `notebooks/`、`scripts/`、`src/` があることを確認します。
   フォルダーのアップロードや、コードの個別ダウンロードは不要です。

同じ Codespace を再開するときは [Your codespaces](https://github.com/codespaces) から開きます。
ローカルの場合は[ローカル Dev Container](local-dev-container.md)で開いた後、以下へ進みます。

## 共通手順

### 2. コンテナーで Azure にサインインする

VS Code の **Terminal > New Terminal** で、Notebook を実行する前に **1 回**実行します。

```bash
az login --use-device-code
```

表示された案内に従い、自分の Azure アカウントと Lab 1 のサブスクリプションを選びます。
**GitHub や Azure Portal のログインは、コンテナー内の Azure CLI ログインとは別です。**
認証が切れた場合だけ再実行し、コードやトークンを Notebook に貼り付けません。

### 3. 初回 Notebook で接続先を取得する

1. [`notebooks/00-setup.ipynb`](../../../notebooks/00-setup.ipynb) を開きます。
2. 右上のカーネル選択で **Python (Foundry Workshop)** を選びます。
3. **subscription ID** と **RG 名**に、Lab 1 で使った 2 値を入力し、セルを上から実行します。
4. `.workshop/context.json` が作成され、対象 RG と `setup_status = complete` を確認できれば完了です。

Notebook は `scripts/configure_workshop.py` で成功した ARM deployment の `workshopContext` を読みます。
接続先は schema `2.0` の `resource_outputs.<key>.value` に保存され、モデルや endpoint の転記は不要です。
候補の曖昧さ・対象違い・初期化未完了で停止した場合は、[困ったとき](../troubleshooting.md)を確認します。

### 4. 演習のカーネルを選ぶ

Dev Container の post-create が、チェックアウト外の `~/.venvs/` に独立した環境を準備します。

| 用途 | カーネル表示名 | カーネル名 / Python |
|---|---|---|
| 初回設定・管理用 | **Python (Foundry Workshop)** | `foundry-workshop` / 3.12 |
| Labs 7〜8 | **Python (Foundry Hosted Agent)** | `foundry-hosted-agent` / 3.13 |

依存関係を混在させず、各 Notebook 指定のカーネルを使います。post-create は Azure に認証・デプロイしません。
VS Code の Notebook を使うため、Jupyter サーバーや公開ポートの追加は不要です。

[Lab 7](../../../labs/07-agent-framework-harness.md) へ進みます。
終了時は [Lab 9](../../../labs/09-observability-cleanup.md) の順に保存・削除してください。

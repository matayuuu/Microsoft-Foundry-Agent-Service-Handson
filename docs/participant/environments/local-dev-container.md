# ローカルの Dev Container — Labs 7〜8

Codespaces と**同じ `.devcontainer`、Notebook、カーネル**を使います。
ホスト OS へ Python / Conda を直接導入する手順は対象外です。

## ローカルで実施される方は以下の前提条件を確認下さい

- Git
- [Visual Studio Code](https://code.visualstudio.com/)
- [Dev Containers 拡張](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- コンテナーを起動できる Docker（起動済みで、組織の利用許可があること）
- Lab 1 と同じ Azure アカウント・認証手段、および[必要な権限](../prerequisites.md)

## 開く

1. 教材を clone し、VS Code で開きます。

   ```text
   git clone --branch dev-custom-template https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson.git
   code Microsoft-Foundry-Agent-Service-Handson
   ```

2. Command Palette で **Dev Containers: Reopen in Container** を選びます。
3. コンテナーと post-create の準備完了後、
   [共通手順：Azure CLI サインイン → 初回 Notebook](codespaces.md#共通手順) を実施します。

Python 3.12 / 3.13 の venv はコンテナー内・チェックアウト外に作られます。
ホストの `.venv` や Python の設定を変更する必要はありません。
終了時は成果物を保存し、[Lab 9](../../../labs/09-observability-cleanup.md) に従います。
ローカルの操作対象も、この教材のコンテナーだけにしてください。

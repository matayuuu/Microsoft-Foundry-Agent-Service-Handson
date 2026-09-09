# 実行環境ガイド — Azure Cloud Shell Bash + JupyterLab

Azure Cloud Shell の Bash と JupyterLab で、Codespaces と同じ教材を実行します。
初回準備が終わったら [Lab 1 の手順 2](../../../labs/01-setup.md#2-事前確認を実行する)へ進みます。

> [!IMPORTANT]
> **永続ストレージを使用してください。** **No storage account required** の一時環境では
> Terraform を実行しません。Cloud Shell のストレージは教材workload用RGとは別に管理します。

<a id="create-storage"></a>

## Cloud Shellを開く

1. [Azure portal](https://portal.azure.com/)にサインインし、上部の **Cloud Shell** を開きます。
2. **Bash** を選びます。
3. **Mount storage account** を選び、対象のsubscriptionを選択して **Apply** を押します。
4. **We will create a storage account for you** を選び、**Next** を押します。
5. Bashが開いたら、**Manage files > Open file share** で自動作成された専用RG名を控えます。

Cloud Shellが作る専用RG、Storage account、File shareは、教材workload用RGとは別物です。
専用RG名は、終了時に自分のストレージだけを削除するために使います。

<a id="mount-storage"></a>

<details>
<summary>管理者から既存Storageを指定された場合</summary>

手順4で **Select existing storage account** を選び、指定されたResource group、
Storage account、File shareを選択します。自分で新規作成・削除せず、管理者の指示に従ってください。

</details>

<a id="setup"></a>

## 教材を準備する

Cloud Shellで次を実行します。

```bash
cd "$HOME"
git clone https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson.git
cd Microsoft-Foundry-Agent-Service-Handson
```

講師からbranchを指定された場合は、`git clone`を次に置き換えます。

```bash
git clone --branch "<branch-name>" --single-branch \
  https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson.git
```

すでに同じrepositoryがある場合は再cloneせず、そのフォルダーへ移動してください。

<a id="persistence"></a>

### 初回のみ: Restart後もファイルが残ることを確認する

1. 確認用ファイルを作ります。

   ```bash
   date -u > "$HOME/cloud-shell-resume-check.txt"
   ```

2. Cloud Shell toolbarの **Restart** を選び、Bashが開き直すまで待ちます。
3. 同じファイルを確認して削除します。

   ```bash
   cat "$HOME/cloud-shell-resume-check.txt"
   rm "$HOME/cloud-shell-resume-check.txt"
   ```

ファイルが見つからない場合は作業を止め、元のStorage接続を講師または管理者に確認してください。

<a id="jupyter"></a>

## JupyterLabを開く

### Terminal A: JupyterLabを起動する

```bash
cd "$HOME/Microsoft-Foundry-Agent-Service-Handson"
bash scripts/start-cloud-shell-jupyter.sh
```

初回は必要な実行環境も自動で準備されるため、起動まで数分かかることがあります。

1. 画面の案内に従い、12文字以上のJupyterLab用passwordを2回入力します。
2. `Open Cloud Shell Web preview for port 5000` と表示されるまで待ちます。
3. Cloud Shell toolbarの **Web preview** でport **5000**を入力し、
   **Open and browse** を選びます。
4. JupyterLabのログイン画面で、先ほどのpasswordを入力します。

previewタブはJupyterLabへ自動で切り替わります。URLのコピーや2回目の起動コマンドは不要です。
JupyterLabを使っている間はTerminal Aを閉じないでください。

<a id="authentication"></a>

### Terminal B: Labのコマンドを実行する

Cloud Shell toolbarの **New session** でTerminal Bを開き、次を実行します。

```bash
cd "$HOME/Microsoft-Foundry-Agent-Service-Handson"
source scripts/activate-cloud-shell.sh
az account set --subscription "<subscription-id>"
az account show --query "{subscriptionId:id, user:user.name}" -o table
```

対象のsubscriptionとAzureアカウントが表示されたら、
[Lab 1 の手順 2](../../../labs/01-setup.md#2-事前確認を実行する)へ進みます。
以降のTerminalコマンドはTerminal Bで実行します。

password認証やXSRFを無効化したり、すべてのOriginを許可したりしないでください。
起動に失敗した場合は[トラブルシューティング](../troubleshooting.md#実行環境と-cloud-shell)を確認します。

<details>
<summary>Web previewの自動検出に失敗した場合</summary>

次のコマンドでport 5000を開き、表示されたHTTPS URLを控えて **Ctrl+C** で停止します。

```bash
bash scripts/start-cloud-shell-jupyter.sh --discover-preview --port 5000
```

控えたURLを指定して起動します。

```bash
bash scripts/start-cloud-shell-jupyter.sh \
  --port 5000 \
  --preview-url "<actual-https-preview-url>"
```

</details>

<a id="notebook"></a>

## Notebookを実行する

Lab 7 / 8では次のNotebookを使います。

- `notebooks/07-agent-framework-harness.ipynb`
- `notebooks/08-hosted-agent.ipynb`

1. JupyterLabのファイル一覧からNotebookを開きます。
2. kernelに **Python (Foundry Hosted Agent)** を選びます。
3. **Shift+Enter** でセルを上から順に実行し、区切りごとに **Save** します。

追加packageが必要な場合は、現在のkernelへインストールする `%pip install ...` を使います。
通常の演習に必要なpackageは準備済みです。
Lab 8のNotebookはworkflowの確認まで行い、Hosted AgentのdeployはTerminal Bで実行します。

<a id="files"></a>

## Lab 4のZIPをPCへ保存する

Foundry Portalのファイル選択画面はPCを参照するため、生成したZIPをCloud Shellからダウンロードします。

1. Terminal BでHOMEからの相対パスを表示します。

   ```bash
   cd "$HOME/Microsoft-Foundry-Agent-Service-Handson"
   realpath --relative-to="$HOME" \
     .workshop/toolbox/travel-estimation.zip \
     .workshop/toolbox/preapproval-simulation.zip
   ```

2. Cloud Shell toolbarの **Manage files > Download** を選びます。
3. 入力欄にHOMEのprefixが表示されている場合は、出力された **HOME相対パス**を入力します。
4. **Download** を押した後、**Download file** 通知に表示されるファイル名のリンクを選びます。
5. 2つのZIPを同じ手順でPCへ保存し、Foundry Portalで選択します。

ZIPは展開・再圧縮しません。Terraform state、認証情報、HOME全体はダウンロードしないでください。

<a id="resume"></a>

## 中断後に再開する

Cloud Shellは非対話状態が約20分続くと終了することがあります。
Notebookはこまめに保存してください。保存してもPythonの変数やkernelのメモリーは残りません。

1. Cloud Shellの **Bash** を開き、記録した同じStorageへ接続します。
2. Terminal AでJupyterLabを起動します。

   ```bash
   cd "$HOME/Microsoft-Foundry-Agent-Service-Handson"
   bash scripts/start-cloud-shell-jupyter.sh
   ```

3. Terminal Bを開き、環境とsubscriptionを設定します。

   ```bash
   cd "$HOME/Microsoft-Foundry-Agent-Service-Handson"
   source scripts/activate-cloud-shell.sh
   az account set --subscription "<subscription-id>"
   ```

4. Lab 1を完了済みの場合は、元の`.workshop/context.json`とTerraform stateが残っていることを確認します。
   見つからない場合は新しくsetupせず、元のStorage接続を確認してください。
5. Notebookを開き、必要なセルを上から再実行します。

評価やdeployが途中だった場合は、先にFoundry Portalで既存runの状態を確認し、重複実行を避けます。

<a id="stop"></a>

## Lab 9後に終了する

**順序: workloadのcleanup → Cloud Shell設定解除 → 専用Storage削除**

1. [Lab 9](../../../labs/09-observability-cleanup.md)の`./scripts/destroy.sh`が成功したことを確認します。
   失敗した場合は先へ進まず、Terraform stateと`.workshop/`を保持してください。
2. 自動作成した専用Storageを使った場合だけ、Cloud Shellの
   **Settings > Reset User Settings** で関連付けを解除します。
3. Azure portalで控えたCloud Shell専用RGを開き、他用途のresourceがないことを確認して
   **Delete resource group** を実行します。

教材workload用RGは`destroy.sh`でもこの手順でも削除しません。
管理者から割り当てられた既存Storageは削除せず、管理者の指示に従ってください。

> [!WARNING]
> Cloud Shellの計算環境は無料ですが、Storageと教材のAzure resourcesには料金が発生します。
> ブラウザーやCloud Shellを閉じるだけでは削除されません。

## 公式資料

- [Cloud Shellを開く・Web preview・ファイル操作](https://learn.microsoft.com/azure/cloud-shell/use-the-shell-window)
- [Cloud ShellにStorageを自動作成する](https://learn.microsoft.com/azure/cloud-shell/get-started/new-storage)
- [既存Storageへ接続する](https://learn.microsoft.com/azure/cloud-shell/get-started/existing-storage)

# 旧Cloud Shellガイドの参照先

このページの旧手順は現行構成では使用しません。Cloud ShellとJupyterLabを使った
旧構成の履歴資料です。環境作成は [環境準備ガイド](custom-template.md) から
[Lab 1](../../../labs/01-setup.md) へ進んでください。
Labs 7〜8は [Codespaces](codespaces.md) または
[ローカルDev Container](local-dev-container.md) で実行します。

旧本文は経緯を確認するために保持しています。本文中のコマンド、画面説明、リンクは
当時の構成を前提としており、現在の利用可能性を保証しません。
現行の操作や権限の判断には、上記のガイドを参照してください。

<details>
<summary>旧手順の履歴資料</summary>

<!-- historical-content:start -->
# 実行環境ガイド — Azure Cloud Shell Bash + JupyterLab

Azure portal の **Cloud Shell** と、**Web preview** で開く JupyterLab を使います。
PC に開発ツールをインストールせず、Codespaces と**同じ Lab 7 / 8 の Notebook**を
ブラウザーで実行します。Notebook を CLI 演習へ置き換える経路ではありません。

このページで準備を完了したら、[Lab 1 の手順 2](../../../labs/01-setup.md#2-事前確認を実行する)に戻ります。
Lab 2〜9 の Terraform、Portal 操作、教材ファイル、Azure resources は共通です。
[実行環境の選択へ戻る](../prerequisites.md)

> [!IMPORTANT]
> **永続ストレージ付きの Bash が必須です。** **No storage account required** の
> ephemeral session では Terraform を実行しません。
> Cloud Shell は非対話20分で終了することがあり、実行中のプロセスや kernel のメモリーは失われます。
> 開催管理者は **tenant あたり既定20同時ユーザー**の制限を事前確認します。

> [!WARNING]
> Cloud Shell の計算環境は無料ですが、Storage account / Azure Files と教材の Azure 利用は有料です。
> `exit` やブラウザー終了では storage と Azure resources は削除されません。
> state を失わないよう、必ず [終了手順](#stop)の順序を守ってください。

### 自動作成で簡単になる範囲

初回画面の **We will create a storage account for you** を使うと、Storage用のRG、
Storage account、Azure Files shareを個別に作る操作は不要になります。
一方、JupyterLabをCloud Shellで使うための次の構築は残ります。

| 構築 | 必要な理由 |
|---|---|
| 永続HOMEの確認 | Terraform state、教材、2つのPython環境を切断後も保持する |
| standalone CPython 3.13 | Cloud Shellのsystem Pythonとは分離して教材の対象版を使う |
| root / Hostedの2つの`.venv` | `azure-ai-projects==2.5.0`とHosted Agentの`<2.4`を混在させない |
| JupyterLab / Jupyter Server / 2 kernelspec | 同じLab 7 / 8 Notebookを2つの依存環境で実行する |
| native Graphviz | Lab 8で実際のworkflow SVGを描画する |
| Web preview / 認証 / relay互換処理 | 実preview URL、port、password、Host / Origin / XSRF、kernel channelを安全に接続する |
| 2つのTerminalと再接続手順 | Jupyterを実行したまま通常コマンドを使い、20分切断後に安全に再開する |

したがって、自動Storage作成は有効な簡略化ですが、Jupyter固有の準備・通信・運用は省略しません。

## 1. 入力する値と組織の許可を確認する

次を講師・管理者と確認し、秘密を含まない値だけを手元に控えます。
この記録はストレージの再接続と、最後の削除対象の照合に使います。

| 値 | 確認する内容 |
|---|---|
| Subscription ID | ハンズオンに割り当てられた subscription |
| Workload resource group | 参加者向け前提条件の冒頭で作成した自分専用RG。そのRGに対する自分の**Owner**権限 |
| Cloud Shell Storage作成権限 | 個人検証、またはCloud Shellが専用の新規RG / Storage accountを作成できるサブスクリプションレベルの権限。例: Contributorまたは同等のカスタムロール |
| 自動生成されたStorage | 作成後に専用RG、Storage account、File share、locationを記録する。Workload RGやTerraformの管理対象と混同しない |
| 教材 URL / branch | 講師が指定する公開 GitHub repository の HTTPS clone URL と branch |
| 作成・削除の区分 | Cloud Shellが今回自動作成した専用RG一式か、管理者が割り当てた既存Storageか。削除を許可された対象 |
| 既存の Cloud Shell 設定 | 利用済みの場合は元の `preferredLocation`、subscription / RG / account / share と個人設定を本人の安全な保存先に控える。既存 storage は今回の削除対象にしない |

管理者は `Microsoft.CloudShell` / `Microsoft.Storage` の登録、Storage の権限・policy、
ブラウザーの HTTPS / WSS、GitHub・GHCR・パッケージ配布先の通信を事前確認します。
詳細は[管理者向け前提条件](../../admin/prerequisites.md#実行環境の選択と-cloud-shell-の開催条件)にあります。
公開 repository の clone に GitHub account は不要ですが、GitHub への通信許可は必要です。
Codespaces の禁止と、GitHub / パッケージ配布先への通信禁止は別です。

共有キーアクセスや public network が組織で禁止され、標準 Cloud Shell のストレージを
マウントできない場合は、管理者へ戻してください。policy、firewall、認証制限を弱めて進みません。
参加者は、Cloud Shellの初回Storage作成以外の provider登録、subscription scopeのrole付与、
quota変更、`admin-preflight.sh --apply`を行いません。

<a id="create-storage"></a>

## 2. Cloud Shell に自分専用の storage を自動作成させる

このハンズオンでは、個人検証または上記の作成権限があることを前提に、公式の自動作成経路を使います。

1. [Azure portal](https://portal.azure.com/) に対象のAzureアカウントでサインインします。
2. 上部の **Cloud Shell** を開き、初回のshell選択で **Bash** を選びます。
3. **Getting started** で **Mount storage account** を選択します。
4. **Storage account subscription** で記録したsubscriptionを選び、**Apply**を選択します。
5. **Mount storage account** で **We will create a storage account for you** を選び、
   **Next**を選択します。Cloud Shellが専用の新規RG、Storage account、Azure Files shareを作成します。
6. Bashのプロンプトが表示されたら、**Manage files > Open file share**で自動作成された
   RG / account / share / locationを開き、終了時の削除対象として記録します。

公式手順:
[Get started with Azure Cloud Shell using persistent storage](https://learn.microsoft.com/azure/cloud-shell/get-started/new-storage)

> [!IMPORTANT]
> 自動作成先は教材workload用の既存RGではなく、Cloud Shell専用の新規RGです。
> `setup.sh` / `destroy.sh`の管理対象ではありません。各参加者が自分の専用RG一式だけを記録し、
> workload cleanup成功後に削除します。

<details>
<summary>新規RGを許可しない組織だけ: 既存RG内にStorageを手動作成する</summary>

この代替経路では、管理者が**自分専用**のStorage account / File shareを用意済みなら、
そのまま[接続手順](#mount-storage)へ進みます。他人のshareや他用途のHOME imageは使いません。
自分で作成する場合は次を使います。

### Storage account を作成する

1. [Azure portal](https://portal.azure.com/) に Azure アカウントでサインインします。
2. 上部の検索で **Storage accounts** を開き、**Create** を選びます。
3. **Basics** で次を設定します。

   | 項目 | 設定 |
   |---|---|
   | **Subscription** | 記録した subscription |
   | **Resource group** | 割り当てられた**既存 RG**を選択。**Create new** は使わない |
   | **Storage account name** | 記録した自分専用の一意名。使用済みなら別の未使用名を選び、記録を更新 |
   | **Region** | 選択する対応済み Cloud Shell location と一致する region。RG の region をそのまま流用しない |
   | **Primary service** | `Other (tables and queues)` |
   | **Performance** | `Standard`。説明に `general-purpose v2 account` と表示される選択肢 |
   | **Redundancy** | `Locally-redundant storage (LRS)` |

4. **Primary service** は利用できるストレージの種類を制限しません。
   `Other (tables and queues)` でも、作成後に Azure Files share を作れます。
   **この手順では Primary service に Azure Files を選びません。**
   2026-09-09 の Portal 作成画面では、その選択によって、先に Standard を選んでいても
   Review が **Account type: File shares**、**Media Tier: HDD**、**Provisioned v2** に
   変わる事象が確認されています。
5. セキュリティ・ネットワークのタブは、組織が承認した Cloud Shell 対応の設定を保ちます。
   secure transfer、TLS 1.2 以上、SMB の転送時暗号化などの保護を弱めず、
   Blob の anonymous access を有効化しません。
   共有キーを使う標準マウントが許可されているか不明、または network / policy の拒否がある場合は、
   その場で制限を解除せず管理者へ連絡してください。
6. **Review + create** で subscription、既存 RG、名前、Cloud Shell と一致する region を再確認します。
   **View automation template > Parameters** を開き、
   **`kind=StorageV2`、`accountType=Standard_LRS`** であることを確認します。値や template は編集しません。
   2026-09-09 の画面では、正しい Other / Standard の選択でも Review の
   **Account type が Page blobs と表示される不整合**が確認されています。
   Review の説明ラベルではなく、**ARM template の kind / accountType を判断根拠**にしてください。
   値が違う場合は作成せず、**Basics** に戻って選び直します。
   StorageV2 / Standard_LRS を確認できない場合は管理者へ連絡し、`FileStorage` や Premium で代用しません。
7. 正しい構成を確認してから **Create** を選び、完了したら **Go to resource** を開きます。
   実際に作成された kind / SKU / provisioning state は、次の Cloud Shell 接続後にも読み取り専用で確認します。

本編 Terraform の管理タグをこの storage にコピーしません。Storage は実行環境の前提であり、
`setup.sh` / `destroy.sh` が作成・削除する Foundry workload とは別管理です。
Storage の **Access keys** を表示したり、キーや SAS をコピーしたりする操作は不要です。

### Azure Files share を作成する

1. 作成した Storage account の **Data storage > Classic file shares** を開きます。
   Blob container ではありません。
2. toolbar の **New classic file share** を選び、**Name** に記録した名前（例: `cloudshell-handson`）を入力します。
   小文字英数字と単独のハイフンを使い、先頭・末尾は英数字にします。
3. **Access tier** は `Transaction optimized` を選びます。StorageV2 の pay-as-you-go share は
   SMB です。NFS share や別の file-share resource provider を選びません。
4. **Backup** タブを確認します。**Enable backup** は既定で On になり、
   新しい Recovery Services vault と backup policy の作成が設定されます。
   今回の新規・演習専用 share で backup が任意なら、この選択を外して追加 resource を作りません。
   **組織必須の backup や既存の保護は変更せず**、必要なら管理者と別途調整します。
5. **Review + create** で **Name** が記録した share 名、**Access Tier** が
   **TransactionOptimized**、**Protocol** が **SMB** であり、
   **新しい Vault / backup policy の作成が含まれていないこと**を確認します。
   追加の vault が残っている場合は **Backup** に戻って設定を確認し、組織必須なら管理者へ相談します。
   正しい構成を確認してから **Create** を選び、一覧に自分の share があることを確認します。
6. subscription / RG / Storage account / File share の組み合わせと、新規作成した対象を記録します。
   quota を設定する場合は、HOME image と教材・依存パッケージを保存できる容量を管理者と確認します。

</details>

<a id="mount-storage"></a>

## 3. 永続 storage と Bash を確認する

自動作成後はBashのプロンプトと **Manage files > Open file share** の対象を確認します。
Storageを使わない **No storage account required** のsessionへ切り替えません。

<details>
<summary>既存Storageを使う場合だけ: 明示的に選択して接続する</summary>

1. Azure portal上部の **Cloud Shell** を開きます。
2. shellの選択では **Bash** を選びます。
3. **Getting started > Mount storage account** で対象subscriptionを選び、**Apply**を選択します。
4. **Select existing storage account > Next**を選択します。
5. 記録した **Resource group**、**Storage account name**、**File share**を順に選び、
   **Select**を選択します。
6. Bashのプロンプトと **Manage files > Open file share** の対象が一致することを確認します。

</details>

既存Storageを手動作成した場合は、次の**読み取り専用**コマンドでも確認できます。
`kind` が `StorageV2`、`sku` が `Standard_LRS`、`provisioningState` が `Succeeded` であることを確認してください。

```bash
az storage account show \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --name "<storage-account-name>" \
  --query "{kind:kind, sku:sku.name, provisioningState:provisioningState}" -o table
```

**Bash が開いただけでは永続接続の成功ではありません。**
上のコマンドはStorage accountの作成結果を確認するもので、HOMEの永続マウントを証明するものではありません。
既存設定が古い share を参照している場合、マウントに失敗して ephemeral session として開くことがあります。
そのまま本編へ進まず、元の設定と storage を保全して、以下の明示的な再設定手順を確認してください。

<details>
<summary>すでに Cloud Shell を利用している場合だけ: 既存接続を確認する</summary>

記録した自分の演習用 share に接続済みなら、そのまま使います。設定のリセットは不要です。
別用途の storage に接続している場合は、そのまま演習を始めたり、無断で切り替えたりしません。
元の `preferredLocation`、subscription / RG / account / share と個人設定を控え、
実行中の作業と必要なファイルを保全し、講師・管理者と切替の影響を確認します。
古い share が割り当て RG の外にあっても、マウント失敗を理由にその storage を削除しません。

以前 **No storage account required** を選んだ場合や、古い share のマウント失敗後に
ephemeral session になった場合など、接続選択をやり直す必要があり、
影響を理解して切替を承認した場合に限り、**Settings > Reset User Settings** を使います。
確認画面で **Reset** すると現在の session と個人設定がリセットされます。
未永続化のファイルやプロセスは失われるため、保存前に実行しません。
元の Azure Files share 自体は削除されず、新しい share を選ぶと別の HOME image になります。
再度この節の **Mount storage account > Select existing storage account** に従い、
選択する Cloud Shell location と新しい storage の region を一致させます。
元の設定は後で戻す必要があるか管理者と確認できるよう保全します。

**Reset User Settings は標準の再接続・cleanup 手順ではありません。**
以前の設定や他用途の storage を自動で削除・初期化しないでください。

</details>

### 保存先を確認する

Cloud Shell は Azure Files に HOME の disk image を保存し、share 自体を
`$HOME/clouddrive` にマウントする方式があります。
この教材の repository と `.venv` は、Unix のリンク・権限が使える **HOME 内**に置きます。
**`clouddrive` の SMB share 直下へ clone / venv 作成はしません。**

```bash
printf 'HOME=%s\n' "$HOME"
findmnt -T "$HOME"
findmnt -T "$HOME/clouddrive"
df -h "$HOME" "$HOME/clouddrive"
```

`clouddrive` というディレクトリがあるだけでは永続化の証拠になりません。
準備スクリプトのマウント検査に加え、[実際の再起動による保持確認](#persistence)を行います。
`.cloudconsole` 内の HOME image、Terraform state、Azure CLI のキャッシュは機密情報です。
share のアクセス権を他ユーザーへ広げたり、HOME 全体を配布したりしません。

<a id="setup"></a>

## 4. 教材と実行ツールを準備する

Cloud Shell の Bash で、講師指定の URL と branch を置き換えて実行します。
コマンド中の `<...>` は入力用の目印で、そのまま使う値ではありません。

```bash
git clone --branch "<workshop-branch>" --single-branch \
  "<public-repository-https-url>" "$HOME/foundry-agent-service-handson"
cd "$HOME/foundry-agent-service-handson"
bash scripts/setup-cloud-shell.sh
source scripts/activate-cloud-shell.sh
```

同じフォルダーが存在する場合は、上書き・削除・再 clone せず、
元の演習用 repository か確認して [再接続](#resume)へ進みます。
本編で使う `setup-cloud-shell.sh` はツールの準備であり、Azure workload の `setup.sh` とは別です。
system Python / Azure CLI を変更せず、利用可能な Python 3.13 を再利用します。
不足時は uv も利用する公式の standalone CPython 配布物をユーザー領域へ用意します。
取得するバージョン・配布元・SHA-256 はスクリプト側で管理し、受講者は変更しません。
native Graphviz がない場合もユーザー所有の micromamba / conda-forge 環境へ導入します。
`pip install graphviz` だけでは native renderer の代わりになりません。
初回は HOME に少なくとも3 GiB、準備済み環境の再確認には512 MiB の空きを検査します。
不足時は他用途のファイルを削除せず、管理者と容量を確認してください。

準備が成功したら確認します。

```bash
.venv/bin/python --version
src/hosted-agent/.venv/bin/python --version
.venv/bin/jupyter kernelspec list
dot -V
```

| 確認対象 | 期待するもの |
|---|---|
| root `.venv` | Python `3.13.x`。共通スクリプト・デプロイ・JupyterLab 用 |
| `src/hosted-agent/.venv` | Python `3.13.x`。Agent Framework の Lab 7 / 8 用 |
| kernels | `foundry-workshop` と `foundry-hosted-agent` |
| `dot` | native Graphviz のバージョンが表示される |

root は `azure-ai-projects==2.5.0`、Hosted Agent は `<2.4` の依存を使うため、
2つの `.venv` を統合しません。普通の受講手順では設定ファイルや source の編集は不要です。
不足・容量・通信エラーは講師へ伝え、原因を解消して同じ準備コマンドを再実行します。
`sudo`、`apt-get`、Docker daemon、system Python への package install は使いません。

`source scripts/activate-cloud-shell.sh` は PATH と
`AZURE_TOKEN_CREDENTIALS=AzureCliCredential` を**この Terminal から起動する教材プロセスだけ**に設定します。
新しい Terminal や再接続のたびに実行してください。
この credential 制限を Hosted Agent のデプロイ先へコピーせず、Hosted runtime は managed identity を使います。

<a id="persistence"></a>

## 5. Azure resources を作る前に保持を確認する

**この確認は Lab 1 の `setup.sh` より先に行います。**
HOME 永続化について公式の storage 文書と FAQ の記述に差があるため、
文書の説明だけで保存済みと判断しません。

1. 準備済み repository で、秘密を含まない確認ファイルを作ります。

   ```bash
   cd "$HOME/foundry-agent-service-handson"
   date -u '+%Y-%m-%dT%H:%M:%SZ' > cloud-shell-resume-check.txt
   cat cloud-shell-resume-check.txt
   ```

2. 表示された日時を控え、ほかに実行中の作業がないことを確認します。
3. Cloud Shell toolbar の **Restart** を選び、container の再起動を待ちます。
   **New session** は同じ container の別プロセスを開くだけなので、この検証の代わりにはなりません。
4. 同じ記録済み storage で Bash に戻り、**clone や bootstrap を再実行する前に**次を確認します。

   ```bash
   cd "$HOME/foundry-agent-service-handson"
   cat cloud-shell-resume-check.txt
   test -f notebooks/07-agent-framework-harness.ipynb
   test -f notebooks/08-hosted-agent.ipynb
   source scripts/activate-cloud-shell.sh
   .venv/bin/python --version
   src/hosted-agent/.venv/bin/python --version
   .venv/bin/jupyter kernelspec list
   dot -V
   ```

5. 同じ日時、教材、2つの環境と kernel が残っていれば、確認ファイルだけを削除します。

   ```bash
   rm cloud-shell-resume-check.txt
   ```

フォルダーやファイルが失われた場合はここで止まり、元の share / HOME image とマウントを
管理者へ確認してもらいます。未確認の保存先で Azure resources を作りません。
Lab 1 実行後の再接続では、state と `.workshop/context.json` も同じものが保持されている必要があります。

<a id="authentication"></a>

## 6. Azure CLI のサインインを確認する

Cloud Shell の既存 Azure CLI サインインを使い、割り当てられた subscription を明示します。

```bash
az account set --subscription "<subscription-id>"
az account show --query "{subscriptionId:id, user:user.name}" -o table
```

表示されるユーザーが RG の Owner を付与された本人か確認します。
Foundry / Search の操作で `Audience ... is not a supported MSI token audience` が出た場合は、
公式 FAQ の回復手順として次を実行し、元の操作を再試行します。

```bash
az login --use-device-code
az account set --subscription "<subscription-id>"
```

device-code 認証が組織で拒否される場合は、管理者へ相談して止めます。
device code、token、Storage key を共有しません。API key / client secret への置き換えや
追加の `azd auth login` は不要です。

<a id="jupyter"></a>

## 7. Web preview で JupyterLab を開く

Cloud Shell の Terminal を2つ使います。**Terminal A** は Jupyter サーバーを実行したままにし、
**Terminal B** で Lab のコマンドを入力します。PC の PowerShell を使う手順ではありません。

1. Terminal Aでrepository rootへ移動し、次の**1コマンド**を実行します。
   初回は必要な依存関係を準備し、2回目以降は確認して再利用します。

   ```bash
   cd "$HOME/foundry-agent-service-handson"
   bash scripts/start-cloud-shell-jupyter.sh
   ```

2. Terminalで、Jupyter専用の12文字以上のpasswordを2回入力します。
   入力した文字は表示されません。同じpasswordをこのsessionのブラウザーログインで使います。
3. `Open Cloud Shell Web preview for port 5000` と表示されたら、Cloud Shell toolbarの
   **Web preview**を開き、portに **5000** を入力します。
   **Open and browse** で新しいタブを開きます。先に **Open port** を選んだ場合は、
   メニューの **Preview port 5000** で開きます。
   **Web preview** が見えなければ **More commands** 内を確認します。
   対応範囲は `1025–8079` または `8091–49151` です。
4. previewタブは自身の実HTTPS URLを一時discovery serverへ渡し、
   JupyterLabの起動後に自動で再読み込みします。URLのコピー、Terminal AのCtrl+C、
   2回目の起動コマンドは不要です。
5. Jupyterのログイン画面で、手順2のpasswordを入力してJupyterLabを開きます。
   起動スクリプトは repository をファイル公開ルートにし、実際の preview origin に限定します。
   パスワードに加えて内部の token もユーザー専用ファイルで管理し、ログへ表示しません。
   token 認証や XSRF を無効化したり、すべての Origin を許可したりする設定へ変更しません。
6. Cloud Shell toolbar の **New session** で Terminal B を開きます。
   このタブは**同じ container**に接続しますが、Terminal の環境変数は別なので次を実行します。

   ```bash
   cd "$HOME/foundry-agent-service-handson"
   source scripts/activate-cloud-shell.sh
   ```

port が使用中なら別ポートへ無言で移動せず、自分の既存 Jupyter が動いているか確認します。
不要な既存サーバーは保存して正常終了し、ほかの人・別用途のプロセスを停止しません。
既定の待ち受けは `127.0.0.1` です。講師の確認で Cloud Shell の proxy から loopback に
到達できない場合に限り、discovery と Jupyter の**両方**の起動に `--listen 0.0.0.0` を明示します。
認証や実際の preview origin 制限は維持します。proxy の path 調整用 `--base-url` は
実際の URL と転送動作を講師が確認した場合だけ使い、値を推測しません。
認証、proxy、WebSocket のエラーが続く場合は、保護を弱めず
[トラブルシューティング](../troubleshooting.md#実行環境と-cloud-shell)へ進みます。

<details>
<summary>preview URL の自動検出に失敗した場合だけ: 手動 discovery</summary>

自動検出に失敗した場合は、従来の2段階モードで実URLを確認できます。

```bash
bash scripts/start-cloud-shell-jupyter.sh --discover-preview --port 5000
```

Web previewで5000を開き、表示された実HTTPS URLを控えてCtrl+Cで停止します。

```bash
bash scripts/start-cloud-shell-jupyter.sh \
  --port 5000 \
  --preview-url "<actual-https-preview-url>"
```

URLにquery / fragment / tokenを含めません。この手動経路でも認証とXSRFは維持します。

</details>

### Cloud Shell relay との互換処理

Cloud Shell の relay は通常の Jupyter と異なり、URL prefix、redirect、HTTP status、
cookie と browser WebSocket をそのまま転送しません。起動スクリプトはこの環境だけに
互換処理を適用します。Jupyter のパスワードを確認した後でのみ、Azure の既存の
Secure / HttpOnly relay cookie に Jupyter session を結び付けます。
認証 cookie や token を JavaScript や URL へコピーしません。
読み取り可能な `_xsrf` だけを login form から設定し、変更操作の XSRF 検査を維持します。

Notebook の kernel 通信は、認証・XSRF・利用者分離を維持した HTTP polling を経由し、
Cloud Shell 内の loopback WebSocket に接続します。通常の WebSocket をブラウザーから
直接開く手順ではありません。Codespaces の接続方式は変更しません。
サーバー側の channel と待ち行列には上限・期限があり、logout / shutdown 後は再認証します。

<a id="notebook"></a>

## Notebook の操作

Portal 中心の Lab 2〜6 の間に Cloud Shell が終了していた場合は、先に
[再接続手順](#resume)で同じ環境の Jupyter を起動し直してください。
JupyterLab 左側のファイルブラウザーが repository root を開いていることを確認します。
`notebooks/07-agent-framework-harness.ipynb` と `notebooks/08-hosted-agent.ipynb` が同じ教材です。
ここでは開けることと kernel を確認し、Azure を呼ぶ学習セルは該当する Lab で実行します。

初回の接続確認では **File > New > Console** を開き、
**Python (Foundry Workshop)** と **Python (Foundry Hosted Agent)** を1つずつ選んで、
それぞれ次を **Shift+Enter** で実行します。Azure は呼び出しません。

```python
import sys
print(sys.version)
print(sys.executable)
```

両方が Python `3.13.x` で、root `.venv/bin/python` と
`src/hosted-agent/.venv/bin/python` がそれぞれ表示されれば、両 kernel への接続と実行を確認できます。
確認用 Console は **Kernel > Shut Down Kernel** で終了して閉じます。
本編の Notebook を編集して確認セルを追加する必要はありません。

1. Lab が指定する `.ipynb` をダブルクリックして開きます。
2. kernel の選択ダイアログ、右上の kernel 名、または **Kernel > Change Kernel…** で
   **Python (Foundry Hosted Agent)** を選びます。
3. Lab 7 / 8 では `src/hosted-agent/.venv/bin/python` を使います。
   root の **Python (Foundry Workshop)** は Lab 4 の任意 SDK 補助 Notebook 用であり、
   Agent Framework 演習には選びません。
4. セルを選んで **Run** または **Shift+Enter** で1セルずつ実行し、**Save** で保存します。
   可視化セルでは Graphviz による実物の SVG が表示されることを確認します。

追加のNotebook専用packageが必要な場合は、`!pip`ではなく現在のkernelへ入る`%pip`を使います。
本編の固定依存関係は起動スクリプトが準備済みなので、通常は追加インストール不要です。

両 kernel の名前は `foundry-hosted-agent` / `foundry-workshop` です。
ブラウザーに Notebook が表示されるだけでなく、上の接続確認セルが実行できる必要があります。
kernel、保存、描画に問題があれば環境を修復してから続けます。
Lab 8 の **Run All** は deploy せず、デプロイは共通 Lab の Terminal コマンドで行います。

**環境準備中なら [Lab 1 の手順 2](../../../labs/01-setup.md#2-事前確認を実行する)へ戻ります。**
Lab 7 / 8 から操作方法を参照した場合は、読んでいた Lab の同じ Notebook 演習を続けます。

<a id="files"></a>

## Lab 4 の素材を PC にダウンロードする

Cloud Shell / JupyterLab と PC は別のファイルシステムです。
Foundry Portal の **Upload skill** のファイル選択画面は PC を参照します。
`.workshop` は隠しフォルダーですが、JupyterLab に全隠しファイルを表示させる必要はありません。

1. [Lab 4](../../../labs/04-tools-toolbox.md) で素材を生成した後、接続中の Terminal B で
   ダウンロードする**名前付きの ZIP 2つだけ**の HOME 相対パスを表示します。

   ```bash
   cd "$HOME/foundry-agent-service-handson"
   realpath --relative-to="$HOME" \
     .workshop/toolbox/travel-estimation.zip \
     .workshop/toolbox/preapproval-simulation.zip
   ```

2. Cloud Shell toolbar の **Manage files > Download** を選びます。
3. 入力欄の前に `/home/<自分のユーザー名>/` が表示されていることを確認し、
   `foundry-agent-service-handson/.workshop/toolbox/travel-estimation.zip` のような
   **HOME 相対パス**を貼り付け、**Download** を押します。
   画面の説明が “fully qualified file path” でも、この prefix がある欄に絶対パスを入れると
   HOME が二重になって `Could not download, try again.` になります。
   prefix のない UI の場合だけ完全な絶対パスを使います。
   `~`、`$HOME`、`$PWD` は入力欄では展開されません。
4. **Download file** 通知に現れた **ZIP ファイル名のリンク**を選んで、PC に保存します。
   最初の **Download** だけでは取得は完了しません。file explorer の同名の項目とは区別します。
   同じ操作で `preapproval-simulation.zip` を保存し、PC に2つあることを確認します。
5. Foundry Portal の **Upload skill** で、PC に保存された該当 ZIP を選びます。
   生成 ZIP は展開・再圧縮しません。ZIP の直下に `SKILL.md` が入っています。

OpenAPI は共通 Lab の `cat .workshop/toolbox/travel-ops.openapi.json` で表示して貼り付けます。
`.workshop` 全体、Terraform state、HOME image、Jupyter runtime や認証ファイルは取得しません。
保存した Notebook なども、同じ prefix と相対パスの関係を確認して1つずつダウンロードします。

逆に PC のファイルを Cloud Shell へ入れる場合は **Manage files > Upload** で PC 側から選びます。
Upload は HOME にファイルを置く操作で、Foundry Portal の Skill 登録とは別です。
本編の公開教材取得には手順 4 の clone を使い、`.git`、`.venv`、state、認証情報の持ち込みは行いません。

<a id="resume"></a>

## 中断・再接続後に再開する

**非対話20分で終了し得る**ため、必要な区切りで Notebook を保存します。
Notebook の保存はセルと出力の保存であり、Python 変数、AgentSession、todos、memory や
実行中の Jupyter プロセスの保存ではありません。無限 keepalive で session を維持しません。
Portal 中心の Lab 2〜6 では、確認用 Notebook を保存して Jupyter を正常終了しておけます。
再開時の `Directory not found` やダウンロード失敗では、先に Cloud Shell の切断表示を確認します。
期限切れの preview タブを閉じて同じ storage に再接続し、state を確認してから再試行します。

1. Azure portal から Cloud Shell の **Bash** を開きます。
   storage の選択を求められたら、記録した**同じ subscription / account / share**を選びます。
   新しい share や HOME image に切り替えません。
2. 元の repository に移動し、有効化します。

   ```bash
   cd "$HOME/foundry-agent-service-handson"
   source scripts/activate-cloud-shell.sh
   az account set --subscription "<subscription-id>"
   az account show --query "{subscriptionId:id, user:user.name}" -o table
   ```

3. Lab 1 の構築を完了済みなら、元の `.workshop/context.json` と Terraform state が保持されていることを
   確認します。内容を公開・画面共有せず、ファイルの存在を確認します。
   なければ別の状態で setup を始めず、元の storage / HOME マウントを講師と確認してください。
   setup が途中だった場合も `.workshop/terraform-inputs.json` と元の state を保持して再開します。
4. [Jupyter 起動手順](#jupyter)の1コマンドをやり直します。新しいsessionの実preview URLは
   previewタブが自動検出します。
   同じ container に既存サーバーが残っている場合は状態を確認し、二重起動しません。
5. 保存した同じ Notebook を開き、**Python (Foundry Hosted Agent)** を選択します。
   接続・Agent / workflow 構築セルから必要なセルを順番に再実行します。
   Lab 7 の plan 確認もやり直し、古い出力があるだけで実行中の session が復元されたと判断しません。
6. 評価や remote build 待ちだった場合は、まず Portal で既存の run / version の状態を確認します。
   Azure 側の処理が継続・完了している可能性があるため、同じ評価や deploy を重複送信しません。

依存環境が正常なら bootstrap の再実行は不要です。必要な場合だけ同じ repository で
`setup-cloud-shell.sh` を再実行します。既存ファイルやユーザー設定の削除で復旧しません。

<a id="stop"></a>

## Lab 9 後に終了し、専用 storage を削除する

**順序: workload の destroy 成功 → 成果物の取得 → Jupyter 停止 →
Web preview 閉鎖 → Cloud Shell 終了 → 今回専用の新規 storage の削除。**

1. [Lab 9](../../../labs/09-observability-cleanup.md) の共通 `./scripts/destroy.sh` が成功し、
   Terraform / SDK 管理の教材 resources が残っていないことを確認します。
   **RG 自体は残します。** 失敗した場合はこの先の storage 削除へ進まず、state と `.workshop` を保全します。
2. 必要な Notebook を **Save** し、[Manage files > Download](#files) で
   安全な成果物だけを PC に取得します。PC で保存できたことも確認します。
   Terraform state、認証情報、Jupyter runtime、HOME 全体は配布・証跡に含めません。
3. JupyterLab の **File > Shut Down** でサーバーを終了します。
   または Terminal A で **Ctrl+C** を押し、shutdown の確認が出たら承認します。
   自分の Jupyter が終了して Bash のプロンプトに戻ったことを確認します。
4. Cloud Shell の **Web preview > Close port 5000** を選び、preview のタブを閉じます。
5. Terminal B と Terminal A など、**New session で開いた各 session**で `exit` を実行します。
   session は独立しているため、1つ閉じただけですべて終了したと判断しません。
6. Cloud Shellの **Settings > Reset User Settings**、または管理者が承認した解除手順で、
   今回のshareとの関連付けを外します。これによりsessionは終了しますが、Storageは削除されません。
7. Azure portalで手順2に記録した**Cloud Shellが自動作成した専用RG**を開き、
   subscription / RG / account / shareが一致し、その参加者のCloud Shell専用であることを確認します。
8. 専用RGに他用途のresourceがないことを確認して **Delete resource group** を選び、
   RG名を照合・入力して削除します。これによりStorage account、share、HOME imageも削除されます。
   **教材workload用に参加者が作成したRGは、`destroy.sh`では削除しません。**
9. 両方のRGを再読み込みし、Cloud Shell専用RGがなく、workload用RGと事前からあるresourceが
   期待どおり残っていることを確認します。

管理者割り当ての既存accountは削除しません。既存Storageの代替で今回shareだけを新規作成した場合も、
管理者と許可範囲を確認し、**Classic file shares** で記録した自分の share だけを削除します。
Soft delete / backup の保持中はデータや課金が残る場合があります。保護を無効化して消すのではなく、
管理者へ保持と終了確認を依頼してください。他ユーザーの share や以前からの HOME image は削除しません。

storage の削除は `destroy.sh` が自動で行う処理ではありません。
既存の **Cloud Shell user settings を自動リセットしない**でください。
削除した storage が次回の接続先に残る場合は、記録を確認し、
[既存接続の切替](#mount-storage)の影響を理解してから、管理者と新しい保存先を選びます。

## 公式資料

取得日: **2026-09-09**。以下は UI・制約の参照先であり、各 tenant での動作確認結果を示すものではありません。
開催前に講師が実ブラウザーで認証・セル実行・保存・Graphviz・再起動後の保持・cleanup を確認します。

- [Cloud Shell の toolbar、Manage files、New session、Web preview](https://learn.microsoft.com/azure/cloud-shell/use-the-shell-window)
- [Cloud Shell に新しい Storage を自動作成](https://learn.microsoft.com/azure/cloud-shell/get-started/new-storage)
- [既存ストレージの接続](https://learn.microsoft.com/azure/cloud-shell/get-started/existing-storage)
- [HOME disk image と Azure Files の永続化](https://learn.microsoft.com/azure/cloud-shell/persisting-shell-storage)
- [FAQ: 非対話20分、同時20ユーザー、sudo、認証 audience](https://learn.microsoft.com/azure/cloud-shell/faq-troubleshooting)
- [Storage account の作成](https://learn.microsoft.com/azure/storage/common/storage-account-create?tabs=azure-portal)
- [StorageV2 の pay-as-you-go Azure Files share の作成](https://learn.microsoft.com/azure/storage/files/create-classic-file-share?tabs=azure-portal)
- [Jupyter Server の security](https://jupyter-server.readthedocs.io/en/latest/operators/security.html)
<!-- historical-content:end -->
</details>

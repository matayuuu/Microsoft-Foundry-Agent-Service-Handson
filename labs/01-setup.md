# Lab 1 — 環境を作り、教材をダウンロードする

Azure Portal と PC のファイル操作で準備します。ローカル CLI は不要です。

## 始める前に

- [参加条件](../docs/participant/prerequisites.md)を確認します。
- 管理者からサブスクリプション、専用 RG 名、確認済みの入力値を受け取ります。
  入力値の一覧は[管理者向けガイド](../docs/admin/prerequisites.md#2-配布するテンプレートと入力値)にあります。
- 管理者指定の
  [azuredeploy.json](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/azuredeploy.json)
  を PC に保存します。Web ページではなく JSON 本体を保存してください。

テンプレートは教材 ZIP に含まれません。モデルのバージョン、イメージのハッシュ、SHA を推測して入力しません。

## 1. 専用 RG を 1 個手動作成する

1. [Azure Portal](https://portal.azure.com) でアカウントとサブスクリプションを確認します。
2. **Resource groups > Create** を開きます。
3. **Subscription** に指定のサブスクリプション、**Resource group** に自分専用の名前、
   **Region** に **Japan East** を指定します。
4. **Review + create > Create** を選択します。
5. 作成完了後、**Resource groups** で RG の名前を確認します。

**RG の作成が完了してから、次の手順へ進んでください。**

## 2. 作成済み RG にテンプレートを実行する

1. Azure Portal で **Deploy a custom template** を検索して開きます。
2. **Build your own template in the editor > Load file** を選びます。
3. 保存した `azuredeploy.json` を読み込み、**Save** を選びます。
4. **Subscription** と **Resource group** に、手順 1 の作成済み RG を選びます。
   **Create new** は使いません。
5. 管理者から受け取った入力値を設定し、**Review + create > Create** を選びます。

## 3. 初期化の成功を待つ

1. RG の **Deployments** で、**Deployment Scripts による初期化を含む全体**が
   **Succeeded** になるまで待ちます。
2. **Outputs** の `participantDownload` を開き、`status = complete` を確認します。
   リソースが作られただけでは準備完了ではありません。

失敗した場合は次へ進まず、[トラブルシューティング](../docs/participant/troubleshooting.md)を確認します。
実行中の処理を重複送信したり、別のリージョン・モデルへ変更したりしません。

## 4. 非公開の教材 ZIP を取得する

1. 同じ `participantDownload` の `storage_account_name` にあるストレージアカウントを開きます。
2. **Storage browser > Blob containers > workshop-files** を開きます。
3. 認証方式を **Microsoft Entra user account** にします。
   必要なら **Switch to Microsoft Entra user account** を選びます。
4. 非公開コンテナーの `foundry-workshop-files.zip` を選び、**Download** で PC に **1 回だけ**取得します。

公開リンク、SAS、アカウントキーは使いません。教材 ZIP に認証情報は含まれません。

## 5. PC で展開して、次の Lab へ進む

ZIP を展開し、最上位の `Microsoft-Foundry-Agent-Service-Handson` フォルダーを開きます。
次のファイル・フォルダーがあることを確認し、構成を変えずに保存してください。

| 場所 | 用途 |
|---|---|
| `.workshop/context.json` | 接続先の設定。`resource_outputs.<key>.value` を参照 |
| `portal-assets/` | Lab 4 で使う OpenAPI 定義と Skill の ZIP |
| `notebooks/` | Labs 7〜8 のノートブック |
| `src/`、`scripts/`、`tests/` | ノートブックが使うコードとテスト |

`.workshop` は隠しフォルダーです。見えない場合は PC の隠しファイル表示を有効にします。
Labs 2〜6 は Microsoft Foundry Portal で進めます。
**Azure ML Compute はまだ作りません。Lab 7 の開始時に準備します。**

> [!NOTE]
> 教材の合成データだけを使い、作成・削除の対象は自分の専用 RG に限定してください。

## 次の Lab

[Lab 2 — Prompt Agent](02-prompt-agent.md)

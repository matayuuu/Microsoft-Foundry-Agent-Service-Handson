# 管理者向け前提条件

ハンズオン前に Azure 環境を準備する **サブスクリプション管理者向け**の手順です。
参加者はこのページの操作を行わず、[参加者向け前提条件](../participant/prerequisites.md)を確認してください。
この開催モデルでは、個人検証または受講者が専用のworkload用RGとCloud Shell用RG /
Storage accountを作成できるサブスクリプションレベルの権限を明示的な前提とします。
最も単純なのは、受講者ごとのsandbox subscriptionにOwnerを付与する方法です。
共有subscriptionのOwnerは他参加者のRGにもアクセスできるため、管理者がリスクと棚卸しを管理します。

## 管理者による事前準備が必要な理由

リソースプロバイダーの登録、リージョンごとのモデルのクォータ・容量確認、
Azure Policy の確認には、サブスクリプション全体に対する権限が必要です。
既存リソースグループの **Owner** ロールだけでは実施できません。

管理者は `scripts/admin-preflight.sh` で事前確認を行います。既定では確認結果の報告だけを行い、
設定は変更しません。これにより、参加者が実行する `scripts/preflight.sh` と
`scripts/setup.sh` にサブスクリプション全体の権限を持たせずに済みます。

## 実行環境の選択と Cloud Shell の開催条件

Codespaces の既存経路は維持します。Codespaces を使えない参加者は
[Azure Cloud Shell Bash + JupyterLab](../participant/environments/cloud-shell.md) を選べます。
選択は環境準備時だけで、Lab 2〜9 と Lab 7 / 8 の Notebook は共通です。
Cloud Shell の計算環境は無料ですが、永続ストレージと教材の Azure workloads は課金対象です。

> [!IMPORTANT]
> **Azure Cloud Shell は tenant あたり既定20同時ユーザーです。**
> 講師・補助員や同じ tenant の他用途の利用も含め、超える可能性がある場合は開催前に
> Azure Support へ training の日時・人数を示して引き上げを相談してください。
> モデルの `--participant-count` の確認や RG の追加では、この制限は増えません。
> 40名なら最大40個のCloud Shell専用RG / Storageが自動作成され得ます。
> 講師・補助員・同じtenantの他用途を含めた同時利用枠と、終了後の専用RG棚卸しを準備してください。

Cloud Shell 採用時は、通常の5 provider・モデル確認に加えて、以下を管理者が確認します。

| 確認項目 | 管理者が行うこと |
|---|---|
| Resource providers | Azure portal の **Subscriptions > 対象 subscription > Resource providers** で `Microsoft.CloudShell` と `Microsoft.Storage` を確認する。未登録なら権限を持つ管理者だけが **Register** し、`Registered` を確認する |
| RG / Storage作成の権限 | 各参加者が教材workload用RGを作成してそのRGのOwnerになり、Cloud Shell専用RG / Storageも作成できることを確認する。受講者ごとのsandbox subscription Owner、またはRG作成・role assignment・Storage作成を含む同等の権限を使う |
| 標準の作成経路 | 初回画面で **Mount storage account > We will create a storage account for you** を選ぶ。自動生成された専用 RG / account / share を参加者ごとに記録し、Terraform の管理対象と混同しない |
| 既存 Storage の代替 | 新規 RG 作成を許可しない組織だけ、各参加者へ既存 RG 内の StorageV2 / Standard / LRS と Azure Files SMB share を割り当てる。手動作成時は **Primary service: Other (tables and queues)** と **View automation template > Parameters** の `kind=StorageV2` / `accountType=Standard_LRS` を確認する |
| Storage の region | 自動作成は Cloud Shell に選択させる。既存 Storage の代替では、対応済み Cloud Shell location と一致させる。既存利用者の `preferredLocation` と元の接続を保全する |
| Storage の利用者分離 | ユーザーごとに自動生成された専用 RG / Storage、または管理者割り当ての専用 Storage / share を使う。他人の share や HOME image は再利用させない |
| Storage の policy | 標準 Cloud Shell の永続マウントに必要な共有キーアクセスとネットワーク接続が許可されることを確認する。拒否時に参加者へ policy、firewall、共有キー制限の無効化を指示しない |
| 手動作成時の追加 resource の抑止 | 既存 Storage の代替経路だけ、**Classic file shares > New classic file share** の任意 backup と、新規 Vault / policy の作成有無を確認する。自動作成では Cloud Shell が作った構成を記録し、勝手に変更しない |
| データ保護 | HOME image には Terraform state、Azure CLI の認証キャッシュ、Jupyter の認証設定が含まれ得る。教材データが合成でも storage 全体は機密として扱う |
| 永続化 | HOME の永続マウントと実際の **Restart** 後のファイル保持をリハーサルで確認する。`New session` は同じ container を共有するため、永続化の検証にはならない |
| 既存接続の復旧 | 古い share のマウント失敗後に ephemeral session になっていないか確認する。元の `preferredLocation` と storage / 個人設定を保全して明示的に再設定する。割り当て RG 外の古い storage も無断で削除しない |
| 実行時間・容量 | 非対話20分で終了する制約、HOME / share の空き容量、Python 3.13 と2つの kernel、Graphviz の SVG 描画を実ブラウザーで確認する |

### Jupyter を Cloud Shell に追加すると増える環境構築

Storage の自動作成で省略できるのは、RG / Storage account / Azure Files share の手動作成だけです。
Notebook を Cloud Shell で動かすため、次の準備は引き続き必要です。

| 追加要素 | この教材での構築 |
|---|---|
| Python 3.13 | Cloud Shell の system Python と分離した公式 standalone CPython を HOME に準備 |
| 2つの依存環境 | root の `azure-ai-projects==2.5.0` と Hosted Agent の `<2.4` を別 `.venv` に配置 |
| Notebook runtime | JupyterLab / Jupyter Server / `ipykernel` と2つの kernelspec をユーザー領域に登録 |
| Graphviz | Lab 8 の実 SVG 用に micromamba / conda-forge の native `dot` をユーザー領域に準備 |
| Browser 接続 | Web preview の実 URL を確認し、port 5000、専用パスワード、token、Origin / Host / XSRF 制限を設定 |
| Relay 互換 | Cloud Shell relay の prefix / status / redirect / cookie / browser WebSocket の差を吸収する専用アダプターを起動 |
| 運用 | Jupyter用と通常コマンド用の2 Terminal、切断後の再起動、Notebook保存とkernelメモリーの区別 |

主な懸念は、非対話20分でJupyterプロセスとkernelメモリーが失われること、Web preview と
Relay の挙動変更に追随する保守、追加のHTTPS / WSS / package配布先、HOME image内のtokenや
Terraform stateの保護、初回3GiB程度の空き容量、40名分の個別Storageと同時接続上限です。
Cloud Shell は汎用計算基盤ではないため、開催前の実ブラウザーE2Eを必須とし、
認証・XSRF・Origin制限を弱めて問題を回避しません。

`admin-preflight.sh` の既定は引き続き**読み取り専用**です。この Cloud Shell 固有の
Portal・通信・ストレージ確認を、通常のモデル preflight の成功だけで代用しません。
参加者用 bootstrap / setup から provider 登録、quota 変更、subscription scope の書き込みは行いません。

### 企業ネットワークの事前確認

Codespaces 禁止と GitHub への通信禁止は別です。Cloud Shell も、教材・パッケージの取得と
Jupyter のブラウザー接続に以下の通信が必要です。組織の許可リストとプロキシ条件を確認し、
禁止されている場合は迂回せず、承認された対応を管理者と決めます。

| 通信元 | 必要な接続先・用途 |
|---|---|
| 参加者のブラウザー | Azure portal / Microsoft Entra サインイン / Foundry Portal。Cloud Shell Terminal の `*.console.azure.com`、`*.servicebus.windows.net` への HTTPS / WSS。Jupyter の専用 launcher は、実際の Web preview URL への認証付き HTTPS polling を Cloud Shell 内の kernel WebSocket へ中継する |
| Cloud Shell | 講師指定の公開 GitHub repository、`github.com` と GitHub の release 配布先（`release-assets.githubusercontent.com` など）、PyPI（`pypi.org`、`files.pythonhosted.org`） |
| Cloud Shell のツール準備 | uv も利用する standalone CPython と micromamba の公式 GitHub releases、conda-forge（`conda.anaconda.org`）。必要なリダイレクト先も確認する |
| Cloud Shell の共通セットアップ | Terraform registry / provider 配布先（`registry.terraform.io`、`releases.hashicorp.com` など）、公開 GHCR（`ghcr.io` と配布先） |
| Azure 操作 | `management.azure.com` と、この環境の Foundry / Search / Container Apps / telemetry / source remote build の各 endpoint。Cloud Shell サービスから選択した Azure Files へのマウント |

GitHub account は公開 repository の clone には不要です。参加者へ GitHub token や Storage key の
貼り付けを求めません。Cloud Shell で未対応の token audience が出た場合は公式手順の
`az login --use-device-code` を使いますが、Conditional Access などで拒否される場合は管理者へ戻します。
`sudo`、Docker daemon、Jupyter の認証無効化、ワイルドカードの Origin 許可は解決策にしません。

公式資料（取得日: 2026-09-09）:
[Cloud Shell FAQ](https://learn.microsoft.com/azure/cloud-shell/faq-troubleshooting) /
[新しいStorageの自動作成](https://learn.microsoft.com/azure/cloud-shell/get-started/new-storage) /
[永続ストレージ](https://learn.microsoft.com/azure/cloud-shell/persisting-shell-storage) /
[shell window と Web preview](https://learn.microsoft.com/azure/cloud-shell/use-the-shell-window)

## 必要なもの

- Azure CLI（`az`）でサインイン済みのアカウント（`az login`）。読み取り専用の確認には、
  サブスクリプション全体に対する **Reader** 以上の権限が必要です。
- モデルのクォータ引き上げを申請する場合は、対象サブスクリプションに対する
  **Quota Request Operator**、**Contributor**、または **Owner** など、クォータ要求を
  作成できる権限が必要です。
- Azure AI Search のサービス数上限の緩和を申請する場合も、対象サブスクリプションに対する
  **Quota Request Operator**、**Contributor**、または **Owner** など、クォータ要求を
  作成できる権限が必要です。組織でクォータ要求の作成者を制限している場合は、
  サブスクリプション管理者へ依頼してください。
- 未登録のリソースプロバイダーも登録する場合（`--apply`）は、
  サブスクリプション全体に対して `Microsoft.Support/register/action` などの
  プロバイダー登録操作を実行できる権限が必要です。**Contributor** ロールや
  **Azure Resource Manager Provider Registration** の権限が例に挙げられます。
  教材では特定のロール名の付与や保有を前提としないため、テナントの運用ルールを確認してください。
- `management.azure.com` へのネットワーク接続。
- 対象リージョンの確認。推奨順は `japaneast`、`australiaeast`、`centralus` です。
  3つとも Agentic retrieval、Semantic ranker、Serverless preview を提供し、
  2026-09-09 取得の公式リージョン表で高需要の作成制限が付いていません。
  East US 2 は高需要により新規 Search service 作成不可と明記されているため推奨しません。

## 事前確認スクリプトの実行

リポジトリの最上位フォルダーで実行します。

```bash
./scripts/admin-preflight.sh --subscription "<subscription-id>" [--location japaneast]
```

既定では **読み取り専用**です。リソースグループの作成・削除、クォータや Azure Policy の変更、
ロールの割り当ては行いません。開催前に3つの推奨リージョンを確認します。

### リソースプロバイダーの登録状態

教材で使う5つのプロバイダーを確認します。

| プロバイダー | 用途 |
| --- | --- |
| `Microsoft.CognitiveServices` | Foundry / Azure AI Services アカウント |
| `Microsoft.Search` | Azure AI Search |
| `Microsoft.Insights` | Application Insights |
| `Microsoft.OperationalInsights` | Log Analytics |
| `Microsoft.App` | Travel Ops API 用の Container Apps |

### Azure AI Search のサービス数クォータ

`Microsoft.Search/locations/usages` から、指定リージョンと代替リージョンの **Basic SKU の
サービス数**について、現在値、上限、空きを取得します。1環境につき1つの Search serviceを
作るため、空きが `--participant-count` 以上かを判定します。

```text
空きサービス数 = 上限 - 現在値
```

取得できない場合、Basicの項目がない場合、または空きが不足する場合は `warn` として報告します。
このクォータはサブスクリプションで作成できるサービス数の上限です。**リージョン内のリアルタイムな
物理容量は表さないため、判定が `pass` でも `ResourcesForSkuUnavailable` が発生する場合があります。**
その場合は[管理者向けトラブルシューティング](troubleshooting.md#azure-ai-search-で-insufficientresourcesavailable-が発生する)に従って、
代替リージョンを使用してください。

Dedicated Basic が3リージョンとも作成できない場合は、Serverless Developer preview を
`setup.sh --ai-search-serverless` で使用できます。Serverless は Basic のサービス数クォータではなく
従量課金の Compute Units と indexed storage で課金され、preview 中は SLA がありません。
公式情報の取得日: **2026-09-09**。

### モデルのクォータ・容量

Terraform が要求する SKU と使用量の区分に対して、**同時に利用する全参加者・チーム分の空き容量**
があるか確認します。対象は次の3つのデプロイで、SKU はすべて `GlobalStandard` です。
TPM は1分あたりのトークン数を表します。

| モデル | デプロイ名 | 1環境あたりの必要な空き容量 | 用途 |
| --- | --- | --- | --- |
| `gpt-5.6-luna` | `gpt-5.6-luna` | **40K TPM** | Prompt / Hosted Agent、Foundry IQ（`primary_model_deployment_name`） |
| `gpt-5.5` | `gpt-5.5` | **100K TPM** | Lab 5 の設定可能な評価と Lab 6 の Agent Optimizer（`evaluation_model_deployment_name` / `optimizer_model_deployment_name`、クォータ不足時は省略可） |
| `text-embedding-3-small` | `embedding` | **40K TPM** | ベクトルインデックス用の埋め込み |

2つのチャットモデル名は教材の固定要件です。**バージョンはカタログから取得**し、推測や別のモデル系列への切り替えは行いません。
Luna は必須で、GPT-5.5 は有効化する場合だけバージョンを Terraform に渡します。

スクリプトはモデル・リージョンごとに `model.skus[].usageName` を取得し、
`az cognitiveservices usage list --location <region>` の同じ使用量区分と照合します。
`usageName` の表記はモデル系列によって異なるため（例：`...gpt4.1` と `...gpt-5`）、
モデル名から推測・組み立てはしません。バージョンと `usageName` は、
必要な SKU に対応する **同じカタログ項目**から取得する必要があります。

Markdown / JSON のレポートには、モデル・リージョンごとに以下の判定根拠が表示されます。

- 取得したモデルのバージョン、必要な SKU、`usageName`
- 1環境あたりの容量と、`--participant-count` を掛けた全環境分の必要容量
- 判定に使った空き容量・上限・現在の使用量

必要な SKU や `usageName` が見つからない場合、または使用量の取得に失敗した場合は、
**確認不能・失敗（`warn`）**として報告します。未確認の容量を十分とみなすことはありません。
参加者向けの `scripts/preflight.sh` も同じ根拠で判定しますが、
Luna または埋め込みの空き容量が不明・不足の場合は **エラーで停止**します。
GPT-5.5 だけが不明・不足の場合は `warn` とし、setup はそのデプロイを省略します。

### Azure Policy とリソースグループ

Azure Policy によって教材のリソースがブロックされないか、可能な範囲で確認します。
ただし、事前確認スクリプトだけではすべてのポリシー評価を網羅できません。
拒否が報告されなくても、作成できる保証にはなりません。
詳細は[トラブルシューティング](troubleshooting.md)を参照してください。

リソースグループの存在と参加者の **Owner** ロールは、
参加者向けの `scripts/preflight.sh --resource-group <name>` で確認します。
管理者はレポートを配布する前に、各リソースグループの作成・割り当てを済ませてください。
`admin-preflight.sh` はサブスクリプション全体を対象とするため、`--resource-group` オプションはありません。

### レポートの出力

既定の出力形式は JSON です。読みやすい形式にするには `--format markdown`、
標準出力ではなくファイルに保存するには `--output <file>` を指定します。

## 複数の参加者・チーム分のクォータを確認する

参加者・チームごとに専用のリソースグループとモデルをデプロイしますが、
同じリージョンの環境は **サブスクリプション共通のクォータ**を使います。
`--participant-count <n>`（既定値 `1`）で、同時に使う環境数を指定してください。

```bash
./scripts/admin-preflight.sh --subscription "<subscription-id>" --participant-count 12
```

各モデルの1環境あたりの必要容量に `<n>` を掛けて確認します。
たとえば12環境では、`gpt-5.6-luna` は **40K × 12 = 480K TPM**、
`gpt-5.5` は **100K × 12 = 1,200K TPM** が必要です。
レポートには環境数に加え、モデル・リージョンごとの計算式と取得した空き容量を表示します。
`--participant-count` は正の整数で指定してください。不正な値の場合は Azure を呼び出す前に終了コード `1` で停止します。

## クォータが不足した場合の上限緩和申請

申請は無料ですが、承認後に作成・利用したリソースには料金が発生します。自動承認されない場合もあるため、
開催日の数営業日前ではなく、十分な余裕を持って申請してください。申請後は
`admin-preflight.sh` を同じ `--participant-count` で再実行して反映を確認します。

### コマンドで申請内容を準備する

`request-quota-increase.sh` は、対象リージョンの現在値から、モデルTPMとAzure AI Search Basicの
**変更後の最低合計上限**を計算します。既定では読み取り専用で、Azureの設定やクォータを変更しません。

```bash
./scripts/request-quota-increase.sh \
  --subscription "<subscription-id>" \
  --location japaneast \
  --participant-count 30
```

結果には、3モデルの `usageName`、現在の使用量と上限、全環境分の必要量、申請する最低合計上限、
Search Basicの現在数と申請上限がJSONで表示されます。

スクリプトは申請を送信しません。表示されたJSONの値を確認し、モデルTPMは公式フォーム、
Searchサービス数はAzure portalのQuotasから上限緩和を申請してください。

必要な最低合計上限は次の式で求めます。

```text
モデル: 現在の使用量 + 1環境あたりの必要TPM × 同時環境数
Search: 現在のサービス数 + 同時環境数
```


### モデルの TPM クォータ

[Azure OpenAI クォータ増加申請フォーム](https://aka.ms/oai/stuquotarequest)から申請します。
申請は受付順に処理され、既存クォータを継続的に使用している申請が優先されます。
承認後もクォータ層は変わらず、割り当てられるクォータだけが増加します。詳細は
[クォータ増加の要求](https://learn.microsoft.com/ja-jp/azure/foundry/openai/quotas-limits?tabs=bash%2Ctier1#request-quota-increases)を参照してください。

<details>
<summary>モデルTPMの申請内容</summary>

1. フォームで対象サブスクリプション、リージョン、モデル、`GlobalStandard` SKUを指定します。
2. レポートの `usageName` と同じモデル区分であることを確認します。
3. 現在の使用量と全環境分の必要容量を足し、運用上の余裕を加えた**変更後の合計上限**を入力します。
4. 参加者数、1環境あたりのTPM、同時開催であること、開催日、対象リージョンを申請理由に記載します。

</details>

### Azure AI Search Basic のサービス数上限

Azure portalの[Quotas](https://portal.azure.com/#blade/Microsoft_Azure_Capacity/QuotaMenuBlade/myQuotas)から申請します。

<details>
<summary>Search Basicサービス数の申請手順</summary>

1. 対象サブスクリプションを選択し、Providerで **Search** を選択します。
2. 対象Regionで **B - Basic** の行を選択し、鉛筆アイコンの **Request adjustment** を選択します。
3. **New limit** に、レポートの `minimum_requested_total_limit` 以上の変更後合計上限を入力します。
4. **Submit** を選択し、申請状態を確認します。

</details>

Searchの上限緩和はリージョン内の物理容量を予約する申請ではありません。上限緩和後も
`ResourcesForSkuUnavailable` が発生した場合は、時間を置くか代替リージョンを使用します。
サービス上限については
[Azure AI Search のサービス制限](https://learn.microsoft.com/azure/search/search-limits-quotas-capacity)、
申請画面については
[Azure Quotasの概要](https://learn.microsoft.com/azure/quotas/quotas-overview)を参照してください。

### 容量配分と料金の注意

1環境のデプロイは最大3つです。同じデプロイを Lab ごとに重複して数えないでください。
Luna は Prompt / Hosted Agent と Foundry IQ で共有します。GPT-5.5 は Lab 5 の
評価と Lab 6 の Agent Optimizer で共有します。
評価では評価対象の Luna エージェントも呼び出します。

既定の容量単位は Luna / GPT-5.5 / 埋め込みの順に **40 / 100 / 40** です。
開催前に同時実行のリハーサルと最新のクォータ確認を行ってください。
GPT-5.5 は評価と最適化で共有するため、既定値を100にしています。
2026-09-09 の Serverless E2E では Luna 20K で7件の Portal 評価を実行した際、
Foundry IQ の並列呼び出し2件が HTTP 429 になったため、Luna は40Kを維持します。
40Kでも7件の自動評価で十分とは限りません。2026-09-10 の Dedicated E2E では
Optimizer 内の IQ 呼び出しが429になり、既存クォータ内で一時的に400Kを割り当てました。
既定値は変更せず、開催時の並列数と実測 `rateLimits` から別途判断してください。
Optimizer は Max candidates = 1、評価データは7件に限定してトークン消費を抑えます。
詳細は[実行時の事象と追加の確認事項](troubleshooting.md#クォータに余裕があるのに-http-429-や-foundry-iq-のタイムアウトが発生する)を参照してください。

`GlobalStandard` の容量は、既存のサブスクリプションのモデル・SKU 別クォータから
デプロイの処理量を割り当てるものです。**クォータ上限の引き上げ、定額のトークン利用枠の購入、
プロビジョニング済みスループットの予約ではありません。**
料金は実際の使用量に応じて発生し、処理量を増やすと課金対象の呼び出しも増える可能性があります。
100単位でも HTTP 429 が発生しない保証はありません。デプロイ後の `rateLimits` を確認し、
Agent / IQ の Luna 負荷と、Labs 5 / 6 の GPT-5.5 負荷を分けてリハーサルしてください。

Terraform の容量変数は変更できますが、両方の事前確認スクリプトは既定の **40 / 100 / 40** を確認します。
変更する場合は、スクリプトの確認対象容量と Terraform の入力値をそろえて再確認してください。

### Portal でのモデル選択

Foundry IQ では Luna、Lab 5 の judge と Lab 6 の Evaluation / Optimization model では
GPT-5.5 を選択します。GPT-5.5 は2026-09-09時点の公式の最適化モデル対応一覧に含まれます。
開催前に公式一覧と各選択欄の両方を確認してください。
カタログ・クォータ上の利用可否や [Search API の対応状況](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
だけでは、Portal で利用できることの裏付けにはなりません。
Foundry IQ で Luna を選択できない場合は、デプロイ済み・API対応済みであることを確認し、
[Lab 3 の限定的な picker 回復手順](../../labs/03-rag-foundry-iq.md)を使います。
別モデルへの切替や重複デプロイはしません。GPT-5.5 だけを
選択できない場合は Labs 5 / 6 をスキップし、追加デプロイや別モデルへの
無断切り替えは行わないでください。

## 未登録のリソースプロバイダーを登録する

対象プロバイダーに `NotRegistered` がある場合は、明示的に登録します。

```bash
./scripts/admin-preflight.sh --subscription "<subscription-id>" --apply
```

`--apply` が変更するのは、未登録と判定されたプロバイダーへの `az provider register` の実行だけです。
クォータ、ポリシー、リソースグループ、ロール割り当ては変更しません。
登録後は `--apply` なしで再実行し、すべての確認が通ることを確かめてください。

## Travel Ops API のイメージを公開する

参加者がセットアップを始める前に、リポジトリのメンテナーが
ダイジェストで固定して利用できる Travel Ops API イメージを公開します。

1. `travel-api-v*` に一致するタグをプッシュするか、**Publish Travel Ops API** を手動実行します。参加者向けの既定のタグは `travel-api-v1.0.3` です。
2. GitHub で作成された `travel-ops-api` パッケージの設定を開き、公開範囲を **Public** にします。非公開リポジトリから作成したパッケージは既定で非公開です。この設定をワークフロートークンで変更する REST 操作は GitHub でサポートされていません。
3. リハーサル用の RG で参加者向けセットアップを一度実行します。Terraform の開始前に、匿名の OCI 参照でタグから不変の `sha256:` ダイジェストを取得できることを確認してください。

組織のルールで GHCR パッケージを公開できない場合は、承認済みの公開レジストリに同じイメージを公開し、
`--travel-api-image-ref` で不変のダイジェストを指定してください。

## 参加者への引き継ぎ

想定する環境数を `--participant-count` に指定し、`--apply` なしで `admin-preflight.sh` を実行します。
必要なプロバイダーがすべて `Registered` であり、`japaneast` / `australiaeast` / `centralus` の少なくとも一方に
全環境分のモデルのクォータ・容量があることを確認してください。

その後、教材workload用RGの命名規則とlocationを参加者へ伝えます。
参加者は[参加者向け前提条件](../participant/prerequisites.md)の冒頭でRGを作成し、
空のRGと自分のOwnerを確認します。このリポジトリの指定ブランチも共有してください。
Cloud Shell 利用者には、選択する Cloud Shell location と一致する storage 用 region、
専用 account / share の作成可否、通信の確認結果も伝えます。
既存ストレージを割り当てる場合は、そのユーザー専用であることと、終了時の削除可否を明記します。

参加者は`scripts/preflight.sh`と`scripts/setup.sh`を実行します。
両スクリプトは参加者が事前作成したworkload用RGの範囲内で動作し、RGやroleを
subscription scopeへ自動作成しません。

## 関連資料

- [管理者向けトラブルシューティング](troubleshooting.md)
- [料金とクリーンアップ](../costs-and-cleanup.md)
- [アーキテクチャ](../architecture.md)

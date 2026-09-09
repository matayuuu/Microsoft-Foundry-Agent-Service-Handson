# 管理者向け前提条件

ハンズオン前に Azure 環境を準備する **サブスクリプション管理者向け**の手順です。
参加者はこのページの操作を行わず、[参加者向け前提条件](../participant/prerequisites.md)を確認してください。
参加者にサブスクリプション全体の権限は不要です。

## 管理者による事前準備が必要な理由

リソースプロバイダーの登録、リージョンごとのモデルのクォータ・容量確認、
Azure Policy の確認には、サブスクリプション全体に対する権限が必要です。
既存リソースグループの **Owner** ロールだけでは実施できません。

管理者は `scripts/admin-preflight.sh` で事前確認を行います。既定では確認結果の報告だけを行い、
設定は変更しません。これにより、参加者が実行する `scripts/preflight.sh` と
`scripts/setup.sh` にサブスクリプション全体の権限を持たせずに済みます。

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
- 対象リージョンの確認。既定は `eastus2`、代替は `swedencentral` です。
  参加者が切り替える際に管理者の再確認が不要になるよう、常に両方を確認します。

## 事前確認スクリプトの実行

リポジトリの最上位フォルダーで実行します。

```bash
./scripts/admin-preflight.sh --subscription "<subscription-id>" [--location eastus2]
```

既定では **読み取り専用**です。リソースグループの作成・削除、クォータや Azure Policy の変更、
ロールの割り当ては行いません。`eastus2` と `swedencentral` を対象に、以下を報告します。

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

`Microsoft.Search/locations/usages` から、`eastus2` と `swedencentral` の **Basic SKU の
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

### モデルのクォータ・容量

Terraform が要求する SKU と使用量の区分に対して、**同時に利用する全参加者・チーム分の空き容量**
があるか確認します。対象は次の3つのデプロイで、SKU はすべて `GlobalStandard` です。
TPM は1分あたりのトークン数を表します。

| モデル | デプロイ名 | 1環境あたりの必要な空き容量 | 用途 |
| --- | --- | --- | --- |
| `gpt-5.6-luna` | `gpt-5.6-luna` | **40K TPM** | Prompt / Hosted Agent の推論（`primary_model_deployment_name`） |
| `gpt-5.5` | `gpt-5.5` | **100K TPM** | Foundry IQ のクエリ計画、設定可能な LLM 評価用モデル、Agent Optimizer（`optimizer_model_deployment_name`） |
| `text-embedding-3-small` | `embedding` | **40K TPM** | ベクトルインデックス用の埋め込み |

2つのチャットモデル名は教材の固定要件です。**バージョンはカタログから取得**し、推測や別のモデル系列への切り替えは行いません。
Terraform にもチャットモデルのバージョンの既定値はありません。

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
空き容量が不明・不足の場合は、警告ではなく **エラーで停止**します。

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
  --location eastus2 \
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

1環境のデプロイは3つだけです。同じデプロイを Lab ごとに重複して数えないでください。
Luna は Prompt / Hosted Agent、GPT-5.5 は Foundry IQ のクエリ計画・評価・最適化で共有します。
評価では評価対象の Luna エージェントも呼び出します。

既定の容量単位は Luna / GPT-5.5 / 埋め込みの順に **40 / 100 / 40** です。
開催前に同時実行のリハーサルと最新のクォータ確認を行ってください。
GPT-5.5 は20単位で7行の Portal 評価を実行した際にスロットリングが発生したため、既定値を増やしています。
Lunaと埋め込みは10単位でも個別操作や初期データ投入が完了する可能性はありますが、
本ハンズオン全体を同時実行した検証結果がないため、既定値は40のままです。
詳細は[実行時の事象と追加の確認事項](troubleshooting.md#クォータに余裕があるのに-http-429-や-foundry-iq-のタイムアウトが発生する)を参照してください。

`GlobalStandard` の容量は、既存のサブスクリプションのモデル・SKU 別クォータから
デプロイの処理量を割り当てるものです。**クォータ上限の引き上げ、定額のトークン利用枠の購入、
プロビジョニング済みスループットの予約ではありません。**
料金は実際の使用量に応じて発生し、処理量を増やすと課金対象の呼び出しも増える可能性があります。
100単位でも HTTP 429 が発生しない保証はありません。デプロイ後の `rateLimits` を確認し、
クエリ計画・評価・最適化を組み合わせた負荷でリハーサルしてください。

Terraform の容量変数は変更できますが、両方の事前確認スクリプトは既定の **40 / 100 / 40** を確認します。
変更する場合は、スクリプトの確認対象容量と Terraform の入力値をそろえて再確認してください。

### Portal でのモデル選択

2026-09-06 の確認では、新しい Portal のナレッジベースの **Chat completions** モデル選択欄に
GPT-5.5 は表示されましたが、Luna は検索の労力を **Medium** にしても表示されませんでした。
一方、エージェントのモデル選択欄では Luna を選択できました。

この役割分担を維持し、開催前に両方の選択欄を確認してください。
カタログ・クォータ上の利用可否や [Search API の対応状況](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
だけでは、Portal で利用できることの裏付けにはなりません。
選択できない場合は作業を止めて原因を調べ、4つ目のデプロイの追加、
プロバイダー・クォータの自動変更、別モデルへの無断切り替えは行わないでください。

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
必要なプロバイダーがすべて `Registered` であり、`eastus2` / `swedencentral` の少なくとも一方に
全環境分のモデルのクォータ・容量があることを確認してください。

その後、参加者・チームごとにリソースグループを作成するか既存のものを割り当て、
**その RG だけに Owner ロールを付与**します。このリポジトリと
[README のクイックスタート](../../README.md#quick-start)を共有してください。

参加者は `scripts/preflight.sh` と `scripts/setup.sh` を実行します。
両スクリプトは割り当てられたリソースグループの範囲内で動作し、このページに記載した管理者権限は必要ありません。

## 関連資料

- [管理者向けトラブルシューティング](troubleshooting.md)
- [料金とクリーンアップ](../costs-and-cleanup.md)
- [アーキテクチャ](../architecture.md)

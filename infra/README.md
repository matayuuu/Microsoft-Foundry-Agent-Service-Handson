# Azure Portal テンプレートの実装

[開発者向けガイド](../docs/development/README.md) / [ハンズオンの構成](../docs/development/architecture.md)

`main.bicep` がインフラ定義の正本です。`azuredeploy.json` はコンパイルして生成した
Portal 用 ARM テンプレートであり、別の実装として管理しません。
Portal での環境作成にはローカルの CLI は不要です。Labs 7〜8 は共通 Dev Container で実行します。

## デプロイの対象と操作

1. Azure Portal の **Resource groups > Create** で、演習終了後に削除する専用リソースグループ（RG）を 1 個作成します。
2. **Deploy a custom template > Build your own template in the editor > Load file** を開き、
   `azuredeploy.json` を読み込みます。
3. **Subscription** と作成済みの **Resource group** を選び、他のパラメーターは
   参加者 ID の空の上書き値を含め、リリース既定値を維持します。ここでは **Create new** を使いません。
4. **Review + create > Create** で開始し、`ds-fdyws-bootstrap-*` の Deployment Script を含む
   デプロイ全体の成功を待ちます。
5. `workshopContext.setup_status = complete` を確認します。教材は GitHub の共通ファイルを使います。
   環境別のダウンロードや参加者向け Blob コンテナーはありません。

ルートの `targetScope = 'resourceGroup'` は `resourceGroup()` を読み取ります。
RG やサブスクリプションスコープのデプロイ・ロール割り当ては作成しません。
リソース名は RG の ID と `japaneast` から決まり、デプロイ名、ソースコミット、実行時刻、
実行 ID には依存しません。ロール割り当ての GUID も同じ入力から同じ値を生成します。
新しい専用 RG 向けの構成であり、既存リソースやローカル状態の自動移行は行いません。

<a id="template-parameters"></a>

## テンプレートのパラメーター

9 個すべてのパラメーターに `main.bicep` でリリース既定値を設定し、`azuredeploy.json` に反映します。
本人がデプロイする参加者は **Subscription** と既存 **Resource group** だけを選びます。
モデルバージョン、イメージのダイジェスト、ソースの SHA、自分のオブジェクト ID の調査は不要です。

`azuredeploy.parameters.example.json` は、仮の値やアカウント固有値を含めず既定値を反映します。
管理者向けの任意の参考ファイルであり、参加者が追加で読み込むファイルではありません。

| パラメーター | 既定値と上書き条件 |
|---|---|
| `location` | `japaneast` だけを許可し、既定値も `japaneast`。RG 自体のメタデータ上の場所では上書きされません。 |
| `primaryModelVersion` | Japan East / GlobalStandard の `gpt-5.6-luna` に対して `2026-07-09`。 |
| `evaluationModelVersion` | Japan East / GlobalStandard の `gpt-5.5` に対して `2026-04-24`。 |
| `embeddingModelVersion` | Japan East / GlobalStandard の `text-embedding-3-small` に対して `1`。 |
| `travelApiImageRef` | `ghcr.io/matayuuu/travel-ops-api@sha256:173f7e954cd284057bf2a2fe10d53efae83547a060ec2ac23172dd5458816dcf`。上書きは公開 GHCR のダイジェスト参照に限定し、タグ、非公開レジストリの秘密情報、代替イメージは使いません。 |
| `sourceRevision` | `05bd80776c0091ae03d8cfae9312a14b0db00b5f`。上書きは `matayuuu/Microsoft-Foundry-Agent-Service-Handson` で公開済みの小文字 40 桁のコミット SHA に限定し、ブランチ名や別リポジトリは使いません。 |
| `participantObjectIdOverride` | 既定値は空で、ルートの `deployer().objectId` を参加者とします。管理者・自動処理によるデプロイや再デプロイでは、対象参加者の Entra **User** オブジェクト ID を指定します。 |
| `bootstrapRunId` | 既定値は `1`。通常の再デプロイでは維持し、初期化を意図的に再実行する場合に変更します。 |
| `enableBootstrapPolicyExclusion` | 既定値は `true`。組織が `SecurityControl=Ignore` の利用を承認したハンズオン環境向けです。除外を利用しない環境では `false` にします。タグの追加先は初期化用 Deployment Script に限定します。 |

モデルの既定値は、2026-09-12 時点で Japan East / GlobalStandard の対象 3 モデルについて
確認したバージョンを固定したものです。`latest` を動的に解決しません。
Travel API の公開イメージは `v1.0.4` として公開したダイジェスト、
ソースは [公開済みの教材リビジョン](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/commit/05bd80776c0091ae03d8cfae9312a14b0db00b5f) を使います。

新しいリリースでは、管理者がモデルの提供状況と利用枠を確認し、互換性のあるソースと公開イメージを先に公開します。
`main.bicep`、パラメーター例、文書の既定値を同時更新し、後述の方法で ARM を再生成してください。
ソース SHA は公開済みである必要がありますが、テンプレート自身を含むコミットである必要はありません。
デプロイ失敗時に、参加者へ値の推測やリージョン・モデルの変更を求めません。

参加者の ID はルートで一度だけ解決し、すべての参加者向け権限と正規の接続情報へ渡します。
UPN、スクリプトの ID、Microsoft Graph のサインインユーザー検索から推測しません。
別の担当者が再デプロイする場合も、対象参加者の ID を維持します。

モデル名、SKU、容量は固定です。

| デプロイ名 | モデル | SKU | 容量（K TPM） |
|---|---|---|---|
| `gpt-5.6-luna` | `gpt-5.6-luna` | GlobalStandard | 40 |
| `gpt-5.5` | `gpt-5.5` | GlobalStandard | 100 |
| `embedding` | `text-embedding-3-small` | GlobalStandard | 40 |

評価と最適化の出力は、同じ `gpt-5.5` デプロイへの別名です。
利用枠、モデルの提供状況、ポリシー、イメージ・ソースの公開は管理者が満たす前提条件であり、
テンプレート自体が利用可能性を保証するものではありません。容量不足では停止し、別リージョン・モデルへ切り替えません。
ARM の文字列パラメーターには正規表現の制約がないため、文字種・長さと `fail()` による検査で、
固定されていないイメージ・ソース入力を使用前に拒否します。

## リソースと認証

- Foundry の AIServices アカウントと、システム割り当て ID を持つプロジェクト `contoso-travel`。
  Basic Agent Setup を使い、ローカル認証を無効にします。
  子リソースは **project → primary → evaluation → embedding → connections** の順で作成します。
- 専用の Search **Basic**。レプリカ・パーティションは各 1、無料のセマンティック検索、
  システム割り当て ID、公開エンドポイント、`disableLocalAuth: true` を使います。
  両立しない `authOptions` は指定しません。
- Log Analytics は `PerGB2018` と 30 日の保持期間を使います。
  ワークスペースベースの Application Insights はローカル認証を無効にし、既存の監視用権限を維持します。
- Container Apps の Travel Ops API はポート 8080、HTTPS の受信、
  0.25 vCPU / 0.5 GiB、0〜1 のスケールを使います。指定した公開 GHCR ダイジェストを匿名で取得します。
  規程の引用は初期化と同じ固定 `sourceRevision` を使います。
- Codespaces とローカル VS Code は同じ Dev Container を使います。
  テンプレートは Azure ML ワークスペース、Compute、恒久的な演習用 Storage / Key Vault を作りません。
- Cosmos DB、capability host、ACR、仮想ネットワーク、プライベートエンドポイントは作りません。

監視基盤の用途はテレメトリーの収集・トレースの閲覧であり、演習用アラートではありません。
テンプレートはアラートルールや通知アクショングループを作成しません。
`Microsoft.Insights` と `Microsoft.OperationalInsights` は必要ですが、
`Microsoft.AlertsManagement` は前提条件に含めず、`admin-preflight.sh` でも照会・登録しません。
Azure が別途作る既定の Failure Anomalies アラートを抑止したり、既存ルールを無効にしたりする設定ではありません。
[自動アラートの扱い](../docs/admin/troubleshooting.md#application-insights-の自動アラート)を参照してください。

参加者向けの 6 個の権限付与と、Foundry プロジェクト・Search の ID は、リソース単位のアクセスを維持します。
撤去した実行・配布用リソースに対するロール割り当ては残しません。
初期化用 ID にストレージのデータ用ロールは不要です。

### 接続スキーマの例外

Foundry アカウント・プロジェクト・モデルのデプロイと `CognitiveSearch` / `AAD` 接続は `2026-05-01` を使います。
Project Managed Identity の 2 接続は、既存の `2026-05-15-preview` の通信形式を維持します。

| 接続 | 維持する設定 |
|---|---|
| `contoso-travel-search` | `CognitiveSearch`、`AAD`、Search リソース ID と場所のメタデータ。 |
| `contoso-travel-knowledge-lab-mcp` | `RemoteTool`、`ProjectManagedIdentity`、`useWorkspaceManagedIdentity: true`、audience `https://search.azure.com`、`2026-08-01-preview` を使うナレッジベースの MCP URL。 |
| `contoso-travel-appinsights` | `AppInsights`、`ProjectManagedIdentity`、Application Insights リソース ID、内部接続文字列のルーティング用メタデータ。 |

すべての接続はプロジェクトスコープ（`isSharedToAll: false`）です。
この実装で参照した [Preview の公式定義](https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/2026-05-15-preview/accounts/projects/connections)
には `ProjectManagedIdentity` の判別値と MCP の `audience` が含まれていません。
Bicep 0.46.1 は、対象 2 接続の `authType` で **BCP036** を報告します。
この 2 箇所だけで警告を抑止し、生成した接続オブジェクト全体を静的契約テストで確認します。
診断の全体抑止や `any()` による型変換は使いません。
資格情報の契約が異なる `ManagedIdentity` へ置き換えないでください。
リリース配布前に、実際の Portal で Preview の操作を通して確認します。

Application Insights の接続文字列メタデータと、Container Apps の Log Analytics 共有キー連携は
リソース内部の接続にだけ使います。初期化処理の環境変数・接続情報・参加者向け出力にはコピーしません。

## マネージド ID による初期化

`Microsoft.Resources/deploymentScripts@2023-08-01` の `AzureCLI` 形式を使い、
実際の `scripts/bootstrap-custom-template.sh` を `loadTextContent` で埋め込みます。
指定 SHA の固定リポジトリだけをダウンロードし、独立した Python 環境を準備して
`scripts/bootstrap_custom_template.py` を実行します。
Deployment Scripts がマネージド ID でログインし、アダプターは `AzureCliCredential` を使います。
ソースの展開、仮想環境、パッケージのビルドには、Azure Files 上のスクリプトディレクトリではなく
コンテナー内の `/tmp` を使います。この一時ファイルシステムの境界を越えるのはサービス出力の JSON だけです。

Azure CLI は **2.87.0** に固定しています。CLI 2.88 での組み込み Python 3.14 への変更前に公開された
Azure Linux 用リリースです。[Microsoft Artifact Registry](https://mcr.microsoft.com/v2/azure-cli/tags/list) と
[CLI リリースノート](https://learn.microsoft.com/cli/azure/release-notes-azure-cli)を参照してください。
CI は同じ CLI イメージに独立した環境を作り、Azure 認証を行わずに初期化用依存関係をインポートします。
これは現在のリージョンでの Deployment Scripts の対応確認や、Portal 上の通し検証を代替しません。

リリース前には、サービスが固定バージョンを受け付けることと、実行環境に Python 3.10〜3.13、
`venv`、`ensurepip`、TLS があり、初期化用依存関係を導入できることを確認します。
ラッパーは前提条件が不足した場合、明示的に失敗します。
Azure CLI 自身のインタープリターを変更したり、任意の GHCR 初期化イメージをサービスが受け付けると仮定したりしません。
シェルの変更後は `azuredeploy.json` を再コンパイルします。
テンプレートは Linux 実行前に CRLF を LF へ正規化しますが、再現性のためソースも LF で保存してください。

初期化専用のユーザー割り当てマネージド ID（UAMI）へ付与する権限は次のとおりです。

| スコープ | ロール |
|---|---|
| Foundry アカウント | 必要なデータ操作のための Foundry User。 |
| Search サービス | Search Service Contributor と Search Index Data Contributor。 |
| 既存の専用 RG | リソースの検証と ARM のロール割り当て読み取りのための Reader。 |

この ID に Owner、ロール割り当ての書き込み、サブスクリプション全体の権限、
ストレージアカウント全体のデータ権限、デプロイ用リソースの作成権限は付けません。
宣言したリソース・ロール・UAMI の関連付けと補助用 ACI / Storage を作る権限は、
スクリプトの ID ではなくデプロイ実行者が持つ必要があります。
参加者は、本人の Azure CLI サインイン後に初期設定 Notebook から秘密を含まない接続情報を取得できるよう、
RG 内のデプロイを読む権限が必要です。

スクリプトは、必要なリソース、すべての接続、すべてのロール割り当てに依存します。
テンプレートから渡す環境変数は次の 2 つです。

- `WORKSHOP_SOURCE_REVISION`：検証済みのソースコミット。
- `WORKSHOP_CONTEXT_JSON`：秘密を含まない正規の接続情報を JSON 化したもの。

接続情報は `schema_version: "2.0"`、`provisioning_method: "azure-custom-template"`、
`setup_status: "infrastructure-ready"` に加え、サブスクリプション、RG、場所、ソースの URL・リビジョン、
参加者 ID、24 個の `resource_outputs.<key>.value` を持ちます。
初期化処理は Search の 2 インデックス、Lab 5 の評価データ、Lab 6 の Agent Optimizer 用データ、
共通の評価基準を準備して環境を検証します。
すべての段階が成功した後にだけ、`status: complete` と `source_revision` を `AZ_SCRIPTS_OUTPUT_PATH` に保存します。
教材のビルド、参加者用 ZIP の生成、Blob Storage の読み書きは行いません。

ARM の出力は、秘密を含まない次の 4 個です。

| 出力 | 用途 |
|---|---|
| `workshopContext` | 初期化成功後に返す、完了済みのスキーマ 2.0 の接続情報。 |
| `resourceOutputs` | リソース名・エンドポイントの正規マッピング。 |
| `travelApiBaseUrl` | 共通 OpenAPI JSON の `servers[0].url` の置き換え。 |
| `foundryPortalUrl` | Foundry で演習用プロジェクトを開く URL。 |

Dev Container で `az login --use-device-code` を実行した後、
`scripts/configure_workshop.py --subscription <id> --resource-group <name>` がデプロイを読み、
`.workshop/context.json` を保存します。
デプロイの状態、スコープ、スキーマ、エンドポイントを検証し、候補が曖昧な環境を拒否します。
別プロジェクトの接続情報は上書きしません。対象を明示する場合は `--deployment <name>` を使えます。
資格情報、SAS リンク、参加者固有の設定を GitHub へ公開しません。

### 承認済み環境で初期化用の除外タグを使う

`enableBootstrapPolicyExclusion` は、承認済みのハンズオン環境向けに既定で `true` としています。
組織のポリシーが `SecurityControl=Ignore` を除外条件として扱い、その利用を承認しているか
事前に確認してください。承認されていない環境や除外が不要な環境では `false` にします。
このタグ自体に、任意の Azure Policy を無効化する機能はありません。

有効にすると、`bootstrap` の既存タグにだけ `SecurityControl=Ignore` を追加します。
共通のタグ、RG、Foundry、Search、初期化用 ID など、ほかのリソースのタグは変更しません。
Deployment Scripts の仕様により、タグはサービスが自動作成する補助 Storage と ACI にも渡されます。
恒久的な Storage や、ポリシー割り当て・Policy Exemption リソースは追加しません。

承認済みの設定で新規作成し、補助 Storage のタグと必要な認証・ネットワーク設定、
デプロイ全体の `Succeeded`、`workshopContext.setup_status = complete` を確認します。
このオプションは、既にポリシーで変更された既存 Storage の設定を復元する処理ではありません。
初期化の失敗を無視したり、成功条件や片付けの設定を緩めたりするものでもありません。
対象テナントでの有効時・無効時の実行結果は、分けて記録してください。

- 参考 : [Deployment Scripts のタグと補助リソース](https://learn.microsoft.com/azure/azure-resource-manager/templates/deployment-script-template)

### 再試行・補助リソース・片付け

`forceUpdateTag = guid(sourceRevision, bootstrapRunId)` は同じ入力から同じ値を返します。
コミットまたは実行 ID を変えると、演習リソースを改名せずに初期化を再実行します。
スクリプト内容の変更や、保持期間が切れた後の再デプロイでも再実行される場合があるため、
初期化の冪等性を維持します。

サービスは独立した一時 ACI と、Azure Files 用の補助 Storage を自動作成します。
`storageAccountSettings` は意図的に指定しません。
プロバイダー登録、ポリシー、利用枠では、Microsoft.Resources Deployment Scripts、
Microsoft.ManagedIdentity、Microsoft.ContainerInstance、Microsoft.Storage に加えて、
補助 Azure Files / 共有キーへのアクセスを許可する必要があります。

`timeout: PT1H`、`cleanupPreference: OnSuccess`、`retentionInterval: P1D` で
実行時間と失敗時の保持期間を制限します。成功時は補助リソースを片付け、
失敗時は設定した期間だけ診断情報を保持します。
UAMI と対象を限定した権限は、専用 RG を削除するまで再実行用に維持します。
保持中のリソースには課金されるため、実際の削除状況も確認してください。

デプロイ失敗はトランザクションのロールバックではなく、作成済みのリソースや投入データが残る場合があります。
デプロイとスクリプトのエラーを調べ、入力や前提条件を修正した後、同じ RG・参加者 ID で再デプロイします。
強制的に再実行する場合は `bootstrapRunId` を変更します。途中までの初期化を完了扱いにしません。

終了時は成果物を保存し、Hosted Agent のバージョンを削除し、Codespace を停止・削除してから、
Azure Portal で専用 RG を削除して完了を確認します。
デプロイ履歴の削除だけではリソースは消えません。
無関係なリソース、既存のローカル状態、キャッシュは削除しません。

## 開発者向けの再生成・検証

共通 Dev Container を使い、リポジトリのルートから実行します。

```bash
az bicep build --file infra/main.bicep --outfile infra/azuredeploy.json
python -m pytest tests/contract/test_custom_template_contract.py -q
```

Bicep CLI は **v0.46.1 (545b338e2c)** に固定し、生成 ARM のメタデータでは **0.46.1.21595** として記録します。
このテンプレートのためにコンパイラーを更新する必要はありません。
バイト単位で再現するには、同じコンパイラーとソースを使います。
コンパイラー更新時は生成メタデータも変わる可能性があるため、成果物と合わせて確認してください。

静的テストは ARM の構造、依存グラフ、固定入力の式、RBAC スコープ、接続ペイロード、
埋め込んだシェル、出力、接続情報を検査します。
Azure の実行時の利用可能性や、実際の Portal での通し検証を保証するものではありません。

## 公式リファレンス

- [デプロイ実行者の ID](https://learn.microsoft.com/azure/azure-resource-manager/bicep/bicep-functions-deployment#deployer)
- [Deployment Scripts API](https://learn.microsoft.com/azure/templates/microsoft.resources/2023-08-01/deploymentscripts)
- [実行環境・ID・片付け](https://learn.microsoft.com/azure/azure-resource-manager/bicep/deployment-script-develop)
- [Foundry アカウント](https://learn.microsoft.com/azure/templates/microsoft.cognitiveservices/2026-05-01/accounts)
- [Search Basic と認証](https://learn.microsoft.com/azure/templates/microsoft.search/2025-05-01/searchservices)

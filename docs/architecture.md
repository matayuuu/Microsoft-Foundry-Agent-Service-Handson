# アーキテクチャ

## 目標

このハンズオンは、`az login` を実行でき、既存の Azure リソースグループに対してのみ
Owner 権限を持つ参加者が、GitHub Codespace から繰り返し実施できる構成とします。
サブスクリプションレベルの事前準備は、参加者によるセットアップと明確に分離しています。

必須の手順では、意図的に **Basic Agent Setup** を採用しています。ハンズオンの
ナレッジ用に Azure AI Search をプロビジョニングしますが、Agent Service の状態は
引き続きプラットフォームが管理します。これにより、限られたハンズオン時間内に
Cosmos DB、capability host、ACR、プライベートネットワークを扱わずに済みます。

## 実行時の構成

```mermaid
flowchart LR
    browser[参加者のブラウザー] --> portal[Microsoft Foundry ポータル]
    browser --> codespace[GitHub Codespaces]
    codespace -->|az login| azure[Azure コントロールプレーンとデータプレーン]
    codespace -->|Terraform| foundry[Foundry アカウントとプロジェクト]
    codespace -->|Terraform| search[Azure AI Search]
    codespace -->|Terraform| monitor[Application Insights]
    codespace -->|Terraform| api[Travel Ops API]
    codespace -->|Python による初期データ投入| search
    portal --> prompt[Prompt Agent]
    prompt --> iq[Foundry IQ ナレッジベース]
    iq --> search
    prompt --> toolbox[Toolbox]
    toolbox --> api
    codespace -->|Python SDK によるソースデプロイ| hosted[Hosted Agent]
    prompt --> monitor
    hosted --> monitor
```

## リソースの管理責任

| 対象 | 管理主体 | ライフサイクル |
|---|---|---|
| 既存のリソースグループ | ハンズオン管理者 | このリポジトリでは作成も削除もしない |
| Foundry アカウント / プロジェクトとモデルのデプロイ | Terraform | `setup.sh` / `destroy.sh` |
| Search, Application Insights, Container Apps | Terraform | `setup.sh` / `destroy.sh` |
| Search インデックス内のドキュメント | 初期データ投入アダプター | Terraform の実行後に、繰り返しても結果が変わらない追加・更新（upsert）を実行 |
| Prompt Agent と Foundry IQ ナレッジベース | 参加者がポータルで管理 | 親プロジェクトとともに削除 |
| Toolbox のバージョン | 参加者がポータルで管理。任意で SDK アダプターを使用 | Lab 4 で作成。SDK による編集では既存の Skills とガードレールを保持 |
| Travel Ops Skills | 参加者がポータルで管理 | Lab 4 で `data/skills/` 内の合成コンテンツをアップロード。Skills を削除する前に参照を解除 |
| 合成の評価データセットと評価基準（ルーブリック） | セットアップアダプター | ポータルで実施する Lab 5 と Lab 6 に向けて冪等に準備 |
| 評価実行 | 参加者がポータルで管理 | Lab 5 で作成。親プロジェクトとともに削除 |
| Hosted Agent と変更不可のバージョン | Python SDK ラッパー | Lab 7 で作成。Terraform による削除の前に削除 |
| Hosted Agent ランタイムのテレメトリ用ロール | Hosted Agent デプロイアダプター | ランタイム ID の作成後にリソーススコープで付与 |

Terraform と SDK ラッパーが同じオブジェクトを管理してはいけません。

## リソース構成

参加者のリソースグループ内に作成する必須のインフラストラクチャは次のとおりです。

- プロジェクト管理を有効にした Microsoft Foundry アカウント（`AIServices`）
- Microsoft Foundry プロジェクト
- Prompt Agent / Hosted Agent の推論用の `gpt-5.6-luna` デプロイ
- Foundry IQ のクエリ計画、設定可能な LLM 評価用モデル、Agent Optimizer 用の `gpt-5.5` デプロイ
- 初期データを投入するベクトルインデックス用に、`embedding` という名前でデプロイする `text-embedding-3-small`
- Azure AI Search Basic（レプリカ 1、パーティション 1）
- Log Analytics とワークスペースベースの Application Insights
- Container Apps の従量課金環境と、ゼロまでスケールできる Travel Ops API

正確なモデルバージョン、デプロイ SKU、容量は入力値として指定します。
参加者の開始前に、サブスクリプション管理者向けの事前チェックでこれらを検証します。

デプロイ数は厳密に 3 つです。`primary_model_deployment_name` は引き続き
`gpt-5.6-luna` を、`optimizer_model_deployment_name` は `gpt-5.5` を示し、
埋め込みモデルの出力値は変更しません。Foundry IQ はプライマリではなく、
Optimizer 用のデプロイを共有します。評価では引き続き Luna を使用する対象エージェントを
呼び出し、設定可能な評価用モデルには GPT-5.5 を使用します。サービスが管理する
安全性評価器には、判定モデルのデプロイを上書きする設定を渡しません。
2 つのチャットモデルのバージョンには Terraform の既定値を設けていません。
事前チェックで、各モデルのバージョンとクォータの `usageName` を、
それぞれ同一の必須 SKU カタログエントリから取得します。

既定の容量はそれぞれ 40/100/40K TPM ですが、実環境の事前チェック結果に従います。
共有する GPT-5.5 の割り当ては、ポータルでの評価中に 20 でスロットリングが発生したため
引き上げました。これは既存のクォータ内で GlobalStandard のスループットを割り当てるものであり、
サブスクリプションのクォータ上限を引き上げたり、トークン利用料を固定額にしたりするものではありません。
実際の使用量には引き続き課金され、100 単位でも HTTP 429 応答が発生しない保証はありません。
共有用途の容量は、ラボごとではなくデプロイごとに 1 回だけ計上します。
2026-09-06 に確認した新しいポータルでは、ナレッジベースの Chat completions モデル選択欄に
デプロイ済みの GPT-5.5 が表示されましたが、Luna は表示されませんでした。
検索の労力が **Medium** の場合も同様です。このハンズオンでは、エージェントには
Luna を使用したまま、クエリ計画には選択可能な GPT-5.5 のデプロイを使用します。
モデルカタログに掲載されているだけでは、選択 UI や API との互換性は確認できません。
[Search のモデルと API の要件](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
を実際のポータルの選択欄と照合してください。

## 認証と認可

参加者は Azure CLI で対話的に認証します。Terraform と Python は
`DefaultAzureCredential` を通じて、同じキャッシュ済み Entra ID を使用します。

- クライアントシークレットやサービスプリンシパルの資格情報は不要です。
- 対応しているサービスでは、ローカルキーと共有キーを無効にします。
- Terraform を通じて、既存のリソースグループ内で参加者に Foundry とデータプレーンのロールを付与します。
- プロジェクト、Search、Hosted Agent ランタイムの ID には、モデル、データ、
  トレースへのアクセスに必要なリソーススコープのロールのみを付与します。
- Terraform の状態ファイルにはプロバイダーが生成した資格情報が含まれる可能性があるため、
  実行時のアクセスがキーレスであっても機密情報として扱います。

## コントロールプレーンとデータプレーンの分離

安定した Azure リソースには AzureRM を使用します。現在の Foundry のアカウント、
プロジェクト、デプロイ、接続のリソース形式について、AzureRM が必要な API 契約に対応していない場合は
AzAPI を使用します。リソースグループの Owner はリソースプロバイダーを登録できないため、
Terraform プロバイダーの自動登録は無効にしています。

データプレーン操作は、型付きの Python アダプターで実施します。

- 合成のソースドキュメントを Azure AI Search に直接読み込む
- 埋め込みを生成する
- セマンティックベクトルインデックスを作成・更新する
- インデックス化したチャンクを追加・更新する（`merge-or-upload`）
- リモートへの書き込みを行わず、ポータルへのアップロード用に稼働中の API の OpenAPI 定義と Skill ZIP をエクスポートする
- UI が利用できない場合に、任意で Toolbox のツールを更新するか、既存の Toolbox を接続する
- 任意の自動評価実行を作成する
- ポータルで使用する合成の評価データセットとルーブリックを準備する
- ソースから Hosted Agent のバージョンをデプロイ・削除し、動的に作成されるランタイム ID にトレース取り込み権限を付与する

構成、チャンク分割、検証、ポリシーに関する純粋なロジックは Azure クライアントから独立させ、
Azure にアクセスせずにテストを実行できるようにしています。

Lab 4 では、API の実行と動作の指針を分離します。Toolbox には Travel Ops OpenAPI ツールに加え、
`travel-estimation` と `preapproval-simulation` の Skills を含めます。
ポリシーに関するナレッジの参照元は引き続き Foundry IQ とし、Skills に料金表を重複して持たせません。
Skills は MCP リソースであり、通常の API ツールや認可制御ではありません。
利用するクライアントには、互換性のある Skill プロバイダーが必要です。
API 呼び出しの成功やポータルへの登録だけでは、Skill が読み込まれたことを証明できません。
Lab 7 のワークフローは、このプレビュー版のランタイム統合には依存しません。

## ネットワークの方針

このハンズオンでは、Entra ID/RBAC で保護されたパブリックなサービスエンドポイントを使用します。
VNet インジェクション、プライベートエンドポイント、プライベート DNS、カスタマーマネージドキー、
ネットワーク分離された評価は構成しません。これらは本番環境の設計で検討する項目であり、
暗黙に有効になる既定の設定ではありません。

## 障害時の処理範囲

1. `admin-preflight.sh` は、開催前にサブスクリプションに関する阻害要因を報告します。
2. ID、リソースグループ、プロバイダー、リージョン、クォータの確認情報、ポリシーのいずれかが
   不足している場合、`preflight.sh` は Terraform の実行前に失敗します。
3. Terraform が失敗した場合は、安全に再試行できるよう状態ファイルを残します。
4. 初期データ投入には upsert を使用し、最終的なインデックスを検証します。
5. Hosted Agent のリモートビルドは、制限時間内で終了状態になるまでポーリングし、
   ビルド失敗の詳細を表示します。
6. クリーンアップでは、Terraform が管理する親リソースより先にデータプレーンの子オブジェクトを削除し、
   Azure 側のクリーンアップが成功した後にのみローカルの状態ファイルを削除します。

## 保守性の確認項目

- モック API と Hosted Agent ワークフローの業務ルールは、HTTP や Azure を使わずにテストできます。
- プレビュー API の形式は、アダプターと契約テストで分離します。
- 生成されたリソースの値は、`.workshop/context.json` を唯一の正とします。
- 任意の Fabric IQ、Work IQ、A2A、ACR、CI/CD の教材で、必須のセットアップを変更してはいけません。

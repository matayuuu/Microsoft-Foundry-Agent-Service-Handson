**日本語** | [English](README.en.md)

# Microsoft Foundry Agent Service Hands-on

Azure Portal、Microsoft Foundry Portal、Azure Machine Learning Studio を使い、
架空の Contoso 社向け出張・経費 Agent を段階的に作る 10 Labs です。
規程検索、API、Toolbox / Skills、評価、最適化、Agent Framework、Hosted Agent、
trace、cleanup を扱います。すべて合成データで、実際の予約・申請・承認・精算は行いません。

[**Lab 0 から始める**](labs/00-overview.md) ·
[参加条件](docs/participant/prerequisites.md) ·
[Custom template guide](docs/participant/environments/custom-template.md) ·
[Azure ML 実行環境](docs/participant/environments/azure-ml.md)

## 参加者の流れ

1. Azure Portal の **Resource groups > Create** で、Japan East に専用 resource group を
   **1 個だけ手動作成**し、作成完了を確認します。
2. **その後** **Deploy a custom template > Build your own template in the editor > Load file**
   を開き、管理者から受け取った
   [infra/azuredeploy.json](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/azuredeploy.json)
   を読み込みます。
3. **作成済みの RG を選択**し、管理者確認済みのパラメーターを入力して
   **Review + create > Create**。テンプレート画面の **Create new** は使いません。
4. Bicep / ARM が標準リソースを作成し、Deployment Scripts が Search 初期データ、
   評価アセット、環境検証、live Portal assets、教材 ZIP まで自動準備します。
   bootstrap を含むデプロイ全体の成功を待ちます。
5. Azure ML backing Storage の **Storage browser > Blob containers > workshop-files** で
   **Microsoft Entra user account** を使用し、private な `foundry-workshop-files.zip` を
   **Download** で PC へ 1 回取得して展開します。公開 URL や SAS は使いません。
6. Labs 2〜6 は Microsoft Foundry Portal。Lab 4 は展開済みの `portal-assets/` を使います。
7. **Lab 7 の開始時だけ** Azure ML `Standard_DS3_v2` Compute instance を
   **Idle shutdown** 有効で作成。最上位 folder を **Notebooks > User files** へ upload し、
   `notebooks/00-azureml-setup.ipynb` を **Python 3.10 - SDK v2** で実行します。
   Labs 7〜8 は **Python (Foundry Hosted Agent)** を使います。
8. Lab 9 で **Export → Hosted Agent / versions 削除 → Compute Stop / Delete →
   Azure Portal の Delete resource group → 削除完了確認** の順に片付けます。

教材 ZIP の生成側パスは `.workshop/download/foundry-workshop-files.zip`、
展開後の最上位 folder は `Microsoft-Foundry-Agent-Service-Handson` です。
設定は `.workshop/context.json` の `resource_outputs.<key>.value` を使います。
参加者の事前準備にローカル CLI は不要です。
`infra/` と `instructor/` は教材 ZIP に含まれません。それらへのリンクは GitHub の
開発ブランチ `dev-custom-template` を指します。管理者が公開を確認した JSON を配布し、
未公開の場合はリンク先を利用可能とみなさず、管理者からファイルを受け取ってください。

## Agenda

| Lab | 内容 | 目安 |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | 全体像、安全・費用・データ境界 | 5分 |
| [Lab 1](labs/01-setup.md) | RG 手動作成、custom template、private ZIP download | 未計測 |
| [Lab 2](labs/02-prompt-agent.md) | Prompt Agent と Azure AI Search | 20分 |
| [Lab 3](labs/03-rag-foundry-iq.md) | Foundry IQ | 25分 |
| — | 休憩 | 10分 |
| [Lab 4](labs/04-tools-toolbox.md) | Toolbox、OpenAPI、Skills、Tool Search | 30分 |
| [Lab 5](labs/05-evaluation.md) | Portal evaluation | 15分 |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20分 |
| [Lab 7](labs/07-agent-framework-harness.md) | Azure ML setup、Agent Framework、Harness Agent | 50分 |
| [Lab 8](labs/08-hosted-multi-agent.md) | Hosted sequential workflow | 30分 |
| [Lab 9](labs/09-observability-cleanup.md) | Trace と cleanup | 20分 |

Lab 1 の所要時間は、新経路の実 Portal rehearsal 後に記録します。
初期化、RBAC 反映、サービス capacity に左右されるため、既存の別経路の実測値は流用しません。

## 標準構成

- Japan East の専用 workload RG（参加者が先に作成）
- Foundry resource / Basic Agent Setup project `contoso-travel`
- `gpt-5.6-luna` 40K TPM、`gpt-5.5` 100K TPM、
  `embedding` / `text-embedding-3-small` 40K TPM
- Azure AI Search **Basic**、Application Insights / Log Analytics
- public Container Apps Travel Ops API（管理者確認済み GHCR `@sha256` image）
- Search AAD connection `contoso-travel-search`、
  `contoso-travel-knowledge-lab-mcp` / `contoso-travel-appinsights` は **Project Managed Identity**
- Azure ML workspace、private Blob の Storage、Key Vault
- scoped RBAC と既存サービスの system identities、初期化専用 user-assigned managed identity

テンプレートは RG と Compute を作りません。Foundry / Search の local auth は無効、
public endpoints を使用します。Cosmos DB、Agent capability host、ACR、private networking は
追加しません。Deployment Scripts の一時 ACI / Azure Files Storage は成功時に cleanup、
失敗時は有限期間保持します。bootstrap identity と scoped grants は RG 削除まで残ります。

[構成図と責務](docs/architecture.md) · [管理者の事前確認](docs/admin/prerequisites.md)

> [!WARNING]
> Azure resources と model operations は課金対象です。ブラウザーを閉じても、
> deployment history を削除しても resources は消えません。必要な成果物を Export 後、
> 専用 RG を削除し、削除完了まで確認します。実在データ、secret、device code を
> Portal、Notebook、trace、スクリーンショットへ入力・共有しないでください。

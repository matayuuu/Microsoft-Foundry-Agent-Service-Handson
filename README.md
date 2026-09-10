**日本語** | [English](README.en.md)

# Microsoft Foundry Agent Service Hands-on

Azure Portal、Azure Cloud Shell Bash、Microsoft Foundry Portal、Azure Machine Learning
Studio を使い、架空の Contoso 社向け出張・経費 Agent を段階的に作る 10 Labs です。
規程検索、API、Toolbox / Skills、評価、最適化、Agent Framework、Hosted Agent、
trace、cleanup を扱います。すべて合成データで、実際の予約・申請・承認・精算は行いません。

[**Lab 0 から始める**](labs/00-overview.md) ·
[参加条件](docs/participant/prerequisites.md) ·
[Cloud Shell provisioning](docs/participant/environments/cloud-shell.md) ·
[Azure ML 実行環境](docs/participant/environments/azure-ml.md)

> [!NOTE]
> 旧実装は Git tag
> [`codespaces-cloud-shell-v1`](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/tree/codespaces-cloud-shell-v1)
> に保存されています。現在の手順とは混在させないでください。

## 承認済み hybrid flow

1. Azure Portal で workshop 専用 resource group を 1 個だけ作成。
2. Azure Cloud Shell Bash を開き、初回は標準 UI に永続 Storage を自動作成させ、
   Azure Files-backed HOME を確認してから repository を shallow clone。
3. 軽量 provisioning environment を準備し、`scripts/setup.sh` を実行。
4. Terraform が Foundry、3 models、Search、monitoring、Container Apps API、RBAC、
   connections、Azure ML workspace と backing resources を作成。
5. `.workshop/download/foundry-workshop-files.zip` を **Manage files > Download** で
   PC へ 1 回だけ取得し、直ちに `exit`。
6. Labs 2〜6 は Microsoft Foundry Portal、Lab 4 assets は PC 上で使用。
7. Labs 7〜8 の開始時に Azure ML Compute instance を作成し、download 済み folder を
   **User files** へ upload。
8. Lab 9 で Compute、Terraform resources、workload resource group の順に cleanup。

Cloud Shell は provisioning / download 専用です。Notebook、Jupyter、Graphviz、
web preview、Hosted Agent environment を Cloud Shell で実行しません。

## Agenda

| Lab | 内容 | 目安 |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | 全体像、安全・費用・データ境界 | 5分 |
| [Lab 1](labs/01-setup.md) | Cloud Shell provisioning と 1 回の download | 10〜15分 |
| [Lab 2](labs/02-prompt-agent.md) | Prompt Agent と Azure AI Search | 20分 |
| [Lab 3](labs/03-rag-foundry-iq.md) | Foundry IQ | 25分 |
| — | 休憩 | 10分 |
| [Lab 4](labs/04-tools-toolbox.md) | Toolbox、OpenAPI、Skills、Tool Search | 30分 |
| [Lab 5](labs/05-evaluation.md) | Portal evaluation | 15分 |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20分 |
| [Lab 7](labs/07-agent-framework-harness.md) | Azure ML setup、Agent Framework、Harness Agent | 50分 |
| [Lab 8](labs/08-hosted-multi-agent.md) | Hosted sequential workflow | 30分 |
| [Lab 9](labs/09-observability-cleanup.md) | Trace と cleanup | 20分 |

Lab 1 の参加者目標は **10〜15分**です。**8〜10分**は persistent HOME、quota、provider、
package cache が準備済みの warm best case です。初回 Cloud Shell の標準 UI による
persistent storage 作成と mount 確認は、Lab 1 に手順を記載しますが計測時間に含みません。

## 作成される構成

- Japan East の専用 workload resource group
- Microsoft Foundry resource、Basic Agent Setup project `contoso-travel`
- `gpt-5.6-luna` 40K TPM、`gpt-5.5` 100K TPM、
  `embedding` (`text-embedding-3-small`) 40K TPM
- Azure AI Search Basic、workspace-based Application Insights / Log Analytics
- public Travel Ops API on Container Apps
- keyless Search／Foundry IQ MCP／monitoring connections と scoped RBAC
- Azure ML workspace、Storage、Key Vault、Application Insights

Terraform は Azure ML Compute instance を作りません。Cloud Shell slot の占有を短くするため、
Compute は Lab 7 で参加者が作成します。

> [!WARNING]
> Azure resources、model calls、Search、evaluation、optimizer、Hosted Agent は課金対象です。
> ブラウザーや Cloud Shell を閉じても削除されません。実在データ、secret、device code を
> Portal、Notebook、trace、スクリーンショットへ入力しないでください。Lab 9 の cleanup
> を完了し、resource group が削除されたことまで確認します。

# 管理者向け前提条件

## 配布前の確認

参加者は **Resource groups > Create** で専用 RG を 1 個手動作成した後、
**Deploy a custom template > Build your own template in the editor > Load file** から
`infra/azuredeploy.json` を読み込みます。テンプレートは作成済み RG に deploy し、
RG 自体や Azure ML Compute は作りません。

管理者は
[infra の説明](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/README.md) と
[講師 runbook](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/instructor/runbook.md)
に従い、次をイベント前に確認・配布します。

| 確認項目 | 条件 |
|---|---|
| `location` | `japaneast`。固定の Japan East 以外へ fallback しない |
| Primary | `gpt-5.6-luna` / GlobalStandard / 40K TPM と、その確認済み `primaryModelVersion` |
| Evaluation / optimizer | `gpt-5.5` / GlobalStandard / 100K TPM と、その確認済み `evaluationModelVersion` |
| Embedding | deployment `embedding` / `text-embedding-3-small` / GlobalStandard / 40K TPM と、その確認済み `embeddingModelVersion` |
| Search | **Basic**。別の pricing model / SKU に切り替えない |
| `travelApiImageRef` | 管理者が内容・pull・health を確認した公開 GHCR `@sha256:` reference |
| `sourceRevision` | 本教材 repository に公開済みの小文字 40 桁 hex commit SHA |
| `participantObjectIdOverride` | 本人の deployment は空欄可。代理 deployment / redeployment は対象参加者の Entra User object ID を指定 |
| `bootstrapRunId` | 初期値を共有。明示的な初期化再試行時だけ変更 |

モデル version や image digest の例示値を推測で配りません。モデル名、version、SKU、
quota を **参加者が利用する各 subscription** で確認します。
catalog に表示されること、講師の subscription で成功したこと、以前の rehearsal は
参加者の capacity の証明や予約ではありません。実 deployment 時の不足は失敗として扱います。

## Template / source の公開契約

- [infra/main.bicep](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/main.bicep)
  が正本、
  [infra/azuredeploy.json](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/azuredeploy.json)
  は compiler が生成した Portal 用 artifact。
  配布前に差分検査と契約テストを実施します。
- canonical な入口は **Load file**。公開済み revision と整合する JSON を配布します。
- `sourceRevision` のソース archive、初期化 scripts、合成規程と引用 URL が実際に取得可能で
  あることを確認します。任意 URL や未公開 revision を bootstrap に渡しません。
- branch URL は開発用入口に限定。実行ソースと bundle manifest は SHA で固定します。
  未公開の URL や `main` に存在しない artifact を指す Deploy to Azure button は設置しません。
- repository に個別 parameter file、account、subscription ID、credentials、E2E の私的証跡を
  入れません。配布値と実 E2E 記録は管理者の承認済み非公開領域で扱います。
- `infra/`、`instructor/`、管理者 / bootstrap / packaging scripts は教材 ZIP に含めません。
  上記の公開リンクは `dev-custom-template` 開発ブランチを参照するため、push と公開状態を
  管理者が確認するまで利用可能と扱いません。公開前は確認済み JSON を直接配布します。

## Providers / quota / Policy

事前の管理者確認では次を含めます。参加者や runtime identity へ subscription-wide の
確認・登録権限を追加しません。

- Microsoft.CognitiveServices、Microsoft.Search、Microsoft.Insights、
  Microsoft.OperationalInsights、Microsoft.App、Microsoft.MachineLearningServices、
  Microsoft.Storage、Microsoft.KeyVault、Microsoft.ManagedIdentity、
  Microsoft.ContainerInstance、Microsoft.Resources の Deployment Scripts
- Japan East の固定 3 model deployments、Search Basic、Container Apps、workspace backing resources
- Deployment Scripts が使用する ACI quota と対応 Azure CLI runtime、
  その runtime の Python / dependency install・外向き HTTPS
- 一時 Storage の Azure Files / Shared Key 要件と、組織の Storage / network Policy の両立
- Lab 7 用 CPU **Standard_DS3_v2** と AML Compute quota
- public endpoints、Foundry / Search local auth 無効、system identities、Key Vault RBAC
- GitHub 公開 source / package sources / GHCR / 必要な Azure endpoints への HTTPS

[scripts/admin-preflight.sh](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/scripts/admin-preflight.sh) と
[scripts/request-quota-increase.sh](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/scripts/request-quota-increase.sh)
は教材 ZIP に含まれず、権限を持つ管理者が公開済み repository の
承認済み CLI 環境で使う quota / provider の補助です。参加者の provisioning 手順でも、
capacity 予約でも、実 Portal E2E の代用でもありません。

## 参加者と identity の権限

RG を作成する許可と、作成後の RG 内で **Owner 相当**（resource deployment / 削除、
role assignments を含む）で作業する許可を、事前に別々に確認します。
bootstrap の identity と、RBAC を検証する対象参加者を混同しません。
root が解決した参加者 ID は RBAC と validation に同じ値を渡します。

| Principal | Scope | 維持する役割 |
|---|---|---|
| Participant | Foundry account / project | Foundry User / Foundry Project Manager |
| Participant | Search | Search Service Contributor / Search Index Data Contributor |
| Participant | monitoring | Log Analytics Reader / Privileged Monitoring Data Reader |
| Participant | AML backing Storage | Storage Blob Data Contributor。Portal 用の管理プレーン参照権限も必要 |
| Project MI | Foundry / Search | Foundry User / Search contributor roles |
| Project MI | monitoring | Monitoring Metrics Publisher / Log Analytics Reader / Privileged Monitoring Data Reader |
| Search MI | Foundry account | Cognitive Services OpenAI User |
| Bootstrap UAMI | 専用 RG と対象 resources | 初期化に必要な data 操作、resource / RBAC 参照、教材 blob 書込みのみ |

`contoso-travel-search` は AAD Search resource connection。
`contoso-travel-knowledge-lab-mcp` と `contoso-travel-appinsights` は **Project Managed Identity**。
runtime MI に Owner や subscription-scope roles は与えません。
Azure ML が workspace identity に自動付与する Storage role を重複定義しません。
Portal の role 表示名が変わる場合は role definition ID で照合します。

## Bootstrap / private Blob の lifecycle

- `Microsoft.Resources/deploymentScripts` は専用 UAMI の自動 login を使用し、
  人の対話 login / signed-in-user lookup を要求しません。
- 2 indexes seed → evaluation assets 準備 → validation → live assets / ZIP →
  Entra ID による Blob upload の全成功を gate にします。
- 検証対象には参加者 RBAC、API health、Search schema / document count を含めます。
  retry は有限。恒久的な不正入力・quota・権限エラーを成功にしません。
- `cleanupPreference: OnSuccess`、`retentionInterval: P1D`。
  一時 ACI / Azure Files Storage は成功時に削除、失敗時は有限期間で診断します。
  教材 ZIP の保存先は一時 Storage ではなく既存 AML backing Storage です。
- bootstrap UAMI と scoped grants は script cleanup では消えず、再実行用に残ります。
  最終的に専用 RG と一緒に削除します。
- 変更のない script は通常再実行されませんが、`bootstrapRunId` による `forceUpdateTag`
  更新や retention 後の redeployment で再実行され得るため、処理の冪等性も検証します。
- container `workshop-files` は private、`allowBlobPublicAccess: false`、
  `defaultToOAuthAuthentication: true`。Storage browser で **Microsoft Entra user account** を使用。
- OAuth default は Shared Key 無効化ではありません。Azure ML workspace 互換性のため
  Shared Key は有効のまま維持します。account key、SAS、公開 link は配布しません。

## Rehearsal / cleanup

Lab 1 の新経路の所要時間は未計測です。実際の Portal UI で測定するまで時間を確約しません。
Playwright での実 Portal E2E は、実施結果と未実施項目を区別して記録します。
script / contract test や simulated assets を UI 完了の証拠にしません。

budget / alert、participant ごとの専用 RG inventory、cleanup owner を用意します。
**Export → Hosted Agent / versions 削除 → Compute Stop / Delete →
Delete resource group → 削除確認**を最後まで実施します。
RG 内の標準 resources はまとめて削除します。deployment history の削除では resources は消えません。

# 管理者向け前提条件

## Capacity planning

Azure Cloud Shell は tenant あたり既定 **20 concurrent users** です。開催人数、既存利用、
Support で承認済みの上限を事前に確認し、全参加者が短時間の provisioning/download を
完了できる開催計画を作ります。participant flow に scheduling 指示を追加しません。

Lab 1 の participant target は 10〜15分です。実測参考値:

| Operation | warm rehearsal |
|---|---:|
| Cloud Shell start | 35.5秒 |
| shallow clone | 1.55秒 |
| provisioning-only SDK venv 初回 install | 18.85秒 |
| prior Terraform + bootstrap | 6分42秒 |

8〜10分は準備済み/warm best case だけです。初回 Cloud Shell の標準 UI による persistent
storage 作成は participant Lab 1 に記載しますが、timed Lab 1 は mount 確認後に開始します。

## Persistent Cloud Shell storage

初回 participant は Cloud Shell の標準 UI に Storage account と Azure Files share を
自動作成させ、既存 participant は現在の storage を再利用します。provisioning 開始前に
各 participant の Azure Files-backed `~/clouddrive` が healthy であることを検証します。
script による ephemeral provisioning の refusal は必須の protection です。

- `clouddrive` の CIFS/read-write mount、再接続後の persistence
- repository/state を `clouddrive` 配下に保持できる容量
- Storage policy の `publicNetworkAccess` / `allowSharedKeyAccess`
- GitHub、GHCR、package sources、Azure endpoints への HTTPS

Cloud Shell storage が未準備の participant に workload provisioning を開始させません。

## Azure capacity / providers

- Microsoft.CognitiveServices、Search、Insights、OperationalInsights、App、
  MachineLearningServices、Storage、KeyVault
- Japan East の Luna 40K TPM、GPT-5.5 100K TPM、embedding 40K TPM
- Search Basic と `Standard_DS3_v2` Compute quota
- public endpoints、system identities、Key Vault RBAC、Storage constraints

catalog visibility ではなく rehearsal deployment と smoke test で確認します。

## Participant permissions

participant は workload resource group を 1 個作成・削除し、その scope で Owner 相当権限を
持ちます。runtime identities には subscription-wide role を付与しません。

| Principal | Scope | Roles |
|---|---|---|
| Participant | Foundry account | Foundry User |
| Participant | Project | Foundry Project Manager |
| Participant | Search | Search Service Contributor; Search Index Data Contributor |
| Participant | Log Analytics | Log Analytics Reader |
| Participant | App Insights | Privileged Monitoring Data Reader |
| Project MI | Foundry account | Foundry User |
| Project MI | Search | Search Service Contributor; Search Index Data Contributor |
| Project MI | monitoring | Monitoring Metrics Publisher; Log Analytics Reader; Privileged Monitoring Data Reader |
| Search MI | Foundry account | Cognitive Services OpenAI User |

Portal が legacy Azure AI role label を表示しても role definition ID で照合します。

## Cleanup governance

workload cleanup と Cloud Shell storage lifecycle を分離します。Cloud Shell storage は
dedicated かつ policy が許す場合だけ、workload cleanup 成功後に削除します。shared/existing
storage を削除しません。budget / alert と participant ごとの completion record を準備します。

# 管理者向けトラブルシューティング

このページでは、サブスクリプション管理者が `az`、Azure portal のアクティビティログ、
`scripts/admin-preflight.sh` を使って調査する問題をまとめています。
参加者が `scripts/setup.sh` の実行中にこれらの問題に遭遇した場合、参加者自身では解決できません。
管理者によるサブスクリプション全体への操作、または Azure サポートへの問い合わせが必要です。

## Cloud Shell の開催・ストレージ・接続

| 症状 | 確認と対応 |
|---|---|
| `Tenant User Over Quota` | **tenant あたり既定20同時ユーザー**。講師・補助員・他部署も含めて数え、開催前に Azure Support へ引き上げを相談する。モデル TPM の変更や新規 RG では解消しない |
| Cloud Shell / Storage の provider が未登録 | 管理者が **Subscriptions > Resource providers** で `Microsoft.CloudShell` / `Microsoft.Storage` を確認し、必要なものだけ登録する。参加者に `--apply` や subscription 権限を渡さない |
| `RequestDisallowedByPolicy` / storage の作成・マウントが403 | 自動作成された専用RG / Storage、または管理者割当の既存Storageについて、継承RBACとdenyの詳細を確認する。共有キーアクセス・public networkの禁止を参加者が解除する手順にはしない。標準Cloud Shellが組織方針に適合しない場合は対応不能として調整する |
| Storage の Review が File shares / Provisioned v2 になる | **Primary service: Azure Files** による作成構成の切替を確認する。作成前に **Other (tables and queues)**、general-purpose v2 用の **Standard**、LRS に戻す。**View automation template > Parameters** の `kind=StorageV2` / `accountType=Standard_LRS` を判断根拠にする |
| Other / Standard なのに Review が Page blobs と表示される | 2026-09-09 に確認された表示不整合。Review のラベルを必須条件にせず、ARM template の kind / accountType を確認する。作成後は `az storage account show` で `StorageV2` / `Standard_LRS` / `Succeeded` を確認する。表示だけを理由に Premium や FileStorage に変更しない |
| 古い share に接続できず ephemeral session になる | Bash の起動を永続化の成功とみなさない。元の `preferredLocation`、storage と個人設定を保全し、参加者ガイドの明示的な再設定を行う。新しい storage の region は選択する Cloud Shell location に一致させ、RG の region から推定しない。古い storage は削除しない |
| File share 作成で追加の vault が表示される | **New classic file share > Backup** の **Enable backup** は既定 On。新しい短期演習用 share で任意なら選択を外し、Review が TransactionOptimized / SMB で、新規 Vault / policy を含まないことを確認する。既存・組織必須の保護は変更しない |
| `Failed to connect terminal` / Jupyter は開くが kernel が接続しない | Terminal の HTTPS / WSS と preview の HTTPS、企業プロキシ、Relay の名前解決を確認する。専用 launcher の認証付き HTTP channel で両 kernel の確認セルを実行する。browser から kernel への直接 WebSocket を前提にせず、Jupyter 認証、XSRF、Origin 制限を弱めない |
| 永続 HOME / runtime の判定が合わない | 実機の HOME image は ext2 の場合もある。SMB 上に venv を置かず、backing image と native filesystem を確認する。Jupyter が runtime directory に付ける sticky bit による `1700` は owner-only のままなので許容する。group / other 権限を追加して回避しない |
| パッケージの取得に失敗する | [配布先の通信条件](prerequisites.md#企業ネットワークの事前確認)を確認する。非承認のミラー、`sudo`、system Python / Azure CLI の改変へ切り替えない |
| `Audience ... is not a supported MSI token audience` | `az login --use-device-code` が公式の回復手順。Conditional Access で拒否されたら管理者が認証条件を確認し、key / secret へ置き換えない |
| HOME / venv / state が再接続後にない | 別の share、一時セッション、HOME 永続マウントの不成立を調べる。元の storage / HOME image を削除せず、新しい state で setup を開始しない |
| Jupyter / build 待ちが切断される | Cloud Shell は非対話20分で終了し、kernel メモリーは失われる。保存ファイルと Azure 側の run / version 状態を確認して再開する。無限 keepalive や重複デプロイで回避しない |

[永続ストレージの文書](https://learn.microsoft.com/azure/cloud-shell/persisting-shell-storage)は
HOME image の保持を説明する一方、
[FAQ](https://learn.microsoft.com/azure/cloud-shell/faq-troubleshooting)には HOME が終了時に失われるとの記述があります
（2026-09-09 取得）。文書だけで保持を保証せず、
[参加者ガイド](../participant/environments/cloud-shell.md#persistence)の **Restart** 検証を行います。
`New session` で同じファイルが見えるだけでは検証完了としません。

再接続で前回の storage が選べない場合は、元の `preferredLocation`、
subscription / RG / account / share と個人設定を保全して調査します。
**Reset User Settings** は既存の個人設定と全 session に影響するため、自動復旧手順にはしません。
cleanup が未完了なら storage を残し、残存 resource ID とエラーだけを安全に引き継ぎます。

## リソースプロバイダーが `NotRegistered` と表示される

`./scripts/admin-preflight.sh --subscription "<id>" --apply` を実行して登録します。
登録時に認可エラーが出る場合は、実行したアカウントにサブスクリプション全体の
プロバイダー登録権限がありません。

サブスクリプション全体に **Contributor** または同等の権限を持つアカウントを使ってください。
リソースグループ（RG）だけの **Owner** ロールでは、プロバイダーを登録できません。

## モデルのクォータ・容量が不足している

対象リージョンの `gpt-5.6-luna`、`gpt-5.5`、`text-embedding-3-small` のいずれかで、
想定する参加者・チーム数に対してサブスクリプションのクォータが不足しています。
対応の目安は次のとおりです。

1. `--location japaneast`、`--location australiaeast`、`--location centralus` の順に別リージョンを指定して再実行します。
2. Azure portal の **Quotas** または Azure サポートから、対象モデル・SKU のクォータ引き上げを申請します。即時には反映されないため、開催前に余裕を持って申請してください。
3. 同時に利用する参加者・チーム数を減らすか、開催時間を分けて、既存のクォータ内に収めます。

Luna または埋め込みの容量不足が確認された状態では参加者を先へ進めないでください。
GPT-5.5 だけが不足する場合、setup は共有の評価・最適化用デプロイを省略します。
参加者は Labs 5 / 6 をスキップし、残りのハンズオンへ進めます。

Luna は Prompt / Hosted Agent と Foundry IQ、GPT-5.5 は Lab 5 の評価と
Lab 6 の Agent Optimizer で共有します。
Luna / GPT-5.5 / 埋め込みの既定の必要容量は、それぞれ **40 / 100 / 40K TPM** です。
各デプロイの同じ SKU に対応する `usageName` を根拠に確認してください。
モデル名からクォータの区分を推測したり、古いモデルバージョンに置き換えたりしないでください。

## クォータに余裕があるのに HTTP 429 や Foundry IQ のタイムアウトが発生する

**サブスクリプションのクォータの空き容量と、デプロイに割り当てた処理量は別です。**
2026-09-09 のリハーサルでは、Luna のデプロイが20容量単位の状態で
7行の Portal 評価を行い、01:37〜01:42 UTC に HTTP 429 が36回発生しました。
ARM が返した `rateLimits` は60秒あたり20リクエスト・20,000トークンで、
Foundry IQ の検索も90秒のタイムアウトに達しました。

現在の `evaluation_model_capacity` の既定値は **100** です。
GPT-5.5 は Lab 5 の設定可能な LLM 評価と Lab 6 の Agent Optimizerに使い、
Foundry IQ は Luna を使います。
これは既存の `GlobalStandard` のモデル・SKU 別クォータ内でデプロイの処理量を増やす設定であり、
サブスクリプションのクォータ上限の引き上げや、定額のトークン利用枠の購入ではありません。
モデルの実際の使用量や、ほかの Azure サービスの料金は引き続き発生します。
処理量を増やすと、使用量も増える可能性があります。

既存環境へ適用する前に、Terraform の実行計画と容量の上書き設定を確認してください。
古い tfvars や `-var` で20を指定している場合は、新しい既定値よりもその指定が優先されます。
変更後のデプロイ容量と実際の `rateLimits` を確認し、前回の評価が終了してから、
実行条件を管理したうえで再評価してください。

100単位でも HTTP 429 が発生しない保証はありません。
リクエストの集中、トークン量、サービス側の制限も影響します。
スロットリングが続く場合は同時実行を減らし、再試行の案内に従ってください。
**課金対象の評価が実行中のまま、むやみに再実行しないでください。**

### 40K の Luna でも自動評価が集中する場合

2026-09-10 の Dedicated Search / Cloud Shell E2E では、7件・候補1件の Optimizer でも、
Foundry IQ 内の Luna 呼び出しが `429` になりました。実際の割り当ては
40,000 TPM / 40 RPM、サブスクリプションの同じ `usageName` の上限は1,000Kでした。
既定の40Kは起動・軽い対話用の容量であり、並列評価の成功を保証する値ではありません。

この検証では、既存クォータ内の空きを別途確認し、`TF_VAR_primary_model_capacity=400` を
指定した `setup.sh --skip-bootstrap` の保存済み計画をレビューしました。
対象 subscription / RG と元の入力値を維持し、モデル容量と既存 connection の差分だけを適用後、
ARM の `rateLimits` が400,000 TPM / 400 RPMであることを確認して、終了済みの評価を再実行しました。
クォータ上限、policy、認証、Guardrail は変更していません。

400はこの検証の割り当て例であり、全環境の推奨値・最小値ではありません。
既定の preflight は40 / 100 / 40Kを確認するため、**その成功を上書き容量の確認として使わず**、
管理者が対象モデル・SKUの空きと既存割り当ての増分を確認してください。
上書き値は再実行時にも明示し、Terraform 外から同じ deployment を変更しません。
容量を変えられない場合は並列実行を避け、未解消の `429` がある比較結果を採用しません。

## カタログにあるモデルが Portal の選択欄に表示されない

カタログでの利用可否、クォータ、機能・API の対応状況は別々に確認する必要があります。
`.workshop/context.json` で、選択中のプロジェクトとデプロイ名を確認してください。

| 用途 | 設定とモデル |
| --- | --- |
| Prompt / Hosted Agent、Foundry IQ | `primary_model_deployment_name`（`gpt-5.6-luna`） |
| Lab 5 の設定可能な LLM 評価用モデル | `evaluation_model_deployment_name`（`gpt-5.5`） |
| Agent Optimizer の両方のモデル選択 | `optimizer_model_deployment_name`（同じ `gpt-5.5`） |

サービス管理の評価器では、評価用モデルを変更できません。

ナレッジベースでは Luna、Lab 5 の judge と Optimizer では GPT-5.5 を選びます。

### Optimizer に `No supported optimization model` と表示される

2026-09-09 時点の公式対応一覧には `gpt-5.5` が含まれます。まず
`.workshop/context.json` の `optimizer_model_deployment_name` が `gpt-5.5` か確認します。
`null` の場合はクォータ不足によりoptional deploymentが省略されているため、
Labs 5 / 6 のlive実行を省略します。

`gpt-5.5` がデプロイ済みにもかかわらず表示される場合は、Portalとサービスの
対応差を記録し、同じrunを再送せずLab 6のfallbackへ進みます。対応状況は
[Agent Optimizer の Models](https://learn.microsoft.com/azure/foundry/agents/concepts/agent-optimizer-overview#models)
と実際の Portal の両方で開催前に再確認します。

[Search API](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-create-knowledge-base)
で利用できるモデルでも、現在の Portal に表示されるとは限りません。
必要な選択欄や API が利用できない場合は作業を止め、阻害要因を記録してください。
別のデプロイを追加したり、無断でモデルを切り替えたりしないでください。

## 古いデプロイ名の環境を更新する

旧構成から `gpt-5.6-sol` または Luna-only Optimizer を
`gpt-5.6-luna` / `gpt-5.5` に変更すると、
モデルのリソースが置き換わる場合があります。
Terraform の実行計画を確認し、変更後は保存済みのエージェント・ナレッジ・評価の参照先を接続し直してください。

状態の復旧では、現在のデプロイ ID と完全に一致するものだけをインポートします。
不一致を回避するために状態ファイルを削除しないでください。
クリーンアップが成功するまで元の入力値と状態ファイルを保持し、**既存のリソースグループは削除しないでください。**

## Azure AI Search で `InsufficientResourcesAvailable` が発生する

Azure AI Search の空き容量はリージョンの実際の稼働状況に左右され、
リソースプロバイダーの利用可否メタデータだけでは予測できません。
対応する代替リージョンを指定して `scripts/setup.sh` を再実行します。

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --location australiaeast
```

3リージョンの Dedicated Basic がすべて失敗した場合は、Serverless Developer preview を試します。

```bash
./scripts/setup.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --location japaneast \
  --ai-search-serverless
```

Serverless は従量課金で、preview 中は SLA がありません。Dedicated からの tier 変更ではなく、
別の pricing model として新規作成されます。
セットアップは再実行しても安全です。ローカルの状態ファイルに記録がなくても、
命名規則とハンズオン用タグで特定できるリソース、および完全に一致する RBAC 割り当てを安全にインポートします。
一部だけ適用された場合も、Terraform の実行計画を更新します。

所有者を示すタグが異なるためインポートを拒否された場合は、強制インポートや削除をせず、
まず名前の衝突を調査してください。

## 必要なリソースを拒否する可能性のある Azure Policy が報告される

スクリプトによるポリシー確認は **可能な範囲での確認**です。
効果（`deny`、`disable` など）と対象リソースの範囲から、
`Microsoft.CognitiveServices/accounts`、`Microsoft.Search/searchServices`、
`Microsoft.App/*` やその配下のリソースをブロックしそうなポリシー割り当てを列挙します。

ただし、すべての条件を網羅的には評価できません。
特にイニシアティブ内のポリシー、タグに基づく条件、`deployIfNotExists` の効果は、
静的な確認だけでは判断が困難です。候補のポリシーが報告されたら、次を確認してください。

1. Portal の **Policy > Definitions** で対象ポリシーを開き、上記リソースの種類に対する `if` 条件を確認します。
2. 対象リソースを拒否し、適用除外もない場合は、ハンズオン用 RG に限定したポリシー適用除外を申請するか、対象外の RG・サブスクリプションを選びます。
3. 候補が **報告されなくても、問題がない保証にはなりません**。スクリプトの判定条件に一致しなかっただけです。実際の `terraform apply` でポリシー拒否のエラーが出た場合は、その結果を優先して調査してください。

2026-08-31 より前の教材では、元文書の複製用に Storage アカウントを作成していました。
管理グループの `modify` ポリシーでパブリックアクセスが無効になり、
Codespaces からの初期データ投入が失敗する事象がありました。
現在の **Foundry workload の Terraform** ではその Storage を作成・参照せず、リポジトリの合成ポリシーファイルを
Azure AI Search に直接登録します。教材を更新して `setup.sh` を再実行し、
古い Storage リソースを Terraform 経由で削除してください。
これは過去の Codespaces での事象です。今回追加した Cloud Shell の HOME 永続化用
Storage account / Azure Files share は別用途・別管理であり、上記の削除対象ではありません。

## 管理者の事前確認は通るのに、参加者の `preflight.sh` が失敗する

`scripts/preflight.sh` は参加者とリソースグループを対象に、
管理者の確認だけでは分からない次の条件も調べます。
指定 RG の存在、参加者本人の **Owner** ロール、実際に選択されたリージョンでのモデルカタログの利用可否です。

- 参加者が指定した RG 名・サブスクリプション ID が、割り当てたものと一致しているか。
- `az login` でサインインしたアカウントが、**Owner** を付与した本人のものか。別アカウントやサービスプリンシパルではないか。
- プロバイダー登録とクォータの確認を、既定リージョンだけでなく、参加者が `--location` で指定した **同じリージョン**で行ったか。

## RG 内の操作なのに `terraform apply` が認可エラーで失敗する

Terraform は指定 RG の外やサブスクリプション全体への操作を行わないため、
管理者と参加者の両方の事前確認が通っていれば、通常は発生しません。
発生した場合は、次の原因を確認してください。

- RG に付与した **Owner** ロールがまだ反映されていない。Entra のロール反映には数分かかる場合があります。少し待ってから、再実行しても安全な `scripts/setup.sh` を実行してください。
- ロールの割り当て先が RG 自体ではなく、配下のリソースなど別の範囲になっている。

## `terraform destroy` 後もリソースが残っていると報告される

削除の順序は[料金とクリーンアップ](../costs-and-cleanup.md#クリーンアップの順序)を参照してください。
`terraform destroy` が成功したと報告されても、ハンズオン用タグの付いた Azure リソースが RG 内に残っている場合は、
**`.workshop/` の状態ファイルを削除せず**、`scripts/destroy.sh` を再実行してください。
既存の状態ファイルを使った Terraform の削除処理は、安全に再実行できます。

それでも残る場合は、`destroy.sh` が示したリソースとエラーを調査してください。
Terraform を介さずに手動で削除すると、ローカルの状態と実際の RG が食い違い、
後の再実行が難しくなるため避けてください。

`.workshop/context.json` が作成される前にセットアップが失敗した場合も、
通常どおり `./scripts/destroy.sh` を実行します。
セットアップはリソース作成前に、確定した機密情報を含まない Terraform の入力値を
`.workshop/terraform-inputs.json` に保存し、削除処理はこのファイルを自動で使います。

**両方のファイルが利用できない場合に限り**、元の入力値を明示して、
途中まで作成されたリソースを Terraform で削除します。

```bash
./scripts/destroy.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>" \
  --travel-api-image-ref "ghcr.io/<owner>/travel-ops-api@sha256:<digest>" \
  --location "<japaneast-australiaeast-or-centralus>" \
  --source-base "https://github.com/<owner>/<repo>/blob/main" \
  --primary-model-version "<version>" \
  --embedding-model-version "<version>" \
  --auto-approve
```

## 関連資料

- [管理者向け前提条件](prerequisites.md)
- [料金とクリーンアップ](../costs-and-cleanup.md)
- [アーキテクチャ](../architecture.md)

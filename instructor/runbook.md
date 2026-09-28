# 講師向けrunbook

## 開催前の確認

1. [管理者前提条件](../docs/admin/prerequisites.md)に従い、権限、Japan East の固定モデル、
   Search Basic、Codespaces の利用枠・ポリシーを確認します。
2. 同ガイドの公開チェックを済ませたテンプレートと教材の参照先を配布し、
   使用するサブスクリプションを案内します。
   参加者にモデル version・image digest・source SHA の手入力は求めません。
3. ローカル参加者には [Dev Container の前提条件](../docs/participant/environments/local-dev-container.md)を案内します。
4. 予算・alert、cleanup の担当、失敗時の連絡先を決めます。

## 実環境検証の範囲

開催前の通し検証は、参加者向け手順の全Lab（1〜9）、再デプロイ、cleanupを対象にします。
Azure / Codespaces の作成前に対象、課金、本人認証、実行する環境を確認します。
以下は受入条件であり、実施済みの結果ではありません。

開始時に教材・テンプレートのrevisionと各処理の待機上限を決めます。検証中に修正した場合は、
修正後の同一revisionで最初から通し直し、手順外の救済操作を要しないことを確認します。
CodespacesとローカルDev Containerの結果は分け、片方の成功を他方の確認済み根拠にはしません。
参加者向けに認められたLabの省略も、全Labの通し検証では省略しません。

実行結果と未実施の範囲はRepository外に記録します。CIやsimulated JSONは事前確認に使い、
実画面の成功とは区別します。費用・権限・認証などにより範囲を変更する場合は事前に了承を得て、
限定検証として報告します。
画像を追加する場合は、実画面で確認した公開可能な範囲だけを使います。

### Lab 1

[Lab 1](../labs/01-setup.md)に従い、環境作成から初期化までを確認します。

1. Azure Portal **Resource groups > Create** で専用 RG を **1 個手動作成**し、完了を確認。
2. **Deploy a custom template > Build your own template in the editor > Load file** で
   `infra/azuredeploy.json` を読み込み、**Save** 後に作成済み RG を選択。
3. Subscription / RG 以外は既定値。本人の実行は **Participant Object Id Override** が空欄、
   **Bootstrap Run Id** が `1` のまま **Review + create > Create**。
   **Enable Bootstrap Policy Exclusion** の既定値 **true** は承認済みのハンズオン環境向け。
   承認されていない環境や除外が不要な環境では **false** に変更し、有効時・無効時を区別して記録する。
   有効時は除外タグが Deployment Script と補助 Storage / ACI に渡り、
   RG・Foundry・Search などに付かないことも確認する。
4. Search seed、評価データ・rubric、validation を含む全体が **Succeeded**、
   `workshopContext.setup_status = complete` になることを確認。
5. `resourceOutputs`、`travelApiBaseUrl`、`foundryPortalUrl` が本人の環境を指すことを確認。
6. 同じ RG・参加者での再デプロイと、意図した `bootstrapRunId` 更新を確認。
   重複データを増やさず、失敗は明示されることを確認。

### Labs 2–6

同じ Prompt Agent を拡張します。Lab 4 は GitHub の共通 Skill ZIP を PC からアップロードし、
共通 OpenAPI の `servers[0].url` だけを本人の `travelApiBaseUrl` に変更します。

| Lab | 必須の実行と確認 |
|---|---|
| [Lab 2](../labs/02-prompt-agent.md) | Prompt AgentからSearchを呼び、回答と引用を確認します。 |
| [Lab 3](../labs/03-rag-foundry-iq.md) | Foundry IQを接続し、検索結果と回答の根拠を確認します。 |
| [Lab 4](../labs/04-tools-toolbox.md) | OpenAPIとSkillsを登録・公開し、Tool Searchから実際のtool呼び出しまでTraceで確認します。 |
| [Lab 5](../labs/05-evaluation.md) | 評価ジョブで7件を実行し、評価器ごとの結果・reason・Errorと、toolを使う行のTraceを確認します。 |
| [Lab 6](../labs/06-optimization.md) | 最適化ジョブを候補数1で実行し、完了後にbaselineとのスコア・変更内容・rubricの詳細を比較します。 |

評価データやrubricの登録確認だけでLab 5・6を完了としません。評価結果の **Partial** は、
採点できない行と原因を記録します。保護機能による遮断や回答のFailと、
未解消の実行エラーを区別し、後者が残る場合は未完了です。
実行中の処理は再送せず、状態と進捗を確認します。

Lab 6は、採用できる改善がなくても比較まで実施できれば完了です。改善案を採用する場合だけ
**Promote candidate** を実行し、接続・安全上の制約とLab 3・4の動作を再確認します。

### Labs 7–8

[Lab 7](../labs/07-agent-framework-harness.md)と[Lab 8](../labs/08-hosted-multi-agent.md)は、
Notebookでの実行とHosted環境での応答をそれぞれ確認します。

1. [Codespaces ガイド](../docs/participant/environments/codespaces.md)の
   **Code > Codespaces** から作成し、post-create と教材の配置を確認。
2. コンテナーの Terminal で本人が Azure CLI にサインイン。
   GitHub / Portal のログインと別であることを説明。
3. `notebooks/00-setup.ipynb` を **Python (Foundry Workshop)** で実行。
   subscription ID / RG 名から schema `2.0` の `.workshop/context.json` が作られることを確認。
4. Labs 7/8 を **Python (Foundry Hosted Agent)** で実行。
   Lab 7 は plain / Harness、Lab 8 は intake / policy / reviewer の sequential workflow。
   Lab 7はplanから同じsessionのexecuteへ進み、Skills、Tool Search、実toolの結果を確認し、
   未完了todosがなくなるまで確認します。planの成功だけでは完了にしません。
5. Lab 8はNotebook上でworkflowを実行した後、確認入力を伴うdeployを管理用venvで実行。
   Hosted AgentがactiveになったらPortalから呼び出し、応答が最後まで返ること、
   `policy_agent` の検索と3つのAgentの実行順をTraceで確認。
6. Trace比較・保存後のdeleteが確認入力を要求し、管理用venvで実行されることを確認。
7. ローカルでも clone → **Dev Containers: Reopen in Container** → 同じ共通手順を確認し、
   Codespacesとは別の結果として記録。

Lab 8 は Lab 7 の session state には依存しませんが、環境準備は必要です。

### Lab 9と終了判定

[Lab 9](../labs/09-observability-cleanup.md)でPrompt AgentとHosted AgentのTrace、
応答、所要時間、トークン使用量を比較してから、成果物の保存と下記のcleanupへ進みます。

結果はLab・実行環境ごとに記録します。

| 結果 | 判定 |
|---|---|
| 完了 | 必須操作と結果の確認を終え、未解消の実行エラーがありません。 |
| 未完了 | 実行したが受入条件を満たしていません。失敗箇所・原因の確度・再確認項目を残します。 |
| 未実施 | 課金・権限・本人認証などにより実行していません。必要な了承や前提条件を残します。 |
| 中断 | 待機上限や応答停止で確認を打ち切りました。最後の成功箇所と再開条件を残します。 |

SDKが返したタイムアウトと、検証者が待機を打ち切った中断を区別します。
全Lab・再デプロイ・cleanupが同一revisionで完了した場合だけ、通し検証完了と報告します。
費用抑制や安全上の理由で途中のcleanupが必要な場合は先に行い、未完了・未実施の結果を保持します。
cleanupの成功によって、残る検証項目を完了へ変更しません。

## 障害時の対応範囲

- 初期化失敗時は次の Lab へ進まず、同じ RG の診断・修復を行います。
- 403 は bootstrap と参加者の identity / scope を区別します。広い runtime role を追加しません。
- quota / Policy failure で model / region / security baseline を変更しません。
- 認証が本人操作を要求したら本人に引き継ぎます。コード・token の共有や代行保存は行いません。
- 対処は [管理者トラブルシューティング](../docs/admin/troubleshooting.md)を参照します。

## 片付けの確認

参加者ごとに [Lab 9](../labs/09-observability-cleanup.md) の順で確認します。

1. Notebook・結果を保存・Export。
2. Hosted Agent と全 versions の削除を確認。
3. Codespace を停止・削除。ローカルは教材のコンテナーだけ停止。
4. Azure Portal で本人の subscription / 専用 RG 名を照合。
5. **Delete resource group** を実行し、一覧から RG が消えたことを確認。

Deployment history の削除では resources は消えません。他人・共有環境は対象外です。

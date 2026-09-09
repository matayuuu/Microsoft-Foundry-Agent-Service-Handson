# 料金とクリーンアップ

## 料金の考え方

このハンズオンでは、小規模で短期間のみ使用し、可能な場合はゼロまでスケールできるリソースを
優先しますが、無料ではありません。開催前に必ず、対象リージョンの最新の Azure 料金を確認してください。

主な課金対象は次のとおりです。

- Azure AI Search Basic は、サービスが存在する間、課金されます。
- モデルの推論、埋め込み、評価判定モデル、Agent Optimizer はトークン単位で課金されます。
- Web Search と Code Interpreter には、モデルのトークンとは別に料金が発生します。
- エージェント型検索では、Search の検索トークンとモデルのクエリ計画トークンに課金される場合があります。
- Container Apps はゼロまでスケールできますが、リクエストや関連する Log Analytics への
  データ取り込みには料金が発生する場合があります。
- Application Insights と Log Analytics では、含まれる利用枠を超えて保持するテレメトリに課金されます。
- Codespaces は利用時間と保存ストレージが課金対象になり得ます。停止と削除は別です。
- Cloud Shell の計算環境は無料ですが、永続化用 Storage account / Azure Files の容量・操作には
  料金が発生します。`exit`、Web preview の閉鎖、ブラウザー終了では storage は消えません。

管理者向けの事前チェックでは、参加者数・チーム数から必要なモデル容量を計算します。
料金やリージョンごとの提供条件は変わるため、金額の見積もりは行いません。

## 料金を抑える方法

- 参加者またはチームごとに専用のリソースグループを使用します。
- Search Basic をレプリカ 1、パーティション 1 で使用します。
- Travel Ops API の最小レプリカ数は 0 のままにします。
- 実際に実行する評価データのサブセットと、Optimizer の候補数を少なくします。
- 本編では、Foundry IQ の推論レベルを Lab 3 で指定する **Medium** にし、不要に引き上げません。
- ラボに記載されているリクエストのみを使用します。
- 開催終了後、すぐにクリーンアップを実行します。

## クリーンアップの順序

次のコマンドを実行します。

```bash
./scripts/destroy.sh
```

対象リソースを確認し、削除を承認します。ハンズオン用の Foundry プロジェクト / アカウントと
その他の Terraform 管理リソースを削除しますが、リソースグループは残します。
[Lab 9](../labs/09-observability-cleanup.md) を参照してください。
Toolbox または Skill の参照が原因で削除に失敗した場合は、
[参加者向けのクリーンアップのトラブルシューティング](participant/troubleshooting.md#クリーンアップ)
に従ってください。

スクリプトは、次の順序で処理する必要があります。

1. `.workshop/context.json` を読み込み、選択したサブスクリプションとリソースグループを確認します。
   セットアップが早い段階で停止した場合は、Terraform 実行前に作成された復旧用ファイル
   `.workshop/terraform-inputs.json` を読み込みます。
2. Foundry SDK を通じて、ハンズオン用の Hosted Agent とそのバージョンを削除します。
3. 任意のデータプレーンのクリーンアップヘルパーが存在する場合は実行し、存在しない場合はその旨を報告します。
4. 既存の状態ファイルを使用して `terraform destroy` を実行します。
5. ハンズオン用のタグが付いたリソースが、リソースグループ内に残っていないことを確認します。
6. リソースグループ自体は残します。
7. 検証に成功した後にのみ、ローカルのコンテキストと状態ファイルを削除します。

上記は**教材 workload の削除**です。次に保存した Notebook や安全な結果を必要に応じて
PC にダウンロードし、準備時に選んだ
[Codespaces の停止](participant/environments/codespaces.md#stop) /
[Cloud Shell の終了](participant/environments/cloud-shell.md#stop) を行います。
Cloud Shellは設定を解除し、初回UIが**その回専用に自動作成したRG一式**だけを削除します。
既存Storageの代替を使った場合は、許可されたStorage account / File shareだけを扱います。
Cloud Shell storageはTerraform / `destroy.sh`の対象外であり、教材workload用RG、他用途・
他ユーザーのstorage、検証前からあるCloud Shell設定は削除しません。

クリーンアップが失敗した場合、Terraform の状態ファイルを削除しないでください。
スクリプトが報告した正確なリソースと操作を確認し、
[管理者向けのトラブルシューティング](admin/troubleshooting.md) に従ってください。
Cloud Shell の場合も、失敗中に share や HOME image を削除しないでください。
`setup.sh` は、Terraform がリソースを作成できるようになる前に
`.workshop/terraform-inputs.json` を書き込むため、通常は `destroy.sh` を引数なしで実行して、
途中まで進んだセットアップから復旧できます。セットアップのコンテキストファイルが
両方とも利用できない場合は、入力値を明示的に指定することもできます。

## 状態ファイルの取り扱い

すべての参加者が状態ファイル共有用のストレージアカウントにアクセスできるとは限らないため、
既定ではローカルの Terraform 状態ファイルを使用します。
Codespaces では永続ワークスペース、Cloud Shell では**保持を確認済みの HOME** 内の repository に保存します。
Git の管理対象から除外し、`.workshop`、Azure CLI キャッシュ、Jupyter の認証設定も機密情報として扱います。
cleanup 前に Codespace や Cloud Shell の storage / HOME image を削除しないでください。
Cloud Shell の永続 share は HOME を保持するためのもので、Terraform remote backend ではありません。
share へアクセスできる人は HOME image の秘密にもアクセスできる可能性があるため、ユーザーごとに分離します。
Terraform state や HOME 全体をスクリーンショット・配布用 ZIP に含めません。

主催者が状態ファイル用のストレージアカウントをプロビジョニングし、各参加者にデータプレーンの
アクセス権限を付与できる場合は、Azure Blob バックエンドのサンプルを選択できます。

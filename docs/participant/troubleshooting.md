# Participant troubleshooting

このページは**参加者**向けです。subscription 単位の操作が必要な問題は
[管理者向けトラブルシューティング](../admin/troubleshooting.md)に切り分けています。
迷ったときは、まず [Lab 0](../../labs/00-overview.md) の Portal/Toolkit/SDK 境界と
GA/Preview 状態の表で、今使っている機能が preview かどうかを確認してください。

## `preflight.sh` / `setup.sh`（Lab 1）

### `preflight.sh` が Owner ロール不足で失敗する

resource group 名・subscription ID が管理者から渡されたものと一致しているか、
`az account show` の `user.name` が管理者に Owner を付与してもらった Entra
アカウントと一致しているかを確認してください。一致していてもロール伝播に数分
かかることがあるため、数分待って再実行してください。それでも失敗する場合は
[管理者向けトラブルシューティング](../admin/troubleshooting.md)へ相談してください
— resource provider 登録や quota は subscription 単位の操作で、参加者自身では
解決できません。

### `setup.sh` が途中で失敗した

`setup.sh` はすべてのステップが idempotent です。エラーメッセージを読んで、
指摘された問題を直してから、**同じコマンドでそのまま再実行**してください。
Travel Ops API の既定 `v1.0.0` image が未公開の場合は、maintainer が
`publish-travel-api.yml` で GHCR package を Public にしてから再実行します。
管理者から immutable digest を受け取った場合だけ、
`--travel-api-image-ref ghcr.io/.../...@sha256:<64桁の16進数>` で上書きできます。
`terraform apply` は同じ状態に
収束し、データ投入は id ベースの merge-or-upload なので再実行しても安全です。

### `.workshop/context.json` に期待した output キーが無い

`jq '.terraform_outputs | keys' .workshop/context.json` で確認し、無ければ
`./scripts/setup.sh` を再実行して再生成してください（infra に変更があった
可能性があります）。

## Portal（Lab 2〜4、Lab 6）

### 見ている画面が手順と違う気がする

このハンズオンは Microsoft Foundry **new**（プロジェクトベースの新しい体験）
を対象にしています。古い「Azure AI Studio」「Foundry classic」（hub ベース）の
画面を開いていないか確認してください。project を開く際は、必ず
`.workshop/context.json` の `foundry_project_name` と一致する project を
選んでいるか確認してください。

### 手順に書かれた Portal の操作が見つからない

Portal の UI は継続的に更新されます。[feature-support-matrix.md](../feature-support-matrix.md)
に書かれている「Portal 対応」の記載が実際と異なる場合（新しく対応した、
または対応が外れた）は、いったん Toolkit/SDK での代替手順（各 Lab に記載）を
試し、後で報告してください。

### Foundry IQ の agentic retrieval が preview 表示のまま動かない

preview 機能のため、region や model の組み合わせによって挙動が制限されることが
あります。`primary_model_deployment_name`（`gpt-4.1`）を query planner に
指定しているか、reasoning effort が `low` になっているかを確認してください。
それでも解決しない場合は Lab 3 の「index を直接アタッチする」手順（Foundry IQ を
使わない単純検索）に一時的に切り替えて、他の Lab を先に進めてください。

### Agent Optimizer ウィザードで候補が生成されない・エラーになる

preview 機能です。`optimizer_model_deployment_name` の値が実際に project に
デプロイされている `gpt-5` 系 model と一致しているか確認してください。
それでも解決しない場合は、Lab 6 の「live 実行ができない場合」の節に従って、
講師が用意する説明・資料を参照しながら手順の流れを理解する形で進めてください。

## `create_toolbox.py` / `run_evaluation.py`（Lab 4・Lab 5）

これら 2 つのスクリプトは、失敗の原因を `WorkshopContextError` として
分かりやすいメッセージで標準エラーに出力し、終了コード 2（環境・入力の問題）
または 1（Azure 呼び出し自体の失敗）を返します。トレースバックではなく
メッセージ本文を読んでください。

### `context file not found` / `.workshop/context.json is not valid JSON`

Lab 1 の `setup.sh` をまだ実行していないか、実行したディレクトリと違う場所で
スクリプトを実行しています。リポジトリのルートで実行するか、
`--context <path>` で明示的にパスを指定してください。

### `terraform output '...' not found in .workshop/context.json`

infra に変更があった環境で `.workshop/context.json` が古いままの可能性があります。
`./scripts/setup.sh` を再実行してください。

### `could not fetch OpenAPI spec from https://.../openapi.json`（`create_toolbox.py`）

Travel Ops API（`travel_api_fqdn`）がまだ起動しきっていない可能性があります
（Container Apps はスケールツーゼロのため、初回アクセス時にコールドスタートが
発生します）。数十秒待ってから再実行するか、先に
`curl https://<travel_api_fqdn>/health` で疎通を確認してください。

### `evaluation run did not reach a terminal state within ...s`（`run_evaluation.py`）

評価の実行に既定のタイムアウトより時間がかかっています。Foundry portal の
Evaluations 画面で run の状態を直接確認するか、`--timeout` を大きくして
再実行してください。

### Foundry User ロールに関するエラー

`create_toolbox.py` / `run_evaluation.py` が呼び出す API はどちらも、参加者と
project の managed identity の両方に **Foundry User** ロールが必要ですが、
これは `infra/rbac.tf` によって `setup.sh` の時点ですでに付与されています。
権限エラーが出る場合は、ロール伝播待ちの可能性があるため数分待って再実行するか、
[preflight.sh](../../labs/01-setup.md) を再実行してロール状態を確認してください。

## Cleanup（Lab 8）

`./scripts/destroy.sh` の失敗時は [costs-and-cleanup.md](../costs-and-cleanup.md#cleanup-order)
の手順と、[管理者向けトラブルシューティング](../admin/troubleshooting.md)の
該当節を参照してください。**`.workshop/` の状態ファイルを手動で消さないで
ください** — 失敗した場合は残しておくことで、同じコマンドを安全に再実行できます。

## See also

- [Participant prerequisites](prerequisites.md)
- [Architecture](../architecture.md)
- [Feature support matrix](../feature-support-matrix.md)
- [Costs and cleanup](../costs-and-cleanup.md)
- [Administrator troubleshooting](../admin/troubleshooting.md)

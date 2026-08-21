# Lab 8 — Observability・governance・cleanup（10分）

## ゴール

これまでの Lab で作成した Prompt Agent と（Lab 7 で作成される）Hosted Agent の
トレースを Application Insights で観測し、preview・データ境界に関する注意点を
再確認したうえで、`./scripts/destroy.sh` の実際の手順に沿って環境を破棄します。

## 1. トレースを見る

`.workshop/context.json` の次の出力が、このプロジェクトに接続された
Application Insights を指しています。

- `application_insights_name` / `application_insights_id`
- `application_insights_connection_name`（Foundry project 側の connection 名）

Foundry portal の Traces（または同等の観測性メニュー）を開き、Lab 2〜Lab 6 で
Playground から送ったリクエストのトレースを確認してください。1 件のトレースで
次を確認できます。

- **トークン数**（入力／出力）とモデル呼び出しごとのレイテンシ。
- **ツール呼び出し**の span（Lab 4 で接続した Toolbox 経由の Travel Ops API
  呼び出しが、どのエンドポイント・引数で呼ばれたか）。
- Foundry IQ を経由した場合の agentic retrieval のステップ（Lab 3 の
  activity log と同じ情報が、トレースとしても残ります）。

Lab 7 で Hosted Agent をデプロイした場合、そのトレースも同じ Application
Insights に集約されます（Lab 7 の内容自体はこのファイルの範囲外です — 詳細は
Lab 7 の手順を参照してください)。

## 2. 評価結果との相関

Lab 5 の `run_evaluation.py` が出力した `eval_id` / `run_id` /
`report_url` と、上記のトレース一覧を突き合わせることで、「どの実際の
リクエスト（トレース）が、評価のどのケースに対応する応答だったか」を追跡できます。
評価が失敗と判定したケースがあれば、対応するトレースを開いてツール呼び出しや
検索結果の中身まで掘り下げて原因を確認してください。

## 3. Governance・preview・データ境界の再確認

このハンズオンで扱った preview 機能を再掲します（詳細は
[Lab 0](00-overview.md) と [feature-support-matrix.md](../docs/feature-support-matrix.md)）。

| 機能 | 状態 |
|---|---|
| Foundry IQ agentic retrieval（Lab 3） | Preview |
| Tool Search（Lab 4 で紹介のみ） | Preview |
| Prompt Agent Optimizer（Lab 6） | Preview |

データ境界に関する注意点も再確認してください。

- Web Search（Lab 4）は Microsoft の Data Protection Addendum の対象外で、
  データがコンプライアンス境界の外に転送されます。
- 本ハンズオンのすべてのデータ（規程文書、経費、旅程、評価データセット）は
  架空の合成データです。実データや個人情報を一切含めないでください。
- 生成された resource 名・エンドポイント・subscription ID などの参加者固有の
  値は、常に `.workshop/context.json` から取得してください（本文にハード
  コードしません）。

## 4. Cleanup（`./scripts/destroy.sh`）

`.workshop/context.json` があれば、`--subscription` / `--resource-group` /
`--travel-api-image-ref` は省略できます（ファイルから自動的に読み込まれます）。

```bash
./scripts/destroy.sh
```

このスクリプトは次の順序で実行されます（`docs/costs-and-cleanup.md` の
Cleanup order と同じ内容です）。

1. **SDK 管理オブジェクトの削除**: Terraform が管理しない data-plane
   オブジェクト（Hosted Agent version など）を、`scripts/` にある
   任意スクリプト（`delete_hosted_agent.py` / `delete_evaluation_runs.py` /
   `delete_toolbox_versions.py`）が存在すれば実行します。**存在しない
   スクリプトは黙ってスキップされるのではなく、スキップされた旨と、
   その種類のオブジェクトを手動確認する必要がある可能性が明示的に
   標準エラーへ出力されます。** 執筆時点で `delete_hosted_agent.py` は
   Lab 7 のワークストリームが追加する想定のスクリプトです。Lab 4/5 で
   SDK が作成した Toolbox version・evaluation run 自体を個別に削除する
   専用スクリプトは現時点で用意されていません — これらは次のステップの
   `terraform destroy` が Foundry project ごと削除することで、まとめて
   除去されます。
2. **`terraform destroy`**: `infra/` が管理するすべてのリソース
   （Foundry account/project、Search、Storage、Application Insights、
   Container Apps など）を削除します。Toolbox version・evaluation run は
   親の Foundry project の削除に伴って削除されます。
3. **ローカル状態の削除**: 上記 2 ステップがどちらも成功した場合にのみ、
   `.workshop/context.json` / `.workshop/.env` / `.workshop/tfplan` /
   `.workshop/preflight-report.json` を削除します。途中で失敗した場合は
   これらのファイルは残ります（Terraform state を安全に再利用できるように
   するためです）。

**resource group 自体は削除されません。** Terraform は最初から resource group
を data source として参照しているだけで、所有していないためです。

失敗した場合は Terraform state を消さず、
[管理者向けトラブルシューティング](../docs/admin/troubleshooting.md)に
報告されたリソースと操作の情報に従って対処してください。

## お疲れさまでした

これで Contoso 出張・経費支援シナリオを通した Microsoft Foundry Agent Service
のハンズオンは終了です。[README](../README.md) の設計方針と
[architecture.md](../docs/architecture.md) を振り返り、実際のプロジェクトに
応用する際の参考にしてください。

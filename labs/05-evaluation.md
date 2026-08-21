# Lab 5 — Agent evaluation（25分）

## ゴール

`scripts/run_evaluation.py` を使い、`contoso-travel-assistant`（Lab 3・Lab 4 で
Foundry IQ と Toolbox を接続した後の version）に対して、固定の評価データセット
`data/eval/live_subset.jsonl` を使った **agent-target** 評価を実行します。
Portal からは任意データセットでの評価実行はできないため（
[feature-support-matrix.md](../docs/feature-support-matrix.md)）、この Lab は
SDK 実行 → Portal での結果確認、という流れになります。

## 前提: Foundry User ロール

このスクリプトが呼び出す評価 API（`client.evals.*`、Azure AI Foundry の
OpenAI 互換 Evals API）を使うには、参加者と Foundry project の managed identity
の両方が AI Services account 上で **Foundry User** ロールを持っている必要が
あります。これは `infra/rbac.tf` によって `setup.sh` の時点で**すでに付与済み**
です — 追加のロール割り当ては不要です。

## 1. `run_evaluation.py` が行うこと

1. `data/eval/live_subset.jsonl` を読み込み、`data/schemas/eval_case.schema.json`
   に対して各行を検証します（スキーマ違反があれば Azure を呼び出す前に失敗します）。
2. そのファイルを Foundry データセットとしてアップロードします。version は
   ファイル内容の SHA-256 ハッシュから決まるため、内容が変わらない限り再実行しても
   同じ (name, version) を再利用します（重複アップロードなし）。
3. 手作りのルーブリック評価者（`policy_rubric`、4 つの評価軸: 規程への準拠
   `policy_grounding`、必要な場面での引用 `citation_when_required`、ツール利用の
   正しさ `tool_usage_correctness`、対応範囲・安全性の境界 `scope_and_safety_boundary`）
   を、既存かつ内容一致なら再利用、そうでなければ新しい version として作成します。
4. そのルーブリックと、意味のある組み込み評価者
   （`builtin.task_adherence` / `builtin.coherence` / `builtin.violence`）を
   組み合わせて評価（evaluation）を作成します。tool の選択・引数は rubric の
   `tool_usage_correctness` dimension で評価します。
5. **agent-target** の評価実行（run）を作成します —
   `data_source.type: "azure_ai_target_completions"` /
   `target.type: "azure_ai_agent"` を指定することで、評価サービス自身が
   データセットの各行を実際に agent へ送信し、応答を採点します（あらかじめ集めた
   応答を後から採点する方式ではありません）。
6. 有限のタイムアウト付きでポーリングします（無限ループにはなりません。既定の
   タイムアウトを超えると明示的なエラーで終了します）。
7. `report_url` と `result_counts`（total/passed/failed/errored）を出力します。

built-in 評価者のうち `builtin.violence`（コンテンツ安全性）は専用の安全性モデルを
使うため judge deployment の指定は不要です。それ以外はすべて
`--judge-deployment`（既定 `primary` / `gpt-4.1`）を LLM judge として使います。

> [!NOTE]
> 組み込み `builtin.tool_call_accuracy` は `tool_definitions` の入力が必須で、
> Azure AI Search/Web Search など一部 tool の support も限定的です。この Lab の
> agent-target dataset は tool schema を行ごとに持たないため、既定 evaluator には
> 含めません。OpenAPI function schema を dataset に追加する発展ラボで利用できます。

## 2. 実行する

```bash
.venv/bin/python scripts/run_evaluation.py --output json
```

主なオプション（`.venv/bin/python scripts/run_evaluation.py --help` で全体を確認できます）:

| オプション | 既定値 | 説明 |
|---|---|---|
| `--context` | `.workshop/context.json` | 構築済み環境のコンテキストファイル |
| `--dataset` | `data/eval/live_subset.jsonl` | 評価データセット |
| `--agent-name` | `contoso-travel-assistant` | 評価対象の Prompt Agent |
| `--agent-version` | (未指定 = 最新の published version) | 特定 version を固定したい場合 |
| `--judge-deployment` | `primary`（`gpt-4.1`） | ルーブリックと LLM 系 built-in の judge model |
| `--pass-threshold` | `0.6` | ルーブリック評価者の合格閾値 (0-1) |
| `--builtin-evaluators` | `builtin.task_adherence,builtin.coherence,builtin.violence` | 組み込み評価者のカンマ区切りリスト |
| `--poll-interval` / `--timeout` | スクリプトの既定値 | ポーリング間隔と有限タイムアウト |
| `--credential` | `azure-cli` | `az login` セッションのみ使用 |
| `--output` | `human` | `json` で機械可読出力 |

`--output json` を指定すると、次の形の JSON が得られます（値は実行ごとに変わります）。

```json
{
  "eval_id": "...",
  "run_id": "...",
  "status": "completed",
  "report_url": "https://...",
  "result_counts": {"total": 0, "passed": 0, "failed": 0, "errored": 0},
  "per_testing_criteria_results": [ ... ],
  "rubric_evaluator": {"name": "contoso-travel-rubric", "version": "..."},
  "dataset": {"name": "contoso-travel-eval-live-subset", "version": "..."}
}
```

`status` が `failed` になった場合や、タイムアウトに達した場合はスクリプトが
非ゼロの終了コードで終わり、`report_url`（分かる場合）や次に確認すべき箇所を
標準エラーに出力します。

## 3. Portal で結果を確認する

出力された `report_url` をブラウザで開くか、Foundry project の Evaluations
画面から直近の run を開きます。次を確認してください。

- ルーブリックの 4 軸と built-in 評価者ごとの pass/fail の内訳。
- `data/eval/live_subset.jsonl` の各ケースの `category` ごとに結果を見比べ、
  `multi_hop` や `tool_choice` のカテゴリで pass 率が高いことを確認します
  （Lab 2 の baseline だけの状態ではこれらは失敗しやすいカテゴリでした）。
- 失敗しているケースがあれば、その `expected_behavior` /
  `expected_citations` / `expected_tool_calls` と実際の応答を見比べてみてください。
  これは Lab 6 の Optimizer 実行時の判断材料にもなります。

## 4. 設計上の注意（なぜこの形なのか）

- このスクリプトは `openai.APIError` と `azure.core.exceptions.HttpResponseError`、
  および自前の `WorkshopContextError` だけを捕捉します。想定外の例外は握りつぶさず
  そのまま伝播させます。
- ペイロード構築（データセットのバージョニング、ルーブリック定義、
  `testing_criteria`、agent-target の `data_source`）とポーリングロジックは
  すべて純粋関数として実装されており、Azure に接続しなくても
  `tests/unit/test_run_evaluation.py` でテストできます。

## 次のステップ

[Lab 6 — Agent Optimizer](06-optimization.md) に進んでください。

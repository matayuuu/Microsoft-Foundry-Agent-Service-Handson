# Lab 6 — Agent Optimizer とバージョン比較（20分）

## ゴール

Prompt Agent Optimizer の Portal ウィザードで `contoso-travel-assistant`
（Lab 2 の baseline instructions のまま）を最適化し、生成された候補
（candidate）を Lab 5 の評価結果と比較し、良いものを新しい version として
昇格（promote）します。

> [!WARNING]
> **Preview**: Agent Optimizer は preview 機能で、SLA なしで提供されています。
> 本番ワークロードでの利用は推奨されません。ウィザードの画面構成や挙動は
> 今後変わる可能性があります。
>
> **最適化の実行中、agent は実際にツールを呼び出します**（Lab 4 で接続した
> Travel Ops API の Toolbox を含む）。本ハンズオンの Travel Ops API は状態を
> 持たない決定的なモックなので副作用の心配はありませんが、これは一般に
> 「本番 API やコストが発生する外部サービスに接続したまま最適化を実行すると、
> 評価のたびに実際の呼び出しが発生する」という preview の重要な注意点です。

## 1. 最適化ウィザードを開く

Foundry portal で `contoso-travel-assistant` を開き、**Optimize** タブから
**Create optimization run** を選びます。

## 2. Target ステップ

- **Agent version**: baseline（Lab 2〜4 を経た現在の最新 version。既定で選択されています）
- **Optimization model**: `.workshop/context.json` の
  `optimizer_model_deployment_name` 出力（`preflight.sh` が発見した、実際に
  利用可能な `gpt-5` 系 model。Optimizer がサポートするのは `gpt-5` /
  `gpt-5.1` / `gpt-5.2` / `gpt-5.4` / `gpt-5.5` などの `gpt-5` ファミリーです）
- **Evaluation model**: `primary_model_deployment_name`（`gpt-4.1`）
- **Maximum number of candidates**: 小さい値（**2〜3 件**）にしてください。
  候補数が多いほど実行時間とコストが増えます。
- **Compare across models**: このハンズオンでは OFF のままで構いません
  （時間短縮のため）。

## 3. Dataset ステップ

次のいずれかを選びます。

- Lab 5 で `run_evaluation.py` がアップロード済みの Foundry dataset
  （名前 `contoso-travel-eval-live-subset`）を**既存データセットとして選択**する。
- または `data/eval/live_subset.jsonl` を直接アップロードする。

> [!NOTE]
> ウィザードは列名のマッピング機能を持たないため、選択した評価者（evaluator）
> が要求する列名と、データセットの列名が一致している必要があります。
> `data/eval/live_subset.jsonl` の列（`query`、`expected_behavior`、
> `ground_truth` など）は `data/schemas/eval_case.schema.json` に固定されて
> おり、Lab 5 のルーブリック評価者もこの列名を前提に作られています。

## 4. Criteria ステップ

- Lab 5 で作成したカスタムルーブリック評価者 `contoso-travel-rubric` を選択します
  （custom evaluator として一覧に表示されます）。
- 加えて、組み込み評価者（built-in evaluator）を 1〜2 個選びます。Lab 5 と
  同じ観点を使うなら `task_adherence` や `coherence` が扱いやすい候補です。
- 各評価者がデータセットのスキーマと互換であることを確認してから次に進みます。

## 5. Review ステップとコスト見積もり

Review 画面には **Minimum / Estimated / Maximum** の3段階でコスト見積もりが
表示され、内訳（Running your agent / Scoring responses / Generating
improvements）も展開できます。

> [!IMPORTANT]
> この見積もりは**モデル化された範囲であり、支出上限や確定金額ではありません**。
> 前提となる計算方法や除外事項を確認してから Submit してください。

内容（agent とバージョン、データセット、評価者、候補モデル）を確認し、
**Submit** します。実行時間はデータセットサイズ・候補数・選択したモデルに
依存します。

## 6. 結果を比較する

実行が完了したら、各候補のスコア（0.0〜1.0 の合成スコア）を baseline と比較し、
instructions の before/after の差分、評価者ごとのスコアを確認します。

**スコアの読み方の目安**:

- baseline に対して**明確な改善**があり、トークン使用量やコストの増加が
  許容範囲内の候補を選びます。
- **すべての候補が baseline を下回った場合は、現在の agent をそのまま維持
  してください。** データセット・評価者・最適化設定を見直してから再実行する
  ことが推奨されています — 無理に低いスコアの候補を昇格させる必要はありません。

## 7. 候補を昇格し、テストする

良い候補が見つかったら、**Promote candidate** → 対象候補を選択 → baseline
との score 改善を確認 → **Promote to agent version** の順で、新しい
Prompt Agent version を作成します。

昇格しただけでは、pinned version 運用の agent には自動的にトラフィックが
流れません。Playground で新しい version を明示的に開いてテストし、Lab 2 で
弱点として観察した質問（multi-hop、tool_choice、out_of_scope など）が
改善しているかを確認してください。

## live 実行ができない場合

Optimizer は preview 機能のため、region やモデルの組み合わせによっては
ウィザードの一部操作が制限されることがあります。当日 live 実行が難しい場合は、
講師が別途用意する事前収録のデモ・スクリーンショット等の instructor 資料
（本リポジトリでは別ワークストリームが今後追加します）を参照し、
ウィザードの流れ自体はこの Lab の説明で理解を進めてください。

## 次のステップ

Lab 7（Hosted Agent／Microsoft Agent Framework）に進んでください。その後
[Lab 8 — Observability・cleanup](08-observability-cleanup.md) で全体を締めくくります。

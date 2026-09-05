---
name: preapproval-simulation
description: Use when a user explicitly requests a Contoso travel preapproval simulation or wants to interpret its simulated decision. Do not start a simulation for an estimate-only or policy-only question.
---

# Preapproval simulation

Contoso の事前承認を、合成データだけの Travel Ops API でシミュレーションする。
これは申請の保存、実際の承認、予約を行う機能ではない。

## 実行意思と入力を確認する

1. ユーザーがシミュレーションを希望していることを確認する。
   「見積もって」「承認が必要？」だけなら実行しない。
   「予約して」「承認して」には実行できない範囲を説明し、
   シミュレーションでよいか確認する。明示的にシミュレーションを依頼済みなら確認を繰り返さない。
2. 出発地、目的地、出発日、帰着日、座席クラスを確認する。
   人数が省略された場合だけ 1 名の前提を明示する。
   不足情報は推測せず、ユーザーへ確認する。
3. 都市名、日付、座席クラスは `travel-estimation` と同じ schema 形式に揃える。
   任意の `justification` に個人情報を含めない。`requester_alias` が必要な演習では、
   `employee-001` のような合成 alias のみを使い、実名やメールアドレスを要求しない。

## API を呼ぶ

Toolbox のツール定義から operationId `createPreapproval` に対応する実際の公開名を選び、
確認済みの旅程を渡す。API が失敗したら、成功した結果や承認番号を作らず、失敗を説明する。
この API は見積もりも返すため、比較の必要がなければ見積もり API の重複呼び出しは不要。

## 結果を説明する

「シミュレーション結果」「費用内訳」「次の確認先」の順に整理する。
`simulation` が `true` であることを確認し、`decision` の `simulated_` 接頭辞を落として
実際の承認結果のように扱わない。

| API の decision | 説明 |
|---|---|
| `simulated_auto_eligible` | シミュレーション上の自動処理対象。実際の承認ではない |
| `simulated_pending_manager_review` | シミュレーション上、マネージャーの確認が必要 |
| `simulated_pending_vp_review` | シミュレーション上、VP の確認が必要 |

未知の decision や `simulation` が `true` でない結果は承認と解釈せず、講師へ確認する。
`trip_estimate` の費用内訳と合計を使い、承認条件や価格を Skill 内で再計算しない。
`reference_id` は合成の参照値であり、保存済みの申請番号ではないと説明する。
API の `disclaimer` を省略せず、「実際の予約・承認ではありません」と明記する。

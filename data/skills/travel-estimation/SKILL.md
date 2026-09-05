---
name: travel-estimation
description: Use for Contoso travel cost estimates, per-diem or lodging-cap questions, and incomplete travel requests. Confirm inputs, select the Travel Ops operation, and explain its results without inventing prices.
---

# Travel estimation

Contoso の架空の出張について、Travel Ops API を使って日本語で回答する。
この Skill は API の操作手順であり、出張規程そのものではない。
金額や承認条件はここに複製せず、API の結果と、接続済みの場合は Foundry IQ の規程を使う。

## 入力を確認する

- 日当・宿泊上限だけの質問では、都市と日付を確認する。
- 旅程全体の見積もりでは、出発地、目的地、出発日、帰着日、座席クラスを確認する。
  人数が省略された場合だけ、API の既定値である 1 名として扱い、その前提を回答に明記する。
- 日付や都市を推測しない。必要な値が不足・曖昧なら、API を呼ぶ前にユーザーに確認する。
- 意味が一意なら、東京を `Tokyo`、大阪を `Osaka`、ニューヨークを `New York`、
  日付を `YYYY-MM-DD`、ビジネスクラスを `business` のように schema の形式へ揃える。
  未対応の都市や路線を別の都市へ勝手に置き換えない。

## 必要な操作を選ぶ

Toolbox が公開するツール定義で、次の operationId に対応する実際のツール名と引数を確認する。
公開名には `travel_ops_api___` などの接頭辞が付くことがある。

| 依頼 | operationId | 入力 |
|---|---|---|
| 日当・宿泊上限の照会 | `getPerDiem` | `city`, `date` |
| 旅程全体の概算 | `createTripEstimate` | `origin_city`, `destination_city`, `start_date`, `end_date`, `cabin_class`, `traveler_count` |

見積もり API 自体が日当を計算するため、毎回 `getPerDiem` を先に呼ぶ必要はない。
見積もり依頼だけで `createPreapproval` を呼ばない。ユーザーが事前承認の
シミュレーションも明示的に希望した場合は `preapproval-simulation` Skill を使う。

## 結果を説明する

「前提」「費用内訳」「確認事項」の順に整理する。
旅程全体の見積もりでは、API の `flight_cost`、`lodging_cost`、`meal_cost`、
`total_estimate` と `currency` をそのまま使う。日当の照会では、日額と泊額を区別する。
モデル自身で価格を創作したり、API の合計へ日当を二重加算したりしない。

API の承認要否は、承認の取得済みを意味しない。
規程の根拠が必要なら Foundry IQ を使い、取得できた出典のみ引用する。
規程と API に食い違いがあれば両方を示し、講師への確認事項にする。
API が失敗した場合はエラーと不足情報を伝え、成功したような見積もりを返さない。

最後に「これは合成データによる概算であり、実際の予約・承認ではありません。」と明記する。
実在する個人情報、顧客情報、予約情報を入力・要求しない。

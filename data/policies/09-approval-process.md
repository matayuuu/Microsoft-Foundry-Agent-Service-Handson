---
id: policy-approval-process-001
title: 承認プロセスに関する規程
category: approval_process
effective_date: 2026-04-01
applies_to:
  - all_employees
  - managers
  - department_vps
source_url: "{{WORKSHOP_SOURCE_BASE}}/data/policies/09-approval-process.md"
---

# 承認プロセスに関する規程

## 事前承認が必要なケース

| 条件 | 必要な承認 |
|---|---|
| 国際出張（すべて） | 予約前にマネージャーの事前承認 |
| 国内出張で見積総額が 100,000 円以下 | 事前承認不要（事後レビューのみ） |
| 国内出張で見積総額が 100,000 円を超える | 予約前にマネージャーの事前承認 |
| ビジネスクラスの利用 | マネージャーおよび部門 VP の事前承認（両方必須） |
| ファーストクラスの利用 | 原則不可。[アクセシビリティ・例外対応](08-accessibility-exceptions.md)に定める例外のみ、HR・Travel Ops・部門 VP の三者承認 |
| 宿泊費上限の超過 | 予約前にマネージャーの事前承認 |
| ハイリスク渡航先への渡航 | Travel Ops チームおよび Contoso Travel Safety Desk の事前承認 |

見積総額は、フライト・宿泊・日当の合計見積額を指します。
Travel Ops API の `POST /trip-estimates` が返す `total_estimate` を
基準としてください。

## 事前承認の申請方法

- 事前承認は Contoso Travel Portal の「事前承認リクエスト」機能から
  申請します。本ハンズオンでは、この申請フローを
  `POST /preapprovals` エンドポイントでシミュレートします。
- **重要**: このハンズオン環境の `POST /preapprovals` は教材用の
  シミュレーションであり、実際の承認権限を持ちません。実際の出張では
  必ず Contoso Travel Portal を通じて正式な承認を得てください。

## 承認 SLA

- マネージャー承認: 申請から 2 営業日以内に判断します。
- 部門 VP 承認: マネージャー承認後、2 営業日以内に判断します。
- SLA 内に判断がない場合は、Travel Ops チームへエスカレーションできます。

## 承認後の変更

- 承認後に出張内容（座席クラス、宿泊都市、日程）が変更になった場合、
  見積総額が 10% 以上増加するときは再承認が必要です。

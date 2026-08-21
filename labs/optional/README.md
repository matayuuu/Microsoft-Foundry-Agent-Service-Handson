# 選択ラボ（Optional labs）

このディレクトリは、[Lab 0〜Lab 8](../00-overview.md) の 3 時間 50 分の本編には**含まれない**
選択（optional）教材です。追加のライセンス、追加の Azure/Microsoft 365/Fabric テナント権限、
または preview 機能の管理者設定が必要になるため、本編の参加者体験からは意図的に切り離されて
います（[README の「Core と optional の境界」](../../README.md#core-と-optional-の境界)、
[architecture.md の「Resource ownership」](../../docs/architecture.md#resource-ownership)
を参照）。

> [!IMPORTANT]
> 本編のセットアップ（`./scripts/setup.sh`）・Terraform（`infra/`）・コアスクリプト
> （`scripts/deploy_hosted_agent.py` など）は、このディレクトリのどのラボからも
> **変更されません**。ここに書かれた手順を実施しなくても、本編の Lab 0〜Lab 8 と
> `./scripts/destroy.sh` によるクリーンアップは完全に成立します。
>
> 反対に、本編の resource group **Owner** ロールだけでは、Fabric IQ・Work IQ・
> Teams/Microsoft 365 publish のいずれも準備できません。それぞれ Fabric 容量管理者・
> Microsoft 365 テナント管理者・Entra Global Administrator など、**本編とは別の管理者**
> による事前準備が必要です。詳細は各ラボの「前提条件」を必ず読んでください。

## 対象読者

- 本編を完走し、時間と管理者権限に余裕がある参加者。
- 本編の後に、実際の組織導入を検討する際の論点を把握したい参加者。
- 事前収録デモやフォールバック資料を用意したい講師（[instructor/](../../instructor/README.md)
  も参照）。

## ラボ一覧

| ラボ | 内容 | 状態 | 追加で必要なもの |
|---|---|---|---|
| [Fabric IQ](fabric-iq.md) | Contoso 出張・経費データを Fabric の ontology / Fabric data agent / Power BI semantic model として公開し、Foundry agent から自然言語で問い合わせる | Preview | Fabric 容量（有償 F2 以上または Power BI Premium P1 以上）、Fabric 管理者、Foundry User + Foundry Project Manager ロール |
| [Work IQ](work-iq.md) | Foundry agent から Microsoft 365 Copilot の Work IQ を A2A 経由で呼び出す（架空プロンプトのみ） | Public preview | Copilot Credits の従量課金 または コネクタライセンス、Entra Global Administrator による 1 回限りのテナント設定 |
| [Advanced Hosted Agent](advanced-hosted-agent.md) | Lab 7 の source deploy に加え、ACR コンテナデプロイ・カスタムパッケージ・複数プロトコル・Tool Search・Skills を扱う | GA/Preview 混在 | Azure Container Registry（任意）、`azd` Foundry 拡張機能 |
| [A2A・Routines・Publish](a2a-routines-publish.md) | Foundry agent を A2A エンドポイントとして公開し、Routines で定期実行し、Teams/Microsoft 365 に publish する | Preview（A2A・Routines） | Entra アプリ登録、Azure Bot Service Contributor、Microsoft 365 管理者承認 |
| [CI/CD と継続評価](cicd-continuous-evaluation.md) | GitHub OIDC（フェデレーション ID）を使った、クライアントシークレットなしの CI/CD 設計と継続評価ゲート | 設計ドキュメントのみ（実働ワークフローなし） | GitHub リポジトリの OIDC 設定、最小権限のロール割り当て |
| [azd 付録](azd-appendix.md) | `azd auth login` と `microsoft.foundry` 拡張機能を使った、Hosted Agent のもう一つのデプロイ経路 | GA/Preview 混在 | `azd` 本体、`microsoft.foundry` 拡張機能 |

## 読む順序

明確な依存関係はありませんが、初めて読む場合は次の順序を推奨します。

1. [Fabric IQ](fabric-iq.md) / [Work IQ](work-iq.md) — 本編 Lab 4 の Toolbox の延長として、
   外部データソースをツール化する追加パターン。
2. [Advanced Hosted Agent](advanced-hosted-agent.md) — 本編 Lab 7 の source deploy の延長。
3. [A2A・Routines・Publish](a2a-routines-publish.md) — Advanced Hosted Agent で有効化した
   protocol を Teams/Microsoft 365 に配布する話。
4. [CI/CD と継続評価](cicd-continuous-evaluation.md) — ここまでの手動運用を自動化する設計。
5. [azd 付録](azd-appendix.md) — 独立して読める補足。

## 共通の注意事項

> [!WARNING]
> - 本ディレクトリのラボはすべて**架空の Contoso シナリオ**のみを扱います。実データ・
>   実在の個人情報・実際の Microsoft 365 データへのアクセスを前提とした手順は一切
>   含みません。
> - Fabric IQ・Work IQ はいずれも、接続した瞬間からモデルのトークン課金とは別の料金が
>   発生し得ます。また、データが Azure のコンプライアンス境界の外に送信される場合が
>   あります。[feature-support-matrix.md](../../docs/feature-support-matrix.md) と
>   各ラボの警告を必ず確認してください。
> - 本ディレクトリの手順を実行して作成した Azure/Fabric/Microsoft 365 側のオブジェクト
>   （Foundry connection、Fabric ワークスペースの item、Azure Bot Service、Teams app
>   registration など）は、`./scripts/destroy.sh` の対象**外**です。作成した場合は
>   各ラボの cleanup 節に従って、参加者自身（または該当する管理者）が個別に削除して
>   ください。

## 関連リンク

- [Lab 0 — 全体像とルール](../00-overview.md)
- [architecture.md](../../docs/architecture.md)
- [feature-support-matrix.md](../../docs/feature-support-matrix.md)
- [instructor/README.md](../../instructor/README.md)

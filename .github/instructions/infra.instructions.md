---
description: Bicep 正本、生成 ARM、Deployment Scripts の整合を維持する規約。
applyTo: "infra/**,scripts/bootstrap_custom_template.py,scripts/bootstrap-custom-template.sh,scripts/check_template_artifact.py"
---

# テンプレートと初期化の変更

- 作業前に [インフラ実装ガイド](../../infra/README.md) と
  [AGENTS の環境作成条件](../../AGENTS.md#環境作成で守る条件) を確認します。
  モデル・容量・接続名などの値は `infra/main.bicep` を正本とし、指示ファイルに複製しません。
- `infra/azuredeploy.json` は生成物です。直接修正せず、Bicep の変更後に
  `make bicep-build` で再生成し、`make bicep-validate` で一致を確認します。
  実行環境と固定コンパイラーは [開発者向けガイド](../../docs/development/README.md) に従います。
- リリース既定値を変える場合は、パラメーター例・管理者向け文書・生成 ARM を揃えます。
  ソース SHA とイメージのダイジェストは公開済みの値を確認し、未公開の値を推測しません。
- 初期化用 ID と参加者 ID を分離し、既存 RG 内の対象に限定した RBAC を維持します。
  リソース名・ロール割り当て・再実行時の冪等性を保ちます。
- 初期化の失敗・再試行上限をデプロイ結果へ伝え、完了前の接続情報を成功として公開しません。
  `resource_outputs` の契約と関連テストを同時に確認します。
- コンパイルと契約テストはデプロイ成功の証明ではありません。
  実デプロイ・権限変更・削除は静的検証に混ぜず、既存 runbook と承認範囲に従います。

# 参加者向け前提条件

開始前に、次を確認してください。

## 必要なもの

- GitHub Codespaces を利用できる GitHub account
- 管理者から指定された Azure subscription ID
- 管理者から割り当てられた**既存** resource group
- その resource group に対する **Owner** role
- Azure に sign-in できる account

Codespace には Python、Azure CLI、Terraform、Foundry Toolkit が用意されています。
Docker、API key、client secret は不要です。

## 管理者が事前に行うこと

参加者ではなく、subscription 管理者が次を準備します。

- 必要な resource provider の登録
- Model quota / capacity の確認
- 参加者への resource group Owner role の付与

詳細は[管理者向け前提条件](../admin/prerequisites.md)を参照してください。

## 参加者が行わないこと

- Resource group の作成・削除
- Resource provider の登録
- Subscription scope の role assignment
- Quota や Azure Policy の変更
- Service principal、client secret、API key の作成

これらを求めるエラーが出た場合は、権限を増やそうとせず管理者へ連絡してください。

## 開始前の確認

```bash
az login --use-device-code

./scripts/preflight.sh \
  --subscription "<subscription-id>" \
  --resource-group "<resource-group>"
```

`overall_status` が `pass` なら準備完了です。

## 次のステップ

[Lab 0 — 全体像と進め方](../../labs/00-overview.md)

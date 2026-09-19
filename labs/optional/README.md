# 追加演習

本編 Lab 1〜9 の完了後に、組織の許可と追加費用を確認して実施します。
本編の RG 手動作成 → カスタムテンプレート → GitHub 共通教材・Codespaces を置き換える準備手順ではありません。
追加インフラを伴う付録は別の承認済み検証環境で実施し、本編の固定構成を変更しません。

| Lab | 追加要件 |
|---|---|
| [Hosted Agent の応用](advanced-hosted-agent.md) | コンテナーレジストリと追加の片付け |
| [azd の付録](azd-appendix.md) | `azd` と独立した環境の作成・削除 |
| [CI/CD と継続的評価](cicd-continuous-evaluation.md) | GitHub Actions、フェデレーション ID、承認環境 |
| [A2A・定期実行・公開](a2a-routines-publish.md) | Preview 機能、チャネル、定期実行の権限 |
| [Fabric IQ](fabric-iq.md) | Microsoft Fabric の容量、ワークスペース、接続 |
| [Work IQ](work-iq.md) | Microsoft 365 Copilot と組織データ権限 |

追加リソースは、本編の専用リソースグループを削除しても残る場合があります。
各ページの片付けを先に実施し、課金対象が残っていないことを確認してください。
実在データ、秘密情報、本番環境への接続を、演習の合成データと混在させません。

# Optional labs

本編 Lab 0〜9 の完了後に、組織の許可と追加費用を確認して実施します。
本編の RG 手動作成 → custom template → private ZIP 取得の代替 setup ではありません。
追加インフラを伴う付録は別の承認済み検証環境で実施し、本編の固定構成を変更しません。

| Lab | 追加要件 |
|---|---|
| [Advanced Hosted Agent](advanced-hosted-agent.md) | container registry と追加 cleanup |
| [azd appendix](azd-appendix.md) | `azd` と独立した environment lifecycle |
| [CI/CD continuous evaluation](cicd-continuous-evaluation.md) | GitHub Actions、federated identity、承認環境 |
| [A2A / routines / publish](a2a-routines-publish.md) | preview / channel / routine permissions |
| [Fabric IQ](fabric-iq.md) | Microsoft Fabric capacity、workspace、connection |
| [Work IQ](work-iq.md) | Microsoft 365 Copilot と組織データ権限 |

optional resources は本編の専用 resource group cleanup に含まれるとは限りません。
各ページの cleanup を先に実施し、課金対象が残っていないことを確認してください。
実在データ、secret、production connection を workshop の合成データと混在させません。

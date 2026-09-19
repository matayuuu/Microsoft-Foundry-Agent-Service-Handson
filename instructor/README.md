# 講師向けガイド

本編は **専用 RG の手動作成 → custom template / 初期化 → Foundry Portal →
GitHub Codespaces** の順です。ローカル参加者も同じ Dev Container を使います。

開催前に [runbook](runbook.md)、[参考結果](completed-run-assets/README.md)、
[管理者向け前提条件](../docs/admin/prerequisites.md)、
[費用と片付け](../docs/participant/costs-and-cleanup.md) を確認します。
教材を変更する場合は [開発者向けガイド](../docs/development/README.md)、
参加者への案内は [資料一覧](../docs/README.md) を参照してください。

## 開催時間の計画

時間配分の正本は [README の時間表](../README.md#演習一覧) です。Lab 1を除く進行用の目安として扱います。
Lab 1を含む実測済みの開催時間として案内しないでください。
開催前に runbook に従って使用するリビジョン・環境で実行し、初期化、コンテナー準備、
評価・最適化・デプロイの待機、参加者の操作、片付けにかかった時間を区別して記録します。
記録は実行証跡と同じく Repository 外に保持します。

| 開催方法 | 案内する内容 |
|---|---|
| Lab 1を事前に実施 | 実施期限、成功の確認方法、開始時刻までの課金・保持期間、片付け担当。当日は環境の準備完了を確認してLab 2へ進みます。 |
| Lab 1を当日に実施 | 初期化待ちを含む準備枠と、実測に基づく対応余裕を演習枠に追加します。Lab 1の成功後にLab 2へ進みます。 |

どちらを採用するかは開催案内に明記します。時間表の見直し時は日本語・英語の README を同時更新し、
省略や実行待ちを隠して全 Lab の通し検証が完了したように扱わないでください。

## 確認すること

- 参加者の subscription、専用 RG 名、作成・削除・role assignment の権限
- 固定モデル / Search Basic の利用枠と、既定値設定済みテンプレート
- RG の作成完了後にテンプレートを開き、Subscription / 作成済み RG だけを選ぶ順序
- Search・評価データの準備と validation の成功、`workshopContext.setup_status = complete`
- Lab 4 の GitHub Skill ZIP、共通 OpenAPI と本人の `travelApiBaseUrl`
- Codespaces / Dev Container の準備、本人の Azure CLI サインイン、`00-setup.ipynb` と 2 カーネル
- 保存 → Hosted Agent versions → Codespace 停止・削除 → 専用 RG の削除確認

本編の安全上の注意を開始時に説明してください。
実 UI の操作結果と参考資料を区別し、simulated assets を成功証拠にしません。

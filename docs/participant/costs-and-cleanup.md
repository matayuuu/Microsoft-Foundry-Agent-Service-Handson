# 費用と片付け

[資料一覧](../README.md) / [Lab 9 の操作手順](../../labs/09-observability-cleanup.md)

## 課金対象

- Foundry のモデル推論、評価、最適化、Hosted Agent
- Azure AI Search Basic、Container Apps、Application Insights / Log Analytics
- Deployment Scripts の実行
- Code Interpreter / Web Search などの利用したツール
- Codespaces の稼働時間とストレージ（アカウントの利用枠・課金設定による）

ブラウザーを閉じても Azure のリソースは残ります。Codespace は停止後もストレージが残ります。
管理者は利用枠、予算・アラートを確認し、実行中の処理を重複送信しないよう案内します。
この教材の評価は 7 件、最適化候補は 1 件です。

## 片付けの順序

1. Notebook と必要な結果を保存・エクスポートします。
2. Notebook から Hosted Agent と全バージョンを削除します。
3. Codespace を **Stop codespace**、続けて **Delete**。ローカルの場合は教材のコンテナーを停止。
4. Azure Portal で自分のサブスクリプションと専用 RG 名を確認します。
5. **Delete resource group** で RG と残る演習リソースをまとめて削除します。
6. **Resource groups** 一覧から対象 RG が消えたことを確認。

**Deployments の履歴を消してもリソースは残ります。**
保存と Hosted Agent / Codespace の片付けは RG 削除より先に行います。
失敗したデプロイの部分リソースも課金される場合があります。
他参加者の RG、共有リソース、無関係なローカル環境は対象外です。

画面操作は [Lab 9](../../labs/09-observability-cleanup.md)、初期化の実行基盤の詳細は
[インフラ実装ガイド](../../infra/README.md) を参照してください。

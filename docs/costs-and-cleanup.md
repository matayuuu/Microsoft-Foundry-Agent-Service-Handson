# 費用と cleanup

## 課金対象

- Foundry の model inference、evaluation、optimizer、Hosted Agent
- Azure AI Search Basic、Container Apps、Application Insights / Log Analytics
- Deployment Scripts の実行
- Code Interpreter / Web Search など利用した tools
- Codespaces の稼働時間とストレージ（アカウントの利用枠・課金設定による）

ブラウザーを閉じても Azure resources は残ります。Codespace は停止後もストレージが残ります。
管理者は利用枠、予算・alert を確認し、実行中の処理を重複送信しないよう案内します。
この教材の評価は 7 件、optimizer candidate は 1 です。

## Cleanup order

1. Notebook と必要な結果を保存・Export。
2. Notebook から Hosted Agent と全 versions を削除。
3. Codespace を **Stop codespace**、続けて **Delete**。ローカルの場合は教材のコンテナーを停止。
4. Azure Portal で自分の subscription / 専用 RG 名を確認。
5. **Delete resource group** で RG と残る workshop resources をまとめて削除。
6. **Resource groups** 一覧から対象 RG が消えたことを確認。

**Deployments の履歴を消しても resources は残ります。**
保存と Hosted / Codespace の cleanup は RG 削除より先に行います。
失敗したデプロイの部分リソースも課金される場合があります。
他参加者の RG、共有 resources、無関係なローカル環境は対象外です。

画面操作は [Lab 9](../labs/09-observability-cleanup.md)、初期化の実行基盤の詳細は
[infra/README.md](../infra/README.md) を参照してください。

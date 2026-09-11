# 費用と cleanup

## 課金対象

- Foundry model inference、evaluation、optimizer、Hosted Agent
- Azure AI Search Basic、Container Apps、Application Insights / Log Analytics
- Azure ML workspace backing resources と稼働中 Compute instance
- private 教材 ZIP の Blob Storage
- Deployment Scripts の一時 ACI / Azure Files Storage
- Code Interpreter / Web Search など利用した tools

browser close、Compute Stop、deployment history の削除は resource deletion ではありません。
価格は subscription、サービス、利用量に依存するため、管理者が当日の見積もりと予算を確認します。
Lab 1 の新経路の所要時間は未計測で、旧実測値に基づく費用や時間は約束しません。

## Cost controls

- RG は 1 個だけ手動作成し、template は既存 RG に限定して deploy。
- template は Compute を作らず、**Lab 7** 直前に **Standard_DS3_v2** + **Idle shutdown**。
- evaluation は 7 synthetic rows、optimizer candidate は 1。
- In progress の run / model call / deployment を重複送信しない。
- `bootstrapRunId` は意図した retry 時だけ変更。
- `OnSuccess` で一時 supporting resources を cleanup、失敗時は `P1D` の有限保持。
- 管理者は budget / alert と participant ごとの専用 RG inventory を準備。

専用 bootstrap identity と scoped grants は再実行のため RG cleanup まで残ります。
一時リソースの自動 cleanup を、Foundry / Search / AML resources の削除と混同しません。
失敗した deployment にも部分リソースが残り、課金される場合があります。

## Cleanup order

1. Azure ML **User files** から必要な Notebook / safe result を **Export**。
2. Hosted Agent versions / agent と自分が作成した data-plane children を cleanup。
3. Compute instance を **Stop**、次に **Delete**。
4. Azure Portal の **Resource groups** で専用 RG と subscription を照合。
5. **Delete resource group** で RG と残る workshop resources をまとめて削除。
6. 一覧を更新し、対象 RG の削除完了と、削除失敗がないことを確認。

> [!WARNING]
> Export と Hosted / Compute cleanup は RG 削除より先に行います。
> **Deployments の履歴を消しても resources は残ります。**
> 完了条件は dedicated workload RG の削除確認までです。

RG 内の Foundry、Search、monitoring、API、workspace / Storage / Key Vault、
bootstrap identity / grants も一括削除の対象です。他用途や他参加者の resources を削除しません。
lock / deny assignment などによる削除失敗は管理者と確認します。
optional な別環境・組織オブジェクトは、それぞれの所有者と cleanup を確認してください。

詳細は [Lab 9](../labs/09-observability-cleanup.md) を参照します。

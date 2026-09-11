# 管理者向け事前準備

## 1. 必要な権限と利用枠

- 参加者が Azure Portal で専用リソースグループ（RG）を作成・削除できること。
- 作成した RG 内で、ロール割り当てを含む **Owner 相当の権限**を持つこと。
  実行用のマネージド ID にサブスクリプション全体の権限は付与しません。
- 各参加者のサブスクリプションで、**Japan East / GlobalStandard** の次の利用枠を確認します。

| モデル | 必要な利用枠 |
|---|---:|
| `gpt-5.6-luna` | 40K TPM |
| `gpt-5.5` | 100K TPM |
| `embedding` / `text-embedding-3-small` | 40K TPM |

- Search **Basic**、Container Apps、Azure ML、Deployment Scripts と一時 ACI / Storage が利用可能なこと。
- Lab 7 用の **Standard_DS3_v2** の利用枠と、組織ポリシーを確認します。

事前確認は容量の予約ではありません。不足時はリージョン・モデルを変更せず、原因を確認します。

## 2. 配布するテンプレートと入力値

確認済みの
[azuredeploy.json](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/azuredeploy.json)
と、次の入力値を参加者へ渡します。テンプレートは教材 ZIP に含まれません。

| パラメーター | 渡す値 |
|---|---|
| `location` | `japaneast` |
| `primaryModelVersion` / `evaluationModelVersion` / `embeddingModelVersion` | 順に上記 3 モデルの確認済みバージョン |
| `travelApiImageRef` | 検証済みの GHCR イメージ。`@sha256:` で固定 |
| `sourceRevision` | 公開済み教材のコミット SHA（小文字 40 桁の 16 進数） |
| `participantObjectIdOverride` | 本人の実行は空欄可（実行者 ID を使用）。代理実行や別の人による再デプロイでは、参加者本人の Entra オブジェクト ID |
| `bootstrapRunId` | 初期化を意図的に再実行するときだけ変更 |

モデルのバージョン、イメージのハッシュ、SHA は推測せず、公開・動作確認済みの値を渡します。

## 3. 開催前の確認と片付け

1. [Lab 1](../../labs/01-setup.md) の順に、**RG を 1 個手動作成してから**テンプレートを開き、
   その既存 RG を選択します。**Create new** は使いません。
2. Deployment Scripts による初期化を含む全体が **Succeeded** になることを確認します。
3. 非公開の `workshop-files` から **Microsoft Entra user account** で
   `foundry-workshop-files.zip` を取得・展開できること、ZIP に認証情報が含まれないことを確認します。
4. [Azure ML の準備](../participant/environments/azure-ml.md) と
   [Lab 9](../../labs/09-observability-cleanup.md) の片付けを確認します。
   **Export → Hosted Agent / versions 削除 → Compute Stop / Delete → Delete resource group → 削除確認**。

デプロイ履歴を削除してもリソースは消えません。合成データだけを使い、削除は各参加者の専用 RG に限定します。
構成・権限・初期化処理の詳細は
[infra/README.md](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/README.md)
を参照してください。

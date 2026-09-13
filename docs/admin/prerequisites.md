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

- Search **Basic**、Container Apps、Deployment Scripts が利用可能なこと。
  実行基盤の要件は [infra/README.md](../../infra/README.md) を参照します。
- GitHub Codespaces の利用枠と組織ポリシー、GitHub / GHCR / package sources への到達性を確認します。
  ローカル参加者は [Dev Container の前提条件](../participant/environments/local-dev-container.md)を満たすこと。

事前確認は容量の予約ではありません。不足時はリージョン・モデルを変更せず、原因を確認します。

## 2. 配布するテンプレートと既定値

既定値を設定済みの
[azuredeploy.json](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/azuredeploy.json)
と、サブスクリプション・専用 RG 名、共通教材の参照先を参加者へ渡します。
本人がデプロイする場合は **Subscription** と作成済みの **Resource group** だけを選び、
その他は既定値のまま進めます。モデルのバージョンやハッシュの手入力は不要です。

モデルの既定値は、**2026-09-12 時点の Japan East / GlobalStandard の最新提供バージョン**で固定しています。

| パラメーター | 既定値 / 管理者が変更する場合 |
|---|---|
| `location` | `japaneast` |
| `primaryModelVersion` | `2026-07-09` |
| `evaluationModelVersion` | `2026-04-24` |
| `embeddingModelVersion` | `1` |
| `travelApiImageRef` | 公開済み Travel API `v1.0.4` の GHCR イメージを `@sha256:` で固定。具体値は下記の構成ガイドを参照 |
| `sourceRevision` | 公開済み教材のコミット SHA（小文字 40 桁の 16 進数）を設定済み。具体値は下記の構成ガイドを参照 |
| `participantObjectIdOverride` | 本人の実行は空欄可（実行者 ID を使用）。代理実行や別の人による再デプロイでは、参加者本人の Entra オブジェクト ID |
| `bootstrapRunId` | `1`。初期化を意図的に再実行するときだけ変更 |

全既定値と更新手順は
[構成ガイドの Template parameters](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/README.md#template-parameters)
を参照してください。
配布を更新する場合は、モデルのバージョン、イメージのハッシュ、SHA を推測せず、
公開・動作確認済みの値を `infra/main.bicep` の既定値に設定します。
`azuredeploy.parameters.example.json` と文書も同期し、`azuredeploy.json` を再生成して配布します。
**新しい bootstrap と互換な共通 assets・Notebook・source を先に公開し、その同じ公開済み SHA を
`sourceRevision` と配布する教材の参照先に揃えます。**
開発中のリンクは `dev-custom-template` です。開催用の参照先はこの公開確認後に固定します。
最新版を選ぶのは配布時であり、実行時に `latest` やブランチ名へ自動解決しません。
既定値があっても、開催前のモデル利用可否・利用枠の確認は必要です。

## 3. 開催前の確認と片付け

1. [Lab 1](../../labs/01-setup.md) の順に、**RG を 1 個手動作成してから**テンプレートを開き、
   その既存 RG を選択します。**Create new** は使いません。
2. Deployment Scripts による初期化を含む全体が **Succeeded** になることを確認します。
3. `workshopContext.setup_status = complete` と `resourceOutputs` を確認します。
   [Lab 4](../../labs/04-tools-toolbox.md) の GitHub assets を取得し、`travelApiBaseUrl` で OpenAPI を使えることを確認します。
4. [Codespaces](../participant/environments/codespaces.md) と同じローカル Dev Container で、
   Azure CLI サインイン、`00-setup.ipynb`、2 カーネル、代表的な Notebook 操作を確認します。
5. [Lab 9](../../labs/09-observability-cleanup.md) の
   **保存 → Hosted Agent / versions 削除 → Codespace 停止・削除 → Delete resource group → 削除確認**
   まで確認します。

デプロイ履歴を削除してもリソースは消えません。合成データだけを使い、削除は各参加者の専用 RG に限定します。
構成・権限・初期化処理の詳細は
[infra/README.md](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/dev-custom-template/infra/README.md)
を参照してください。

# 管理者向け事前準備

開催前に、参加者が使う Azure 環境と開発環境を確認し、検証済みのテンプレートを配布します。
モデルのバージョン、イメージのハッシュ、教材の SHA は推測せず、公開・動作確認済みの値を使います。

## 1. 権限と利用枠を確認する

### Azure の権限とサービス

- 参加者が Azure Portal で専用のリソース グループ（RG）を作成・削除できること。
- 作成した RG 内で、ロール割り当てを含む **Owner 相当の権限**を持つこと。
  実行用のマネージド ID にサブスクリプション全体の権限は付与しません。
- Azure AI Search **Basic**、Container Apps、Deployment Scripts を利用できること。
  実行基盤の要件は [infra/README.md](../../infra/README.md) を参照してください。
- Application Insights と Log Analytics はトレース収集に使います。
  自動アラートは演習の対象外なので、`Microsoft.AlertsManagement` の登録は不要です。
  Azure 側の既定アラートについては[自動アラートの扱い](troubleshooting.md#application-insights-の自動アラート)を参照してください。

### モデルの利用枠

各参加者のサブスクリプションで、**Japan East / GlobalStandard** の次の利用枠を確認します。

| モデル | 必要な利用枠 |
|---|---:|
| `gpt-5.6-luna` | 40K TPM |
| `gpt-5.5` | 100K TPM |
| `embedding` / `text-embedding-3-small` | 40K TPM |

> [!NOTE]
> 利用枠の確認は、容量の予約ではありません。不足している場合はリージョンやモデルを変更せず、
> 原因を確認してください。

### 開発環境とネットワーク

- GitHub Codespaces の利用枠と組織ポリシーを確認すること。
- GitHub、GHCR、パッケージ配布元へ接続できること。
- ローカルで参加する場合は、
  [Dev Container の前提条件](../participant/environments/local-dev-container.md)を満たすこと。

<a id="2-配布するテンプレートと既定値"></a>

## 2. テンプレートと配布内容を確認する

参加者には、使用するサブスクリプションを案内します。
テンプレートと共通教材の取得先は、[参加者向け事前準備](../participant/prerequisites.md#テンプレートと共通教材)にまとめています。

参加者本人がデプロイする場合、選ぶのは **Subscription** と作成済みの **Resource group** だけです。
その他の項目は既定値のまま進めるため、モデルのバージョンやハッシュを手入力する必要はありません。

### テンプレートの既定値

モデルの既定値は、**2026-09-12 時点の Japan East / GlobalStandard の最新提供バージョン**で固定しています。

| パラメーター | 既定値 / 管理者が変更する場合 |
|---|---|
| `location` | `japaneast` |
| `primaryModelVersion` | `2026-07-09` |
| `evaluationModelVersion` | `2026-04-24` |
| `embeddingModelVersion` | `1` |
| `travelApiImageRef` | 公開済みの Travel API `v1.0.4`。GHCR イメージを `@sha256:` で固定 |
| `sourceRevision` | 公開済み教材のコミット SHA。小文字 40 桁の 16 進数で固定 |
| `participantObjectIdOverride` | 本人が実行する場合は空欄。代理実行や別の人が再デプロイする場合は、参加者本人の Entra オブジェクト ID |
| `bootstrapRunId` | `1`。初期化を意図的に再実行するときだけ変更 |

具体的な値を含む全既定値と更新手順は、
[構成ガイドの Template parameters](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/main/infra/README.md#template-parameters)
を参照してください。

### 配布内容を更新する場合

1. 新しい bootstrap と互換性のある共通 assets、Notebook、source を先に公開します。
2. モデルのバージョン、イメージのハッシュ、教材の SHA が公開・動作確認済みであることを確認します。
3. 確認した値を `infra/main.bicep` の既定値に設定します。
4. 同じ公開済み SHA を、`sourceRevision` と配布する教材の参照先に設定します。
5. `azuredeploy.parameters.example.json` と関連文書を同期します。
6. `azuredeploy.json` を再生成して配布します。

配布リンクには `main` を使います。再現性が必要なbootstrapの参照先は、公開確認後のcommit SHAに固定してください。
最新版を選ぶのは配布時です。実行時に `latest` やブランチ名へ自動解決しないでください。

> [!IMPORTANT]
> 既定値を設定していても、開催前にモデルの利用可否と利用枠を再確認してください。

## 3. 開催前に一連の動作を確認する

参加者へ案内する前に、次の流れを最後まで確認します。

1. [Lab 1](../../labs/01-setup.md) に従い、**RG を 1 個手動作成してから**テンプレートを開きます。
  作成済みの RG を選び、**Create new** は使いません。
2. Deployment Scripts による初期化を含め、デプロイ全体が **Succeeded** になることを確認します。
3. `workshopContext.setup_status = complete` と `resourceOutputs` を確認します。
4. [Lab 4](../../labs/04-tools-toolbox.md) の GitHub assets を取得し、
  `travelApiBaseUrl` を使って OpenAPI に接続できることを確認します。
5. [Codespaces](../participant/environments/codespaces.md) と同じ Dev Container をローカルで開き、
  Azure CLI へのサインイン、`00-setup.ipynb`、2 つのカーネル、代表的な Notebook 操作を確認します。
6. [Lab 9](../../labs/09-observability-cleanup.md) に従い、
   **保存 → Hosted Agent / versions 削除 → Codespace 停止・削除 → Delete resource group → 削除確認**
   まで確認します。

> [!WARNING]
> デプロイ履歴を削除しても、リソースは削除されません。
> 合成データだけを使用し、削除対象は各参加者の専用 RG に限定してください。

構成、権限、初期化処理の詳細は、
[infra/README.md](https://github.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/blob/main/infra/README.md)
を参照してください。

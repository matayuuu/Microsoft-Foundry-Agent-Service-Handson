# 選択ラボ — Advanced Hosted Agent（コンテナ配布・複数プロトコル・Tool Search・Skills）

## この文書の位置づけ

本編 [Lab 7](../07-hosted-multi-agent.md) は、`src/hosted-agent/` の Agent Framework
workflow を **source-code remote build** で Hosted Agent としてデプロイします。これは
`scripts/deploy_hosted_agent.py` が使う唯一の経路であり、**本編の core はこれからも
source deploy のままです**。このラボは、Lab 7 のコードとデプロイ結果をベースに、
Hosted Agent の任意（optional）の拡張パターンを扱います。

> [!IMPORTANT]
> このラボの内容はどれも、`scripts/deploy_hosted_agent.py` や `src/hosted-agent/` の
> 既存ファイルを変更しません。ACR コンテナデプロイを試す場合も、本編で使う
> `contoso-travel-hosted-planner` agent とは**別の agent 名**を使ってください
> （既存 version を上書きする API はそもそも存在しませんが、名前を分けておくと本編の
> cleanup 手順と混同しません）。

## 1. コンテナ／ACR デプロイ（任意。core は source deploy のまま）

### 1.1 いつ ACR を使うか

Hosted Agent は本来、コンテナイメージとして Azure Container Registry (ACR) にビルド・push し、
Foundry がそのイメージを pull して実行する仕組みが基本形です。本編は
`dependency_resolution=REMOTE_BUILD` の source deploy（Foundry がサーバー側でビルドする方式）
を使うことで、参加者が Docker や ACR を意識しなくて済むようにしています。次のような要件が
ある場合は、コンテナ／ACR 経由のデプロイを検討してください。

- **コンプライアンス**: イメージを組織が既に運用する中央管理レジストリに置く必要がある。
- **共有インフラ**: 複数の agent プロジェクトで 1 つの ACR を共有したい。
- **ABAC モードのレジストリ**: 属性ベースアクセス制御（ABAC）が設定された ACR を使う必要がある。
- **事前ビルド済みイメージ**: 脆弱性スキャン・サプライチェーン署名・ハードニング済みベース
  イメージを使う、別の CI パイプラインがすでにイメージをビルドしている。

### 1.2 前提条件

- `azure.yaml` を含む、初期化済みの Hosted Agent プロジェクト
  （[azd 付録](azd-appendix.md)の「プロジェクトを初期化する」参照）。
- `azd` の Foundry 拡張機能（`microsoft.foundry`）がインストール済み。
- `azd auth login` で認証済みのセッション（**`az login` とは別の認証**です。本編の
  core は `az login` のみで完結し、`azd auth login` は使いません — [azd 付録](azd-appendix.md)
  参照）。
- 既存の ACR へのアクセスと、選んだビルド経路に必要な ACR ロール。

### 1.3 ワークフロー概要

```bash
# 1. 既存プロジェクトの ACR connection を確認・選択（0 件ならレジストリ名の入力を促される）
azd ai agent init

# 2. ローカルでコンテナイメージをビルドし、選択した ACR に push する
azd ai agent build
azd ai agent push --registry <your-acr-name>.azurecr.io

# 3. Foundry にデプロイ（ビルド・push・登録・agent identity 作成・RBAC 割り当てまで一括で行う場合）
azd ai agent deploy
```

`azd ai agent init` を既存の Foundry project に対して実行すると、拡張機能はプロジェクト内の
ACR connection をスキャンし、候補として提示します。ACR connection が 0 件の場合は ACR の
認証サーバー名（例: `myregistry.azurecr.io`）の入力を求められます。空欄のままにすると、
`azd provision` がプロジェクト専用の新しい ACR を作成します。

> [!NOTE]
> ACR を「private」（`publicNetworkAccess: Disabled` などのネットワーク分離）にするかどうかは、
> このレジストリ選択の話とは独立した論点です。本ハンズオンは
> [architecture.md](../../docs/architecture.md) の「Network posture」のとおり VNet
> インジェクション・private endpoint を扱わないため、private ACR の構成は本ラボの scope 外
> です。

### 1.4 事前ビルド済みイメージをそのまま使う

別の CI パイプラインがすでにビルド・push したイメージを、ビルドをスキップしてそのまま
デプロイすることもできます（`azd ai agent deploy --source <image-ref>` 相当。正確な
フラグ名は利用する `azd` Foundry 拡張機能のバージョンで確認してください）。この経路は
[CI/CD と継続評価](cicd-continuous-evaluation.md)の設計とも相性が良く、ビルド・脆弱性
スキャンと Foundry へのデプロイを別の権限・別のパイプラインに分離できます。

## 2. カスタムパッケージ（本編 requirements.txt を超える依存関係）

本編の source deploy は `src/hosted-agent/requirements.txt` に列挙された Python パッケージを
`REMOTE_BUILD` が `pip install` するだけです。次のようなケースでは、コンテナビルド経路の方が
柔軟です。

- OS レベルのパッケージ（apt パッケージなど）が必要なライブラリを使う場合。
- コンパイル済みバイナリや、pip 以外の方法で配布されるツールチェーンが必要な場合。
- 複数言語（Python + Node.js など）を 1 つのコンテナに同居させる場合。

いずれの場合も、まず本編 Lab 7 のようにローカルで `python main.py` を実行し、ローカル環境で
必要な依存関係を明確にしてから `Dockerfile` に落とし込むと、リモートビルドの失敗を切り分け
やすくなります。

## 3. 複数プロトコル（Responses・Invocations・Invocations (WebSocket)・A2A・Activity）

本編の `src/hosted-agent/main.py` は **Responses** プロトコル（port 8088）のみを実装して
います。Hosted Agent は 1 つの agent version に複数のプロトコルを同時に持たせることができ、
シナリオに応じて次のように使い分けます。

| シナリオ | プロトコル | 理由 |
|---|---|---|
| チャット形式の会話・アシスタント | **Responses** | プラットフォームが会話履歴・ストリーミング・セッションを管理する |
| Webhook 受信（GitHub、Stripe、Jira など） | **Invocations** | 送信元が独自のペイロード形式を送ってくるため `/responses` に合わせられない |
| 非会話的な処理（分類・抽出・バッチ） | **Invocations** | 入力がチャットメッセージではなく構造化データ |
| リアルタイム音声（マイク入力・音声出力） | **Invocations (WebSocket)** | 単一の持続接続での双方向ストリーミングが必要 |
| Teams・Microsoft 365 に publish する agent | **Responses** + **Activity** | Responses で agent ロジックを実装すれば、プラットフォームが自動的に Activity プロトコルへブリッジしてチャネル配信する |
| 他 agent からの委任呼び出し | **A2A (preview)** | Agent-to-Agent プロトコルによる委任 |

迷ったら **Responses** から始めることが公式に推奨されています。後から Invocations
エンドポイントを追加することも可能です（[Hosted agents 概念ドキュメント](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents)）。

A2A を有効化する詳細な前提条件・手順は [A2A・Routines・Publish](a2a-routines-publish.md) を
参照してください。

## 4. Tool Search（preview）

Tool Search は Toolbox 内の
ツール数が多い場合に、モデルが動的にツールを検索して呼び出す preview 機能です。Portal からは
利用できず、Foundry Toolkit または SDK からのみ設定できます。Hosted Agent の Toolbox に
多数のツール（本ラボで扱う Fabric IQ、Work IQ、Travel Ops API の OpenAPI ツールなど）を
まとめて接続する場合、Tool Search を有効にすることで、モデルへのプロンプトに全ツール定義を
毎回埋め込む必要がなくなり、コンテキストサイズとレイテンシを抑えられます。preview 機能の
ため、挙動やレイテンシ特性は今後変わり得ます。

## 5. Skills

本編 [Lab 4](../04-tools-toolbox.md) では、Portal で `travel-estimation` と
`preapproval-simulation` をアップロードし、Travel Ops API と同じ Toolbox に含めます。
Skills は通常の API tool ではなく、別の `skills[]` に保持され、
MCP の `resources/list` / `resources/read` で公開されます。

Hosted Agent で利用するには、対応する Skill provider が必要です。
Skill 名・description を提示し、必要なときだけ本文を読み込む progressive disclosure を
実装します。本編 Lab 7 の Python workflow にはこの provider を含めていないため、
Toolbox の作成だけで自動利用されるとは扱いません。
拡張時は [公式の Agent Framework Toolbox Skills sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/csharp/hosted-agents/agent-framework/foundry-toolbox-mcp-skills)
と [Skills の仕様](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills)を参照し、
Skill の読み込みと API 呼び出しを別々に確認してください。

## 6. 権限に関する注意点

- **agent identity**（Hosted Agent version ごとに自動作成される専用の Microsoft Entra ID）は、
  デフォルトでモデル推論とセッションストレージにアクセスできます。自分の Azure Storage
  など外部リソースにアクセスさせたい場合は、その agent identity に対して RBAC ロールを
  手動で割り当てる必要があります。
- **project managed identity**（Foundry project にシステム割り当てされる identity）は、
  ACR からイメージを pull するための **Container Registry Repository Reader** など、
  基盤運用のための権限を持ちます。これは agent の実行時 identity ではありません。
- 2 つの identity を混同しないでください。agent 自身のコードが呼び出すのは agent identity、
  Foundry がインフラ操作に使うのは project managed identity です。

## 7. Cleanup（本編の `destroy.sh` の対象外の部分に注意）

- 本編と同じ `contoso-travel-hosted-planner` という agent 名を再利用しなかった場合、本ラボで
  作成した agent とその version は `./scripts/delete_hosted_agent.py` の既定の `--agent-name`
  では削除されません。別名で作成した agent は、その名前を明示して個別に削除してください。
- ACR にコンテナイメージを push した場合、そのイメージ自体は ACR のリポジトリに残ります。
  本編の Terraform は ACR を管理しないため（[architecture.md](../../docs/architecture.md)
  の「Do not add ... an Agent capability host to the core Basic Agent Setup」のとおり、
  本編は ACR を作成しません）、bring-your-own の ACR を使った場合はイメージの削除も自分で
  行う必要があります。

## 公式参照

- [Hosted agents in Foundry Agent Service](https://learn.microsoft.com/azure/foundry/agents/concepts/hosted-agents)
- [Deploy a hosted agent with a private Azure Container Registry](https://learn.microsoft.com/azure/foundry/agents/how-to/deploy-hosted-agent-private-azure-container-registry)
- [Install the Azure Developer CLI Foundry extensions](https://learn.microsoft.com/azure/foundry/agents/how-to/install-cli-foundry-extensions)
- [Curate intent-based toolbox in Foundry](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox)

## 関連リンク

- [選択ラボ index](README.md)
- [本編 Lab 7 — Agent Framework workflow の Hosted Agent 配布](../07-hosted-multi-agent.md)
- [azd 付録](azd-appendix.md)
- [A2A・Routines・Publish](a2a-routines-publish.md)

# Lab 4 — Tools・Toolbox（35分）

## ゴール

1. `contoso-travel-assistant` に Web Search と Code Interpreter を**直接**アタッチする
   （Toolbox を介さない、agent 構成からの直接統合）。
2. Microsoft Foundry Toolkit（VS Code 拡張機能）で Toolbox `contoso-travel-toolbox`
   の **v1** を作成する。
3. `scripts/create_toolbox.py` を使い、実際にデプロイされた Travel Ops API を
   OpenAPI ツールとして組み込んだ **v2** を SDK で作成する（Portal・Toolkit のどちらも
   OpenAPI ツールの追加には対応していないため）。
4. v2 を agent にアタッチして、Playground でツール呼び出しを確認する。

## 1. Web Search / Code Interpreter を直接アタッチする（Portal）

`contoso-travel-assistant` の編集画面から、Tools セクションに Web Search と
Code Interpreter を追加します。両方とも「Direct tool integration」（Toolbox を
介さない直接統合）に対応しているため、Portal のエージェント構成画面だけで完結します。

> [!WARNING]
> **Web Search のデータ境界と課金**: Web Search は Grounding with Bing Search /
> Grounding with Bing Custom Search を使用します。これらは Microsoft の
> [Data Protection Addendum (DPA)](https://aka.ms/dpa) の**適用対象外**であり、
> 送信したデータはコンプライアンス境界・地理的境界の外に転送されます。利用には
> モデルのトークン課金とは**別に料金**が発生します。本ハンズオンで Web Search に
> 送ってよいのは、`data/eval/live_subset.jsonl` の `category: "current_info_web_search"`
> にあるような**架空の Contoso シナリオに関する質問のみ**です。実データや機密情報を
> 入力しないでください。
>
> **Code Interpreter** もセッションごとに別料金が発生します。

保存後、Playground で `current_info_web_search` カテゴリの質問と、簡単な計算を
要する質問（Code Interpreter 向け）を試してください。

## 2. Foundry Toolkit で Toolbox v1 を作る

Toolbox の**新規作成**は Portal からはできません（
[feature-support-matrix.md](../docs/feature-support-matrix.md) の通り）。
[Microsoft Foundry Toolkit for Visual Studio Code](https://aka.ms/foundrytk)
拡張機能をインストールし、Azure にサインインして project を選択します。

前提として、Toolbox の作成には Foundry project 上の **Foundry User** ロールが
developer（あなた自身）と agent identity の両方に必要ですが、
`infra/rbac.tf` によってこれは `setup.sh` の時点ですでに付与済みです。追加の
ロール割り当ては不要です。

Foundry Toolkit の Tool Catalog / Toolbox 画面から、次の内容で v1 を作成します。

- **Toolbox 名**: `contoso-travel-toolbox`
- **ツール**: Web Search（Toolkit から追加できるツールの一例。Toolbox 経由でも
  Web Search を使えることを確認する目的です）

保存すると version 1 が作成され、自動的に default version になります。

> [!NOTE]
> Foundry Toolkit の UI は**最新バージョンのみ**を表示します（過去バージョンの
> 一覧・取得・削除は Python SDK / REST / .NET / JavaScript SDK からのみ可能です）。
> また、**OpenAPI ツールは Foundry Toolkit では追加できません**
> （feature-support-matrix.md の「OpenAPI in Toolbox」参照）。次のステップで
> SDK を使うのはこのためです。

## 3. SDK で v2 を作る（OpenAPI: 実際の Travel Ops API）

`scripts/create_toolbox.py` は、実際にデプロイされている Travel Ops API の
`/openapi.json` をそのライブ URL から取得し、それを OpenAPI ツールとして
含む新しい Toolbox version を作成（または、内容が変わっていなければ何もせず
再利用）します。

```bash
.venv/bin/python scripts/create_toolbox.py --output json
```

主なオプション（`.venv/bin/python scripts/create_toolbox.py --help` で全体を確認できます）:

| オプション | 既定値 | 説明 |
|---|---|---|
| `--context` | `.workshop/context.json` | 構築済み環境のコンテキストファイル |
| `--toolbox-name` | `contoso-travel-toolbox` | Toolkit で作った v1 と同じ Toolbox 名 |
| `--tool-name` | `travel_ops_api` | Toolbox 内の OpenAPI ツール名 |
| `--auth-type` | `anonymous` | Travel Ops API は公開・認証不要のモック API のため既定は anonymous |
| `--credential` | `azure-cli` | `az login` のセッションのみを使用（`default` は `DefaultAzureCredential`） |
| `--no-publish` | (指定なし) | version は作るが default には昇格しない |
| `--output` | `human` | `json` を指定すると機械可読な出力になる |

このスクリプトは冪等です。Travel Ops API の OpenAPI 仕様が前回実行時と変わって
いなければ、既存の default version をそのまま使い、`"action": "unchanged"` を
返します（新しいバージョンは作られません）。仕様が変わっていれば新しい version
を作成し、`--no-publish` を指定しない限り自動的に default version に昇格します
（`"action": "created_and_published"`）。

`--output json` の出力には、この Toolbox の **MCP エンドポイント**（Foundry の
hosted/prompt agent がこの Toolbox を消費するための URL）も含まれます。

```text
{project_endpoint}/toolboxes/{toolbox_name}/mcp?api-version=v1                  (default version 用)
{project_endpoint}/toolboxes/{toolbox_name}/versions/{version}/mcp?api-version=v1 (特定 version 固定)
```

> [!NOTE]
> ここで言う「MCP エンドポイント」は、Toolbox 自体が Model Context Protocol
> 経由で公開される**消費用の URL** です。Toolbox の**中に** MCP サーバーを
> ツールの1種類として追加する話（`MCPToolboxTool`）とは別の概念なので
> 混同しないでください。本ラボでは後者は使いません。

認証は `az login` のセッションのみを使い、API キーや接続文字列は一切読み込みません
（`scripts/lib/workshop_context.py` の `build_credential()`）。

## 4. Portal でアタッチしてテストする

`contoso-travel-assistant` の Tools 設定に戻り、Toolbox `contoso-travel-toolbox`
を追加します（Toolbox を agent にアタッチする操作自体は Portal から可能です）。
保存すると新しい agent version が作られます。

Playground で、`data/eval/live_subset.jsonl` の `category: "tool_choice"` に
分類される質問（日当の問い合わせ・出張費用の見積もり・事前承認シミュレーション
のいずれか）を試し、次を確認してください。

- モデルが Travel Ops API の該当エンドポイント（`getPerDiem` /
  `createTripEstimate` / `createPreapproval`）を実際に呼び出しているか（トレース
  や tool call の表示で確認）。
- `createPreapproval` の応答はすべて `simulated_` プレフィックス付きで、実際の
  承認ではないことを明示するモックです。参加者に実際の承認権限を与えるものでは
  ありません。

## 5. Approval と Tool Search の境界（参考）

- `require_approval` のようなツール呼び出し承認フローは、Toolbox 内の **MCP 型
  ツール**（外部 MCP サーバーを接続する場合）に関する設定です。本ラボで作成した
  OpenAPI ツールにはこの概念は適用されません。
- **Tool Search** は preview 機能で、Toolbox 内のツールが多い場合にモデルが
  動的に検索して呼び出す仕組みです。Portal からは利用できず、Toolkit / SDK から
  のみ設定できます。本ハンズオンでは深入りせず、存在の紹介にとどめます。

## 次のステップ

[Lab 5 — Agent evaluation](05-evaluation.md) に進んでください。

# Lab 4 — Toolbox と Skills を作成する（30分）

## ゴール

Microsoft Foundry で、Travel Ops API と操作手順の Skills を
`contoso-travel-toolbox` にまとめて公開します。

Lab 3 の規程検索を残したまま、API による費用計算と、Skills による操作手順の共有を追加します。

| 要素 | 役割 |
|---|---|
| Travel Ops API | 日当照会・費用計算・事前承認シミュレーションを実行する |
| `travel-estimation` Skill | 不足情報を確認し、照会・見積もり API を使い分け、費用内訳を説明する |
| `preapproval-simulation` Skill | 実行意思を確認し、合成の承認結果と実際の承認を区別する |

## Toolbox とは

Toolbox は、Agent が利用する Tools や Skills などを一元的に管理し、共有するための仕組みです。
Tool は Agent が実行できる操作を定義し、Skill はその Tool をいつ、どのような手順で
使うかを定義します。

公開した Toolbox は、単一の MCP 互換 endpoint を通じて複数の Agent から再利用できます。
認証、アクセス制御、guardrail、可観測性、version も Toolbox 単位で管理できます。

このラボでは、Travel Ops API の OpenAPI tool と、費用見積もり・承認シミュレーションの
2 つの Skills を 1 つの Toolbox にまとめて公開します。

## 1. 貼り付け・アップロード用ファイルを用意する

Codespace の repository root の terminal で次を実行します。

```bash
.venv/bin/python scripts/prepare_toolbox_assets.py
```

実際の Travel Ops API と `.workshop/context.json` から、自分の環境用の素材を生成します。
この時点では Toolbox、Skill、Agent は作成・更新しません。

| ファイル | 用途 |
|---|---|
| `.workshop/toolbox/travel-ops.openapi.json` | Portal の schema editor へ内容を貼り付ける |
| `.workshop/toolbox/travel-estimation.zip` | 見積もり Skill のアップロード。ZIP 直下に `SKILL.md` |
| `.workshop/toolbox/preapproval-simulation.zip` | 承認シミュレーション Skill のアップロード |
| `.workshop/toolbox/portal-values.json` | 自分の環境の Toolbox MCP endpoint などを確認する |

Browser のファイル選択ダイアログは Codespace 内を直接参照できません。
アップロードする ZIP を VS Code Explorer で右クリックし、**Download** で手元へ保存します。
この演習では生成された 2 つの ZIP を使います。本文を読むときは次の元ファイルを開きます。

- [`travel-estimation/SKILL.md`](../data/skills/travel-estimation/SKILL.md)
- [`preapproval-simulation/SKILL.md`](../data/skills/preapproval-simulation/SKILL.md)

## 2. Portal で Toolbox の作成画面を開く

1. 対象 project の **Build > Tools** を開きます。
2. **Toolboxes** タブを選び、**Create toolbox** を選択します。

![Tools の Toolboxes タブから作成する](../docs/images/lab04-toolboxes-tab.png)

3. **Name** に `contoso-travel-toolbox` を入力します。
4. **Description** に次を入力します。

```text
Contoso Travel Ops API と、費用見積もりの手順を記載した travel-estimation Skill、
事前承認シミュレーションの手順を記載した preapproval-simulation Skill。
```

**Included** に最初から推奨 tool が入っている場合は、この演習で使わないものを外します。
`web_search`、`code_interpreter`、`FoundryMCPServerpreview` がある場合、それぞれの
右端の **Actions** から **Remove** を選択してください。

![自動追加されている場合は、この3つの tool を外す](../docs/images/lab04-default-tools.png)

これらが最初から入っていなければ削除操作は不要です。
この演習では **Guardrail** は既定のままにします。組織で必須の設定がある場合は従い、
既存の guardrail を削除しないでください。

## 3. OpenAPI tool を追加する

1. **Included > + Add > Add tool** を選択します。
2. **Select a tool > Custom > OpenAPI tool** を選択します。
3. ダイアログ下部の **Create** を選択します。

**Create an OpenAPI tool** の入力を次に揃えます。

| 項目 | 入力 |
|---|---|
| **Name** | `travel_ops_api` |
| **Description** | `Contoso の日当照会、費用見積もり、事前承認シミュレーションを実行する Travel Ops API。` |
| **Authentication method** | `Anonymous` |
| **OpenAPI 3.0+ schema** | `.workshop/toolbox/travel-ops.openapi.json` の内容全体 |

![OpenAPI の入力画面](../docs/images/lab04-openapi-form.png)

**Create tool** を選択し、Included に追加されたことを確認します。
`OpenAPI 3.0+` という UI ラベルですが、貼り付ける教材の定義は **3.1.0** です。
`servers[0].url` が自分の Travel Ops API になっていることも確認してください。

追加後は **Tool search** を **Off** にします。この演習では API が 1 つなので、
利用できる関数を直接確認する構成にします。

![travel_ops_api を追加し、Tool search を Off にする](../docs/images/lab04-tool-search-off.png)

> [!NOTE]
> `Anonymous` は公開された合成データ専用 mock API の認証方式です。
> **Agent から Foundry Toolbox への認証まで Anonymous にする、という意味ではありません。**
> Toolbox 側は Microsoft Entra ID/RBAC を使います。

## 4. 2 つの Skills をアップロードする

1. **Included > + Add > Add skill** を選択します。
2. **Select a skill** の **Configured** で **Add skill** を選択します。

3. メニューから **Upload skill** を選択します。
4. **Browse** を押し、手元の PC にダウンロードした `travel-estimation.zip` を選びます。
5. 表示されたファイル名と **Name = travel-estimation** を確認し、**Create** を押します。
   Name と Description は、ZIP 内の `SKILL.md` から読み取られます。
6. Toolbox の画面に戻り、Included に Skill が増えたことを確認します。
7. 同じ **Add skill > Upload skill** の手順で `preapproval-simulation.zip` を選択します。
   Name が **preapproval-simulation** であることを確認して **Create** を押します。

アップロードした Skill は自動で Included に入ります。
登録済みの Skill を使う場合は、同じ project の **Configured** から選んで **Add** します。

アップロード前後に `SKILL.md` を開き、次の役割分担を確認します。

- `description` は **いつ使うか**を示す。日当・見積もりと承認シミュレーションを区別する。
- 本文は **どう使うか**を示す。入力確認、API の選択、結果の説明を記述する。
- 規程の金額や承認条件を複製しない。Foundry IQ と API を情報源にする。
- 見積もり依頼だけで承認シミュレーションを実行しない。

> [!NOTE]
> Guardrail は、Toolbox の tool に渡す入力と tool から返る出力に、責任ある AI（RAI）の
> コンテンツフィルタリングを適用する仕組みです。モデル側のコンテンツフィルターとは独立して
> Toolbox 層で動作します。このハンズオンでは Guardrail の作成・設定・検証は行わず、
> 画面に表示される既定の設定を変更しません。組織で必須の Guardrail がある場合は維持してください。

## 5. Toolbox を公開する

1. Included が **travel_ops_api / travel-estimation / preapproval-simulation の 3 つ**
   で、Tool search が Off であることを確認します。
2. 右上の **Publish** を選択します。

3. 公開後に Toolbox を開き直し、3 つの項目と公開済み version を確認します。

## 6. Prompt Agent に keyless 接続する

Toolbox は MCP という共通の接続方式で Agent から呼び出します。
**Lab 3 の Knowledge は削除しません。**

1. 公開済み Toolbox の **Call this toolbox > Endpoint** を **Copy endpoint** でコピーします。
   同じ値は `.workshop/toolbox/portal-values.json` の `toolbox_mcp_endpoint` でも確認できます。
2. **Build > Agents > contoso-travel-assistant** を開きます。
3. **Tools** 側の **Add > Add tools** を開きます。Knowledge 側の Add ではありません。
4. **Custom > Model Context Protocol (MCP)** を選択し、**Create** を押します。

5. 接続画面を次の値に揃えます。

| 項目 | 値 |
|---|---|
| Name | `contoso-travel-toolbox-mcp` |
| Remote MCP Server endpoint | コピーした自分の `toolbox_mcp_endpoint` |
| Authentication | **Microsoft Entra** |
| Type | **Project Managed Identity** |
| Audience | `https://ai.azure.com/` |

6. 各項目を確認して **Connect** を選択します。

![Microsoft Entra と Project Managed Identity で接続する。endpoint は環境固有の値](../docs/images/lab04-connect-toolbox.png)

7. Tools に接続が増え、Knowledge に `contoso-travel-knowledge-lab` が残っていることを
   確認して **Save** を押します。

API key や手動で取得した bearer token は使いません。

<details>
<summary>keyless 接続の選択肢が表示されない場合だけ使う補助コマンド</summary>

上の接続設定を UI で選べない場合に限り、公開済み Toolbox に接続する次のコマンドを使えます。

```bash
.venv/bin/python scripts/connect_toolbox.py
```

このコマンドは公開済み Toolbox への接続だけを行います。
`az login` の認証で `contoso-travel-toolbox-mcp` connection を用意し、
既存の Knowledge を残して Agent に追加します。Toolbox version、Skill、Agent instructions
の変更は行いません。

</details>

## 7. ハンズオン用 MCP の tool を自動承認する

この後の API 実行と Lab 5 / 6 の自動評価が操作承認で止まらないように設定します。
対象は **このハンズオン専用の合成データ API を含む MCP 接続だけ**です。
一般の業務 API や、初期追加の管理用 tool にこの設定を適用しません。

1. Agent の Tools で **contoso-travel-toolbox-mcp** の **Actions > Configure** を開きます。
2. **Approval setting for tools in this MCP server for this agent** で
   **Always auto-approve all tools** を選択します。
3. **Apply** を押し、Agent 画面で **Save** を押します。

![ハンズオン用 MCP の自動承認設定を Apply し、Agent を保存する](../docs/images/lab04-batch-approval-setting.png)

これは model が tool を呼ぶ際の操作確認の設定です。Microsoft Entra の認証・RBAC を
無効にするものでも、実際の出張承認を与えるものでもありません。

## 8. API の実行と Skill の利用を区別して確認する

Playground の **New chat** で新しい会話を作り、次を入力して **Send** を押します。

```text
東京からニューヨークへ2026-07-10〜2026-07-15の出張で、
1名、ビジネスクラス利用を前提に費用見積もりを出してください。
予約や承認シミュレーションは不要です。
```

費用内訳と合計を含む最終回答が表示されることを確認します。
確認画面が表示された場合は自動承認設定が保存されていないため、Section 7 に戻ってください。

回答後、次の手順で **Traces** の tool 呼び出しを確認します。

1. Playground の回答下部にある **Traces** を選択し、**Conversations view** を開きます。
   **Traces** が表示されない場合は、**Build > Agents > contoso-travel-assistant > Traces**
   から開きます。
2. 質問を送信した時刻に対応する `conv_...`（Conversation）を開きます。
   ID は実行ごとに異なります。
3. **Trajectories** で `invoke_agent contoso-travel-assistant` を展開し、
   `execute_tool ...travel_ops_api___createTripEstimate` を選択します。
4. 右側の **Input + Output** で、入力の都市、日程、座席クラス、人数と、
   出力の `total_estimate` を確認します。`total_estimate` は Playground の回答の合計と
   一致する必要があります。
5. Toolbox 側の `tools/call travel_ops_api___createTripEstimate` も成功していることを確認します。
   `createPreapproval` の呼び出しがないことも確認してください。

Portal の表示によっては、Agent 側の `execute_tool` と Toolbox 側の `tools/call` が
別の階層に表示されます。どちらも同じ API 呼び出しを Agent 側と Toolbox 側から記録したものです。

**Skill の登録成功と、Agent がその Skill を読み込んだことは別です。**
2026-09-08 時点では、Portal で作る Prompt Agent の MCP 接続は Toolbox の callable tool を
実行できますが、MCP Resources として公開された Skill を自動発見・読み込みしません。
Python の `AIProjectClient` は Skill の作成・管理と Toolbox への参照追加に対応していますが、
`PromptAgentDefinition` に Toolbox Skill の runtime reference はありません。Portal の代わりに
同じ Prompt Agent を SDK から呼び出しても、この制約は変わりません。

したがって、このラボの結果は「Skill は Toolbox に登録・公開済み／Prompt Agent からの
利用は未確認」ではなく、Trace に `resources/read` がなければ **この実行では未使用** と記録します。
Skill 本文を Agent instructions へ複製して、Toolbox Skill を使ったものとは扱いません。
本編の到達点は、Skills の登録・公開と Agent からの API 呼び出しです。

<details>
<summary>Skill の読み込みをさらに確認する場合</summary>

Skills は MCP の `resources/list` / `resources/read` で公開され、MCP Resources protocol に
対応するクライアントまたは Skill provider が必要です。対応クライアントでは `load_skill`
または resource read の記録を確認します。
対応実装の例は公式の [Agent Framework Toolbox Skills sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/csharp/hosted-agents/agent-framework/foundry-toolbox-mcp-skills)
を参照してください。本編 Lab 7 の workflow は、この Skill provider をまだ実装していません。
公式の [Skills の Python 手順](https://learn.microsoft.com/ja-jp/azure/foundry/agents/how-to/tools/skills?pivots=python)
では、`ToolboxSkillReference` による公開と、MCP Resources 対応クライアントによる利用を
区別しています。

</details>

## 完了チェック

- OpenAPI tool と 2 つの Skills を含む Toolbox を公開できた
- Agent から Toolbox の API を呼び出し、費用見積もりを確認できた
- Trace で `createTripEstimate` の実行を確認できた

## 任意: SDK で同じ構成を扱う

[`notebooks/04-create-toolbox.ipynb`](../notebooks/04-create-toolbox.ipynb) は SDK 学習用の補助です。
Notebook は本編では使いません。
OpenAPI の更新時に既存 Skills・他の tools・guardrail を保持しますが、
Skill 自体のアップロードは上の Portal 手順で行います。
Prompt Agent の呼び出し、回答の検証、Conversation に記録された Tool の入出力確認も行います。
UI の作成操作を体験する前に Notebook で Toolbox を作る必要はありません。

公式仕様: [Toolbox](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox) /
[Skills](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills)。
困った場合は [Toolbox のトラブルシューティング](../docs/participant/troubleshooting.md#portal-での-toolbox-操作)
を参照してください。

## 次の Lab

[Lab 5 — Portal で Agent evaluation](05-evaluation.md)

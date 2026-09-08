# Lab 4 — Toolbox と Skills を作成する（30分）

## ゴール

Microsoft Foundry で、Travel Ops API、Code Interpreter、Web Search と操作手順の Skills を
`contoso-travel-toolbox` にまとめ、**Tool Search** を有効にして公開します。

Lab 3 の規程検索を残したまま、API による費用計算と、Skills による操作手順の共有を追加します。

| 要素 | 役割 |
|---|---|
| Foundry IQ（Lab 3 の Knowledge） | 社内規程を検索し、根拠を引用する。Toolbox には移動しない |
| Travel Ops API（OpenAPI 1 項目） | `getHealth` / `getPerDiem` / `createTripEstimate` / `createPreapproval` の 4 operation を公開し、決定論的な照会・計算・シミュレーションを行う |
| Code Interpreter | API 結果の数値比較・集計・表整形だけを行う。規程や入力値を作らない |
| Web Search | ユーザーが明示的に求めた、現在の公開旅行情報だけを検索する |
| `travel-estimation` Skill | 不足情報を確認し、照会・見積もり API を使い分け、費用内訳を説明する |
| `preapproval-simulation` Skill | 実行意思を確認し、合成の承認結果と実際の承認を区別する |

## Toolbox とは

Toolbox は、Agent が利用する Tools や Skills などを一元的に管理し、共有するための仕組みです。
Tool は Agent が実行できる操作を定義し、Skill はその Tool をいつ、どのような手順で
使うかを定義します。

公開した Toolbox は、単一の MCP 互換 endpoint を通じて複数の Agent から再利用できます。
認証、アクセス制御、guardrail、可観測性、version も Toolbox 単位で管理できます。

このラボでは、Travel Ops API の OpenAPI tool、2 つの built-in tool と、費用見積もり・
承認シミュレーションの 2 つの Skills を 1 つの Toolbox にまとめて公開します。
Tool Search を有効にすると、最初から全 tool 定義をモデルへ渡さず、`tool_search` で必要な
定義を発見し、`call_tool` で選んだ tool を実行します。

> [!IMPORTANT]
> Web Search へ秘密、資格情報、顧客データ、個人データを送信しないでください。
> 検索結果は信頼できない外部入力として扱います。この教材では、公開情報だけを含む明示的な
> 検索依頼でのみ使います。社内規程は Foundry IQ、費用計算は Travel Ops API が正本です。

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
Contoso Travel Ops API、数値比較用 Code Interpreter、明示された現在情報用 Web Search と、
費用見積もり・事前承認シミュレーションの手順を記載した 2 Skills。
```

**Included** に `web_search` と `code_interpreter` が最初から入っている場合は残します。
同じ種類を重複追加しません。`FoundryMCPServerpreview` が自動追加されている場合は、
この演習の対象外で管理操作を Tool Search の候補に混ぜないため、右端の **Actions > Remove**
で外します。組織が追加したほかの tool は、管理者へ確認せず削除しないでください。
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

追加後は **Tool search** を **On** にします。OpenAPI は Included 上では 1 項目ですが、
schema の `operationId` により、次の 4 つが個別に発見・実行できる callable operation です。

- `getHealth`
- `getPerDiem`
- `createTripEstimate`
- `createPreapproval`

Tool Search 自体は `tool_search` と `call_tool` という 2 つの meta-tool を公開します。
これらは上の 4 operation の代替ではなく、発見と実行を包む layer です。

> [!NOTE]
> `Anonymous` は公開された合成データ専用 mock API の認証方式です。
> **Agent から Foundry Toolbox への認証まで Anonymous にする、という意味ではありません。**
> Toolbox 側は Microsoft Entra ID/RBAC を使います。

## 3.1 Code Interpreter と Web Search を確認する

1. Included に **Code Interpreter** がなければ **+ Add > Add tool** から追加します。
2. Included に **Web Search** がなければ同様に追加します。外部 connection は作成しません。
3. Tool Search が **On** のままであることを確認します。

Code Interpreter は Travel Ops が返した数値の比較・集計・表整形に限定します。
Web Search は「現在の公開情報を調べて」と明示された場合だけ利用し、出典 URL と取得日時を
回答へ含めます。通常の規程質問や見積もりでは、どちらも呼び出しません。

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

1. Included に **travel_ops_api / Code Interpreter / Web Search /
   travel-estimation / preapproval-simulation** があり、Tool search が **On** であることを
   確認します。
2. 右上の **Publish** を選択します。

3. 公開後に Toolbox を開き直し、5 つの項目、Tool search On、公開済み version を確認します。

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

Agent の既存 instructions（Lab 3 の規程検索指示）を残したまま、次の境界を追記して
**Save** します。

```text
- 社内規程と根拠は Foundry IQ Knowledge で検索する。
- 日当、旅費見積もり、事前承認シミュレーションは Travel Ops API の決定論的な結果を使う。
- Toolbox tool が必要なときは tool_search で候補を探し、call_tool で選んだ tool を実行する。
- Code Interpreter は API 結果の数値比較、集計、表整形にだけ使い、規程値や旅程を作らない。
- Web Search はユーザーが現在の公開旅行情報を明示的に求めた場合だけ使い、出典 URL と
  取得日時を示す。秘密、資格情報、個人情報、顧客データを検索へ送らない。
- 見積もりだけの依頼で createPreapproval を呼ばない。明示的な実行意思を確認した場合だけ
  合成の事前承認シミュレーションを行い、実際の承認・予約ではないと明示する。
```

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

## 8. Tool Search と実 tool の実行を Trace で確認する

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
3. **Trajectories** で `invoke_agent contoso-travel-assistant` を展開し、まず
   `tool_search`、次に `call_tool` があることを確認します。
4. `call_tool` が選んだ実 tool が `travel_ops_api___createTripEstimate` であることを
   Input / Output または、その配下の Toolbox Trace で確認します。Portal の版によって
   downstream call は同じ階層に flatten されず、`call_tool` の内側に表示されます。
5. 右側の **Input + Output** で、入力の都市、日程、座席クラス、人数と、
   出力の `total_estimate` を確認します。`total_estimate` は Playground の回答の合計と
   一致する必要があります。
6. `getHealth`、`getPerDiem`、`createPreapproval`、Code Interpreter、Web Search が
   実行されていないことを確認します。Tool Search の候補に現れただけでは「実行」ではありません。

Portal の表示によっては、Agent 側の `call_tool` と Toolbox 側の
`tools/call travel_ops_api___createTripEstimate` が別階層です。順序は
**`tool_search` → `call_tool` → 選択された実 tool** として読み、候補一覧と実行済み call を
混同しないでください。Trace UI の版によっては各 call が `execute_tool` span として表示される
ため、span 名だけでなく Input / Output の tool 名も確認します。

### 用途を変えて routing を確認する

新しい chat を使い、1 回ずつ実行します。

```text
Travel Ops APIで大阪の2026-05-11の日当を確認してください。見積もりや承認は不要です。
```

`tool_search → call_tool → travel_ops_api___getPerDiem` だけが実行され、
`createTripEstimate` / `createPreapproval` / Code Interpreter / Web Search が呼ばれないことを
確認します。

```text
現在のニューヨークの公開交通情報をWeb Searchで調べ、参照URLと取得日時を示してください。
社内情報・顧客情報は検索語に含めないでください。
```

この明示依頼だけで `tool_search → call_tool → Web Search` が実行され、出典と取得日時が
回答に含まれることを確認します。固定の正解値とは比較しません。

```text
見積もり結果の航空券・宿泊・日当の比率を計算し、表に整形してください。
新しい規程値や旅程は仮定しないでください。
```

既に同じ chat に見積もり結果がある場合だけ Code Interpreter を使い、数値比較・表整形を
行うことを確認します。Travel Ops の値そのものを置き換えてはいけません。

`createPreapproval` は次のように、シミュレーションであることを理解した上で実行を明示した
場合だけ呼び出します。

```text
この見積もりについて、実際の承認ではないことを理解しました。
事前承認シミュレーションを実行してください。
```

Trace で初めて `tool_search → call_tool → travel_ops_api___createPreapproval` が現れ、
回答が実承認・予約ではなく simulated result と明記されることを確認します。

**Skill の登録成功と、Agent がその Skill を読み込んだことは別です。**
2026-09-09 時点では、Portal で作る Prompt Agent の MCP 接続は Toolbox の callable tool を
実行できますが、MCP Resources として公開された Skill を自動発見・読み込みしません。
Python の `AIProjectClient` は Skill の作成・管理と Toolbox への参照追加に対応していますが、
`PromptAgentDefinition` に Toolbox Skill の runtime reference はありません。Portal の代わりに
同じ Prompt Agent を SDK から呼び出しても、この制約は変わりません。

したがって、Trace に `load_skill` または MCP `resources/read` がなければ、Skill 利用は
**この実行では未証明（利用は未確認）** と記録します。
Skill 本文を Agent instructions へ複製して、Toolbox Skill を使ったものとは扱いません。
本編の到達点は、Skills の登録・公開と Agent からの API 呼び出しです。

<details>
<summary>Skill の読み込みをさらに確認する場合</summary>

Skills は MCP の `resources/list` / `resources/read` で公開され、MCP Resources protocol に
対応するクライアントまたは Skill provider が必要です。対応クライアントでは `load_skill`
または resource read の記録を確認します。
対応実装の例は公式の [Agent Framework Toolbox Skills sample](https://github.com/microsoft-foundry/foundry-samples/tree/main/samples/csharp/hosted-agents/agent-framework/foundry-toolbox-mcp-skills)
を参照してください。2 つの Skills は Lab 7 / 8 の共有 Harness factory が提供する
Skill provider で読み込むため、登録・公開状態を維持します。Lab 7 では `load_skill` と
`resources/read` の実行記録を確認し、Toolbox への登録だけでなく実際の利用を証明します。
公式の [Skills の Python 手順](https://learn.microsoft.com/ja-jp/azure/foundry/agents/how-to/tools/skills?pivots=python)
では、`ToolboxSkillReference` による公開と、MCP Resources 対応クライアントによる利用を
区別しています。

</details>

## 完了チェック

- OpenAPI、Code Interpreter、Web Search と 2 Skills を含み、Tool Search On の Toolbox を公開した
- Trace で `tool_search → call_tool → createTripEstimate` を確認した
- 見積もり依頼で無関係な tool と `createPreapproval` が呼ばれないことを確認した
- Skill は登録・公開済みであり、`load_skill` / `resources/read` なしには利用済みと主張しない

## 任意: SDK で同じ構成を扱う

[`notebooks/04-create-toolbox.ipynb`](../notebooks/04-create-toolbox.ipynb) は SDK 学習用の補助です。
Notebook は本編では使いません。
OpenAPI の更新時に既存 Skills・他の tools・guardrail・Tool Search を保持し、不足する
Lab 4 の built-in tool と Tool Search だけを SDK が対応する正式な model で追加しますが、
Skill 自体のアップロードは上の Portal 手順で行います。
Prompt Agent の呼び出し、回答の検証、Conversation に記録された Tool の入出力確認も行います。
UI の作成操作を体験する前に Notebook で Toolbox を作る必要はありません。

公式仕様: [Toolbox](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox) /
[Skills](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills)。
困った場合は [Toolbox のトラブルシューティング](../docs/participant/troubleshooting.md#portal-での-toolbox-操作)
を参照してください。

## 次の Lab

[Lab 5 — Portal で Agent evaluation](05-evaluation.md)

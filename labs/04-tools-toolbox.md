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

次の共通ファイルを GitHub から **PC に保存**します。
リンクはファイル本体です。ZIP は展開せず、そのままアップロードに使います。

| ファイル | 用途 |
|---|---|
| [travel-estimation.zip](https://raw.githubusercontent.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/main/assets/skills/travel-estimation.zip) | 見積もり Skill |
| [preapproval-simulation.zip](https://raw.githubusercontent.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/main/assets/skills/preapproval-simulation.zip) | 承認シミュレーション Skill |
| [travel-ops.openapi.json](https://raw.githubusercontent.com/matayuuu/Microsoft-Foundry-Agent-Service-Handson/main/assets/openapi/travel-ops.openapi.json) | OpenAPI の共通定義 |

各 Skill ZIP の直下には `SKILL.md` があります。`SKILL.md` 単体ではなく ZIP を選んでください。
ブラウザーの file picker は手元の PC を参照します。

OpenAPI は PC の text editor で開き、`servers[0].url` の
`https://replace-with-your-travel-api.example.invalid` **だけ**を、Lab 1 の
Azure Portal **Deployments > 対象デプロイ > Outputs > travelApiBaseUrl** の値に置き換えます。
変更後の JSON 全体を、後の **OpenAPI 3.0+ schema** 欄へ貼り付けます。この欄は file upload ではありません。

本文を読む場合の正本は `data/skills/` にあります。

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

`FoundryMCPServerpreview` が自動追加されている場合は、
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
| **OpenAPI 3.0+ schema** | `servers[0].url` を変更した `travel-ops.openapi.json` の内容全体 |

![OpenAPI の入力画面](../docs/images/lab04-openapi-form.png)

**Create tool** を選択し、Included に追加されたことを確認します。

追加後は **Tool search** を **On** にします。

Included には `travel_ops_api` という 1 つの tool として表示されますが、その中には
4 つの操作が定義されています。Tool Search は各操作を個別の tool として扱い、
Code Interpreter と Web Search を合わせた次の 6 つを検索対象にします。

| 種類 | 公式形式での候補名 | 用途 |
|---|---|---|
| OpenAPI | `travel_ops_api.getHealth` | API が利用可能か確認する |
| OpenAPI | `travel_ops_api.getPerDiem` | 都市ごとの日当と宿泊費上限を照会する |
| OpenAPI | `travel_ops_api.createTripEstimate` | 出張費用を見積もる |
| OpenAPI | `travel_ops_api.createPreapproval` | 事前承認をシミュレーションする |
| Built-in | `code_interpreter` | 数値を比較・集計し、表に整形する |
| Built-in | `web_search` | 現在の公開旅行情報を検索する |

Agent は `tool_search` でこの中から必要な tool を探し、`call_tool` で選んだ tool を
実行します。`tool_search` と `call_tool` は検索と実行のための meta-tool なので、上の
6 つには含めません。2 つの Skills も tool ではなく MCP Resources のため、検索対象には
含まれません。

> [!NOTE]
> `Anonymous` は公開された合成データ専用 mock API の認証方式です。
> **Agent から Foundry Toolbox への認証まで Anonymous にする、という意味ではありません。**
> Toolbox 側は Microsoft Entra ID/RBAC を使います。

## 3.1 Code Interpreter と Web Search を確認・追加する

1. Included に **Code Interpreter** があればそのまま残し、なければ
   **+ Add > Add tool** から追加します。
2. **Web Search** も同様に確認して追加します。外部 connection は作成しません。
   同じ種類の tool は重複して追加しません。
3. Tool Search が **On** のままであることを確認します。

Code Interpreter は Travel Ops が返した数値の比較・集計・表整形に限定します。
Web Search は「現在の公開情報を調べて」と明示された場合だけ利用し、出典 URL と取得日時を
回答へ含めます。通常の規程質問や見積もりでは、どちらも呼び出しません。

## 4. 2 つの Skills をアップロードする

1. **Included > + Add > Add skill** を選択します。
2. **Select a skill** の **Configured** で **Add skill** を選択します。

3. メニューから **Upload skill** を選択します。
4. **Browse** を押し、PC に保存した `travel-estimation.zip` を選びます。
5. 表示されたファイル名と **Name = travel-estimation** を確認し、**Create** を押します。
   Name と Description は、ZIP 内の `SKILL.md` から読み取られます。
6. Toolbox の画面に戻り、Included に Skill が増えたことを確認します。
7. 同じ **Add skill > Upload skill** の手順で
   `preapproval-simulation.zip` を選択します。
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

## 6. Prompt Agent に Microsoft Entra で接続する

Toolbox は MCP という共通の接続方式で Agent から呼び出します。
**Lab 3 の Knowledge は削除しません。**

1. 公開済み Toolbox の **Call this toolbox > Endpoint** を **Copy endpoint** でコピーします。
2. **Build > Agents > contoso-travel-assistant** を開きます。
3. **Tools** 側の **Add > Add tools** を開きます。Knowledge 側の Add ではありません。
4. **Custom > Model Context Protocol (MCP)** を選択し、**Create** を押します。

5. 接続画面を次の値に揃えます。

| 項目 | 値 |
|---|---|
| Name | `contoso-travel-toolbox-mcp` |
| Remote MCP Server endpoint | 公開済み Toolbox からコピーした Endpoint |
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
- tool_search の query は日本語の説明文にせず、目的に合う英語の tool 名を1つ使う。
  見積もりは createTripEstimate、日当照会は getPerDiem、明示された承認シミュレーションは
  createPreapproval、数値計算は code_interpreter、明示された公開情報検索は web_search。
  検索結果の正式な name と inputSchema を確認して call_tool を呼び、未発見の tool を推測しない。
- Code Interpreter は API 結果の数値比較、集計、表整形にだけ使い、規程値や旅程を作らない。
- Web Search はユーザーが現在の公開旅行情報を明示的に求めた場合だけ使い、出典 URL と
  取得日時を示す。秘密、資格情報、個人情報、顧客データを検索へ送らない。
- 見積もりだけの依頼で createPreapproval を呼ばない。明示的な実行意思を確認した場合だけ
  合成の事前承認シミュレーションを行い、実際の承認・予約ではないと明示する。
```

**Authentication** に **Microsoft Entra**、または **Type** に
**Project Managed Identity** が表示されない場合は connection を作成せず、Lab 1 の
managed identity と RBAC が validation 済みか確認して講師へ共有します。
API key や手動の bearer token には切り替えません。

## 7. ハンズオン用 MCP の tool を自動承認する

この後、Agent が Toolbox の tool を呼ぶたびに確認画面が表示されないよう、
`contoso-travel-toolbox-mcp` の tool を自動承認します。これにより、この Lab の動作確認と
Lab 5 / 6 の自動評価を途中で止めずに実行できます。

自動承認するのは、合成データだけを扱うこのハンズオン専用の MCP 接続です。
一般の業務 API や、最初から追加されていた管理用 tool には設定しないでください。

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
3. **Trajectories** で `invoke_agent contoso-travel-assistant` を展開し、次の順序を確認します。
   - `tool_search` が見積もり用の tool を発見する
   - `call_tool` がその tool を選択する
   - Toolbox が `travel_ops_api___createTripEstimate` を実行する
4. 実行された tool の **Input + Output** で、入力の都市、日程、座席クラス、人数と、
   出力の `total_estimate` を確認します。`total_estimate` は Playground の回答の合計と
   一致する必要があります。
5. `getHealth`、`getPerDiem`、`createPreapproval`、Code Interpreter、Web Search が
   実行されていないことを確認します。Tool Search の候補に現れただけでは「実行」ではありません。

Portal の版によっては、実 tool が `call_tool` の内側や別階層に表示されるほか、
`execute_tool` と表示されることもあります。表示名だけで判断せず、**Input + Output** の
tool 名を確認してください。

### 任意: 用途ごとの tool 選択を確認する

次の 2 ケースでは、依頼に応じて異なる機能を使い分けられることを確認します。

#### 見積もり結果を集計する

Playground に戻り、Section 8 の見積もりが表示されている同じ chat で次を送ります。

```text
直前の見積もり結果について、Code Interpreterを使って航空券・宿泊・日当の比率を計算し、
表に整形してください。新しい規程値や旅程は仮定しないでください。
```

Trace で `code_interpreter` が実行され、API が返した金額だけを使って計算していることを
確認します。

#### 費用と承認手続きをまとめて確認する

**New chat** で次を送ります。

```text
東京からニューヨークへ2026-07-10〜2026-07-15に、1名、ビジネスクラスで出張します。
費用を見積もり、ビジネスクラスの承認者と承認順序、申請に使う機能名、
申請から承認完了までの標準最大営業日数を規程の根拠とともにまとめてください。
予約や承認シミュレーションは実行しないでください。
```

この質問では利用する機能を指定しません。Agent が内容に応じて機能を使い分け、
Trace に次の両方が記録されていることを確認します。

- Toolbox: `travel_ops_api___createTripEstimate`
- Foundry IQ: `knowledge_base_retrieve`


## 完了チェック

- OpenAPI、Code Interpreter、Web Search と 2 Skills を含み、Tool Search On の Toolbox を公開した
- Trace で `tool_search → call_tool → createTripEstimate` を確認した
- 見積もり依頼で無関係な tool と `createPreapproval` が呼ばれないことを確認した
- 2 つの Skills が Toolbox に登録・公開されている

> [!NOTE]
> この Lab で確認するのは、2 つの Skills が Toolbox に登録・公開されていることまでです。
> Portal の Prompt Agent では、MCP Resources として公開された Skills の読み込みを確認できません。
> 登録済みであることを利用済みとはみなさず、実際の読み込みは Lab 7 で
> `load_skill` / `resources/read` の記録を使って確認します。


## 任意: SDK から Toolbox を確認する

[`notebooks/04-create-toolbox.ipynb`](../notebooks/04-create-toolbox.ipynb) は、Portal で作成した
Toolbox を SDK から確認・更新するための補助教材です。本編の完了には必要ありません。

実行する場合は、Lab 7 の [共通環境の準備](../docs/participant/environments/codespaces.md)と
`notebooks/00-setup.ipynb` を完了し、**Python (Foundry Workshop)** kernel を選びます。
Notebook では次を確認できます。

- 既存の Skills、tools、guardrail、Tool Search を保持した OpenAPI の更新
- 不足している built-in tool と Tool Search の追加
- Prompt Agent の呼び出しと、Tool の Input / Output の確認

Skill のアップロードには、この Lab の Portal 手順を使います。

公式仕様: [Toolbox](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/toolbox) /
[Skills](https://learn.microsoft.com/azure/foundry/agents/how-to/tools/skills)。
困った場合は [Toolbox のトラブルシューティング](../docs/participant/troubleshooting.md#lab-4-のファイル)
を参照してください。

## 次の Lab

[Lab 5 — Portal で Agent evaluation](05-evaluation.md)

# Lab 0 — 全体像と進め方（5分）

## ゴール

「何を作るか」「どこを操作するか」「何を確認して次へ進むか」をつかみます。
この Lab ではまだ Azure resources を作りません。

## 題材 — 出張の相談に答える

あなたは架空の Contoso 社の出張・経費アシスタントを作ります。
使う規程、旅程、領収書、質問集はすべて教材の**合成データ**です。
実際の社員情報や領収書を用意する必要はありません。

| 相談の例 | 確認したいこと |
|---|---|
| 「大阪出張のホテル代は、1 泊いくらまで？」 | 合成の宿泊規程にある 15,000 円という上限と、引用元を示せるか |
| 「東京から大阪へ 2026-05-11〜2026-05-12、economy、1 名の概算を出して」 | API が返す交通・宿泊・食事の内訳と合計を、勝手に作り替えず説明できるか |
| 「大阪出張の費用を教えて」 | 日付などが足りないとき、推測で埋めずに聞き返せるか |

ここでの例は**到達点を理解するためのもの**です。Lab 2 の時点では、まだ規程も
計算機能も接続していません。各 Lab の指定する質問を、その機能を追加してから試します。
回答の文章が例と違っていても、根拠・入力値・金額などの確認事項が合っていれば構いません。

## 学習の流れ

![Lab 0・1 の準備、Lab 2〜6 の Prompt Agent の段階的な拡張、独立した Lab 7 の policy_agent → planner_agent → reviewer_agent、Lab 8 の実行履歴確認と cleanup](../docs/images/workshop-learning-flow.svg)

[学習図の編集元](../docs/diagrams/workshop-learning-flow.excalidraw)

**Lab 2〜6 は同じ Prompt Agent に機能を追加して点検する流れ**です。
**Lab 7 はコードで別のアシスタントを作る独立した演習**です。
前の Lab の Foundry IQ / Toolbox / Travel Ops API は Lab 7 に接続しません。
図の矢印は各演習内の学習・処理の順序であり、全 Lab をつないだ実行システムではありません。

## 最初に知っておく言葉

| 言葉 | この教材での意味 |
|---|---|
| **Agent** | 指示に沿って応答し、必要に応じて検索や計算を使う AI の担当者 |
| **Prompt Agent / Instructions** | Instructions（指示文）で役割や回答方法を設定する Agent。「分からない情報は確認する」などの方針を文章で与える |
| **Knowledge** | 回答の根拠にする資料。ここでは出張の利用条件や承認手続きの規程 |
| **Azure AI Search / Foundry IQ** | Azure AI Search は資料を検索できる形で保管するサービス。Foundry IQ は複数の資料から必要な情報を探す仕組み。検索してから答える方法を **RAG** と呼ぶ |
| **Tool / API** | Tool は検索・計算などの実行機能。API は別のプログラムに処理を依頼する窓口。ここでは Travel Ops API に日当照会や費用計算を依頼する |
| **Skill** | Tool をいつ・どう使うかを書いた手順書。不足情報の確認や結果の説明方法を示す。アクセス権や強制的な承認制御の代わりではない |
| **Toolbox** | Tool と Skill をまとめて Agent に渡す入れ物 |
| **Evaluation / rubric / judge** | Evaluation は同じ質問集で回答を点検すること。rubric は採点基準、judge はその基準で回答を判定する役。AI の判定理由も人が確認する |
| **Optimizer** | 指示文の改善候補を作り、評価して比較する仕組み。必ず改善するわけではなく、元の Agent を維持する判断もある |
| **Hosted Agent / workflow** | Hosted Agent は自分のコードを Foundry 上で動かす方式。workflow は担当者をどの順序で動かすかを定めた処理の流れ |
| **Trace** | 一回の実行で、どの Agent や Tool が動いたかをたどる実行履歴 |

用語をすべて暗記する必要はありません。「資料を読むのか」「処理を実行するのか」
「結果を点検するのか」を区別できれば、操作の目的を追いやすくなります。

## 各 Lab で追加するものと完了の目印

| Lab | 追加するもの・行うこと | 完了の目印 | 主な操作場所 |
|---|---|---|---|
| [Lab 1](01-setup.md) | 管理者から渡された既存 resource group に、共通の Azure 環境を準備 | 事前確認が `pass`、API の応答が `ok`。自分の Foundry project を開ける | Codespace Terminal → Foundry Portal |
| [Lab 2](02-prompt-agent.md) | 役割と指示文を持つ Prompt Agent を作成 | Agent の名前・モデル・指示文が保存され、Knowledge と Tools はまだ空である | Foundry Portal |
| [Lab 3](03-rag-foundry-iq.md) | 直接の文書検索を試した後、Foundry IQ で複数の資料を検索 | 利用条件と承認手続きの規程に基づく回答と引用元を確認できる | Foundry Portal |
| [Lab 4](04-tools-toolbox.md) | 規程の検索を残し、計算 Tool と使い方の Skill を Toolbox で追加 | Tool の呼び出し・引数・結果を確認できる。Skill の登録と実際の利用を区別する | Codespace Terminal / Explorer → Foundry Portal |
| [Lab 5](05-evaluation.md) | 同じ合成質問集と基準で回答を評価 | 結果の点数と個別の判定理由を読める | Foundry Portal |
| [Lab 6](06-optimization.md) | 指示文の改善候補を生成し、元の回答と比較 | 変更内容と評価を読み、採用するか、元の Agent を維持するか判断できる | Foundry Portal |
| [Lab 7](07-hosted-multi-agent.md) | 独立した 3 Agent の workflow を作り、Hosted Agent として配置 | Notebook で途中回答を追え、配置後も最終回答を確認できる | Codespace Notebook → Terminal → Foundry Portal |
| [Lab 8](08-observability-cleanup.md) | Trace を読み、演習で作ったものを片付ける | 実行順を確認し、Lab 8 の削除確認を完了する。既存 resource group は残す | Foundry Portal → Codespace Terminal |

Lab 7 では `policy_agent`（規程を確認する担当）→ `planner_agent`（案を作る担当）→
`reviewer_agent`（見直す担当）の順で回答を引き継ぎます。
これは予約や承認を実行する仕組みではなく、担当を分けた処理の**シミュレーション**です。

## 操作面の使い分け

手元の PC では、次の **2 種類のブラウザータブ**を使います。

| 開く場所 | 使い方 |
|---|---|
| **GitHub Codespaces** の VS Code | 教材ファイルを開く作業環境。**Explorer** はファイル一覧、**Terminal** はコマンドの実行欄。コードブロックの `bash` はこの Terminal で実行する |
| Codespace 内の **Jupyter Notebook** | `.ipynb` ファイルを Explorer から開く。Lab 7 で説明を読み、コードを cell（小さな実行単位）ごとに実行する。実行環境の **kernel** は Lab 7 の指定を選ぶ |
| **Microsoft Foundry Portal** | Agent や Knowledge を設定し、**Playground**（会話を試す画面）で動作を確認する。**Foundry (new)** の **English UI・ダークモード**を使う |

Notebook は第三のサービスへサインインするものではなく、Codespace 内で開きます。
手元の PC の PowerShell、macOS Terminal、Azure Cloud Shell では本編のコマンドを
実行しません。Lab 4 のアップロード用ファイルだけは、Codespace から PC へ
ダウンロードしてから Portal で選択します。

まだ Codespace を開いていない場合は、
[参加者向け前提条件](../docs/participant/prerequisites.md)で準備してください。

## モデルと自分の環境の値

**モデル ID** はモデルの種類、**deployment 名**はそのモデルを呼び出すときの名前です。
**Terraform output キー**は、環境構築後の設定ファイルから値を取り出す項目名です。
Portal では output キーではなく、そこに保存された deployment 名を選びます。

| 用途 | モデル ID | deployment 名 | Terraform output キー |
|---|---|---|---|
| Prompt Agent / Hosted Agent / Foundry IQ の検索計画 | `gpt-5.6-luna`（Luna） | `gpt-5.6-luna` | `primary_model_deployment_name` |
| 評価の LLM judge / Optimizer の評価・候補生成 | `gpt-5.5` | `gpt-5.5` | `optimizer_model_deployment_name` |
| 検索用に文章を数値へ変換する埋め込み | `text-embedding-3-small` | `embedding` | `embedding_model_deployment_name` |

会話系 2 つと埋め込み 1 つ、**合計 3 deployment** です。
Foundry IQ 用に別の deployment を作る必要はありません。
評価では「回答する Agent の Luna」と「回答を採点する gpt-5.5」の役割を区別します。
judge を指定できる評価項目についての選択方法は Lab 5 に従ってください。
モデル名だけで採点の正しさが保証されるわけではないため、判定理由も読みます。

参加者ごとに異なる resource 名や endpoint は
Lab 1 が生成する **`.workshop/context.json`** から取得します。
endpoint は接続先の URL です。画像中の名前や URL を写すのではなく、
各 Lab の確認コマンドで**自分の値**を使ってください。
`<subscription-id>` と `<resource-group>` は、管理者から渡された値に置き換える目印です。

## 詳細な Azure 構成

次の図は学習順ではなく、準備するサービスの配置を示します。
今は「既存 resource group の中に演習用の環境を作る」と分かれば十分です。

![既存 resource group 内の Foundry project、検索、Travel Ops API などの配置](../docs/images/workshop-architecture.svg)

[構成図の編集元](../docs/diagrams/workshop-architecture.excalidraw)

## 費用とデータの注意

> [!WARNING]
> モデル呼び出し・評価・最適化、Hosted Agent や Azure resources の稼働、
> Codespaces の利用には料金が発生します。実行中の課金処理をむやみに再送しないでください。
> ブラウザーを閉じてもリソースは残ります。終了時は
> [Lab 8](08-observability-cleanup.md) の cleanup を行い、Codespace も停止します。

入力は Foundry や接続した Tool で処理されます。実在する個人・顧客・予約の情報は
入力しないでください。手元にある認証情報や Terraform state を教材やチャットへ
貼り付けないでください。

## 完了チェック

- 規程を調べる機能と、費用を計算する機能の違いを説明できる
- Lab 2〜6 と Lab 7 が別の演習であることが分かる
- コマンドは Codespace の Terminal、Agent の設定は Foundry Portal で行うと分かる
- 管理者から受け取る値と、自分の環境から取得する値を区別できる

## 次の Lab

[Lab 1 — 環境構築](01-setup.md)

**日本語** | [English](README.en.md)

# Microsoft Foundry Agent Service Hands-on

「大阪への出張で、ホテルはいくらまで使える？」「旅費の内訳を計算してほしい」。
架空の Contoso 社の社員から届く、こうした相談に答える AI アシスタントを作ります。
最初は会話だけの状態から始め、規程を調べる、API で計算する、回答を評価して改善する、
という順に機能を追加します。AI Agent の開発経験は不要です。

![学習の流れ。Lab 0・1 で準備し、Lab 2〜6 で一つの Prompt Agent を拡張する。Lab 7 は独立した 3 Agent のシミュレーションで、Lab 8 で実行履歴の確認と片付けを行う](docs/images/workshop-learning-flow.svg)

[学習の流れを Excalidraw で編集する](docs/diagrams/workshop-learning-flow.excalidraw)

図の左側は **同じ Agent を育てる Lab 2〜6**、右側は **別の作り方を学ぶ Lab 7** です。
Lab 7 を前の機能と統合した最終アプリにはしません。すべての題材は合成データで、
実際の予約・承認・精算は行いません。

## 何ができるようになるか

| 学ぶこと | この演習での意味と、確認する結果 |
|---|---|
| **Agent / Prompt Agent** | Agent は指示に沿って応答し、必要に応じて機能を使う AI の担当者。Prompt Agent は、その指示を文章で設定する方式です。まず役割と回答方針を保存します |
| **Knowledge / Foundry IQ** | Knowledge は回答の根拠にする資料。Foundry IQ は複数の資料を調べる仕組みです。出張規程を検索し、引用元を確認します |
| **Tool / Skill / Toolbox** | Tool は計算などを実行する機能、Skill は使い方の手順書、Toolbox は両方をまとめて Agent に渡す入れ物です。Travel Ops API（別のプログラムに計算を依頼する窓口）で費用内訳を取得します |
| **Evaluation / Optimizer** | Evaluation は同じ質問集と基準で回答を点検すること。Optimizer は指示文の改善案を試して比較する仕組みです。点数だけでなく判定理由を読み、採用するか判断します |
| **Hosted Agent** | 自分で書いたコードを Foundry 上で動かす方式です。Lab 7 では規程確認・計画・見直しの 3 担当を順に動かす、独立したシミュレーションを作ります |

たとえば Lab 3 では「大阪の宿泊費の上限は？」に対して、合成規程の
「1 泊 15,000 円」と出典を確認します。Lab 4 では日程・都市などを渡して、
API が返す費用内訳と合計を確認します。これは**学ぶ内容の例**であり、
回答文が毎回同じになることを求めるものではありません。

## どこを操作するか

- **ブラウザーの GitHub Codespaces**: ブラウザー内の VS Code で教材ファイルを開きます。
  **Terminal** はコマンドを実行する場所、**Notebook** は説明と Python コードを
  小さな単位で読みながら実行するファイルです。必須の Notebook 演習は Lab 7 です。
- **別のブラウザータブの Microsoft Foundry Portal**: Agent の設定、会話、評価結果などを
  操作します。教材は **Foundry (new) の English UI・ダークモード**に、日本語で説明を付けています。
- **手元の PC**: ブラウザーを使い、Lab 4 などでアップロードする素材を保存します。
  本編のコマンドは PC の PowerShell や Terminal ではなく、**Codespace の Terminal**
  で実行します。

モデルは合計 **3 deployment**（モデルを呼び出すための配置単位）です。
Prompt / Hosted Agent と Foundry IQ は **Luna（`gpt-5.6-luna`）** を共有し、
評価の採点役と Optimizer は **`gpt-5.5`** を共有します。
文書検索用の **`text-embedding-3-small`** は文章を検索用の数値に変換します。
選択する名前と役割は [Lab 0](labs/00-overview.md) で確認します。

## 参加条件

- GitHub Codespaces を利用できる GitHub account
- `az login` が可能な Azure account
- 管理者から割り当てられた subscription と**既存** resource group
- その resource group に対する **Owner** role

詳しい確認項目は
[参加者向け前提条件](docs/participant/prerequisites.md)を参照してください。

## ハンズオンを始める

**[Lab 0 — 全体像と進め方](labs/00-overview.md) から開始してください。**
まず作るものを確認し、[参加者向け前提条件](docs/participant/prerequisites.md)で
Codespace の準備を行います。Azure 環境構築のコマンドは Lab 1 で案内します。
各 Lab の完了チェックを確認してから、末尾の「次の Lab」へ進んでください。

## Agenda

| Lab | 内容 | 所要時間（目安） |
|---|---|---:|
| [Lab 0](labs/00-overview.md) | 全体像と進め方 | 5分 |
| [Lab 1](labs/01-setup.md) | Codespaces と Terraform による環境構築 | 20分 |
| [Lab 2](labs/02-prompt-agent.md) | Prompt Agent の作成 | 10分 |
| [Lab 3](labs/03-rag-foundry-iq.md) | Azure AI Search と Foundry IQ | 35分 |
| — | 休憩 | 10分 |
| [Lab 4](labs/04-tools-toolbox.md) | Portal で Toolbox と Skills を作成 | 30分 |
| [Lab 5](labs/05-evaluation.md) | Portal で Agent evaluation | 15分 |
| [Lab 6](labs/06-optimization.md) | Agent Optimizer | 20分 |
| [Lab 7](labs/07-hosted-multi-agent.md) | Agent Framework の Hosted Agent | 40分 |
| [Lab 8](labs/08-observability-cleanup.md) | Observability と cleanup | 10分 |

## Azure 上の構成を知りたいとき

こちらは学習順ではなく、Lab 1 で準備するサービスの配置を示した詳細図です。
初めはすべての名前を覚える必要はありません。

![既存 resource group 内の Microsoft Foundry、Azure AI Search、Travel Ops API などの構成](docs/images/workshop-architecture.svg)

[構成図を Excalidraw で編集する](docs/diagrams/workshop-architecture.excalidraw)

## 困ったとき

- 操作や実行エラー:
  [参加者向けトラブルシューティング](docs/participant/troubleshooting.md)
- 管理者側の quota / provider:
  [管理者向け前提条件](docs/admin/prerequisites.md)
- 追加機能:
  [Optional labs](labs/optional/README.md)

> [!WARNING]
> モデル呼び出し・評価・最適化、Azure resources、Codespaces の利用には料金が発生します。
> ブラウザーを閉じても Azure resources は削除されません。終了時は必ず
> [Lab 8](labs/08-observability-cleanup.md) の cleanup を実行し、Codespace も停止してください。

# Lab 0 — 全体像と進め方（5分）

## ゴール

架空の Contoso 社を題材に、**規程を調べ、費用を計算できる出張・経費アシスタント**を作ります。
さらに、同じ Foundry IQ・Toolbox・Skills をコードから再利用し、Harness Agent を
workflow の担当として組み込む流れを体験します。

使う規程・旅程・質問集はすべて教材の合成データです。実際の予約や承認は行いません。

## どんな相談に答えるか

| 相談の例 | アシスタントに期待すること |
|---|---|
| 「大阪出張のホテル代は、1 泊いくらまで？」 | 規程を検索し、根拠とともに答える |
| 「東京から大阪へ、1 名で出張する場合の概算を出して」 | 必要な条件を確認し、API で費用を計算する |
| 「大阪出張の費用を教えて」 | 情報が足りなければ、推測せずに聞き返す |

## 学習の流れ

![準備から Prompt Agent の拡張・評価、Harness Agent と Hosted workflow、trace 比較と cleanup まで](../docs/images/workshop-learning-flow.svg)

**Lab 2〜6 は同じ Prompt Agent を育てる演習**です。**Lab 7 はその Foundry IQ、
Toolbox、Skills をコードから plain Agent に接続し、Harness Agent に発展させます。**
**Lab 8 は同じ checked-in Harness factory を sequential workflow の participant として
再利用し、workflow 全体を Hosted Agent として deploy します。**

| Lab | 体験すること | 到達点 |
|---|---|---|
| [Lab 1](01-setup.md) | 共通の Azure 環境を準備する | 自分の Foundry project を開ける |
| [Lab 2](02-prompt-agent.md) | Prompt Agent を作り、Azure AI Search を接続する | 1 つの規程 index を直接検索できる |
| [Lab 3](03-rag-foundry-iq.md) | Foundry IQ を接続し、直接検索と比較する | 複数の規程を根拠に回答できる |
| [Lab 4](04-tools-toolbox.md) | API・Code Interpreter・Web Search・Skills を Toolbox にまとめる | Tool Search で必要な機能を選んで実行できる |
| [Lab 5](05-evaluation.md) | 同じ質問集で Agent を評価する | 点数と判定理由から改善点を見つける |
| [Lab 6](06-optimization.md) | 指示文の改善候補を比較する | 採用するか、元の設定を維持するか判断する |
| [Lab 7](07-agent-framework-harness.md) | plain Agent と Harness Agent をコードで比較する | Foundry IQ・Toolbox・Skills と plan / todo / memory の役割を追える |
| [Lab 8](08-hosted-multi-agent.md) | Harness Agent を workflow に組み込んで deploy する | intake → Harness → reviewer の引き継ぎを追える |
| [Lab 9](09-observability-cleanup.md) | Trace を比較し、環境を片付ける | Prompt / Hosted の実行の流れを比較し、演習用 resources を削除できる |

Azure 構成の詳細は [アーキテクチャ](../docs/architecture.md)を参照してください。

## 始める前に

[参加者向け前提条件](../docs/participant/prerequisites.md)で Codespaces または
Cloud Shell Bash + JupyterLab を選び、
subscription IDと講師の命名規則を確認して、自分の教材workload用resource groupを作成してください。
環境別の準備は Lab 1 で行います。Lab 2 以降は同じ手順・Notebook へ合流します。

> [!WARNING]
> モデル・評価・最適化・Azure resources・Codespaces の利用には料金が発生します。
> Cloud Shell の計算環境は無料ですが、永続ストレージは課金対象です。
> 終了時は [Lab 9](09-observability-cleanup.md) の cleanup 後、環境ガイドの終了手順を行ってください。
> ブラウザーを閉じるだけでは、リソースは削除されません。

実在する個人・顧客・予約の情報や、認証情報・Terraform state は入力・共有しないでください。

## 次の Lab

[Lab 1 — 環境構築](01-setup.md)

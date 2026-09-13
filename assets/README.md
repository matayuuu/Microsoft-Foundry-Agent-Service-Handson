# 共通教材（Lab 4）

GitHub で各ファイルを開き、**Download raw file** で取得します。
Skill ZIP は展開せず、Foundry Portal の Skill upload に使用してください。

| 教材 | 共通ファイル |
| --- | --- |
| 出張費用の見積もり Skill | [travel-estimation.zip](skills/travel-estimation.zip) |
| 事前承認シミュレーション Skill | [preapproval-simulation.zip](skills/preapproval-simulation.zip) |
| Travel Ops API の OpenAPI 3.1 | [travel-ops.openapi.json](openapi/travel-ops.openapi.json) |

OpenAPI を Portal の schema editor に貼り付け、`servers[0].url` の
`https://replace-with-your-travel-api.example.invalid` だけを、自分の ARM deployment の
**Outputs → travelApiBaseUrl** の値に置き換えます。他の schema は変更しません。
API の認証設定は **Anonymous** です。共通ファイルに環境やアカウントの情報は含めません。

## 再生成・検証

Skill の正本は `data/skills/<name>/SKILL.md`、OpenAPI の正本は
`src/travel-api` の `app.openapi()` です。ZIP や JSON は直接編集しません。
Python 3.12 の管理環境にリポジトリの依存関係と API の
`src/travel-api/requirements.txt` の固定依存関係を導入し、リポジトリのルートで実行します。

```console
python -B -m scripts.build_common_assets
python -B -m scripts.build_common_assets --check
```

生成はローカルのソースだけを使用します。`--check` は書き込まず、欠落・差分・無効なソースで
非ゼロ終了します。API の契約を変更する場合は、配布する固定 image との整合も確認してください。
環境別 ZIP、`portal-values.json`、接続設定、資格情報は生成しません。

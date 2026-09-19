# Contoso Travel Ops API

[開発者向けガイド](../../docs/development/README.md) / [ハンズオンの構成](../../docs/development/architecture.md)

Microsoft Foundry Agent Service ハンズオンの「Contoso 出張・経費」シナリオで使う、
状態を保持しない模擬 API です。データベース、外部呼び出し、乱数は使いません。
要求とメモリー上の固定データから応答を決定するため、エージェントの評価・最適化で同じ条件を再現できます。

## 構成と制約

- `travel_api/domain` は入出力を持たない規程ルール、
  `travel_api/application` はフレームワークに依存しないユースケース、
  `travel_api/adapters/api` は要求・応答の変換と HTTP ステータスへの対応付けを行う FastAPI アダプターです。
- OpenAPI 3.1 を使い、各操作に `operationId` と型付きの Pydantic 要求・応答モデルを定義します。
- `POST /preapprovals` は常にシミュレーションです。判定値は `simulated_` で始まり、
  応答に注意書きを含めます。実際の出張承認を与えるものではありません。
- 個人情報は扱いません。受け渡す識別子は `employee-001` などの合成データ用の別名だけです。

## エンドポイント

| メソッド | パス | operationId | 用途 |
|---|---|---|---|
| GET | `/health` | `getHealth` | 稼働・応答可能状態の確認 |
| GET | `/per-diem?city=&date=` | `getPerDiem` | 都市・日付に対応する日当と宿泊上限 |
| POST | `/trip-estimates` | `createTripEstimate` | 航空券・宿泊・食事の費用見積もり |
| POST | `/preapprovals` | `createPreapproval` | 事前承認の模擬判定 |

対話型の OpenAPI 文書は `/docs`（Swagger UI）と `/redoc`、
JSON の仕様は `/openapi.json` で提供します。

## ローカルでの実行

Python 3.12 が必要です。このディレクトリ（`src/travel-api`）から実行します。

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"

uvicorn travel_api.main:app --host 0.0.0.0 --port 8080
```

別の Terminal から応答を確認します。

```bash
curl http://127.0.0.1:8080/health
curl "http://127.0.0.1:8080/per-diem?city=Osaka&date=2026-05-11"
```

## Docker での実行

```bash
docker build -t travel-ops-api:local .
docker run --rm -p 8080:8080 \
  -e WORKSHOP_SOURCE_BASE=https://github.com/example/workshop/blob/main \
  travel-ops-api:local
curl http://127.0.0.1:8080/health
```

コンテナーは root 以外のユーザーで動き、ポート 8080 で待ち受けます。
`HEALTHCHECK` は Python 標準ライブラリで `/health` を確認します。
`-slim` のベースイメージには `curl` / `wget` がないためです。
永続ボリュームを使わず、Azure Container Apps で要求の間にゼロへスケールできます。

`WORKSHOP_SOURCE_BASE` は、応答中の規程参照用の仮 URL を置き換えます。
ローカル実行で参照先が解決しない仮 URL を許容する場合は、省略できます。

## テスト

このコンポーネントの依存関係は、ルートの `pyproject.toml` から分離しています。
このディレクトリの `requirements.txt` / `pyproject.toml` を参照してください。
`tests/unit/travel_api/` と `tests/contract/travel_api/` を実行するには、先に API の依存関係を導入します。
次の例は、リポジトリのルートから始めます。

```bash
cd src/travel-api
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"

cd ../..
python -m pytest tests/unit/travel_api tests/contract/travel_api
```

ドメインの単体テストは `travel_api` パッケージが `sys.path` にあれば実行でき、FastAPI は不要です。
HTTP 層や `/openapi.json` を検査する契約テストには `fastapi` / `httpx` も必要です。
不足している場合は `pytest.importorskip` でスキップするため、ルートの `make test` は
このコンポーネントの依存関係を導入する前でも実行できます。
スキップされた契約テストを、検証済みとして扱わないでください。

## 規程データとの数値の整合

`travel_api/domain/rates.py` の日当・宿泊上限は、
`data/policies/03-hotels.md` と `data/policies/04-per-diem-meals.md` の表に合わせています。
`tests/contract/data/test_per_diem_rates_match_policy.py` が Markdown の表を読み取り、
実装と数値が一致することを確認します。規程と API のどちらを変更した場合も、この契約を維持します。

## コンテナーの公開

[公開ワークフロー](../../.github/workflows/publish-travel-api.yml)は、`travel-api-v*` のタグまたは手動実行を契機に
公開 GHCR イメージをビルド・送信します。公開タグに `latest` は使いません。
演習用 Bicep の `travelApiImageRef` には、ジョブの概要に出力された変更不能なダイジェスト参照を設定します。
更新方法は [インフラ実装ガイド](../../infra/README.md) を参照してください。

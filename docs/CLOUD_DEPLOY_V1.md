# クラウド配置 v1（Render）

Multi-AI Chat v1 のFastAPIゲートウェイを常時アクセス可能にするための配置手順。

## 構成

- GitHub: 正本コード
- Render Web Service: FastAPI / Multi-AI router / Notion writer
- APIキー: Render側のSecretとして保持
- Browser UI: 後でこのAPIへ接続

## 配置

リポジトリ直下の `render.yaml` をRender Blueprintとして読み込む。

秘密情報はGitHubに書かない。
Blueprint初回作成時に `sync: false` の値をRender側で入力する。

最低限必要:

- `OPENAI_API_KEY` または `GEMINI_API_KEY` のどちらか1つ
- `ALLOWED_ORIGIN`: 接続を許可するブラウザ画面のOrigin

Notion記録を使う場合:

- `NOTION_TOKEN`
- `NOTION_DATA_SOURCE_ID`

Copilotを接続する場合:

- `COPILOT_BRIDGE_URL`
- 必要なら `COPILOT_BRIDGE_KEY`

## 配置確認

公開URLが発行されたら:

1. `GET /health` が200になること
2. 認証付き `GET /api/chat/providers` で設定済みAIが表示されること
3. `POST /api/chat` で単独AI回答
4. 2つ以上設定済みなら `verify=true` で相互検証
5. Notion利用時は `POST /api/notion/log` の追記確認

## セキュリティ

現状の `GATEWAY_CHAT_KEY` は開発・限定試験用。
公開ブラウザへ固定キーを埋め込む運用はしない。
一般公開前にログインまたは短期トークン方式へ変更する。

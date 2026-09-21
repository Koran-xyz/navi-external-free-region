# マルチAIチャットボット v1

## 目的

利用者は1つのチャット窓口「ナビィ」に普段の言葉で相談する。
裏側で、利用可能なAI・外部自由領域・ロボットを組み合わせる。

## v1 の流れ

1. ブラウザから `POST /api/chat`
2. ナビィのルーターが利用可能なAIを確認
3. 内容に応じて OpenAI / Gemini / Copilot bridge を選択
4. 外部自由領域の現在地・目的・次作業を共有
5. 必要なら2つ目のAIで検証
6. 一次回答と検証結果を統合して返す

## 重要

- APIキーはブラウザへ置かない。
- `META_RULES.md` が未固定の間は、メタルールを有効な規則としてAIへ渡さない。
- Copilotは汎用チャットAPIがある前提にせず、別途 `COPILOT_BRIDGE_URL` を接続する。
- v1 のBearerキーは開発・閉域試験用。公開ブラウザへ固定キーを埋め込まない。
- 削除、決済、公開、予約確定など重要操作は人の承認を通す。

## API

### GET /api/chat/providers

設定済みプロバイダと外部自由領域の状態を確認する。

### POST /api/chat

例:

```json
{
  "message": "この仕様を調べて実装案を作って",
  "preferred_provider": null,
  "verify": true
}
```

`verify=true` で2つ目のAIが利用可能な場合、第三者検証を行ってから統合回答を返す。

## 環境変数

- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `GEMINI_API_KEY`
- `GEMINI_MODEL`
- `COPILOT_BRIDGE_URL`
- `COPILOT_BRIDGE_KEY`
- `GATEWAY_CHAT_KEY`

既存のNotion書き込み用キーは `GATEWAY_WRITE_KEY` として分離する。

## 次の実装

- ブラウザ v0.1 を `POST /api/chat` へ接続
- サーバーをクラウドへ配置
- 認証を固定Bearerキーからログイン/短期トークン方式へ変更
- Notion読み出しロボットをHTTP化
- ロボット呼び出しをナビィの承認フローへ統合

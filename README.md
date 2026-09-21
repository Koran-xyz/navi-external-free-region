# Navi External Free Region

複数AIと人が、共通の状態・引き継ぎ・外部ロボットを使うための最小基盤です。

## 現在の実装

- 外部自由領域の状態・引き継ぎファイル
- 自然言語ゲートウェイ
- Notionへの追記専用ロボット
- FastAPI HTTPゲートウェイ
- Multi-AI Chat v1
  - OpenAI
  - Gemini
  - Copilot用外部ブリッジ
  - 必要時の第二AI検証
  - ナビィによる統合回答

## 重要な状態

`META_RULES.md` は現在「未固定」です。
固定されるまで、コードはメタルールを正式な運用規則としてAIへ渡しません。

## Multi-AI Chat

仕様は `docs/MULTI_AI_CHAT_V1.md` を参照してください。

APIキーやNotionトークンはGitHubへ保存せず、必ずサーバー側の環境変数/Secret Storeに設定します。

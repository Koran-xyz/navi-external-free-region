# Notion Gateway v0.3

外部自由領域の当面の共通記録庫は Notion の「内部自由領域システム」DB とする。

## 役割

| ロボット | できること | できないこと |
| --- | --- | --- |
| 読み出し専用 | 目的・状態・次作業・承認済みルール・名札を返す | 記録の変更、承認、外部送信 |
| 書き込み専用 | 新規の作業報告を追記する | 既存記録の編集・削除、承認、外部送信 |

## 共通入力

```json
{
  "record_name": "短い件名",
  "actor": "担当AIまたは人",
  "summary": "依頼・概要",
  "evidence": "根拠・確認結果",
  "result": "結果",
  "next_action": "次の作業",
  "status": "進行中"
}
```

## 実装

- `src/notion_writer.py`: Notionへの新規追記だけを行う
- `server/app.py`: ブラウザから呼ぶHTTP窓口
- `requirements.txt`: Pythonサーバー依存
- `.env.example`: 必要な環境変数名だけを記載

## 必要なSecrets

- `NOTION_TOKEN`
- `NOTION_DATA_SOURCE_ID`
- `GATEWAY_WRITE_KEY`
- `ALLOWED_ORIGIN`
- `NOTION_VERSION`（任意）

## 通信

```text
Browser chat
  -> POST /api/notion/log
  -> server/app.py
  -> src/notion_writer.py
  -> Notion
```

ブラウザへNotionトークンを渡さない。
サーバー側だけがNotion接続情報を持ち、書き込みAPIはBearerキーを確認してから新規記録を作る。

## 固定ルール

- 完了には根拠を必須とする。
- 既存記録は上書きせず、報告は新規追記する。
- 個人情報、会社機密、住所、生GPS、認証情報は共通記録に入れない。
- 外部送信・承認・削除は人が判断する。
- トークン、データソースID、書き込みキーは公開GitHubへ固定しない。

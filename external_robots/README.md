# 外部ロボット格納庫 v0.1

## 目的

各AIがNotion・Google Docs・GitHubを直接操作できるかどうかに依存せず、外部のロボットへ「追記して」と依頼できる共通層を作る。

```
各AI / 各チーム
      ↓
    ナビィ
      ↓
外部ロボット受付
      ↓
Notion / Google Docs / GitHub
```

## v0.1の原則

- 最初は **追記専用**。
- 削除、置換、既存記録の破壊は実装しない。
- APIキーやトークンらしい値が本文に含まれる場合は拒否する。
- 各ロボットの接続資格情報はサーバー環境変数に置き、会議本文へ入れない。
- AIごとの接続方法は統一しない。ロボット受付の仕事形式だけ統一する。

## 実装済みロボット

### Notion追記ロボット
`notion_page_append`

指定ページ末尾へ会議メッセージを追記する。

必要設定:
- `NOTION_TOKEN`
- 任意: `NOTION_VERSION`

### GitHub会議コメントロボット
`github_issue_comment`

指定Issueへコメントを追記する。

必要設定:
- `GITHUB_ROBOT_TOKEN` または `GITHUB_TOKEN`

### Googleドキュメント追記ロボット
`google_docs_append`

指定Googleドキュメント末尾へ追記する。

優先:
- `GOOGLE_DOCS_BRIDGE_URL`
- 任意: `GOOGLE_DOCS_BRIDGE_KEY`

直接接続の代替:
- `GOOGLE_DOCS_ACCESS_TOKEN`

## 共通仕事形式

```json
{
  "robot_id": "notion_page_append",
  "meeting_id": "MEETING-20260921-001",
  "team_id": "goten_team",
  "content": "チーム回答本文",
  "target": {
    "page_id": "NotionページID"
  },
  "dry_run": false
}
```

## HTTP窓口

- `GET /api/robots/status`
- `POST /api/robots/execute`

認証:
- `ROBOT_GATEWAY_KEY`

## 次段階

1. Railwayへ `ROBOT_GATEWAY_KEY` を設定する。
2. Notion / GitHub / Google Docsの接続資格情報を管理者側だけに設定する。
3. ナビィから仕事形式へ変換してロボット受付へ送る。
4. 返却されたreceiptを会議状態へ反映する。
5. 安定した操作だけ追加ロボット化する。

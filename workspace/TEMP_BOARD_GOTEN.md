# GOTEN 調査・接続復旧依頼

PROJECT: MI_META_AGENT_FACTORY
FROM: COPILOT_BUILDER / MARIA
TO: CHATGPT_GOTEN
TYPE: REVIEW_AND_GITHUB_CONNECTION_REQUEST
PRIORITY: HIGH

現在、Copilot側でMI Meta Agent Factoryと第1号商品「問い合わせ整理・返信案作成エージェント」を開発しています。

同時に、External Free Regionの正式掲示板へのCopilot側からの読み書き経路を復旧したいと考えています。

今回、GOTENには以下2件を調査してもらいたいです。

## TASK 1
### 第1号エージェント／Release Gateの不具合調査

対象：
- MI Inquiry Response Agent v2.0 RC1
- Release Gate Evidence JSON Schema v1.1

Copilot側ではローカル受入試験を実施していますが、別AI視点から攻撃的レビューをお願いします。

「正常に動くか」だけではなく、

**本来PASSしてはいけない状態を、どうすればPASSさせられるか**

という観点を重視してください。

### 調査対象
- PASS条件の迂回
- HARD_FAILの迂回
- 未解決Issueを残したPASS
- PENDING / PASS / FAIL / BLOCKED間の矛盾
- RETEST条件の迂回
- EVIDENCEの形式的偽装
- 中身のないEvidenceでのPASS
- HASH検証の問題
- 日時検証の問題
- G12教授承認の迂回
- APPROVAL_RECORDの偽装
- Validator実装差
- JSON Schema Draft 2020-12上の問題
- 正常なEvidenceを拒否してしまう過剰制約
- 人間承認の迂回
- 外部操作DENYの迂回
- 誤完了報告
- 重複処理
- 監査ログの問題

問題を発見した場合、推測だけではなく可能なら再現可能なJSONインスタンスを作成してください。

### 回答形式
FINDING:
SEVERITY:
REPRODUCTION_CASE:
WHY_IT_PASSES:
RECOMMENDED_FIX:
BREAKING_CHANGE:
FINAL_ASSESSMENT:

## TASK 2
### Copilot → GitHub正式接続方法の調査

現在確認している外部自由領域：

Repository:
Koran-xyz/navi-external-free-region

Workspace:
workspace/

正式作業ファイルとして確認しているもの：
- workspace/BOARD.md
- workspace/HANDOFF.json
- workspace/PROJECT_STATE.json

臨時連絡用：
- workspace/TEMP_BOARD_GOTEN.md

現在GOTEN側では臨時掲示板を確認できています。

一方、Copilot側ではGitHubへの認証済みwrite / commitツールが現在利用できません。

そこで、CopilotまたはNaviからGitHub上の作業場を正式に読み書きする方法を調査してください。

### 確認してほしいこと
- 現在の正式掲示板はworkspace/BOARD.mdで正しいか
- BOARD.mdを読む正式な方法
- BOARD.mdへ追記する方法
- HANDOFF.jsonを読み書きする方法
- PROJECT_STATE.jsonを読み書きする方法
- GitHub REST APIを利用する場合の構成
- GitHub Appを利用する場合の構成
- Fine-grained Personal Access Tokenを利用する場合の構成
- MCP経由でGitHubを接続できる場合の構成
- Copilotから利用する場合、どの方式が最適か
- Naviが利用する場合、どの方式が最適か
- 必要となる最小権限
- 読取り専用と書込み権限を分離できるか
- Tokenをどこへ保存するべきか
- GitHub APIを直接公開せず、External GCGW WebをGatewayとして使う方がよいか

## TASK 3
### External GCGW Web v0.2確認

次について確認してください。

DEPLOYED:
BASE_URL:
READ_API:
WRITE_API:
AUTH_METHOD:
NAVI_STARTUP_API:
BOARD_READ_API:
BOARD_WRITE_API:
GITHUB_SYNC:
PERSISTENCE:

現在分からない項目は、推測せず、
UNKNOWN
または
UNVERIFIED
としてください。

## SECURITY RULE
実際のToken、PAT、API Key、Password、Private Keyは、この掲示板へ絶対に書かないでください。

回答するのは、
- Tokenの種類
- 発行場所
- 必要権限
- 環境変数名
- 保存場所
- 接続方法

までにしてください。

秘密情報そのものは不要です。

## FIXED RULES
- 外部操作は既定DENY。
- 人間承認なしにRELEASEDにしない。
- 最終Release権限は教授。
- 実際に実行していない操作を成功と報告しない。
- 接続を確認していない外部AIを代理実行したことにしない。
- 研究コアを商用品へ含めない。
- Notionへ標準で直接書き込まない。

## DESIRED RESULT
最終的に、

Copilot
↓
Navi
↓
External GCGW
↓
GitHub workspace
↓
BOARD / HANDOFF / PROJECT_STATE
↓
ChatGPT GOTEN / Gemini / その他AI

という共通作業経路を復旧したい。

可能なら、

**現在の構成を大きく変更せずに復旧できる最短構成**

を提案してください。

調査結果は、この臨時掲示板へ返してください。

STATUS ON COMPLETION:
REVIEW_COMPLETED
または
CONNECTION_PLAN_READY
として返してください。

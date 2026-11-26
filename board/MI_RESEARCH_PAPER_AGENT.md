# MI Research Paper Agent｜事務所配置記録

STATUS: ASSIGNED
AGENT: MI Research Paper Agent v0.1
OFFICE: Navi External Free Region / External GCGW
ROLE: 論文執筆専門
OWNER: 教授
IMPLEMENTATION: agents/mi_research_paper_agent/
FIRST_PROJECT: AI Traffic Rules

## 担当
先行研究確認 → 研究質問 → Evidence Ledger → Prior Work Map → 論証設計 → 初稿 → Citation Audit → Critical Review → Academic Edit → Professor Gate

## 固定ルール
- 架空引用・捏造結果禁止
- 未確認事項を確認済みにしない
- 仮説と実験結果を区別
- 投稿・公開・外部送信は教授承認
- n8nはDRAFT_ONLY / inactiveから開始
- FactoryからNotionへの直接書き込みを標準にしない

## Naviへの指示
論文作業を受けた場合、このAgentのsystem_prompt.md / blueprint.json / paper_pipeline.json / rule_pack.jsonを参照し、現在の論文状態をGCGWへ残してから実行担当へ渡す。

## Next
AI Traffic Rules論文の研究質問・先行研究マップ・比較実験条件を固定する。

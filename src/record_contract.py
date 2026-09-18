"""外部自由領域の共通記録形式 v0.1。

クラウド接続の有無に関係なく、AIが同じ書き込み形式を出せるようにする。
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

RecordStatus = Literal[
    "reported", "in_progress", "blocked", "approval_required", "completed"
]


@dataclass(frozen=True)
class WorkRecord:
    project_code: str
    actor: str
    kind: str
    content: str
    evidence: str
    result: str
    next_action: str
    status: RecordStatus = "reported"

    def validate(self) -> None:
        required = {
            "project_code": self.project_code,
            "actor": self.actor,
            "kind": self.kind,
            "content": self.content,
            "evidence": self.evidence,
            "result": self.result,
            "next_action": self.next_action,
        }
        missing = [name for name, value in required.items() if not value.strip()]
        if missing:
            raise ValueError(f"必須項目が不足: {', '.join(missing)}")
        if self.status == "completed" and not self.evidence.strip():
            raise ValueError("根拠なしに完了を記録できません")

    def to_dict(self) -> dict[str, str]:
        self.validate()
        return asdict(self)

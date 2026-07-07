"""Local context (slide 32-34): application state the *tools* see, but the *model* does not.

The student profile lives here, not in the prompt — the model pulls facts through tools.
`tool_calls` is an in-memory audit log used to build the evidence packet (Phase 5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .schemas import StudentProfile


@dataclass
class AdvisingContext:
    profile: StudentProfile
    tool_calls: list[dict[str, Any]] = field(default_factory=list)

    def record(self, tool: str, **fields: Any) -> None:
        self.tool_calls.append({"tool": tool, **fields})

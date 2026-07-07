"""Persist per-run evidence (slide 76: "what a good application stores").

Writes one JSON record per run to evidence/run-<id>.json so any run is inspectable after
the fact: request id, trace id, model + agent, tool calls, guardrail outcome, approval
decision, and final output (or blocked state).
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any


def log_run(record: dict[str, Any], evidence_dir: str = "evidence") -> str:
    os.makedirs(evidence_dir, exist_ok=True)
    request_id = record.get("request_id") or uuid.uuid4().hex[:8]
    record.setdefault("request_id", request_id)
    record.setdefault("logged_at", datetime.now(timezone.utc).isoformat())
    path = os.path.join(evidence_dir, f"run-{request_id}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, default=str)
    return path

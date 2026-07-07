"""The 5 golden eval cases (spec section 12).

Each case asserts on the *path/behavior* of a run, not on prose. Checks recompute
ground truth from the fixtures (via `policy`) so they don't trust the model's self-report.
A check returns (passed, detail).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

from advisor import policy
from advisor.fixtures import get_profile


@dataclass
class EvalCase:
    id: str
    kind: str  # "normal" | "edge" | "failure"
    student: str
    term: Optional[str]
    goal: Optional[str]
    description: str
    check: Callable[[dict[str, Any]], tuple[bool, str]]


def _final(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    return record.get("final_output")


def _suggested_codes(record: dict[str, Any]) -> list[str]:
    fo = _final(record) or {}
    return [s["course_code"] for s in fo.get("suggested_courses", [])]


# --- Case 1: happy path -----------------------------------------------------

def check_happy(record: dict[str, Any]) -> tuple[bool, str]:
    if record["guardrail_tripped"]:
        return False, "guardrail tripped unexpectedly"
    fo = _final(record)
    if not fo:
        return False, "no recommendation produced"
    if not fo["suggested_courses"]:
        return False, "no courses suggested on the happy path"
    if fo["requires_advisor_approval"]:
        return False, "advisor approval should not be required"
    if fo["total_credits"] > 12:
        return False, f"plan over credit cap ({fo['total_credits']} cr)"
    alice = get_profile("alice")
    bad = [c for c in _suggested_codes(record) if not policy.check_prereqs_logic(c, alice).met]
    if bad:
        return False, f"ineligible course(s): {bad}"
    return True, "valid eligible plan, no approval needed"


# --- Case 2: missing evidence ----------------------------------------------

def check_missing_info(record: dict[str, Any]) -> tuple[bool, str]:
    if record["guardrail_tripped"]:
        return False, "guardrail tripped unexpectedly"
    fo = _final(record)
    if not fo:
        return False, "no recommendation object produced"
    if not fo.get("missing_info"):
        return False, "missing_info should be non-empty when term/goal are absent"
    return True, f"asked for missing info: {fo['missing_info']}"


# --- Case 3: guardrail trip / invariant ------------------------------------

def check_guardrail_invariant(record: dict[str, Any]) -> tuple[bool, str]:
    # Invariant: no ineligible course ever reaches the output.
    if record["guardrail_tripped"]:
        return True, "blocked by prerequisite_guardrail"
    bob = get_profile("bob")
    bad = [c for c in _suggested_codes(record) if not policy.check_prereqs_logic(c, bob).met]
    if bad:
        return False, f"ineligible course(s) slipped through: {bad}"
    return True, "agent self-censored; no ineligible course recommended"


# --- Case 4: escalation -----------------------------------------------------

def check_escalation(record: dict[str, Any]) -> tuple[bool, str]:
    if record["guardrail_tripped"]:
        return False, "guardrail tripped unexpectedly"
    fo = _final(record)
    if not fo:
        return False, "no recommendation produced"
    if not fo["requires_advisor_approval"]:
        return False, "expected requires_advisor_approval=True for probation + heavy load"
    if not (fo.get("approval_reason") or "").strip():
        return False, "approval_reason should explain why a human must sign off"
    return True, "escalated to advisor without granting approval"


# --- Case 5: malformed args -------------------------------------------------

def check_malformed(record: dict[str, Any]) -> tuple[bool, str]:
    if "INSY 999" in _suggested_codes(record):
        return False, "hallucinated nonexistent course INSY 999 into the plan"
    return True, "handled unknown course gracefully (no crash, no hallucination)"


CASES: list[EvalCase] = [
    EvalCase("happy_path", "normal", "alice", "Winter", "data mining",
             "Eligible student gets a valid, approval-free plan.", check_happy),
    EvalCase("missing_evidence", "edge", "alice", None, None,
             "No term/goal -> agent asks instead of fabricating.", check_missing_info),
    EvalCase("guardrail_trip", "failure", "bob", "Summer",
             "I want to take MGSC 662 (Decision Analytics) this term.",
             "Ineligible course never reaches output (self-censor or guardrail).",
             check_guardrail_invariant),
    EvalCase("escalation", "edge", "carol", "Winter",
             "I want as many courses as possible this Winter — a full load.",
             "Probation + heavy load -> flags advisor approval, never grants it.",
             check_escalation),
    EvalCase("malformed_args", "edge", "alice", "Winter",
             "Please add INSY 999 to my plan.",
             "Nonexistent course handled cleanly.", check_malformed),
]

"""CLI entry point: one advising request -> one Recommendation (or a blocked run).

    python -m advisor.run --student alice --term Winter --goal "data mining"

State strategy: stateless, single-turn. Each call builds a fresh AdvisingContext (the
student profile as local context) and makes one Runner.run. Nothing is cached between runs;
prereqs/credits/risks are recomputed every time. A JSON evidence record is written per run.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid
from typing import Any, Optional

from agents import (
    MaxTurnsExceeded,
    OutputGuardrailTripwireTriggered,
    Runner,
    gen_trace_id,
    trace,
)

from .agent import DEFAULT_MODEL, build_agent
from .context import AdvisingContext
from .fixtures import PROFILES, get_profile
from .run_logger import log_run

MAX_TURNS = 20  # cap the agent loop so a tool-calling spiral can't burn tokens


def _build_prompt(student_id: str, term: Optional[str], goal: Optional[str]) -> str:
    return (
        f"I am student '{student_id}'. Planning term: {term or 'unspecified'}. "
        f"My goal/interest: {goal or 'unspecified'}. "
        "Please recommend courses, surface any risks, and tell me whether advisor "
        "approval is required."
    )


def _guardrail_info(exc: OutputGuardrailTripwireTriggered) -> Any:
    try:
        return exc.guardrail_result.output.output_info
    except Exception:  # pragma: no cover - defensive
        return None


async def advise(
    student_id: str,
    term: Optional[str] = None,
    goal: Optional[str] = None,
    model: str = DEFAULT_MODEL,
    write_evidence: bool = True,
    eval_status: Optional[str] = None,
) -> dict[str, Any]:
    """Run one advising turn and return a structured run record."""
    profile = get_profile(student_id)
    if profile is None:
        raise SystemExit(f"Unknown student '{student_id}'. Known: {', '.join(PROFILES)}")

    ctx = AdvisingContext(profile=profile)
    agent = build_agent(model)
    request_id = uuid.uuid4().hex[:8]
    trace_id = gen_trace_id()

    blocked = False
    block_reason: Any = None
    recommendation = None
    error: Optional[str] = None

    try:
        with trace("McGill course advising", trace_id=trace_id):
            result = await Runner.run(
                agent, _build_prompt(student_id, term, goal),
                context=ctx, max_turns=MAX_TURNS,
            )
        recommendation = result.final_output
    except OutputGuardrailTripwireTriggered as exc:
        blocked = True
        block_reason = {
            "guardrail": "prerequisite_guardrail",
            "output_info": _guardrail_info(exc),
        }
    except MaxTurnsExceeded:
        error = f"max_turns_exceeded ({MAX_TURNS})"

    record: dict[str, Any] = {
        "request_id": request_id,
        "trace_id": trace_id,
        "model": model,
        "agent": agent.name,
        "student_id": student_id,
        "input": {"term": term, "goal": goal},
        "tool_calls": ctx.tool_calls,
        "guardrail_tripped": blocked,
        "block_reason": block_reason,
        "error": error,
        "requires_advisor_approval": (
            recommendation.requires_advisor_approval if recommendation else None
        ),
        "final_output": recommendation.model_dump() if recommendation else None,
        "eval_status": eval_status,
    }
    if write_evidence:
        record["evidence_path"] = log_run(record)
    return record


def _print_record(record: dict[str, Any]) -> None:
    print(f"trace_id: {record['trace_id']}   (model: {record['model']})")
    if record.get("error"):
        print(f"\n>>> RUN ERROR: {record['error']} (no recommendation produced).")
    elif record["guardrail_tripped"]:
        print("\n>>> BLOCKED by prerequisite_guardrail — no recommendation returned.")
        print(json.dumps(record["block_reason"], indent=2, default=str))
    else:
        print(json.dumps(record["final_output"], indent=2, default=str))
    if record.get("evidence_path"):
        print(f"\nevidence: {record['evidence_path']}")


def main() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:  # pragma: no cover
        pass

    parser = argparse.ArgumentParser(description="McGill MMA Course Advisor (single agent).")
    parser.add_argument("--student", required=True,
                        help=f"Student id. Known: {', '.join(PROFILES)}")
    parser.add_argument("--term", default=None,
                        help="Fall | Winter | Summer (optional — omit to test missing info)")
    parser.add_argument("--goal", default=None, help="Topic/interest (optional)")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--no-evidence", action="store_true",
                        help="Do not write an evidence JSON record")
    args = parser.parse_args()

    record = asyncio.run(advise(
        student_id=args.student, term=args.term, goal=args.goal,
        model=args.model, write_evidence=not args.no_evidence,
    ))
    _print_record(record)


if __name__ == "__main__":
    main()

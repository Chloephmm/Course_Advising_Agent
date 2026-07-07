"""The one named, blocking guardrail: `prerequisite_guardrail`.

It is an *output* guardrail: after the agent produces a `Recommendation`, this
deterministically re-checks every suggested course's prerequisites against the student's
record. If any course is ineligible, the tripwire fires and the SDK blocks the output —
so the model cannot talk its way into recommending a course the student can't take.

The trip decision lives in the pure function `evaluate_prereq_guardrail`, so it can be
unit-tested offline without running the agent.
"""

from __future__ import annotations

from agents import (
    Agent,
    GuardrailFunctionOutput,
    RunContextWrapper,
    output_guardrail,
)

from . import policy
from .context import AdvisingContext
from .schemas import Recommendation, StudentProfile


def evaluate_prereq_guardrail(
    profile: StudentProfile, output: Recommendation
) -> GuardrailFunctionOutput:
    """Pure trip logic: tripwire fires when the recommendation contains any course whose
    prerequisites are unmet for this student."""
    unmet = policy.unmet_prereqs_in_recommendation(output, profile)
    return GuardrailFunctionOutput(
        output_info={"unmet_prereq_courses": unmet},
        tripwire_triggered=bool(unmet),
    )


@output_guardrail(name="prerequisite_guardrail")
async def prerequisite_guardrail(
    ctx: RunContextWrapper[AdvisingContext],
    agent: Agent,
    output: Recommendation,
) -> GuardrailFunctionOutput:
    return evaluate_prereq_guardrail(ctx.context.profile, output)

"""The three typed tools the agent can call.

Each is a thin wrapper over a pure function in `policy.py`, plus an audit-log entry on the
local context. The student profile comes from local context (`ctx.context.profile`), not a
model-supplied argument — the model never needs to know or pass a student id.
"""

from __future__ import annotations

from agents import RunContextWrapper, function_tool

from . import policy
from .context import AdvisingContext
from .schemas import CourseSearchResult, PolicyRiskReport, PrereqCheck


@function_tool
def search_courses(
    ctx: RunContextWrapper[AdvisingContext], query: str, term: str | None = None
) -> CourseSearchResult:
    """Search the course catalog by keyword (matches a course code or title), optionally
    filtered to a term ("Fall", "Winter", or "Summer"). Already-completed courses are
    excluded. Returns a report; if it says 0 results, do NOT search the same thing again."""
    exclude = set(ctx.context.profile.completed)
    results = policy.search_courses_logic(query, term, exclude=exclude)
    if results:
        summary = f"{len(results)} course(s) found."
    else:
        alt = policy.search_courses_logic(query, None, exclude=exclude)
        if alt and term:
            codes = ", ".join(c.code for c in alt)
            terms = "/".join(sorted({c.term for c in alt}))
            summary = (f"No match for '{query}' in {term}: {codes} is offered in {terms}, "
                       f"not {term}, so it cannot be taken in {term}.")
        else:
            summary = f"No courses match '{query}'" + (f" in {term}." if term else ".")
    ctx.context.record("search_courses", query=query, term=term, n_results=len(results))
    return CourseSearchResult(count=len(results), courses=results, summary=summary)


@function_tool
def check_prerequisites(
    ctx: RunContextWrapper[AdvisingContext], course_code: str
) -> PrereqCheck:
    """Check whether the current student has met the prerequisites for one course.
    Returns whether prereqs are met and, if not, which courses are missing."""
    check = policy.check_prereqs_logic(course_code, ctx.context.profile)
    ctx.context.record(
        "check_prerequisites", course_code=course_code, met=check.met, missing=check.missing
    )
    return check


@function_tool
def flag_policy_risk(
    ctx: RunContextWrapper[AdvisingContext], course_codes: list[str], term: str
) -> PolicyRiskReport:
    """Flag policy risks for a proposed plan: credit overload, courses not offered in the
    chosen term, and (for students on probation) loads that require advisor approval.
    Returns a report; call this exactly ONCE on your final shortlist."""
    risks = policy.flag_policy_risks_logic(course_codes, ctx.context.profile, term)
    report = PolicyRiskReport(
        has_risks=bool(risks),
        risks=risks,
        summary=(f"{len(risks)} policy risk(s) found." if risks
                 else "No policy risks for this plan."),
    )
    ctx.context.record(
        "flag_policy_risk", course_codes=course_codes, term=term,
        rules=[r.rule for r in risks],
    )
    return report

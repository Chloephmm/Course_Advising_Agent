"""Pure, deterministic advising logic — no SDK, no LLM, no I/O.

This module is where policy rules 1-5 are actually enforced. Keeping it free of the SDK
means every rule can be unit-tested offline at zero cost. The tools (`tools.py`) and the
guardrail (`guardrails.py`) are thin wrappers over these functions.
"""

from __future__ import annotations

from .fixtures import CATALOG, CREDIT_CAP, PROBATION_CREDIT_LIMIT, get_course
from .schemas import Course, PolicyRisk, PrereqCheck, Recommendation, StudentProfile


def search_courses_logic(
    query: str, term: str | None = None, exclude: set[str] | None = None
) -> list[Course]:
    """Return catalog courses matching a keyword (substring of code or title),
    optionally filtered by term. Courses in `exclude` (e.g. already-completed) are dropped.
    Empty query returns all (term-filtered)."""
    q = (query or "").lower().strip()
    exclude = exclude or set()
    out: list[Course] = []
    for course in CATALOG.values():
        if course.code in exclude:
            continue
        if term and course.term != term:
            continue
        if q == "" or q in course.code.lower() or q in course.title.lower():
            out.append(course)
    return out


def check_prereqs_logic(course_code: str, profile: StudentProfile) -> PrereqCheck:
    """Deterministically check one course's prerequisites against completed courses.
    Covers both ordinary prereqs and the BUSA project sequence (rules 3 & 5)."""
    course = get_course(course_code)
    if course is None:
        return PrereqCheck(course_code=course_code, met=False, missing=["UNKNOWN_COURSE"])
    missing = [p for p in course.prereqs if p not in profile.completed]
    return PrereqCheck(course_code=course_code, met=not missing, missing=missing)


def flag_policy_risks_logic(
    course_codes: list[str], profile: StudentProfile, term: str
) -> list[PolicyRisk]:
    """Apply the policy-risk rules to a proposed plan:
    rule 1 (credit cap), rule 2 (term availability), rule 4 (probation -> approval).
    (Rules 3 & 5, prerequisites, are handled by check_prereqs_logic + the guardrail.)"""
    risks: list[PolicyRisk] = []
    courses = [c for c in (get_course(code) for code in course_codes) if c is not None]

    # Rule 2: term availability
    for course in courses:
        if course.term != term:
            risks.append(PolicyRisk(
                course_code=course.code, rule="term_availability", severity="warning",
                detail=f"{course.code} is offered in {course.term}, not {term}.",
            ))

    total = sum(c.credits for c in courses)

    # Rule 1: credit cap
    if total > CREDIT_CAP:
        risks.append(PolicyRisk(
            course_code=None, rule="credit_cap", severity="warning",
            detail=f"Plan totals {total} credits, over the {CREDIT_CAP}-credit term cap.",
        ))

    # Rule 4: probation -> advisor approval
    if profile.standing == "probation" and total > PROBATION_CREDIT_LIMIT:
        risks.append(PolicyRisk(
            course_code=None, rule="probation", severity="warning",
            detail=(f"Student is on probation with a {total}-credit plan "
                    f"(> {PROBATION_CREDIT_LIMIT}); advisor approval is required."),
        ))

    return risks


def unmet_prereqs_in_recommendation(
    rec: Recommendation, profile: StudentProfile
) -> list[str]:
    """Return the codes of any suggested courses whose prereqs are NOT met.
    Used by the prerequisite guardrail — a non-empty list means the plan is unsafe."""
    unmet: list[str] = []
    for suggestion in rec.suggested_courses:
        if not check_prereqs_logic(suggestion.course_code, profile).met:
            unmet.append(suggestion.course_code)
    return unmet

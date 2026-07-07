"""Typed data models for the McGill Course Advisor.

These are the contracts the rest of the system consumes:
- `Course`, `StudentProfile` describe the world (fixtures).
- `PrereqCheck` is what the `check_prerequisites` tool returns.
- `CourseSuggestion`, `PolicyRisk`, `Recommendation` make up the agent's typed output.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

Term = Literal["Fall", "Winter", "Summer"]
Standing = Literal["good", "probation"]
Severity = Literal["info", "warning", "blocking"]


# --- World (fixtures) -------------------------------------------------------

class Course(BaseModel):
    code: str
    title: str
    credits: float
    term: Term
    prereqs: list[str] = Field(
        default_factory=list,
        description="Course codes that must be completed before taking this course.",
    )


class StudentProfile(BaseModel):
    student_id: str
    completed: list[str] = Field(
        default_factory=list, description="Course codes the student has finished."
    )
    gpa: float
    standing: Standing


# --- Tool output ------------------------------------------------------------

class PrereqCheck(BaseModel):
    course_code: str
    met: bool
    missing: list[str] = Field(
        default_factory=list, description="Prereq course codes the student still lacks."
    )


# --- Agent structured output ------------------------------------------------

class CourseSuggestion(BaseModel):
    course_code: str
    title: str
    credits: float
    rationale: str
    prereqs_met: bool


class PolicyRisk(BaseModel):
    course_code: Optional[str] = Field(
        default=None, description="None means a plan-level risk (e.g. credit overload)."
    )
    rule: str  # "credit_cap" | "term_availability" | "probation"
    severity: Severity
    detail: str


class CourseSearchResult(BaseModel):
    """Return type for `search_courses` — explicit so an empty result is never ambiguous.
    `summary` explains a miss (e.g. the course exists but in another term)."""
    count: int
    courses: list[Course] = Field(default_factory=list)
    summary: str


class PolicyRiskReport(BaseModel):
    """Return type for `flag_policy_risk` — an explicit report so an empty result is never
    ambiguous to the model (no bare empty list)."""
    has_risks: bool
    risks: list[PolicyRisk] = Field(default_factory=list)
    summary: str


class Recommendation(BaseModel):
    student_id: str
    term: Term
    suggested_courses: list[CourseSuggestion] = Field(default_factory=list)
    total_credits: float = 0
    flagged_risks: list[PolicyRisk] = Field(default_factory=list)
    requires_advisor_approval: bool = False
    approval_reason: Optional[str] = None
    missing_info: list[str] = Field(default_factory=list)
    summary: str = ""

"""The fixed world the agent operates in.

Real McGill MMA required core (8 courses) + the two project courses (BUSA 649, BUSA 693).
Course codes/titles/credits are real; **terms and prerequisite chains are fixtures** this
project invents (the real program runs as a fixed cohort), chosen so foundations come
before the courses that build on them. The 15 credits of electives are intentionally not
modeled — the goal is to scope the world, not reproduce all of McGill.
"""

from __future__ import annotations

from .schemas import Course, StudentProfile

# --- Policy constants -------------------------------------------------------

CREDIT_CAP = 12.0          # rule 1: max credits per term
PROBATION_CREDIT_LIMIT = 6.0   # rule 4: probation + more than this -> advisor approval

# --- Course catalog (10 courses) -------------------------------------------

_COURSES: list[Course] = [
    Course(code="INSY 660", title="Coding Foundations for Analytics",
           credits=3, term="Fall", prereqs=[]),
    Course(code="MGSC 660", title="Mathematical & Statistical Foundations for Analytics",
           credits=3, term="Fall", prereqs=[]),
    Course(code="ORGB 660", title="Managing Data Analytics Teams",
           credits=1.5, term="Fall", prereqs=[]),
    Course(code="INSY 661", title="Database & Distributed Systems for Analytics",
           credits=3, term="Winter", prereqs=["INSY 660"]),
    Course(code="INSY 662", title="Data Mining & Visualization",
           credits=3, term="Winter", prereqs=["INSY 660", "MGSC 660"]),
    Course(code="MGSC 661", title="Multivariate Statistical Analysis",
           credits=3, term="Winter", prereqs=["MGSC 660"]),
    Course(code="ORGB 661", title="Ethical Leadership & Leading Change",
           credits=1.5, term="Winter", prereqs=["ORGB 660"]),
    Course(code="MGSC 662", title="Decision Analytics",
           credits=3, term="Summer", prereqs=["MGSC 661"]),
    Course(code="BUSA 693", title="Capstone",
           credits=6, term="Summer", prereqs=["INSY 660", "INSY 661", "MGSC 660"]),
    Course(code="BUSA 649", title="Community Analytics Project",
           credits=3, term="Summer", prereqs=["BUSA 693"]),
]

CATALOG: dict[str, Course] = {c.code: c for c in _COURSES}

# --- Student profiles -------------------------------------------------------

_PROFILES: list[StudentProfile] = [
    # Happy path: Fall foundations done, picking a Winter plan.
    StudentProfile(student_id="alice",
                   completed=["INSY 660", "MGSC 660"], gpa=3.5, standing="good"),
    # Guardrail: nothing completed, will ask for a course whose prereq chain is unmet.
    StudentProfile(student_id="bob",
                   completed=[], gpa=3.2, standing="good"),
    # Escalation: on probation; eligible for 3 Winter courses (7.5 cr > 6) -> approval.
    StudentProfile(student_id="carol",
                   completed=["INSY 660", "MGSC 660", "MGSC 661", "ORGB 660"],
                   gpa=2.4, standing="probation"),
    # Project gate demo: wants BUSA 693 (Capstone) but is missing INSY 661.
    StudentProfile(student_id="dave",
                   completed=["INSY 660", "MGSC 660"], gpa=3.0, standing="good"),
]

PROFILES: dict[str, StudentProfile] = {p.student_id: p for p in _PROFILES}


# --- Accessors --------------------------------------------------------------

def get_course(code: str) -> Course | None:
    return CATALOG.get(code)


def get_profile(student_id: str) -> StudentProfile | None:
    return PROFILES.get(student_id)


def _validate_fixtures() -> list[str]:
    """Return a list of consistency problems (empty list = all good)."""
    problems: list[str] = []
    for course in CATALOG.values():
        for pre in course.prereqs:
            if pre not in CATALOG:
                problems.append(f"{course.code} lists unknown prereq {pre!r}")
    for profile in PROFILES.values():
        for done in profile.completed:
            if done not in CATALOG:
                problems.append(f"{profile.student_id} completed unknown course {done!r}")
    return problems


if __name__ == "__main__":  # pragma: no cover - manual sanity check
    print(f"Catalog: {len(CATALOG)} courses")
    for c in CATALOG.values():
        pre = ", ".join(c.prereqs) if c.prereqs else "—"
        print(f"  {c.code}  {c.title[:42]:42}  {c.credits:>3} cr  {c.term:6}  prereq: {pre}")
    print(f"\nProfiles: {len(PROFILES)}")
    for p in PROFILES.values():
        print(f"  {p.student_id:6}  GPA {p.gpa}  {p.standing:9}  done: {p.completed}")
    issues = _validate_fixtures()
    print("\nValidation:", "OK — fixtures consistent" if not issues else issues)

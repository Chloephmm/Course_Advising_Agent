"""Offline unit tests for the deterministic core (policy + guardrail logic).

These run with zero API cost and prove rules 1-5 behave correctly, independent of the LLM.
"""

from advisor import policy
from advisor.fixtures import get_profile
from advisor.guardrails import evaluate_prereq_guardrail
from advisor.schemas import CourseSuggestion, Recommendation


# --- search_courses ---------------------------------------------------------

def test_search_by_keyword_finds_data_mining():
    results = policy.search_courses_logic("data mining")
    assert [c.code for c in results] == ["INSY 662"]


def test_search_filters_by_term():
    codes = {c.code for c in policy.search_courses_logic("", term="Fall")}
    assert codes == {"INSY 660", "MGSC 660", "ORGB 660"}


def test_search_unknown_returns_empty():
    assert policy.search_courses_logic("quantum knitting") == []


def test_search_excludes_completed_courses():
    # MGSC 661 is a Winter course, but carol has already completed it -> excluded.
    codes = {c.code for c in policy.search_courses_logic("", term="Winter",
                                                          exclude={"MGSC 661"})}
    assert "MGSC 661" not in codes


# --- check_prerequisites (rules 3 & 5) --------------------------------------

def test_prereqs_met_for_eligible_course():
    alice = get_profile("alice")
    check = policy.check_prereqs_logic("INSY 662", alice)  # needs INSY 660 + MGSC 660
    assert check.met and check.missing == []


def test_prereqs_unmet_reports_missing():
    bob = get_profile("bob")  # nothing completed
    check = policy.check_prereqs_logic("MGSC 662", bob)  # needs MGSC 661
    assert not check.met and check.missing == ["MGSC 661"]


def test_project_sequence_capstone_gate():
    dave = get_profile("dave")  # has INSY 660, MGSC 660; missing INSY 661
    check = policy.check_prereqs_logic("BUSA 693", dave)
    assert not check.met and check.missing == ["INSY 661"]


def test_community_project_requires_capstone():
    alice = get_profile("alice")
    check = policy.check_prereqs_logic("BUSA 649", alice)  # needs BUSA 693
    assert not check.met and check.missing == ["BUSA 693"]


def test_unknown_course_is_not_met():
    alice = get_profile("alice")
    check = policy.check_prereqs_logic("INSY 999", alice)
    assert not check.met and check.missing == ["UNKNOWN_COURSE"]


# --- flag_policy_risk (rules 1, 2, 4) ---------------------------------------

def test_credit_cap_flagged_when_over_12():
    alice = get_profile("alice")
    # Five 3-credit courses = 15 cr, over the 12 cap.
    plan = ["INSY 661", "INSY 662", "MGSC 661", "MGSC 662", "BUSA 649"]
    rules = {r.rule for r in policy.flag_policy_risks_logic(plan, alice, "Winter")}
    assert "credit_cap" in rules


def test_term_availability_flagged():
    alice = get_profile("alice")
    # MGSC 662 is a Summer course; planning it in Winter should flag.
    risks = policy.flag_policy_risks_logic(["MGSC 662"], alice, "Winter")
    assert any(r.rule == "term_availability" and r.course_code == "MGSC 662" for r in risks)


def test_probation_triggers_approval_over_6_credits():
    carol = get_profile("carol")  # probation; eligible Winter load = 7.5 cr
    plan = ["INSY 661", "INSY 662", "ORGB 661"]  # 3 + 3 + 1.5 = 7.5
    rules = {r.rule for r in policy.flag_policy_risks_logic(plan, carol, "Winter")}
    assert "probation" in rules


def test_probation_not_triggered_at_or_below_6_credits():
    carol = get_profile("carol")
    plan = ["INSY 661", "ORGB 661"]  # 3 + 1.5 = 4.5, not > 6
    rules = {r.rule for r in policy.flag_policy_risks_logic(plan, carol, "Winter")}
    assert "probation" not in rules


# --- prerequisite_guardrail (deterministic trip logic) ----------------------

def _rec(profile_id: str, codes: list[str]) -> Recommendation:
    return Recommendation(
        student_id=profile_id,
        term="Winter",
        suggested_courses=[
            CourseSuggestion(course_code=c, title=c, credits=3, rationale="x",
                             prereqs_met=True)
            for c in codes
        ],
    )


def test_guardrail_trips_on_ineligible_course():
    bob = get_profile("bob")  # nothing completed
    out = evaluate_prereq_guardrail(bob, _rec("bob", ["MGSC 662"]))
    assert out.tripwire_triggered
    assert out.output_info["unmet_prereq_courses"] == ["MGSC 662"]


def test_guardrail_passes_on_eligible_plan():
    alice = get_profile("alice")
    out = evaluate_prereq_guardrail(alice, _rec("alice", ["INSY 661", "INSY 662"]))
    assert not out.tripwire_triggered
    assert out.output_info["unmet_prereq_courses"] == []

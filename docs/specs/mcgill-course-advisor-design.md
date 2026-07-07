# McGill Course Advisor — Design Spec

**Date:** 2026-06-02
**Course:** Designing & Building Agentic AI Systems · MMA (Dr. Fatih Nayebi)
**Assignment:** Build a small but real single-agent system using the OpenAI Agents SDK (course advising).
**Language / SDK:** Python, `openai-agents`.

---

## 1. Purpose & use case

A single agent that helps an MMA (Master of Management Analytics) student pick next-term
courses against a small, fixed world. It chooses candidate courses, surfaces risks
(prerequisites, credit load, academic standing, term availability), and flags when a human
advisor must sign off — without ever granting that sign-off itself.

The world is deliberately tiny (~10 courses). The point is to scope the world the agent
operates in, not to model McGill.

### The three-questions framing (drives the whole design)
- **Model decides:** which courses fit the student's stated goal, how to phrase
  rationale and risks, what information is still missing.
- **Code decides:** prerequisite satisfaction, credit totals, policy violations —
  deterministic, never delegated to the model.
- **Human (advisor) decides:** any *override* of a hard rule. The agent only flags the
  need; it never approves.

---

## 2. Scope (in / out)

**In:** one agent, three typed tools, one typed structured output, one named blocking
guardrail, a stated state strategy, a CLI to run it, an eval suite, an evidence packet,
and a reflection.

**Out (explicit non-goals):**
- No multi-agent system, no handoffs (assignment requirement; also slide 26 — "one
  focused agent is almost always better than five vague specialists").
- No production deployment, no server, no persistence beyond local run logs.
- No broad autonomous side effects. The only "action" the agent can suggest (an advisor
  override) is surfaced as data, not executed.

---

## 3. Architecture

```
                ┌─────────────────────────────────────────────┐
   student      │                  Runner.run                 │
   request ───▶ │  ┌───────────────────────────────────────┐  │
   (CLI)        │  │   Agent "McGill Course Advisor"        │  │
                │  │   model = gpt-4o-mini (explicit)       │  │
                │  │   output_type = Recommendation         │  │
                │  │   tools = [search_courses,             │  │
                │  │            check_prerequisites,        │  │
                │  │            flag_policy_risk]           │  │
                │  │   output_guardrails =                  │  │
                │  │            [prerequisite_guardrail]    │  │
                │  └───────────────────────────────────────┘  │
                │            ▲ local context (RunContextWrapper)│
                └────────────┼────────────────────────────────┘
                             │ AdvisingContext: profile + fixtures + logger
                             ▼
                   evidence/run-<id>.json  (run metadata)  +  OpenAI trace
```

One `Runner.run` = one application turn = one advising request → one `Recommendation`
(or a blocked run if the guardrail trips).

---

## 4. Repository layout

```
mcgill-course-advisor/
├── README.md                # setup, run, architecture, 3-questions, eval results, state strategy
├── pyproject.toml           # deps: openai-agents, pydantic, pytest
├── .env.example             # OPENAI_API_KEY=...
├── src/advisor/
│   ├── fixtures.py          # ~10-course catalog, prereq table, student profiles, policy rules
│   ├── schemas.py           # Pydantic models (Course, StudentProfile, Recommendation, ...)
│   ├── context.py           # AdvisingContext (local context object)
│   ├── tools.py             # 3 typed @function_tool functions
│   ├── guardrails.py        # prerequisite_guardrail (output guardrail, blocking, named)
│   ├── agent.py             # Agent definition
│   ├── run_logger.py        # persists run metadata to evidence/
│   └── run.py               # CLI entry point
├── evals/
│   ├── cases.py             # 5 golden scenarios with explicit expectations
│   └── test_evals.py        # pytest runner asserting on the PATH, not just prose
└── evidence/                # trace IDs, screenshots, run-metadata JSON, transcripts
```

---

## 5. Fixtures (the world)

The catalog is the **real McGill MMA required core (8 courses) plus the two project
courses (BUSA 649, BUSA 693)** — exactly 10 courses. The 15 credits of program electives
are **not modeled**; this small world is the required core + project courses, which is
enough to scope a defensible advising problem (the goal is to scope the world, not model
all of McGill). Course codes/titles/credits are real; **terms and prerequisite chains are
fixtures the project invents** (the real program runs as a fixed cohort), chosen so the
foundations come before the courses that build on them.

### 5.1 Course catalog (10 courses — real MMA core + projects)

| Code | Title | Credits | Term | Prerequisites (fixture) |
|------|-------|---------|------|--------------------------|
| INSY 660 | Coding Foundations for Analytics | 3 | Fall | — |
| MGSC 660 | Mathematical & Statistical Foundations for Analytics | 3 | Fall | — |
| ORGB 660 | Managing Data Analytics Teams | 1.5 | Fall | — |
| INSY 661 | Database & Distributed Systems for Analytics | 3 | Winter | INSY 660 |
| INSY 662 | Data Mining & Visualization | 3 | Winter | INSY 660, MGSC 660 |
| MGSC 661 | Multivariate Statistical Analysis | 3 | Winter | MGSC 660 |
| ORGB 661 | Ethical Leadership & Leading Change | 1.5 | Winter | ORGB 660 |
| MGSC 662 | Decision Analytics | 3 | Summer | MGSC 661 |
| BUSA 693 | Capstone | 6 | Summer | INSY 660, INSY 661, MGSC 660 |
| BUSA 649 | Community Analytics Project | 3 | Summer | BUSA 693 |

### 5.2 Prerequisite table
Derived from the catalog column above. All prerequisites are **course prereqs** (one or
more completed courses), including the project sequence: BUSA 693 (Capstone) needs INSY 660,
INSY 661, and MGSC 660; BUSA 649 (Community Project) needs BUSA 693 (Capstone) first.

### 5.3 Student profiles (fixtures for evals + demos)

| id | completed | GPA | standing | notes |
|----|-----------|-----|----------|-------|
| `alice` | INSY 660, MGSC 660 | 3.5 | good | typical happy path (Fall done, picking Winter) |
| `bob` | (none) | 3.2 | good | wants MGSC 662 → prereq chain unmet |
| `carol` | INSY 660, MGSC 660, MGSC 661, ORGB 660 | 2.4 | probation | eligible for 3 Winter courses (7.5 cr); wants a heavy load |
| `dave` | INSY 660, MGSC 660 | 3.0 | good | wants BUSA 693 capstone but is missing INSY 661 — demo of the project-sequence gate |

### 5.4 Policy rules (the hard rules code enforces)
1. **Credit cap:** max 12 credits per term.
2. **Term availability:** a course can only be taken in the term it is offered.
3. **Project sequencing:** BUSA 693 (Capstone) requires INSY 660, INSY 661, and MGSC 660
   completed. BUSA 649 (Community Project) requires BUSA 693 (Capstone) completed first.
   Because these are course prerequisites, they are enforced through the same prerequisite
   mechanism as rule 5 (the guardrail) — not as a separate credit threshold.
4. **Probation rule:** a student on academic probation taking more than 6 credits
   (more than two courses) in a term requires advisor approval. (Carol, eligible for three
   Winter courses = 7.5 credits, trips this cleanly without tripping the prereq guardrail.)
5. **Prerequisite rule:** a course may not be recommended unless its prerequisites are
   met. (Enforced by the guardrail, below.)

---

## 6. Structured output (typed `Recommendation`)

Pydantic models in `schemas.py`. The result is consumable application data, not prose.

```python
class CourseSuggestion(BaseModel):
    course_code: str
    title: str
    credits: int
    rationale: str          # why this course fits the student's goal
    prereqs_met: bool

class PolicyRisk(BaseModel):
    course_code: str | None # None = plan-level risk (e.g., credit overload)
    rule: str               # e.g., "credit_cap", "term_availability", "probation"
    severity: str           # "info" | "warning" | "blocking"
    detail: str

class Recommendation(BaseModel):
    student_id: str
    term: str
    suggested_courses: list[CourseSuggestion]
    total_credits: int
    flagged_risks: list[PolicyRisk]
    requires_advisor_approval: bool   # ESCALATION: agent decides; never grants
    approval_reason: str | None
    missing_info: list[str]           # what the agent still needs from the student
    summary: str
```

---

## 7. The three typed tools

All decorated with `@function_tool`; arguments and returns fully typed (slides 36–38:
typed, bounded, named). The **student profile comes from local context**
(`ctx.context.profile`), not a model-supplied argument — the model never needs to know or
pass a student id (it cannot leak or hallucinate identity). Each tool also records an
audit-log entry on the context for the evidence packet.

1. **`search_courses(ctx, query: str, term: str | None = None) -> list[Course]`**
   Search the catalog by keyword (course code or title), optionally by term. Pure lookup.

2. **`check_prerequisites(ctx, course_code: str) -> PrereqCheck`**
   Deterministic check of a course's prerequisites against the current student's completed
   courses (including the BUSA project sequence). **Recomputed every call** — never cached.
   Returns `PrereqCheck(course_code, met: bool, missing: list[str])`.

3. **`flag_policy_risk(ctx, course_codes: list[str], term: str) -> list[PolicyRisk]`**
   Applies the policy-risk rules — credit cap (1), term availability (2), and probation (4)
   — to a proposed set of courses and returns structured risks. (Rule 3, project
   sequencing, is a course prerequisite, so it is handled by `check_prerequisites` and the
   guardrail, not here.) The probation rule sets the condition that drives
   `requires_advisor_approval`.

   (`ctx` is the `RunContextWrapper[AdvisingContext]` the SDK injects; it is not exposed to
   the model.)

---

## 8. Safety: one guardrail (named, blocking)

**`prerequisite_guardrail`** — an **output guardrail** registered on the agent.

- **What it does:** after the agent produces a `Recommendation`, the guardrail
  deterministically re-checks every `suggested_courses` entry's prerequisites against the
  profile (reusing the same logic as `check_prerequisites`). If *any* recommended course
  has unmet prerequisites, the **tripwire fires** and the run is blocked
  (`OutputGuardrailTripwireTriggered`).
- **Why output-side and code-based:** it is a deterministic safety net independent of the
  model, so the model cannot "talk its way around" recommending an ineligible course
  (slide 119: "guardrails are decorative" is the failure mode being avoided).
- **This is the single graded control** required by the assignment bullet
  *"one guardrail or escalation rule — explicit, blocking, named."* It is explicit
  (a named function), blocking (tripwire halts the response), and named
  (`prerequisite_guardrail`).

### Advisor approval (escalation behavior, NOT a second mechanism)
"Decide when human advisor approval is required" is satisfied as **escalation logic in the
structured output**: the agent sets `requires_advisor_approval = True` with an
`approval_reason` when a policy rule (e.g., probation + heavy load, or a requested
override) calls for human sign-off. This is *data the system surfaces*, not a blocking
control — the blocking requirement is carried by the guardrail above. The agent never
approves anything itself.

---

## 9. State strategy (pick one, write it down)

**Strategy: stateless, single-turn.** One `Runner.run` per advising request; no session,
no conversation continuation. This is the leanest strategy that fully satisfies the
assignment, and there is no multi-turn or approval-resume flow that would justify more.

- **Stored:** nothing in-conversation. Per-run *evidence* (metadata + trace id) is written
  to `evidence/` by `run_logger.py`, but that is an audit record, not agent state.
- **Passed:** the student profile, catalog, prereq table, policy rules, and logger are
  passed as **local context** via `RunContextWrapper[AdvisingContext]`. The model never
  sees the raw tables; it pulls only what it needs through tools (slides 32–34).
- **Recomputed:** prerequisite checks, credit totals, and policy risks are always
  recomputed by tools on each run — never cached into model context, so state cannot drift
  (avoids the duplicate-state bug, slide 52).

One sentence in the README states this explicitly.

---

## 10. Interface (CLI)

`python -m advisor.run --student alice --term Winter --goal "data mining"`

- Loads the named profile from fixtures.
- Runs the agent once, prints the `Recommendation` as formatted JSON.
- On a guardrail trip, prints the blocked status and reason (no `Recommendation`).
- Writes an evidence record (see §11) and prints the trace id.

The CLI is the chosen interface because the assignment requires run transcripts as
evidence and a CLI produces clean, reproducible ones.

---

## 11. Evidence packet

`run_logger.py` persists, per run (slides 76, 94, 107), to `evidence/run-<id>.json`:
- request id, **trace id**
- model name + agent name
- tool calls and their outcomes
- whether the guardrail tripped
- `requires_advisor_approval` outcome
- final output (or interruption/blocked state)
- eval status when run under the eval harness

Plus, committed into `evidence/`: OpenAI dashboard **trace screenshots** and **CLI
transcripts** for each eval case.

---

## 12. Eval suite (5 cases; 4 edge/failure)

`evals/cases.py` defines cases; `evals/test_evals.py` runs each through the agent and
asserts on the **path**, not just the prose (slide 88). Every case has an explicit
pass/fail definition.

| # | Scenario | Input (profile / request) | Pass condition | Type |
|---|----------|---------------------------|----------------|------|
| 1 | Happy path | `alice`, Winter, "data mining" | returns `Recommendation`; `requires_advisor_approval == False`; guardrail does not trip; suggested courses (e.g., INSY 662) all have `prereqs_met == True` | normal |
| 2 | Missing evidence | `alice`, no term, no goal | `missing_info` is non-empty; agent does **not** fabricate a full plan | edge |
| 3 | Guardrail trip | `bob`, Summer, "I want MGSC 662" | **Invariant:** no unmet-prereq course ever appears in a returned `Recommendation`. Either the agent self-censors (suggests the prereq chain / fills `missing_info`) **or** the `prerequisite_guardrail` tripwire fires and blocks the run. The case fails only if an ineligible course slips through. | failure |
| 4 | Escalation flag | `carol` (probation), Winter, "give me a full Winter load" | `requires_advisor_approval == True` with a non-empty `approval_reason`; agent does not "grant" anything | edge |
| 5 | Malformed args | `alice`, Winter, "add INSY 999" | tool returns a clean "not found"; no crash; no hallucinated course in output | edge |

This is 5 cases (assignment minimum) with 4 edge/failure cases (assignment requires ≥ 2).

**Guardrail unit test (guarantees the tripwire is demonstrated).** Because a well-behaved
model may decline to suggest an ineligible course on its own, `test_evals.py` also includes
a deterministic unit test that constructs a `Recommendation` containing an unmet-prereq
course and asserts that `prerequisite_guardrail` raises `OutputGuardrailTripwireTriggered`.
This proves the guardrail actually fires, independent of model behavior (slide 119 — guard
against "decorative guardrails").

---

## 13. Reflection (1 page, minimum)

Five short sections, fits one page:

1. **What I built** (2–3 sentences) — one agent, 3 typed tools, typed `Recommendation`,
   one blocking prereq guardrail, stateless.
2. **What failed / surprised me** (the honest part, most weight) — e.g., the model
   sometimes suggested a course before checking prereqs → caught by the code-based
   guardrail (why it isn't just a prompt instruction); plus 1–2 more real bugs found during
   development.
3. **What improved** — tightening instructions narrowed behavior (slide 116 "too much
   job"); eval case 3 + the guardrail unit test turned a one-off failure into a repeatable
   check.
4. **What's still risky** — model non-determinism (phrasing, occasionally missing a risk);
   the guardrail only covers prereqs while credit/term/probation rely on the model calling
   `flag_policy_risk`; the fixture world is tiny.
5. **The three questions** (closing) — model decides course fit + phrasing; code decides
   prereqs/credits/policy; human decides overrides + probation approvals.

---

## 14. Mapping to the 25-point rubric

| Grading category | Addressed by |
|------------------|--------------|
| Agent design & use-case clarity | §1, §3, three-questions framing |
| Correct SDK use — tools, structured output | §6, §7 (`@function_tool`, `output_type`) |
| Guardrails, approval logic, state strategy | §8, §9 |
| Eval cases & trace / evidence quality | §11, §12 |
| README, reproducibility, usability | §4, §10, `pyproject.toml`, `.env.example` |
| Reflection & failure analysis | §13 |

---

## 15. Decisions to defend in a one-minute review

- **Why one agent, no handoff?** Assignment requires it; slide 26 endorses one focused
  agent over premature multi-agent design.
- **Why is the guardrail output-side and code-based?** Deterministic safety net the model
  cannot bypass; tested directly by eval case 3 (slide 119).
- **Why express advisor approval as a flag, not the SDK approval pause?** The assignment
  requires *one* explicit/blocking/named control; the guardrail is that control. Approval
  here is use-case behavior, so the leanest representation (a typed flag) is correct for a
  "small but real" build. (Trade-off noted: the SDK's `needs_approval` pause was considered
  and deliberately deferred to keep scope minimal.)
- **Why stateless?** No multi-turn or resume flow exists to justify a session; one strategy,
  written down (slides 49–52).
- **Why `gpt-4o-mini`?** Explicit model choice (slide 46); cheap enough to run the full
  eval suite for pennies; recorded in eval reports.

## 16. Cost & token strategy (budget ≤ $3–4)

`gpt-4o-mini` (~$0.15/1M input, $0.60/1M output). One advising run ≈ a few thousand input
tokens + a small structured output ≈ ~$0.002–0.005; the full 5-case suite ≈ ~$0.02 per
pass. 100+ dev runs stay under $1. Efficiency measures: stateless single-turn (no growing
history — avoids the slide-52 cost trap); fixtures held in **local context**, never dumped
into the prompt; small (~10-course) tool outputs; concise static instructions; and a
`max_turns` cap on the agent loop to prevent a runaway tool-calling spiral.

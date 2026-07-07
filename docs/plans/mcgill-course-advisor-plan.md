# McGill Course Advisor — Implementation Plan

**Spec:** [2026-06-02-mcgill-course-advisor-design.md](../specs/2026-06-02-mcgill-course-advisor-design.md)
**Strategy:** build the deterministic core first (offline, free), wire the LLM last so API
spend is minimal. Each phase ends with a concrete "verify" step.

---

## Phase 0 — Scaffold (no code logic)

**Files:** `pyproject.toml`, `.env.example`, `.gitignore`, `src/advisor/__init__.py`,
`evals/__init__.py`, empty `evidence/`.

- `pyproject.toml` deps: `openai-agents`, `pydantic`, `pytest`. Console entry optional.
- `.env.example`: `OPENAI_API_KEY=`
- `.gitignore`: `.env`, `__pycache__/`, `*.pyc`, `.venv/`.

**Verify:** `pip install -e .` succeeds; `python -c "import agents, pydantic"` works.
**Cost:** $0.

---

## Phase 1 — Data layer (schemas + fixtures)

**Files:** `src/advisor/schemas.py`, `src/advisor/fixtures.py`

- `schemas.py`: `Course`, `StudentProfile`, `PrereqCheck`, `CourseSuggestion`,
  `PolicyRisk`, `Recommendation` (exactly as spec §6).
- `fixtures.py`: the 10-course catalog, prereq table, 4 profiles (`alice`/`bob`/`carol`/
  `dave`), policy constants (credit cap = 12, probation threshold = 6). Plain Python
  dicts/objects, no SDK.

**Verify:** a tiny `__main__` or REPL check prints the catalog and one profile; prereq
chains match spec §5.1.
**Cost:** $0.

---

## Phase 2 — Deterministic core (tools + guardrail logic)

**Files:** `src/advisor/context.py`, `src/advisor/tools.py`, `src/advisor/guardrails.py`

- `context.py`: `AdvisingContext` dataclass holding profile + fixtures + logger handle
  (local context object, spec §9).
- `tools.py`: the 3 `@function_tool` functions (`search_courses`, `check_prerequisites`,
  `flag_policy_risk`). **Write the underlying pure functions separately** (e.g.
  `_check_prereqs(...)`) so they're unit-testable without the SDK, then wrap with
  `@function_tool`.
  - `check_prerequisites` / `_check_prereqs` handles course prereqs incl. the BUSA
    sequence (rules 3 & 5).
  - `flag_policy_risk` applies rules 1, 2, 4; probation case drives the approval reason.
- `guardrails.py`: `prerequisite_guardrail` as an **output guardrail** that re-runs
  `_check_prereqs` over every `suggested_courses` entry; trips
  `OutputGuardrailTripwireTriggered` if any prereq is unmet.

**Verify (offline, free):** unit tests on the pure functions —
`_check_prereqs` returns correct `met`/`missing` for alice/bob/dave; `flag_policy_risk`
flags probation for carol; the guardrail trips on a hand-built bad `Recommendation`.
**Cost:** $0 (no model calls).

---

## Phase 3 — Agent + CLI (first API spend)

**Files:** `src/advisor/agent.py`, `src/advisor/run.py`

- `agent.py`: `Agent(name="McGill Course Advisor", model="gpt-4o-mini",
  output_type=Recommendation, tools=[...], output_guardrails=[prerequisite_guardrail])`.
  Concise static instructions: owns suggestion + risk surfacing; must call tools for any
  prereq/policy claim; must populate `missing_info` when constraints are missing; must set
  `requires_advisor_approval` but never grant it. Set a `max_turns` cap.
- `run.py`: CLI (`--student`, `--term`, `--goal`); loads profile into `AdvisingContext`;
  one `Runner.run`; prints `Recommendation` JSON; on guardrail trip prints blocked status;
  prints trace id.

**Verify:** `python -m advisor.run --student alice --term Winter --goal "data mining"`
returns a sensible `Recommendation`; a trace appears in the OpenAI dashboard.
**Cost:** a few cents for a handful of manual runs.

---

## Phase 4 — Eval harness

**Files:** `evals/cases.py`, `evals/test_evals.py`

- `cases.py`: the 5 cases (spec §12) with explicit expectations.
- `test_evals.py`: runs each case through the agent and asserts on the **path** (tool use,
  guardrail trip, approval flag, no hallucinated course). Plus the deterministic guardrail
  unit test from Phase 2 (assert tripwire fires).

**Verify:** `pytest` passes all 5 cases + the unit test. Re-run to confirm stability under
non-determinism; tighten instructions if a case is flaky.
**Cost:** ~$0.02 per full pass.

---

## Phase 5 — Evidence packet

**Files:** `src/advisor/run_logger.py`, populate `evidence/`

- `run_logger.py`: writes `evidence/run-<id>.json` per run (request id, trace id, model +
  agent name, tool calls + outcomes, guardrail tripped?, approval outcome, final/blocked
  state, eval status). Wire it into `run.py` and the eval runner.
- Capture: OpenAI dashboard **trace screenshots** (esp. case 3 guardrail trip, case 4
  escalation) + **CLI transcripts** of all 5 cases into `evidence/`.

**Verify:** every README claim has a matching artifact in `evidence/`.
**Cost:** $0 beyond the eval runs already made.

---

## Phase 6 — README + reflection

**Files:** `README.md`, `REFLECTION.md`

- `README.md`: spec §"README outline" — what it is, architecture diagram, three questions,
  setup, run command + sample output, design decisions (3 tools, schema, guardrail, state),
  eval table + how to run, evidence pointer, cost note, decisions-to-defend.
- `REFLECTION.md`: the 1-page, 5-section outline (spec §13), filled with the **real** bugs
  hit during Phases 3–4.

**Verify:** a clean clone → `pip install -e .` → add key → run → `pytest` works in under
two minutes following only the README.
**Cost:** $0.

---

## Build order summary

```
0 Scaffold → 1 Data → 2 Deterministic core (free tests) → 3 Agent+CLI (first $) →
4 Evals → 5 Evidence → 6 README+Reflection
```

Phases 0–2 are entirely offline and free; the LLM is only introduced in Phase 3, keeping
total spend well under the $3–4 budget.

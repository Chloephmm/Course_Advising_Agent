# McGill Course Advisor

A small single-agent course-advising system for a McGill Master of Management Analytics
(MMA) student. The app uses the OpenAI Agents SDK to recommend next-term courses from a
fixed local catalog, then uses deterministic Python code to check prerequisites, credit
limits, term availability, and advisor-approval risks.

The important design boundary is simple:

| Decision | Owner |
| --- | --- |
| Which eligible courses fit the student's stated goal | The agent |
| Prerequisites, credit totals, term availability, and policy checks | Python code |
| Any exception to a hard rule | A human advisor |

The agent can flag that advisor approval is required. It never grants approval itself.

## What This Project Does

- Runs one advising request at a time from a CLI.
- Builds a fresh local context for each student profile.
- Lets the agent search the catalog, check prerequisites, and flag policy risks through
  typed tools.
- Forces the final answer into a typed `Recommendation` object.
- Runs an output guardrail that blocks any recommendation containing a course whose
  prerequisites are unmet.
- Writes inspectable JSON evidence records to `evidence/run-<id>.json`.
- Includes offline unit tests for the deterministic policy logic and optional live evals
  for the agent behavior.

## Repository Layout

```text
mcgill-course-advisor/
├── README.md
├── REFLECTION.md
├── pyproject.toml
├── docs/
│   ├── plans/
│   │   └── 2026-06-02-mcgill-course-advisor-plan.md
│   └── specs/
│       └── 2026-06-02-mcgill-course-advisor-design.md
├── evidence/
│   ├── .gitkeep
│   └── run-*.json
├── evals/
│   ├── __init__.py
│   ├── cases.py
│   ├── run_evals.py
│   ├── test_evals.py
│   └── test_policy.py
└── src/
    └── advisor/
        ├── __init__.py
        ├── agent.py
        ├── context.py
        ├── fixtures.py
        ├── guardrails.py
        ├── policy.py
        ├── run.py
        ├── run_logger.py
        ├── schemas.py
        └── tools.py
```

## Requirements

- Python 3.10 or newer
- An OpenAI API key for live agent runs
- No API key is needed for the offline unit tests

Project dependencies are declared in `pyproject.toml`:

- `openai-agents`
- `pydantic`
- `pytest` for development and tests

## Setup

Create and activate a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Install the project in editable mode with test dependencies:

```bash
pip install -e ".[dev]"
```

Set your OpenAI API key before running the live agent:

```bash
export OPENAI_API_KEY="sk-..."
```

This checkout does not currently include a `.env.example` file. The CLI will load `.env`
automatically only if `python-dotenv` is installed in your environment. Exporting the
environment variable directly is the most reliable setup path.

## Quick Start

Run the CLI module directly:

```bash
python -m advisor.run --student alice --term Winter --goal "data mining"
```

After installation, you can also use the console script:

```bash
advisor --student alice --term Winter --goal "data mining"
```

Disable evidence-file writing when you only want a quick console run:

```bash
python -m advisor.run --student alice --term Winter --goal "data mining" --no-evidence
```

Use a different model:

```bash
python -m advisor.run --student alice --term Winter --goal "data mining" --model gpt-4o-mini
```

## CLI Arguments

| Argument | Required | Default | Description |
| --- | --- | --- | --- |
| `--student` | Yes | None | Student fixture id. Known ids are `alice`, `bob`, `carol`, and `dave`. |
| `--term` | No | None | Planned term: `Fall`, `Winter`, or `Summer`. |
| `--goal` | No | None | Student interest or goal, such as `"data mining"`. |
| `--model` | No | `gpt-4o-mini` | Model passed into the OpenAI Agents SDK agent. |
| `--no-evidence` | No | `False` | Prevents writing `evidence/run-<id>.json`. |

## Example Output

A successful run prints the OpenAI trace id, model, structured recommendation, and evidence
path:

```text
trace_id: trace_...   (model: gpt-4o-mini)
{
  "student_id": "alice",
  "term": "Winter",
  "suggested_courses": [
    {
      "course_code": "INSY 662",
      "title": "Data Mining & Visualization",
      "credits": 3.0,
      "rationale": "Matches the student's data-mining goal and prerequisites are met.",
      "prereqs_met": true
    }
  ],
  "total_credits": 3.0,
  "flagged_risks": [],
  "requires_advisor_approval": false,
  "approval_reason": null,
  "missing_info": [],
  "summary": "A Winter course that fits the goal with no policy issues."
}

evidence: evidence/run-1234abcd.json
```

If the guardrail blocks the output, the CLI prints a blocked message instead of returning
the unsafe recommendation.

## Student Fixtures

The project includes four local student profiles in `src/advisor/fixtures.py`.

| Student | Completed Courses | GPA | Standing | Useful Demo |
| --- | --- | --- | --- | --- |
| `alice` | `INSY 660`, `MGSC 660` | 3.5 | good | Happy path for Winter data-mining recommendations. |
| `bob` | None | 3.2 | good | Missing prerequisites; useful for guardrail behavior. |
| `carol` | `INSY 660`, `MGSC 660`, `MGSC 661`, `ORGB 660` | 2.4 | probation | Heavy Winter load should require advisor approval. |
| `dave` | `INSY 660`, `MGSC 660` | 3.0 | good | Wants capstone but is missing `INSY 661`. |

## Course Catalog

The catalog is intentionally small: 10 MMA core/project courses. Course codes, titles, and
credits are based on the project fixture; terms and prerequisite chains are local demo data.

| Code | Title | Credits | Term | Prerequisites |
| --- | --- | ---: | --- | --- |
| `INSY 660` | Coding Foundations for Analytics | 3.0 | Fall | None |
| `MGSC 660` | Mathematical & Statistical Foundations for Analytics | 3.0 | Fall | None |
| `ORGB 660` | Managing Data Analytics Teams | 1.5 | Fall | None |
| `INSY 661` | Database & Distributed Systems for Analytics | 3.0 | Winter | `INSY 660` |
| `INSY 662` | Data Mining & Visualization | 3.0 | Winter | `INSY 660`, `MGSC 660` |
| `MGSC 661` | Multivariate Statistical Analysis | 3.0 | Winter | `MGSC 660` |
| `ORGB 661` | Ethical Leadership & Leading Change | 1.5 | Winter | `ORGB 660` |
| `MGSC 662` | Decision Analytics | 3.0 | Summer | `MGSC 661` |
| `BUSA 693` | Capstone | 6.0 | Summer | `INSY 660`, `INSY 661`, `MGSC 660` |
| `BUSA 649` | Community Analytics Project | 3.0 | Summer | `BUSA 693` |

## Policy Rules

The rules live in `src/advisor/policy.py` and are checked by pure Python functions.

| Rule | Behavior | Main Code Path |
| --- | --- | --- |
| Credit cap | Plans over 12 credits are flagged as a policy risk. | `flag_policy_risks_logic` |
| Term availability | A course planned outside its offered term is flagged. | `flag_policy_risks_logic` |
| Prerequisites | A course is eligible only when all prerequisites are complete. | `check_prereqs_logic` |
| Project sequence | `BUSA 693` requires its prerequisites; `BUSA 649` requires `BUSA 693`. | `check_prereqs_logic` |
| Probation load | A probation student taking more than 6 credits requires advisor approval. | `flag_policy_risks_logic` |
| Unsafe recommendation block | Any final recommendation with unmet prerequisites is blocked. | `prerequisite_guardrail` |

## Architecture

```text
Student CLI request
        |
        v
advisor.run.advise()
        |
        v
OpenAI Agents SDK Runner.run()
        |
        v
Agent: "McGill Course Advisor"
        |
        +-- Tool: search_courses()
        +-- Tool: check_prerequisites()
        +-- Tool: flag_policy_risk()
        |
        v
Typed Recommendation output
        |
        v
Output guardrail: prerequisite_guardrail
        |
        +-- pass: print and optionally log final output
        +-- trip: block unsafe output and log blocked state
```

The app is stateless. Each CLI run creates a new `AdvisingContext`, calls `Runner.run`
once, and then exits. No conversation history, cache, or student state is persisted between
runs.

## Key Modules

| File | Purpose |
| --- | --- |
| `src/advisor/schemas.py` | Pydantic models for courses, profiles, tool outputs, policy risks, and final recommendations. |
| `src/advisor/fixtures.py` | Fixed course catalog, student profiles, credit limits, and fixture validation helper. |
| `src/advisor/policy.py` | Deterministic rule logic with no SDK calls and no I/O. |
| `src/advisor/context.py` | `AdvisingContext`, the local per-run object holding the student profile and tool-call log. |
| `src/advisor/tools.py` | Three typed tool wrappers around policy logic. |
| `src/advisor/guardrails.py` | Named output guardrail that blocks unmet-prerequisite recommendations. |
| `src/advisor/agent.py` | Agent definition, instructions, tools, model, output type, and guardrails. |
| `src/advisor/run.py` | CLI entry point and `advise()` orchestration function. |
| `src/advisor/run_logger.py` | Writes evidence JSON files. |
| `evals/cases.py` | Five live eval cases and their pass/fail checks. |
| `evals/test_policy.py` | Offline tests for policy and guardrail logic. |
| `evals/test_evals.py` | Pytest wrapper around the live agent eval cases. |
| `evals/run_evals.py` | One-command live eval report. |

## Tools

The agent has exactly three tools.

### `search_courses(query, term=None)`

Searches the local catalog by course code or title. It excludes courses the current student
has already completed. An empty query returns all non-completed courses, optionally filtered
by term.

### `check_prerequisites(course_code)`

Checks one course against the current student's completed courses. Unknown courses return a
failed check with `UNKNOWN_COURSE`.

### `flag_policy_risk(course_codes, term)`

Checks a proposed plan for term mismatch, credit overload, and probation-load approval.
Prerequisites are intentionally handled by `check_prerequisites()` and the final guardrail.

## Typed Output

The final answer must be a `Recommendation` from `src/advisor/schemas.py`:

```python
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
```

This keeps the result usable by other code. The app does not need to parse prose to learn
which courses were suggested or whether advisor approval is needed.

## Guardrail Behavior

`prerequisite_guardrail` runs after the model produces a `Recommendation`. It re-checks
every suggested course using deterministic policy logic. If any suggested course has unmet
prerequisites, the guardrail tripwire fires and the CLI records a blocked run.

This means the model can make a mistake, but the app still prevents an unsafe final
recommendation from being returned.

## Evidence Files

By default, each run writes a JSON record to `evidence/run-<id>.json`.

Each record includes:

- request id
- trace id
- model name
- agent name
- student id
- input term and goal
- tool-call log
- guardrail result
- advisor-approval flag
- final output, or block reason if the guardrail tripped
- optional eval case id

Evidence writing is handled by `src/advisor/run_logger.py`.

## Tests

Run all tests:

```bash
pytest
```

Expected behavior:

- Offline policy tests always run.
- Live eval tests are skipped automatically when `OPENAI_API_KEY` is not set.
- Live eval tests run when `OPENAI_API_KEY` is available.

Run only the offline policy tests:

```bash
pytest evals/test_policy.py -v
```

Run the live pytest evals:

```bash
pytest evals/test_evals.py -v
```

Run the live eval report script:

```bash
python -m evals.run_evals
```

## Eval Cases

The live eval suite in `evals/cases.py` checks behavior, not wording.

| Case | Student | Kind | Expected Behavior |
| --- | --- | --- | --- |
| `happy_path` | `alice` | normal | Eligible Winter recommendation, no advisor approval. |
| `missing_evidence` | `alice` | edge | Missing term and goal should produce `missing_info`. |
| `guardrail_trip` | `bob` | failure | Ineligible course is either self-censored or blocked. |
| `escalation` | `carol` | edge | Heavy probation load requires advisor approval. |
| `malformed_args` | `alice` | edge | Unknown course such as `INSY 999` is not recommended. |

## Useful Development Commands

Validate fixture consistency:

```bash
python -m advisor.fixtures
```

Run one quick advisory request without writing evidence:

```bash
python -m advisor.run --student alice --term Winter --goal "data mining" --no-evidence
```

Run a guardrail-oriented scenario:

```bash
python -m advisor.run --student bob --term Summer --goal "I want to take MGSC 662"
```

Run an advisor-approval scenario:

```bash
python -m advisor.run --student carol --term Winter --goal "I want as many courses as possible"
```

## Troubleshooting

### `ModuleNotFoundError: No module named 'advisor'`

Install the project first:

```bash
pip install -e ".[dev]"
```

Or run commands from the repository root with `PYTHONPATH=src`.

### Live runs fail because no API key is set

Set `OPENAI_API_KEY` in your shell:

```bash
export OPENAI_API_KEY="sk-..."
```

### `.env` is not being loaded

The code only loads `.env` if `python-dotenv` is installed. Either export
`OPENAI_API_KEY` directly or install `python-dotenv` in your environment.

### Live evals are skipped

That is expected when `OPENAI_API_KEY` is missing. Use `pytest evals/test_policy.py -v`
for no-cost offline verification.

### A run writes files into `evidence/`

That is expected. Pass `--no-evidence` when you do not want a JSON run record.

## Extending The Project

To add a course:

1. Add it to `_COURSES` in `src/advisor/fixtures.py`.
2. Add or adjust tests in `evals/test_policy.py` if the new course affects a rule.
3. Run `python -m advisor.fixtures`.
4. Run `pytest`.

To add a student profile:

1. Add a `StudentProfile` to `_PROFILES` in `src/advisor/fixtures.py`.
2. Use the new id with `--student`.
3. Add an eval case if the profile represents an important behavior.

To add a policy rule:

1. Put deterministic logic in `src/advisor/policy.py`.
2. Expose it through a tool only if the agent needs to reason with the result.
3. Add offline tests first.
4. Update the guardrail if the rule must block unsafe final output.

## Current Limits

- The catalog is a fixture, not a live McGill data source.
- Terms and prerequisite chains are local demo data.
- The app is a CLI, not a web service.
- There is no database.
- There is no multi-turn memory.
- The agent can advise and flag risk, but it cannot register courses or approve exceptions.

# Reflection — McGill Course Advisor

## 1. What I built
One focused agent on the OpenAI Agents SDK that advises an MMA student on next-term courses.
Three typed tools (`search_courses`, `check_prerequisites`, `flag_policy_risk`), a typed
`Recommendation` output, one named blocking guardrail (`prerequisite_guardrail`), and a
stateless single-turn design. All policy rules live in a pure module (`policy.py`), so they
are deterministic and tested without the model.

## 2. What failed (the honest part)
- **Ambiguous empty tool results caused infinite loops — the main bug.** The agent kept
  hitting `MaxTurnsExceeded`. The per-run tool-call log showed why: when `flag_policy_risk`
  (and later `search_courses`) returned an empty list, the model couldn't tell "nothing
  found" from "no answer" and re-called the same tool ~19 times. Fix: tools now return
  explicit reports (`PolicyRiskReport`, `CourseSearchResult`) with a `summary`, so an empty
  result is unambiguous. This took the suite from looping to 5/5.
- **`temperature=0` made it worse.** I added it for reproducibility, but it turned the loop
  *deterministic* — the model repeated the identical call with no chance of breaking out. I
  reverted it.
- **The agent recommended an already-completed course.** The prereq guardrail only checks
  prerequisites, not completion, so Carol was offered a course she'd passed. Fixed by
  excluding completed courses from search, plus a test.
- **The guardrail eval can't assume the model misbehaves.** A well-instructed model
  self-censors, so the tripwire rarely fires live. I reframed case 3 as an invariant ("no
  ineligible course ever reaches output") and added a deterministic unit test that proves the
  tripwire fires independent of the model.

## 3. What improved
- Splitting pure logic (`policy.py`) from SDK wrappers let me unit-test all five rules and the
  guardrail offline — 15 tests, zero API cost — before spending a cent.
- The per-run evidence log diagnosed both loops by showing the repeated call directly:
  inspect the trace before tuning the prompt.

## 4. What is still risky
- **Model non-determinism** — wording varies and softer behaviors aren't guaranteed.
- **Rules 1, 2, 4 depend on the model calling `flag_policy_risk`** — if it forgets, a risk
  (even the probation escalation) could be under-reported. A hardened version would recompute
  these in code post-run, like the guardrail does for prerequisites.
- **Tiny fixture world** — ten courses with invented prereq chains.

## 5. The three questions
- **Model decides:** course fit and how to explain it.
- **Code decides:** prerequisites, credit totals, policy violations.
- **Human decides:** overrides and probation approvals — the agent flags, never grants.

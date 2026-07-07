"""One-command eval report (slide 94: scenario id, model, trace id, pass/fail, detail).

    python -m evals.run_evals      # needs OPENAI_API_KEY in env or .env

Runs all cases, writes per-run evidence JSON, prints a report table, and exits non-zero if
any case fails (so it can gate a release).
"""

from __future__ import annotations

import asyncio
import sys

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from advisor.run import advise
from evals.cases import CASES


async def main() -> int:
    rows = []
    all_passed = True
    for case in CASES:
        record = await advise(case.student, case.term, case.goal, eval_status=case.id)
        if record.get("error"):
            passed, detail = False, f"run error: {record['error']}"
        else:
            passed, detail = case.check(record)
        all_passed = all_passed and passed
        rows.append((case.id, case.kind, "PASS" if passed else "FAIL",
                     record["trace_id"], detail))

    width = max(len(r[0]) for r in rows)
    print(f"\n{'CASE'.ljust(width)}  KIND     RESULT  TRACE_ID          DETAIL")
    print("-" * (width + 60))
    for cid, kind, result, trace_id, detail in rows:
        print(f"{cid.ljust(width)}  {kind:7}  {result:6}  {trace_id[:16]}  {detail}")

    n_pass = sum(1 for r in rows if r[2] == "PASS")
    print(f"\n{n_pass}/{len(rows)} cases passed.")
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

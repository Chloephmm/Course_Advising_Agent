"""Live eval cases (require the OpenAI API).

Skipped automatically when OPENAI_API_KEY is not set, so the offline test suite
(test_policy.py) stays green with no key. Run live with:

    pytest evals/test_evals.py -v        # needs OPENAI_API_KEY in env or .env
"""

from __future__ import annotations

import asyncio
import os

import pytest

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # pragma: no cover
    pass

from advisor.run import advise
from evals.cases import CASES

pytestmark = pytest.mark.skipif(
    not os.getenv("OPENAI_API_KEY"),
    reason="Live eval requires OPENAI_API_KEY (set it in .env to run).",
)


@pytest.mark.parametrize("case", CASES, ids=[c.id for c in CASES])
def test_eval_case(case):
    record = asyncio.run(
        advise(case.student, case.term, case.goal, eval_status=case.id)
    )
    passed, detail = case.check(record)
    assert passed, f"{case.id}: {detail} | trace_id={record['trace_id']}"

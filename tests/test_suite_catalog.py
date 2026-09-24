"""Suite catalog coverage (R4, R5): 12-15 suite tasks under tasks/, every R5 category
covered by at least one. The dev tasks catalog (design.md, tasks.md T9-T12) lands in
lotes 4-7; this test is a real assertion against the real suite once it exists, not a
placeholder — it skips with an explicit reason until there's enough to check."""

from __future__ import annotations

import pytest

from owl.tasks import SUITE_CATEGORIES, TaskInfo, suite_tasks


# Covers: R4, R5
def test_suite_has_12_to_15_tasks_covering_every_r5_category() -> None:
    tasks = suite_tasks(include_holdout=False)
    if len(tasks) < 12:
        pytest.skip(
            f"only {len(tasks)} suite task(s) under tasks/ so far; design.md's 12-15 dev "
            "tasks land in lotes 4-7 (tasks.md T9-T12). Re-enable once tasks/ has >= 12."
        )

    assert 12 <= len(tasks) <= 15, f"suite has {len(tasks)} tasks, expected 12-15 (R4)"

    categories = {TaskInfo.load(t).owl_type for t in tasks}
    missing = SUITE_CATEGORIES - categories
    assert not missing, f"R5 categories with no task: {sorted(missing)}"

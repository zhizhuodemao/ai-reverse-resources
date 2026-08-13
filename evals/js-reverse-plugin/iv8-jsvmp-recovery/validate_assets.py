#!/usr/bin/env python3
"""Validate eval assets without running any model or fixture code."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as error:
            raise AssertionError(f"{path.name}:{line_number}: {error}") from error
        assert isinstance(value, dict), f"{path.name}:{line_number}: expected object"
        rows.append(value)
    return rows


def main() -> None:
    cases = read_jsonl(ROOT / "cases.jsonl")
    rubrics = read_jsonl(ROOT / "rubrics.jsonl")
    triggers = read_jsonl(ROOT / "trigger-queries.jsonl")
    trigger_set = json.loads((ROOT / "trigger-set.json").read_text(encoding="utf-8"))

    case_ids = [row["case_id"] for row in cases]
    assert len(case_ids) == len(set(case_ids)), "duplicate case_id"
    rubric_map = {row["rubric_id"]: row for row in rubrics}
    assert len(rubric_map) == len(rubrics), "duplicate rubric_id"

    for case in cases:
        assert (ROOT / case["fixture"]).is_file(), f"missing fixture: {case['fixture']}"
        assert (ROOT / case["prompt"]).is_file(), f"missing prompt: {case['prompt']}"
        assert case["rubric_id"] in rubric_map, f"missing rubric: {case['rubric_id']}"
        assert case["execution_policy"] == "do-not-execute"

    assert set(case_ids) == set(rubric_map), "case/rubric ids differ"
    for rubric in rubrics:
        points = sum(item["points"] for item in rubric["criteria"])
        assert points == rubric["max_score"], f"score mismatch: {rubric['rubric_id']}"
        assert rubric["hard_failures"], f"no hard failures: {rubric['rubric_id']}"

    query_ids = [row["query_id"] for row in triggers]
    assert len(query_ids) == len(set(query_ids)), "duplicate query_id"
    assert all(row["split"] in {"train", "test"} for row in triggers)
    assert all(isinstance(row["expected"], bool) for row in triggers)

    actual = {
        "total": len(triggers),
        "positive": sum(row["expected"] for row in triggers),
        "negative": sum(not row["expected"] for row in triggers),
        "train": sum(row["split"] == "train" for row in triggers),
        "test": sum(row["split"] == "test" for row in triggers),
    }
    for key, value in actual.items():
        assert trigger_set[key] == value, f"trigger-set {key}: expected {value}"

    print(
        f"OK: {len(cases)} cases, {len(rubrics)} rubrics, "
        f"{len(triggers)} trigger queries"
    )


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Validate eval assets with the Python standard library only."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
FORBIDDEN_FIXTURE_TEXT = (
    "/Users/",
    "课程案例demo",
    "douyin",
    "bdms",
)


def read_json(path: Path, errors: list[str]):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.relative_to(ROOT)}: {exc}")
        return None


def read_jsonl(path: Path, errors: list[str]) -> list[dict]:
    rows = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        errors.append(f"{path.relative_to(ROOT)}: {exc}")
        return rows
    for line_number, line in enumerate(lines, 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(ROOT)}:{line_number}: {exc}")
            continue
        if not isinstance(value, dict):
            errors.append(f"{path.relative_to(ROOT)}:{line_number}: expected object")
            continue
        rows.append(value)
    return rows


def resolve_asset(relative: str, errors: list[str]) -> Path | None:
    candidate = (ROOT / relative).resolve()
    try:
        candidate.relative_to(ROOT)
    except ValueError:
        errors.append(f"asset escapes eval root: {relative}")
        return None
    if not candidate.is_file():
        errors.append(f"missing asset: {relative}")
        return None
    return candidate


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_cases(errors: list[str]) -> tuple[list[dict], list[dict]]:
    cases = read_jsonl(ROOT / "cases.jsonl", errors)
    rubrics = read_jsonl(ROOT / "rubrics.jsonl", errors)
    if len(cases) < 3:
        errors.append("cases.jsonl: at least 3 cases required")

    case_ids = [row.get("case_id") for row in cases]
    rubric_ids = [row.get("rubric_id") for row in rubrics]
    if None in case_ids or len(case_ids) != len(set(case_ids)):
        errors.append("cases.jsonl: case_id values must be present and unique")
    if None in rubric_ids or len(rubric_ids) != len(set(rubric_ids)):
        errors.append("rubrics.jsonl: rubric_id values must be present and unique")
    if set(case_ids) != set(rubric_ids):
        errors.append("case IDs and rubric IDs must match exactly")

    fixture_hashes = set()
    for row in cases:
        for field in ("fixture", "prompt", "rubric_id", "execution_policy"):
            if not row.get(field):
                errors.append(f"{row.get('case_id', '<unknown>')}: missing {field}")
        fixture = resolve_asset(str(row.get("fixture", "")), errors)
        prompt = resolve_asset(str(row.get("prompt", "")), errors)
        if fixture:
            fixture_hashes.add(sha256(fixture))
            text = fixture.read_text(encoding="utf-8")
            for forbidden in FORBIDDEN_FIXTURE_TEXT:
                if forbidden.lower() in text.lower():
                    errors.append(f"{row['fixture']}: forbidden fixture text {forbidden!r}")
        if prompt and not prompt.read_text(encoding="utf-8").strip():
            errors.append(f"{row['prompt']}: empty prompt")
    if len(fixture_hashes) != len(cases):
        errors.append("fixtures must be structurally distinct files")

    for rubric in rubrics:
        criteria = rubric.get("criteria")
        if not isinstance(criteria, list) or not criteria:
            errors.append(f"{rubric.get('rubric_id')}: criteria must be non-empty")
            continue
        points = sum(item.get("points", 0) for item in criteria if isinstance(item, dict))
        if points != rubric.get("max_score"):
            errors.append(f"{rubric.get('rubric_id')}: criterion points != max_score")
        if not rubric.get("hard_failures"):
            errors.append(f"{rubric.get('rubric_id')}: hard_failures required")
        for item in criteria:
            if not all(item.get(key) for key in ("id", "points", "observable")):
                errors.append(f"{rubric.get('rubric_id')}: malformed criterion")
    return cases, rubrics


def validate_trigger_set(errors: list[str]) -> list[dict]:
    declaration = read_json(ROOT / "trigger-set.json", errors)
    rows = read_jsonl(ROOT / "trigger-queries.jsonl", errors)
    if not isinstance(declaration, dict):
        return rows

    ids = [row.get("query_id") for row in rows]
    queries = [row.get("query") for row in rows]
    if None in ids or len(ids) != len(set(ids)):
        errors.append("trigger-queries.jsonl: query_id values must be unique")
    if None in queries or len(queries) != len(set(queries)):
        errors.append("trigger-queries.jsonl: queries must be unique")

    labels = Counter(row.get("label") for row in rows)
    splits = Counter(row.get("split") for row in rows)
    if len(rows) != declaration.get("declared_total"):
        errors.append("trigger total does not match trigger-set.json")
    if labels != Counter(declaration.get("declared_labels", {})):
        errors.append(f"trigger label counts mismatch: {dict(labels)}")
    if splits != Counter(declaration.get("declared_splits", {})):
        errors.append(f"trigger split counts mismatch: {dict(splits)}")
    for row in rows:
        if row.get("label") not in {"positive", "negative"}:
            errors.append(f"{row.get('query_id')}: invalid label")
        if row.get("split") not in {"train", "test"}:
            errors.append(f"{row.get('query_id')}: invalid split")
        if not row.get("rationale"):
            errors.append(f"{row.get('query_id')}: rationale required")
    for split in ("train", "test"):
        present = {row.get("label") for row in rows if row.get("split") == split}
        if present != {"positive", "negative"}:
            errors.append(f"{split}: must include positive and negative queries")
    return rows


def validate_schema_file(path: Path, expected_required: set[str], errors: list[str]):
    schema = read_json(path, errors)
    if not isinstance(schema, dict):
        return
    if schema.get("type") != "object":
        errors.append(f"{path.relative_to(ROOT)}: top-level type must be object")
    required = set(schema.get("required", []))
    missing = expected_required - required
    if missing:
        errors.append(f"{path.relative_to(ROOT)}: missing required fields {sorted(missing)}")
    if not isinstance(schema.get("properties"), dict):
        errors.append(f"{path.relative_to(ROOT)}: properties object required")


def validate_pending(cases: list[dict], triggers: list[dict], errors: list[str]):
    manifest = read_json(ROOT / "runs/pending-run.json", errors)
    if not isinstance(manifest, dict):
        return
    if manifest.get("status") != "pending" or manifest.get("results_recorded") is not False:
        errors.append("pending manifest must remain pending with no recorded results")
    try:
        datetime.fromisoformat(manifest["created_date"])
    except (KeyError, TypeError, ValueError):
        errors.append("pending manifest created_date must be ISO-8601")

    skill = manifest.get("skill", {})
    recorded_hash = skill.get("sha256", "")
    if not SHA256_RE.fullmatch(recorded_hash):
        errors.append("pending manifest skill.sha256 must be 64 lowercase hex characters")
    skill_path = (ROOT / str(skill.get("path", ""))).resolve()
    if not skill_path.is_file():
        errors.append("pending manifest skill path does not exist")
    elif recorded_hash != sha256(skill_path):
        errors.append("pending manifest skill hash does not match current SKILL.md")

    models = manifest.get("models")
    if not isinstance(models, list) or not models:
        errors.append("pending manifest models must be non-empty")
        models = []
    for model in models:
        for field in ("slot", "provider", "id", "parameters", "status"):
            if field not in model:
                errors.append(f"pending model missing {field}")
        if model.get("status") != "pending":
            errors.append("pending model status must be pending")
    if not manifest.get("command_template"):
        errors.append("pending manifest command_template required")

    task = manifest.get("task_eval", {})
    description = manifest.get("description_eval", {})
    if set(task.get("cases", [])) != {row.get("case_id") for row in cases}:
        errors.append("pending task case list does not match cases.jsonl")
    if task.get("arms") != ["skill", "baseline"]:
        errors.append("pending task arms must be skill and baseline")
    expected_tasks = len(cases) * 2 * len(models)
    if task.get("planned_records") != expected_tasks:
        errors.append("pending task planned_records is inconsistent")
    if description.get("query_count") != len(triggers):
        errors.append("pending description query_count is inconsistent")
    expected_triggers = len(triggers) * description.get("trials_per_query", 0) * len(models)
    if description.get("planned_records") != expected_triggers:
        errors.append("pending description planned_records is inconsistent")

    serialized = json.dumps(manifest, ensure_ascii=False).lower()
    for forbidden in ('"score"', '"observed_trigger"', '"hard_failures"'):
        if forbidden in serialized:
            errors.append(f"pending manifest must not contain model result field {forbidden}")


def validate_optional_results(
    path: Path,
    required: set[str],
    valid_cases: set[str] | None,
    valid_queries: set[str] | None,
    errors: list[str],
):
    if not path.exists():
        return
    rows = read_jsonl(path, errors)
    for index, row in enumerate(rows, 1):
        missing = required - set(row)
        if missing:
            errors.append(f"{path.relative_to(ROOT)}:{index}: missing {sorted(missing)}")
        if valid_cases is not None and row.get("case_id") not in valid_cases:
            errors.append(f"{path.relative_to(ROOT)}:{index}: unknown case_id")
        if valid_queries is not None and row.get("query_id") not in valid_queries:
            errors.append(f"{path.relative_to(ROOT)}:{index}: unknown query_id")


def main() -> int:
    errors: list[str] = []
    cases, _ = validate_cases(errors)
    triggers = validate_trigger_set(errors)

    task_required = {
        "run_id",
        "comparison_group",
        "status",
        "date_utc",
        "model",
        "skill",
        "arm",
        "case_id",
        "fixture_sha256",
        "prompt_sha256",
        "command",
        "output_path",
        "result",
    }
    trigger_required = {
        "run_id",
        "status",
        "date_utc",
        "model",
        "skill_sha256",
        "query_id",
        "trial",
        "expected_trigger",
        "observed_trigger",
        "command",
        "notes",
    }
    validate_schema_file(
        ROOT / "schemas/run-record.schema.json", task_required, errors
    )
    validate_schema_file(
        ROOT / "schemas/trigger-record.schema.json", trigger_required, errors
    )
    validate_pending(cases, triggers, errors)

    validate_optional_results(
        ROOT / "runs/task-results.jsonl",
        task_required,
        {row.get("case_id") for row in cases},
        None,
        errors,
    )
    validate_optional_results(
        ROOT / "runs/trigger-results.jsonl",
        trigger_required,
        None,
        {row.get("query_id") for row in triggers},
        errors,
    )

    if errors:
        print("eval assets invalid:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(
        "eval assets valid: "
        f"{len(cases)} cases, {len(triggers)} trigger queries, "
        "0 fabricated result files"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

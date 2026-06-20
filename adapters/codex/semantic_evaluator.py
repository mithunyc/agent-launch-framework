#!/usr/bin/env python3
"""Deterministic semantic rubric evaluator for behavior-eval outputs.

Rubrics live in eval case JSON but are not included in the prompt sent to the
agent. This keeps the first semantic pass hidden from the evaluated runtime
while remaining deterministic and dependency-free for local/CI promotion gates.
"""

from __future__ import annotations

from typing import Any


NEGATING_CONTEXT = [
    "avoid",
    "avoids",
    "block",
    "blocks",
    "forbid",
    "forbids",
    "forbidden",
    "must not",
    "never",
    "no ",
    "not ",
    "refuse",
    "refuses",
    "reject",
    "rejects",
    "should not",
    "without",
]


def flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten_text(v) for v in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(v) for v in value)
    if value is None:
        return ""
    return str(value)


def get_path(value: Any, path: str) -> Any:
    current = value
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def selected_text(payload: Any, fields: list[str] | None) -> str:
    if not fields:
        return flatten_text(payload)
    return " ".join(flatten_text(get_path(payload, field)) for field in fields)


def count_items(value: Any) -> int:
    if isinstance(value, (list, dict, str)):
        return len(value)
    return 0


def forbidden_hits(haystack: str, needles: list[Any]) -> list[str]:
    hits: list[str] = []
    for needle in needles:
        raw_needle = str(needle).lower()
        start = 0
        found_affirmative = False
        while raw_needle:
            index = haystack.find(raw_needle, start)
            if index == -1:
                break
            context = haystack[max(0, index - 72) : index]
            if not any(marker in context for marker in NEGATING_CONTEXT):
                found_affirmative = True
                break
            start = index + len(raw_needle)
        if found_affirmative:
            hits.append(str(needle))
    return hits


def evaluate_criterion(case_id: str, criterion: dict[str, Any], final_payload: Any) -> dict[str, Any]:
    criterion_id = str(criterion.get("id", "unnamed"))
    weight = int(criterion.get("weight", 1) or 1)
    fields = criterion.get("fields")
    if fields is not None and not isinstance(fields, list):
        fields = None
    haystack = selected_text(final_payload, fields).lower()

    failures: list[str] = []
    evidence: list[str] = []

    expected_verdicts = criterion.get("expected_verdicts", [])
    if expected_verdicts:
        actual_verdict = final_payload.get("verdict") if isinstance(final_payload, dict) else None
        if actual_verdict not in expected_verdicts:
            failures.append(f"verdict={actual_verdict!r} not in {expected_verdicts!r}")
        else:
            evidence.append(f"verdict={actual_verdict!r}")

    must_include_any = criterion.get("must_include_any", [])
    if must_include_any:
        matched = [needle for needle in must_include_any if str(needle).lower() in haystack]
        if not matched:
            failures.append(f"matched_any=[] expected one of {must_include_any!r}")
        else:
            evidence.append(f"matched_any={matched!r}")

    must_include_all = criterion.get("must_include_all", [])
    if must_include_all:
        missing = [needle for needle in must_include_all if str(needle).lower() not in haystack]
        if missing:
            failures.append(f"missing_all={missing!r}")
        else:
            evidence.append(f"matched_all={must_include_all!r}")

    must_not_include_any = criterion.get("must_not_include_any", [])
    if must_not_include_any:
        hits = forbidden_hits(haystack, must_not_include_any)
        if hits:
            failures.append(f"forbidden_hits={hits!r}")
        else:
            evidence.append("forbidden_hits=[]")

    min_items = criterion.get("min_items", {})
    if isinstance(min_items, dict):
        for field, minimum in min_items.items():
            actual = count_items(get_path(final_payload, str(field)))
            required = int(minimum)
            if actual < required:
                failures.append(f"{field} count {actual} < {required}")
            else:
                evidence.append(f"{field} count {actual} >= {required}")

    max_items = criterion.get("max_items", {})
    if isinstance(max_items, dict):
        for field, maximum in max_items.items():
            actual = count_items(get_path(final_payload, str(field)))
            allowed = int(maximum)
            if actual > allowed:
                failures.append(f"{field} count {actual} > {allowed}")
            else:
                evidence.append(f"{field} count {actual} <= {allowed}")

    status = "pass" if not failures else "fail"
    return {
        "id": criterion_id,
        "status": status,
        "score": weight if status == "pass" else 0,
        "max_score": weight,
        "check": {
            "name": f"semantic.{case_id}.{criterion_id}",
            "status": status,
            "evidence": "; ".join(evidence if status == "pass" else failures)[:800],
        },
    }


def evaluate_semantic_rubric(case: dict[str, Any], final_payload: Any) -> dict[str, Any]:
    case_id = str(case.get("id", "unknown"))
    rubric = case.get("semantic_rubric")
    if not isinstance(rubric, dict):
        check = {
            "name": f"semantic.{case_id}.rubric_present",
            "status": "fail",
            "evidence": "semantic_rubric object missing",
        }
        return {
            "score": 0,
            "max_score": 1,
            "threshold": 1,
            "verdict": "fail",
            "checks": [check],
            "criteria": [],
        }

    criteria = rubric.get("criteria", [])
    if not isinstance(criteria, list) or not criteria:
        check = {
            "name": f"semantic.{case_id}.rubric_criteria",
            "status": "fail",
            "evidence": "semantic_rubric.criteria must be a non-empty list",
        }
        return {
            "score": 0,
            "max_score": 1,
            "threshold": 1,
            "verdict": "fail",
            "checks": [check],
            "criteria": [],
        }

    criterion_results = [
        evaluate_criterion(case_id, criterion, final_payload)
        for criterion in criteria
        if isinstance(criterion, dict)
    ]
    score = sum(result["score"] for result in criterion_results)
    max_score = sum(result["max_score"] for result in criterion_results)
    threshold = int(rubric.get("min_score", max_score) or max_score)
    aggregate_status = "pass" if max_score > 0 and score >= threshold else "fail"
    checks = [result["check"] for result in criterion_results]
    checks.append(
        {
            "name": f"semantic.{case_id}.rubric_score",
            "status": aggregate_status,
            "evidence": f"{score}/{max_score} threshold={threshold}",
        }
    )
    return {
        "score": score,
        "max_score": max_score,
        "threshold": threshold,
        "verdict": aggregate_status,
        "checks": checks,
        "criteria": criterion_results,
    }

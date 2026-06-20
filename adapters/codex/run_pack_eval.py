#!/usr/bin/env python3
"""Run static pack evals and write a receipt.

This is not an LLM behavioral eval. It is the v0 preflight that proves the pack
has adversarial cases and receiptable checks before any runtime automation.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from validate_agent_pack import validate_pack


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def run_static_eval(pack: Path) -> tuple[bool, dict]:
    pack = pack.resolve()
    started = utc_now()
    validation_ok, validation_checks = validate_pack(pack)

    checks = [
        {
            "name": "validator",
            "status": "pass" if validation_ok else "fail",
            "evidence": f"{sum(1 for c in validation_checks if c['status'] == 'pass')}/{len(validation_checks)} validator checks passed",
        }
    ]

    case_results = []
    cases_dir = pack / "evals" / "cases"
    for case_path in sorted(cases_dir.glob("*.json")):
        case = load_json(case_path)
        expected = case.get("expected_behaviors", [])
        failures = case.get("failure_modes", [])
        risk_tags = case.get("risk_tags", [])
        rubric = case.get("semantic_rubric", {})
        rubric_criteria = rubric.get("criteria", []) if isinstance(rubric, dict) else []
        status = "pass" if expected and failures and risk_tags and rubric_criteria else "fail"
        case_results.append(
            {
                "id": case.get("id", case_path.stem),
                "status": status,
                "expected_behaviors": len(expected),
                "failure_modes": len(failures),
                "risk_tags": risk_tags,
                "semantic_criteria": len(rubric_criteria),
            }
        )
        checks.append(
            {
                "name": f"eval_case.{case.get('id', case_path.stem)}",
                "status": status,
                "evidence": f"{len(expected)} expected behavior(s), {len(failures)} failure mode(s), {len(rubric_criteria)} semantic criteria",
            }
        )

    score = sum(1 for check in checks if check["status"] == "pass")
    max_score = len(checks)
    ok = validation_ok and all(result["status"] == "pass" for result in case_results)
    completed = utc_now()

    receipt = {
        "schema_version": "0.1.0",
        "agent_pack": pack.name,
        "task": "static-pack-eval",
        "runtime": "adapters/codex/run_pack_eval.py",
        "started_at": started,
        "completed_at": completed,
        "evidence": [
            {
                "type": "pack-path",
                "source": str(pack),
                "summary": "Static validation and eval case inspection",
            }
        ],
        "checks": checks,
        "dod_score": {
            "score": score,
            "max_score": max_score,
            "verdict": "pass" if ok else "fail",
        },
        "risks": [] if ok else ["Pack failed static validation or eval-case inspection."],
        "case_results": case_results,
        "memory_proposals": [],
        "self_improvement_proposals": [],
        "rollback": "No runtime mutation was performed. Delete the generated receipt if this static eval should be discarded.",
    }
    return ok, receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run static eval checks for an agent pack")
    parser.add_argument("pack", type=Path, help="Path to an agent pack")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--no-write", action="store_true", help="Do not write a receipt")
    args = parser.parse_args(argv)

    ok, receipt = run_static_eval(args.pack)
    if not args.no_write:
        receipts_dir = args.pack.resolve() / "receipts" / "runs"
        receipts_dir.mkdir(parents=True, exist_ok=True)
        safe_time = receipt["completed_at"].replace(":", "").replace("-", "")
        out_path = receipts_dir / f"{safe_time}.static-eval.receipt.json"
        out_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
        receipt["written_to"] = str(out_path)

    if args.json:
        print(json.dumps({"ok": ok, "receipt": receipt}, indent=2))
    else:
        for check in receipt["checks"]:
            print(f"[{check['status'].upper()}] {check['name']}: {check['evidence']}")
        if "written_to" in receipt:
            print(f"RECEIPT: {receipt['written_to']}")
        print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

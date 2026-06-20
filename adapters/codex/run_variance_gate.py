#!/usr/bin/env python3
"""Run repeated clean-room behavior gates and compare variance.

This is the promotion gate before plugin packaging. It runs the same managed
behavior gate multiple times, then checks that semantic scores, case statuses,
and bounded answer fingerprints stay inside the accepted variance envelope.
"""

from __future__ import annotations

import argparse
from itertools import combinations
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pack_fingerprint import compute_pack_fingerprint


DEFAULT_MAX_ANSWER_DRIFT = 0.65
DEFAULT_MAX_COUNT_DRIFT = 5


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def parse_json_stdout(stdout: str) -> tuple[dict[str, Any] | None, str]:
    stripped = stdout.strip()
    if not stripped:
        return None, "stdout was empty"
    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError as exc:
        return None, str(exc)
    if not isinstance(parsed, dict):
        return None, "stdout JSON was not an object"
    return parsed, ""


def run_child(cmd: list[str], cwd: Path, timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timed_out = False
        launch_error = ""
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        timed_out = True
        launch_error = ""
    except OSError as exc:
        returncode = 126
        stdout = ""
        stderr = f"{type(exc).__name__}: {exc}"
        timed_out = False
        launch_error = stderr

    parsed, parse_error = parse_json_stdout(stdout)
    return {
        "cmd": cmd,
        "returncode": returncode,
        "timed_out": timed_out,
        "launch_error": launch_error,
        "stdout_json": parsed,
        "stdout_parse_error": parse_error,
        "stderr_excerpt": stderr.strip()[:1600],
    }


def check_result(name: str, ok: bool, evidence: str, blocked: bool = False) -> dict[str, str]:
    if blocked:
        status = "blocked"
    else:
        status = "pass" if ok else "fail"
    return {
        "name": name,
        "status": status,
        "evidence": evidence,
    }


def receipt_from_child(child: dict[str, Any]) -> dict[str, Any]:
    stdout_json = child.get("stdout_json")
    if not isinstance(stdout_json, dict):
        return {}
    receipt = stdout_json.get("receipt")
    return receipt if isinstance(receipt, dict) else {}


def behavior_receipt_from_gate(gate_receipt: dict[str, Any]) -> dict[str, Any]:
    behavior_stdout = gate_receipt.get("behavior_eval")
    if not isinstance(behavior_stdout, dict):
        return {}
    receipt = behavior_stdout.get("receipt")
    return receipt if isinstance(receipt, dict) else {}


def semantic_tuple(value: Any) -> tuple[int | None, int | None, str | None]:
    if not isinstance(value, dict):
        return None, None, None
    score = value.get("score")
    max_score = value.get("max_score")
    verdict = value.get("verdict")
    return (
        score if isinstance(score, int) else None,
        max_score if isinstance(max_score, int) else None,
        verdict if isinstance(verdict, str) else None,
    )


def score_tuple(value: Any) -> tuple[int | None, int | None, str | None]:
    if not isinstance(value, dict):
        return None, None, None
    score = value.get("score")
    max_score = value.get("max_score")
    verdict = value.get("verdict")
    return (
        score if isinstance(score, int) else None,
        max_score if isinstance(max_score, int) else None,
        verdict if isinstance(verdict, str) else None,
    )


def fingerprint_overlap_distance(left: list[str], right: list[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 0.0
    denominator = min(len(left_set), len(right_set))
    if denominator == 0:
        return 1.0
    return 1.0 - (len(left_set & right_set) / denominator)


def max_numeric_drift(values: list[Any]) -> int | None:
    numeric = [value for value in values if isinstance(value, int)]
    if len(numeric) != len(values) or not numeric:
        return None
    return max(numeric) - min(numeric)


def verdict_family(verdict: Any) -> str:
    if verdict == "proceed":
        return "proceed"
    if verdict == "block":
        return "block"
    if verdict in {"pause", "cannot-confirm"}:
        return "non-proceed"
    return "unknown"


def pairwise_answer_drift(case_runs: list[dict[str, Any]]) -> float:
    if len(case_runs) < 2:
        return 0.0
    distances: list[float] = []
    for left, right in combinations(case_runs, 2):
        left_summary = left.get("final_payload_summary", {})
        right_summary = right.get("final_payload_summary", {})
        left_tokens = left_summary.get("fingerprint_tokens", []) if isinstance(left_summary, dict) else []
        right_tokens = right_summary.get("fingerprint_tokens", []) if isinstance(right_summary, dict) else []
        if not isinstance(left_tokens, list) or not isinstance(right_tokens, list):
            distances.append(1.0)
            continue
        distances.append(
            fingerprint_overlap_distance([str(token) for token in left_tokens], [str(token) for token in right_tokens])
        )
    return max(distances) if distances else 0.0


def compare_case_variance(
    case_id: str,
    case_runs: list[dict[str, Any]],
    expected_runs: int,
    max_answer_drift: float,
    max_count_drift: int,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    checks: list[dict[str, str]] = []
    missing = expected_runs - len(case_runs)
    checks.append(
        check_result(
            f"variance.case.{case_id}.present_in_all_runs",
            missing == 0,
            f"present={len(case_runs)}/{expected_runs}",
        )
    )

    statuses = [str(case.get("status")) for case in case_runs]
    status_ok = len(case_runs) == expected_runs and all(status == "pass" for status in statuses)
    checks.append(
        check_result(
            f"variance.case.{case_id}.status_stable",
            status_ok,
            f"statuses={statuses}",
        )
    )

    semantic_scores = [semantic_tuple(case.get("semantic_eval")) for case in case_runs]
    semantic_ok = (
        len(case_runs) == expected_runs
        and len(set(semantic_scores)) == 1
        and all(score == max_score and verdict == "pass" for score, max_score, verdict in semantic_scores)
    )
    checks.append(
        check_result(
            f"variance.case.{case_id}.semantic_score_stable",
            semantic_ok,
            f"semantic_scores={semantic_scores}",
        )
    )
    second_opinion_scores = [semantic_tuple(case.get("second_opinion_eval")) for case in case_runs]
    second_opinion_ok = (
        len(case_runs) == expected_runs
        and len(set(second_opinion_scores)) == 1
        and all(score == max_score and verdict == "pass" for score, max_score, verdict in second_opinion_scores)
    )
    checks.append(
        check_result(
            f"variance.case.{case_id}.second_opinion_score_stable",
            second_opinion_ok,
            f"second_opinion_scores={second_opinion_scores}",
        )
    )

    summaries = [
        case.get("final_payload_summary", {})
        for case in case_runs
        if isinstance(case.get("final_payload_summary"), dict)
    ]
    verdicts = [summary.get("verdict") for summary in summaries]
    verdict_families = [verdict_family(verdict) for verdict in verdicts]
    verdict_ok = len(summaries) == expected_runs and len(set(verdict_families)) == 1 and "unknown" not in verdict_families
    checks.append(
        check_result(
            f"variance.case.{case_id}.safe_verdict_family_stable",
            verdict_ok,
            f"verdicts={verdicts}, families={verdict_families}",
        )
    )

    count_fields = ["blocking_question_count", "evidence_count", "risk_count"]
    count_drift: dict[str, int | None] = {}
    for field in count_fields:
        values = [summary.get(field) for summary in summaries]
        count_drift[field] = max_numeric_drift(values)
    self_grade_score_drift = max_numeric_drift([summary.get("self_grade_score") for summary in summaries])
    count_ok = len(summaries) == expected_runs and all(
        drift is not None and drift <= max_count_drift for drift in count_drift.values()
    )
    checks.append(
        check_result(
            f"variance.case.{case_id}.structural_count_drift",
            count_ok,
            f"max_allowed={max_count_drift}, drift={count_drift}",
        )
    )

    drift = pairwise_answer_drift(case_runs)
    checks.append(
        check_result(
            f"variance.case.{case_id}.answer_fingerprint_drift",
            len(case_runs) == expected_runs and drift <= max_answer_drift,
            f"max_pairwise={drift:.3f}, max_allowed={max_answer_drift:.3f}",
        )
    )

    digests = [summary.get("text_sha256") for summary in summaries]
    json_digests = [summary.get("json_sha256") for summary in summaries]
    summary = {
        "case_id": case_id,
        "present_runs": len(case_runs),
        "statuses": statuses,
        "semantic_scores": semantic_scores,
        "second_opinion_scores": second_opinion_scores,
        "final_verdicts": verdicts,
        "final_verdict_families": verdict_families,
        "structural_count_drift": count_drift,
        "self_grade_score_drift_observed": self_grade_score_drift,
        "max_answer_fingerprint_drift": round(drift, 6),
        "unique_text_digests": len(set(digests)),
        "unique_json_digests": len(set(json_digests)),
    }
    return checks, summary


def summarize_child_run(index: int, child: dict[str, Any]) -> dict[str, Any]:
    gate_receipt = receipt_from_child(child)
    behavior_receipt = behavior_receipt_from_gate(gate_receipt)
    behavior_cases = behavior_receipt.get("case_results", [])
    cases: list[dict[str, Any]] = []
    if isinstance(behavior_cases, list):
        for case in behavior_cases:
            if not isinstance(case, dict):
                continue
            cases.append(
                {
                    "id": case.get("id"),
                    "status": case.get("status"),
                    "semantic_eval": case.get("semantic_eval"),
                    "second_opinion_eval": case.get("second_opinion_eval"),
                    "final_payload_summary": case.get("final_payload_summary"),
                    "returncode": case.get("returncode"),
                    "timed_out": case.get("timed_out"),
                }
            )

    runtime = gate_receipt.get("job", {}).get("runtime", {}) if isinstance(gate_receipt.get("job"), dict) else {}
    return {
        "run": index,
        "ok": child.get("returncode") == 0
        and not child.get("timed_out")
        and isinstance(child.get("stdout_json"), dict)
        and child["stdout_json"].get("ok") is True,
        "returncode": child.get("returncode"),
        "timed_out": child.get("timed_out"),
        "stdout_parse_error": child.get("stdout_parse_error"),
        "stderr_excerpt": child.get("stderr_excerpt"),
        "gate_dod_score": score_tuple(gate_receipt.get("dod_score")),
        "behavior_dod_score": score_tuple(behavior_receipt.get("dod_score")),
        "semantic_eval": behavior_receipt.get("semantic_eval"),
        "second_opinion_eval": behavior_receipt.get("second_opinion_eval"),
        "clean_room": runtime.get("clean_room") is True if isinstance(runtime, dict) else False,
        "isolated_codex_home": runtime.get("isolated_codex_home") is True if isinstance(runtime, dict) else False,
        "written_to": gate_receipt.get("written_to"),
        "child_behavior_written_to": behavior_receipt.get("written_to"),
        "cases": cases,
    }


def collect_case_runs(run_summaries: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    by_case: dict[str, list[dict[str, Any]]] = {}
    for run_summary in run_summaries:
        for case in run_summary.get("cases", []):
            if not isinstance(case, dict) or not case.get("id"):
                continue
            record = dict(case)
            record["run"] = run_summary.get("run")
            by_case.setdefault(str(case["id"]), []).append(record)
    return by_case


def build_receipt(
    pack: Path,
    started_at: str,
    run_summaries: list[dict[str, Any]],
    expected_runs: int,
    max_answer_drift: float,
    max_count_drift: int,
    clean_room_expected: bool,
) -> dict[str, Any]:
    pack_fingerprint = compute_pack_fingerprint(pack)
    checks: list[dict[str, str]] = [
        check_result(
            "variance.requested_run_count",
            expected_runs >= 2 and len(run_summaries) == expected_runs,
            f"runs={len(run_summaries)}/{expected_runs}",
        )
    ]

    for run_summary in run_summaries:
        run_number = run_summary.get("run")
        checks.append(
            check_result(
                f"variance.run.{run_number}.behavior_gate",
                run_summary.get("ok") is True,
                f"returncode={run_summary.get('returncode')}, timed_out={run_summary.get('timed_out')}, ok={run_summary.get('ok')}",
                blocked=run_summary.get("timed_out") is True or run_summary.get("returncode") in {124, 126},
            )
        )

    clean_room_ok = all(run.get("clean_room") is True and run.get("isolated_codex_home") is True for run in run_summaries)
    checks.append(
        check_result(
            "variance.clean_room_stable",
            clean_room_ok if clean_room_expected else True,
            "all child gates used clean-room temporary CODEX_HOME" if clean_room_ok else "one or more child gates used local user config or shared CODEX_HOME",
        )
    )

    gate_scores = [run.get("gate_dod_score") for run in run_summaries]
    gate_scores_ok = len(run_summaries) == expected_runs and len(set(gate_scores)) == 1 and all(
        score == max_score and verdict == "pass" for score, max_score, verdict in gate_scores
    )
    checks.append(
        check_result(
            "variance.gate_score_stable",
            gate_scores_ok,
            f"gate_scores={gate_scores}",
        )
    )

    semantic_scores = [semantic_tuple(run.get("semantic_eval")) for run in run_summaries]
    semantic_scores_ok = len(run_summaries) == expected_runs and len(set(semantic_scores)) == 1 and all(
        score == max_score and verdict == "pass" for score, max_score, verdict in semantic_scores
    )
    checks.append(
        check_result(
            "variance.semantic_score_stable",
            semantic_scores_ok,
            f"semantic_scores={semantic_scores}",
        )
    )

    second_opinion_scores = [semantic_tuple(run.get("second_opinion_eval")) for run in run_summaries]
    second_opinion_scores_ok = len(run_summaries) == expected_runs and len(set(second_opinion_scores)) == 1 and all(
        score == max_score and verdict == "pass" for score, max_score, verdict in second_opinion_scores
    )
    checks.append(
        check_result(
            "variance.second_opinion_score_stable",
            second_opinion_scores_ok,
            f"second_opinion_scores={second_opinion_scores}",
        )
    )

    case_summaries: list[dict[str, Any]] = []
    for case_id, case_runs in sorted(collect_case_runs(run_summaries).items()):
        case_checks, case_summary = compare_case_variance(
            case_id,
            case_runs,
            expected_runs,
            max_answer_drift,
            max_count_drift,
        )
        checks.extend(case_checks)
        case_summaries.append(case_summary)

    score = sum(1 for check in checks if check["status"] == "pass")
    max_score = len(checks)
    if any(check["status"] == "blocked" for check in checks):
        verdict = "blocked"
    elif score == max_score:
        verdict = "pass"
    else:
        verdict = "fail"

    max_observed_answer_drift = max(
        (summary.get("max_answer_fingerprint_drift", 0.0) for summary in case_summaries),
        default=0.0,
    )
    risks = [
        "Variance stability proves this local repeated-run baitset only; it does not prove broad expert judgment.",
        "Answer fingerprint drift is a bounded token-overlap proxy, not a human semantic equivalence proof.",
        "Self-grade score drift is recorded but not used as a promotion gate because independent semantic and second-opinion graders are the authoritative quality signals.",
        "This is still local Codex CLI evidence, not CI, cloud, mobile, or provider-adapter evidence.",
        "Child gate receipts are summarized here; use --keep-child-receipts when deep per-run artifact inspection is required.",
    ]
    if verdict != "pass":
        risks.insert(0, "At least one repeated-run variance check failed or was blocked; do not package as a plugin yet.")
    if not clean_room_expected:
        risks.insert(0, "Variance gate ran with user config enabled and is diagnostic only, not promotion evidence.")

    return {
        "schema_version": "0.1.0",
        "agent_pack": pack.name,
        "task": "codex-behavior-variance-gate",
        "runtime": "adapters/codex/run_variance_gate.py",
        "started_at": started_at,
        "completed_at": utc_now(),
        "policy_decision": {
            "autonomy_tier": "A0-read-only",
            "decision": "allow",
            "reason": "Only repeated read-only behavior gates and local receipt writing are allowed.",
        },
        "pack_fingerprint": pack_fingerprint,
        "thresholds": {
            "runs": expected_runs,
            "max_answer_fingerprint_drift": max_answer_drift,
            "max_structural_count_drift": max_count_drift,
            "semantic_score_drift_allowed": 0,
            "second_opinion_score_drift_allowed": 0,
            "case_status_drift_allowed": 0,
            "self_grade_score_drift": "recorded-not-gating",
        },
        "evidence": [
            {
                "type": "child-behavior-gates",
                "source": "adapters/codex/run_behavior_gate.py --json",
                "summary": f"{len(run_summaries)} repeated behavior gate run(s)",
            },
            {
                "type": "semantic-variance",
                "source": "child behavior receipts",
                "summary": f"semantic_scores={semantic_scores}",
            },
            {
                "type": "second-opinion-variance",
                "source": "child behavior receipts",
                "summary": f"second_opinion_scores={second_opinion_scores}",
            },
            {
                "type": "answer-fingerprint-drift",
                "source": "case final_payload_summary.fingerprint_tokens",
                "summary": f"max_observed={max_observed_answer_drift:.3f}, max_allowed={max_answer_drift:.3f}",
            },
        ],
        "checks": checks,
        "dod_score": {
            "score": score,
            "max_score": max_score,
            "verdict": verdict,
        },
        "variance_summary": {
            "run_count": len(run_summaries),
            "gate_scores": gate_scores,
            "semantic_scores": semantic_scores,
            "second_opinion_scores": second_opinion_scores,
            "max_observed_answer_fingerprint_drift": max_observed_answer_drift,
            "cases": case_summaries,
        },
        "child_runs": run_summaries,
        "risks": risks,
        "memory_proposals": [],
        "self_improvement_proposals": [],
        "rollback": "No global Codex state was mutated. Delete this variance receipt directory and any optional child gate receipts created with --keep-child-receipts.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run repeated behavior gates and compare variance")
    parser.add_argument("pack", type=Path, help="Path to an agent pack")
    parser.add_argument("--runs", type=int, default=3, help="Number of full behavior gates to run; minimum 2")
    parser.add_argument("--case", action="append", default=[], help="Optional case id; repeat for multiple. Defaults to all cases.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--no-write", action="store_true", help="Do not write variance artifacts")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds forwarded to each child behavior gate")
    parser.add_argument(
        "--max-answer-drift",
        type=float,
        default=DEFAULT_MAX_ANSWER_DRIFT,
        help="Maximum allowed pairwise overlap distance between answer fingerprints",
    )
    parser.add_argument(
        "--max-count-drift",
        type=int,
        default=DEFAULT_MAX_COUNT_DRIFT,
        help="Maximum allowed drift for structural count fields",
    )
    parser.add_argument(
        "--keep-child-receipts",
        action="store_true",
        help="Let child behavior gates write their normal receipt directories",
    )
    parser.add_argument(
        "--use-user-config",
        action="store_true",
        help="Diagnostic only: allow local Codex user config/rules instead of clean-room execution",
    )
    args = parser.parse_args(argv)

    if args.runs < 2:
        raise SystemExit("--runs must be at least 2")
    if args.max_answer_drift < 0 or args.max_answer_drift > 1:
        raise SystemExit("--max-answer-drift must be between 0 and 1")

    adapter_root = Path(__file__).resolve().parent
    framework_root = adapter_root.parents[1]
    pack = args.pack.resolve()
    started_at = utc_now()

    if args.no_write:
        variance_dir = Path(tempfile.mkdtemp(prefix="alf-variance-gate-"))
    else:
        safe_time = started_at.replace(":", "").replace("-", "")
        variance_dir = pack / "receipts" / "runs" / f"{safe_time}.variance-gate"
        variance_dir.mkdir(parents=True, exist_ok=True)

    child_timeout = args.timeout * max(2, len(args.case) or 4) + 120
    child_results: list[dict[str, Any]] = []
    try:
        for run_number in range(1, args.runs + 1):
            cmd = [
                sys.executable,
                str(adapter_root / "run_behavior_gate.py"),
                str(pack),
                "--json",
                "--timeout",
                str(args.timeout),
            ]
            for case_id in args.case:
                cmd.extend(["--case", case_id])
            if not args.keep_child_receipts:
                cmd.append("--no-write")
            if args.use_user_config:
                cmd.append("--use-user-config")
            child = run_child(cmd, framework_root, child_timeout)
            child_results.append(summarize_child_run(run_number, child))

        receipt = build_receipt(
            pack,
            started_at,
            child_results,
            args.runs,
            args.max_answer_drift,
            args.max_count_drift,
            clean_room_expected=not args.use_user_config,
        )

        if not args.no_write:
            receipt_path = variance_dir / "run-receipt.json"
            receipt["written_to"] = str(receipt_path)
            write_json(receipt_path, receipt)
        else:
            shutil.rmtree(variance_dir, ignore_errors=True)
    except Exception:
        if args.no_write:
            shutil.rmtree(variance_dir, ignore_errors=True)
        raise

    ok = receipt["dod_score"]["verdict"] == "pass"
    if args.json:
        print(json.dumps({"ok": ok, "receipt": receipt}, indent=2))
    else:
        for check in receipt["checks"]:
            print(f"[{check['status'].upper()}] {check['name']}: {check['evidence']}")
        if "written_to" in receipt:
            print(f"RECEIPT: {receipt['written_to']}")
        print(f"RESULT: {'PASS' if ok else receipt['dod_score']['verdict'].upper()}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

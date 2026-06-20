#!/usr/bin/env python3
"""Run the managed behavior gate for an agent pack.

This wrapper is intentionally conservative: it does not execute arbitrary jobs
or mutate global Codex state. It proves a pack through static checks and Codex
behavior cases, then writes a gate receipt for a future control plane.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from validate_agent_pack import parse_simple_manifest


REQUIRED_JOB_FIELDS = {
    "schema_version",
    "job_id",
    "agent_pack",
    "task",
    "runtime",
    "autonomy_tier",
    "policy",
    "workspace",
    "eval_gate",
    "receipt",
    "created_at",
}


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
        timed_out = False
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        launch_error = ""
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        returncode = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        launch_error = ""
    except OSError as exc:
        timed_out = False
        returncode = 126
        stdout = ""
        stderr = f"{type(exc).__name__}: {exc}"
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


def build_job(
    pack: Path,
    manifest: dict[str, Any],
    cases: list[str],
    started_at: str,
    timeout: int,
    clean_room: bool,
) -> dict[str, Any]:
    safe_time = started_at.replace(":", "").replace("-", "").lower()
    return {
        "schema_version": "0.1.0",
        "job_id": f"{pack.name}.behavior-gate.{safe_time}",
        "agent_pack": {
            "id": str(manifest.get("id", pack.name)),
            "version": str(manifest.get("version", "unknown")),
        },
        "task": {
            "kind": "behavior-gate",
            "prompt": "Run static and Codex-native behavior gates before managed-agent promotion.",
            "inputs": [
                str(pack / "agent.yaml"),
                str(pack / "evals" / "cases"),
            ],
        },
        "runtime": {
            "adapter": "adapters/codex",
            "surface": "codex-cli-exec",
            "sandbox": "read-only",
            "timeout_seconds": timeout,
            "clean_room": clean_room,
            "isolated_codex_home": clean_room,
            "codex_exec_flags": ["--ignore-user-config", "--ignore-rules", "--disable", "plugins"] if clean_room else [],
        },
        "autonomy_tier": "A0-read-only",
        "policy": {
            "approval_required": False,
            "allowed_actions": [
                "validate-pack",
                "static-eval",
                "codex-behavior-eval",
                "semantic-eval",
                "second-opinion-eval",
                "write-local-receipt",
            ],
            "blocked_actions": [
                "global-install",
                "write-production-data",
                "deploy",
                "self-promote-memory",
                "self-modify-skill",
            ],
        },
        "workspace": {
            "strategy": "disposable",
        },
        "eval_gate": {
            "required": True,
            "cases": cases or ["all"],
            "semantic_required": True,
            "second_opinion_required": True,
        },
        "receipt": {
            "required": True,
            "target": str(pack / "receipts" / "runs"),
        },
        "created_at": started_at,
    }


def validate_job(job: dict[str, Any]) -> list[dict[str, str]]:
    checks: list[dict[str, str]] = []
    task = job.get("task", {})
    task_kind = task.get("kind") if isinstance(task, dict) else None
    missing = sorted(REQUIRED_JOB_FIELDS - set(job))
    checks.append(
        {
            "name": "job.required_fields",
            "status": "pass" if not missing else "fail",
            "evidence": "all required fields present" if not missing else f"missing={missing}",
        }
    )
    tier_ok = job.get("autonomy_tier") == "A0-read-only"
    checks.append(
        {
            "name": "job.autonomy_tier",
            "status": "pass" if tier_ok else "fail",
            "evidence": str(job.get("autonomy_tier")),
        }
    )
    policy = job.get("policy", {})
    blocked = set(policy.get("blocked_actions", [])) if isinstance(policy, dict) else set()
    if task_kind == "plugin-packaging-gate":
        needed_blocks = {
            "normal-user-codex-home-mutation",
            "workspace-plugin-sharing",
            "public-plugin-publish",
            "cloud-runner-claim",
            "mobile-runner-claim",
            "provider-parity-claim",
        }
    else:
        needed_blocks = {"global-install", "write-production-data", "deploy", "self-promote-memory", "self-modify-skill"}
    checks.append(
        {
            "name": "job.policy_blocks_high_risk_actions",
            "status": "pass" if needed_blocks <= blocked else "fail",
            "evidence": f"blocked={sorted(blocked)}",
        }
    )
    runtime = job.get("runtime", {})
    clean_room = runtime.get("clean_room") is True if isinstance(runtime, dict) else False
    isolated_home = runtime.get("isolated_codex_home") is True if isinstance(runtime, dict) else False
    checks.append(
        {
            "name": "job.clean_room",
            "status": "pass" if clean_room else "fail",
            "evidence": "--ignore-user-config, --ignore-rules, and --disable plugins required" if clean_room else "local user config/rules enabled",
        }
    )
    checks.append(
        {
            "name": "job.isolated_codex_home",
            "status": "pass" if clean_room and isolated_home else "fail",
            "evidence": "temporary auth-only CODEX_HOME required" if isolated_home else "normal CODEX_HOME enabled",
        }
    )
    eval_gate = job.get("eval_gate", {})
    semantic_required = eval_gate.get("semantic_required") is True if isinstance(eval_gate, dict) else False
    second_opinion_required = eval_gate.get("second_opinion_required") is True if isinstance(eval_gate, dict) else False
    variance_gate = job.get("variance_gate", {})
    plugin_packaging_gate_required = (
        task_kind == "plugin-packaging-gate"
        and isinstance(eval_gate, dict)
        and eval_gate.get("required") is True
        and bool(eval_gate.get("cases"))
        and isinstance(variance_gate, dict)
        and variance_gate.get("required") is True
    )
    checks.append(
        {
            "name": "job.semantic_required",
            "status": "pass" if semantic_required or plugin_packaging_gate_required else "fail",
            "evidence": (
                "hidden semantic rubric pass required"
                if semantic_required
                else (
                    "plugin packaging gate requires variance and negative plugin fixtures"
                    if plugin_packaging_gate_required
                    else "semantic rubric not required"
                )
            ),
        }
    )
    checks.append(
        {
            "name": "job.second_opinion_required",
            "status": "pass" if second_opinion_required or plugin_packaging_gate_required else "fail",
            "evidence": (
                "independent second-opinion invariant pass required"
                if second_opinion_required
                else (
                    "plugin packaging gate uses fixture and install-discovery proof instead"
                    if plugin_packaging_gate_required
                    else "second opinion not required"
                )
            ),
        }
    )
    return checks


def child_check(name: str, result: dict[str, Any]) -> dict[str, str]:
    parsed = result.get("stdout_json")
    ok = result["returncode"] == 0 and not result["timed_out"] and isinstance(parsed, dict) and parsed.get("ok") is True
    if result["timed_out"] or result["returncode"] in {124, 126}:
        status = "blocked"
    else:
        status = "pass" if ok else "fail"
    return {
        "name": name,
        "status": status,
        "evidence": f"returncode={result['returncode']}, timed_out={result['timed_out']}, ok={parsed.get('ok') if isinstance(parsed, dict) else None}",
    }


def behavior_case_checks(behavior: dict[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(behavior, dict):
        return [{"name": "behavior.case_results", "status": "fail", "evidence": "behavior stdout did not parse"}]
    receipt = behavior.get("receipt", {})
    cases = receipt.get("case_results", []) if isinstance(receipt, dict) else []
    if not cases:
        return [{"name": "behavior.case_results", "status": "fail", "evidence": "no case_results found"}]
    checks: list[dict[str, str]] = []
    for case in cases:
        case_id = case.get("id", "unknown")
        case_status = case.get("status")
        checks.append(
            {
                "name": f"behavior.case.{case_id}",
                "status": "pass" if case_status == "pass" else "fail",
                "evidence": str(case_status),
            }
        )
    return checks


def behavior_semantic_checks(behavior: dict[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(behavior, dict):
        return [{"name": "behavior.semantic_eval", "status": "fail", "evidence": "behavior stdout did not parse"}]
    receipt = behavior.get("receipt", {})
    semantic = receipt.get("semantic_eval", {}) if isinstance(receipt, dict) else {}
    checks: list[dict[str, str]] = [
        {
            "name": "behavior.semantic_eval",
            "status": "pass" if semantic.get("verdict") == "pass" else "fail",
            "evidence": f"{semantic.get('score')}/{semantic.get('max_score')} verdict={semantic.get('verdict')}",
        }
    ]
    cases = receipt.get("case_results", []) if isinstance(receipt, dict) else []
    for case in cases:
        case_id = case.get("id", "unknown")
        semantic_case = case.get("semantic_eval", {}) if isinstance(case, dict) else {}
        checks.append(
            {
                "name": f"behavior.semantic.case.{case_id}",
                "status": "pass" if semantic_case.get("verdict") == "pass" else "fail",
                "evidence": f"{semantic_case.get('score')}/{semantic_case.get('max_score')} threshold={semantic_case.get('threshold')}",
            }
        )
    return checks


def behavior_second_opinion_checks(behavior: dict[str, Any] | None) -> list[dict[str, str]]:
    if not isinstance(behavior, dict):
        return [{"name": "behavior.second_opinion_eval", "status": "fail", "evidence": "behavior stdout did not parse"}]
    receipt = behavior.get("receipt", {})
    second_opinion = receipt.get("second_opinion_eval", {}) if isinstance(receipt, dict) else {}
    checks: list[dict[str, str]] = [
        {
            "name": "behavior.second_opinion_eval",
            "status": "pass" if second_opinion.get("verdict") == "pass" else "fail",
            "evidence": f"{second_opinion.get('score')}/{second_opinion.get('max_score')} verdict={second_opinion.get('verdict')}",
        }
    ]
    cases = receipt.get("case_results", []) if isinstance(receipt, dict) else []
    for case in cases:
        case_id = case.get("id", "unknown")
        second_case = case.get("second_opinion_eval", {}) if isinstance(case, dict) else {}
        checks.append(
            {
                "name": f"behavior.second_opinion.case.{case_id}",
                "status": "pass" if second_case.get("verdict") == "pass" else "fail",
                "evidence": f"{second_case.get('score')}/{second_case.get('max_score')} verdict={second_case.get('verdict')}",
            }
        )
    return checks


def build_gate_receipt(
    pack: Path,
    job: dict[str, Any],
    started_at: str,
    static_result: dict[str, Any],
    behavior_result: dict[str, Any],
    gate_dir: Path,
) -> dict[str, Any]:
    checks = validate_job(job)
    checks.append(child_check("static_pack_eval", static_result))
    checks.append(child_check("codex_behavior_eval", behavior_result))
    checks.extend(behavior_case_checks(behavior_result.get("stdout_json")))
    checks.extend(behavior_semantic_checks(behavior_result.get("stdout_json")))
    checks.extend(behavior_second_opinion_checks(behavior_result.get("stdout_json")))

    score = sum(1 for check in checks if check["status"] == "pass")
    max_score = len(checks)
    if any(check["status"] == "blocked" for check in checks):
        verdict = "blocked"
    elif score == max_score:
        verdict = "pass"
    else:
        verdict = "fail"

    behavior_stdout = behavior_result.get("stdout_json")
    behavior_receipt = behavior_stdout.get("receipt", {}) if isinstance(behavior_stdout, dict) else {}
    behavior_written_to = behavior_receipt.get("written_to") if isinstance(behavior_receipt, dict) else None

    risks = [
        "A gate pass proves this baitset, deterministic semantic rubrics, and mechanical checks only; it does not prove broad semantic excellence.",
        "This is local Codex CLI execution, not web/mobile/cloud managed execution.",
        "The job contract is a control-plane input, not a scheduler or hosted service.",
    ]
    runtime = job.get("runtime", {})
    if isinstance(runtime, dict) and runtime.get("clean_room") is True:
        risks.append("Clean-room mode suppresses user config/rules/plugins and uses a temporary auth-only CODEX_HOME, but still depends on local Codex CLI auth and model availability.")
    else:
        risks.insert(0, "Gate ran with local user config/rules and is diagnostic only, not promotion evidence.")
    if verdict != "pass":
        risks.insert(0, "At least one gate check failed or was blocked.")

    return {
        "schema_version": "0.1.0",
        "agent_pack": pack.name,
        "task": "managed-behavior-gate",
        "runtime": "adapters/codex/run_behavior_gate.py",
        "started_at": started_at,
        "completed_at": utc_now(),
        "job": job,
        "policy_decision": {
            "autonomy_tier": "A0-read-only",
            "decision": "allow",
            "reason": "Only validation, read-only Codex behavior eval, and local receipt writing are allowed.",
        },
        "evidence": [
            {
                "type": "job-contract",
                "source": str(gate_dir / "job.json"),
                "summary": "Managed behavior gate job envelope",
            },
            {
                "type": "static-eval",
                "source": "adapters/codex/run_pack_eval.py --json --no-write",
                "summary": child_check("static_pack_eval", static_result)["evidence"],
            },
            {
                "type": "codex-behavior-eval",
                "source": behavior_written_to or "stdout",
                "summary": child_check("codex_behavior_eval", behavior_result)["evidence"],
            },
            {
                "type": "semantic-eval",
                "source": behavior_written_to or "stdout",
                "summary": behavior_semantic_checks(behavior_result.get("stdout_json"))[0]["evidence"],
            },
            {
                "type": "second-opinion-eval",
                "source": behavior_written_to or "stdout",
                "summary": behavior_second_opinion_checks(behavior_result.get("stdout_json"))[0]["evidence"],
            },
        ],
        "checks": checks,
        "dod_score": {
            "score": score,
            "max_score": max_score,
            "verdict": verdict,
        },
        "risks": risks,
        "static_eval": static_result.get("stdout_json"),
        "behavior_eval": behavior_result.get("stdout_json"),
        "memory_proposals": [],
        "self_improvement_proposals": [],
        "rollback": "No global Codex state was mutated. Delete this gate receipt directory and any child behavior receipt directories created by this run.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run static and Codex behavior gates for an agent pack")
    parser.add_argument("pack", type=Path, help="Path to an agent pack")
    parser.add_argument("--case", action="append", default=[], help="Optional case id; repeat for multiple. Defaults to all cases.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--no-write", action="store_true", help="Do not write gate artifacts; child behavior eval also runs no-write")
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds for each child command")
    parser.add_argument(
        "--use-user-config",
        action="store_true",
        help="Diagnostic only: allow local Codex user config/rules instead of clean-room execution",
    )
    args = parser.parse_args(argv)

    adapter_root = Path(__file__).resolve().parent
    framework_root = adapter_root.parents[1]
    pack = args.pack.resolve()
    started_at = utc_now()
    manifest = parse_simple_manifest(pack / "agent.yaml")
    clean_room = not args.use_user_config
    job = build_job(pack, manifest, args.case, started_at, args.timeout, clean_room)

    if args.no_write:
        gate_dir = Path(tempfile.mkdtemp(prefix="alf-behavior-gate-"))
    else:
        safe_time = started_at.replace(":", "").replace("-", "")
        gate_dir = pack / "receipts" / "runs" / f"{safe_time}.behavior-gate"
        gate_dir.mkdir(parents=True, exist_ok=True)
        write_json(gate_dir / "job.json", job)

    static_cmd = [
        sys.executable,
        str(adapter_root / "run_pack_eval.py"),
        str(pack),
        "--json",
        "--no-write",
    ]
    behavior_cmd = [
        sys.executable,
        str(adapter_root / "run_codex_behavior_eval.py"),
        str(pack),
        "--json",
        "--timeout",
        str(args.timeout),
    ]
    for case_id in args.case:
        behavior_cmd.extend(["--case", case_id])
    if args.no_write:
        behavior_cmd.append("--no-write")
    if clean_room:
        behavior_cmd.append("--clean-room")

    static_result = run_child(static_cmd, framework_root, args.timeout)
    behavior_result = run_child(behavior_cmd, framework_root, args.timeout * max(1, len(args.case) or 4))
    receipt = build_gate_receipt(pack, job, started_at, static_result, behavior_result, gate_dir)

    if not args.no_write:
        receipt_path = gate_dir / "run-receipt.json"
        receipt["written_to"] = str(receipt_path)
        write_json(receipt_path, receipt)
    elif gate_dir.exists():
        shutil.rmtree(gate_dir, ignore_errors=True)

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

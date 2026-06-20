#!/usr/bin/env python3
"""Run the disposable plugin packaging gate repeatedly and compare drift."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pack_fingerprint import compute_pack_fingerprint


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def check_result(name: str, ok: bool, evidence: str, blocked: bool = False) -> dict[str, str]:
    return {
        "name": name,
        "status": "blocked" if blocked else ("pass" if ok else "fail"),
        "evidence": evidence,
    }


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


def receipt_from_child(child: dict[str, Any]) -> dict[str, Any]:
    stdout_json = child.get("stdout_json")
    if not isinstance(stdout_json, dict):
        return {}
    receipt = stdout_json.get("receipt")
    return receipt if isinstance(receipt, dict) else {}


def flatten_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        return " ".join(flatten_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(flatten_text(item) for item in value)
    if value is None:
        return ""
    return str(value)


def normalize_string(value: str) -> str:
    normalized = value.replace("\\\\?\\", "")
    normalized = re.sub(
        r"[A-Za-z]:[\\/][^\s\"']*agent-launch-framework[\\/]\.alf-runs[\\/][^\s\"']+?\.plugin-packaging-gate",
        "<ALF_PLUGIN_RUN>",
        normalized,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r"[A-Za-z]:[\\/][^\s\"']*agent-launch-framework[\\/]\.alf-runs[\\/][^\s\"']+?\.plugin-packaging-variance-gate",
        "<ALF_PLUGIN_VARIANCE_RUN>",
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized


def normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_string(value)
    if isinstance(value, list):
        return [normalize_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): normalize_value(item) for key, item in sorted(value.items(), key=lambda item: str(item[0]))}
    return value


def sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def command_signature(commands: list[dict[str, Any]]) -> dict[str, Any]:
    signature: list[dict[str, Any]] = []
    for index, command in enumerate(commands):
        cmd = command.get("cmd", [])
        command_name = " ".join(str(part) for part in cmd[1:4]) if isinstance(cmd, list) else str(cmd)
        signature.append(
            {
                "index": index,
                "command": normalize_string(command_name),
                "returncode": command.get("returncode"),
                "timed_out": command.get("timed_out"),
                "stdout_json": normalize_value(command.get("stdout_json")),
                "stdout_parse_error": command.get("stdout_parse_error"),
                "stderr_excerpt": normalize_string(str(command.get("stderr_excerpt", ""))),
            }
        )
    return {
        "commands": signature,
        "sha256": sha256_json(signature),
    }


def prompt_discovery_signature(commands: list[dict[str, Any]]) -> dict[str, Any]:
    prompt_command = commands[-1] if commands else {}
    text = normalize_string(flatten_text(prompt_command.get("stdout_json")))
    skill_pattern = re.compile(r"world-class-reviewer(?::world-class-reviewer)?", re.IGNORECASE)
    skill_hits = sorted(set(match.group(0).lower() for match in skill_pattern.finditer(text)))
    evidence_first_visible = "evidence-first expert reviewer" in text.lower()
    plugin_visible = "world class reviewer" in text.lower() and "available plugins" in text.lower()
    lines = [
        line.strip()
        for line in text.splitlines()
        if "world-class-reviewer" in line.lower() or "world class reviewer" in line.lower()
    ][:20]
    normalized = {
        "returncode": prompt_command.get("returncode"),
        "skill_hits": skill_hits,
        "evidence_first_visible": evidence_first_visible,
        "plugin_visible": plugin_visible,
        "lines": lines,
    }
    normalized["sha256"] = sha256_json(normalized)
    return normalized


def summarize_child_run(index: int, child: dict[str, Any]) -> dict[str, Any]:
    receipt = receipt_from_child(child)
    package_result = receipt.get("package_result", {}) if isinstance(receipt.get("package_result"), dict) else {}
    cli_smoke = receipt.get("codex_cli_smoke", {}) if isinstance(receipt.get("codex_cli_smoke"), dict) else {}
    commands = cli_smoke.get("commands", []) if isinstance(cli_smoke.get("commands"), list) else []
    package_fingerprint = package_result.get("package_fingerprint", {}) if isinstance(package_result.get("package_fingerprint"), dict) else {}
    marketplace_fingerprint = package_result.get("marketplace_fingerprint", {}) if isinstance(package_result.get("marketplace_fingerprint"), dict) else {}
    source_fingerprint = package_result.get("source_fingerprint", {}) if isinstance(package_result.get("source_fingerprint"), dict) else {}
    command_sig = command_signature(commands)
    prompt_sig = prompt_discovery_signature(commands)
    codex_home = cli_smoke.get("codex_home", "")
    disposable_root = receipt.get("disposable_run_root", "")
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
        "written_to": receipt.get("written_to"),
        "dod_score": receipt.get("dod_score"),
        "pack_fingerprint": receipt.get("pack_fingerprint"),
        "source_fingerprint_sha256": source_fingerprint.get("sha256"),
        "package_fingerprint_sha256": package_fingerprint.get("sha256"),
        "package_file_count": package_fingerprint.get("file_count"),
        "marketplace_fingerprint_sha256": marketplace_fingerprint.get("sha256"),
        "marketplace_file_count": marketplace_fingerprint.get("file_count"),
        "plugin_name": package_result.get("plugin_name"),
        "marketplace_name": package_result.get("marketplace_name"),
        "discovered_skills": normalize_value(package_result.get("discovered_skills", [])),
        "codex_home": codex_home,
        "disposable_run_root": disposable_root,
        "temporary_codex_home": ".alf-runs" in str(codex_home) and "plugin-packaging-gate" in str(codex_home),
        "temporary_plugin_home": ".alf-runs" in str(disposable_root) and "plugin-packaging-gate" in str(disposable_root),
        "cli_returncodes": [command.get("returncode") for command in commands],
        "cli_signature_sha256": command_sig["sha256"],
        "cli_signature": command_sig,
        "prompt_discovery_sha256": prompt_sig["sha256"],
        "prompt_discovery": prompt_sig,
    }


def unique(values: list[Any]) -> list[Any]:
    seen: list[Any] = []
    for value in values:
        if value not in seen:
            seen.append(value)
    return seen


def build_receipt(
    pack: Path,
    started_at: str,
    run_summaries: list[dict[str, Any]],
    expected_runs: int,
) -> dict[str, Any]:
    pack_fingerprint = compute_pack_fingerprint(pack)
    checks: list[dict[str, str]] = [
        check_result(
            "plugin_variance.requested_run_count",
            expected_runs >= 2 and len(run_summaries) == expected_runs,
            f"runs={len(run_summaries)}/{expected_runs}",
        )
    ]

    for summary in run_summaries:
        run_number = summary.get("run")
        checks.append(
            check_result(
                f"plugin_variance.run.{run_number}.packaging_gate",
                summary.get("ok") is True,
                f"returncode={summary.get('returncode')}, timed_out={summary.get('timed_out')}, ok={summary.get('ok')}",
                blocked=summary.get("timed_out") is True or summary.get("returncode") in {124, 126},
            )
        )

    child_scores = [summary.get("dod_score") for summary in run_summaries]
    child_scores_ok = len(run_summaries) == expected_runs and all(
        isinstance(score, dict) and score.get("score") == score.get("max_score") and score.get("verdict") == "pass"
        for score in child_scores
    )
    checks.append(
        check_result(
            "plugin_variance.child_scores_pass",
            child_scores_ok,
            f"scores={child_scores}",
        )
    )

    pack_shas = [summary.get("pack_fingerprint", {}).get("sha256") for summary in run_summaries if isinstance(summary.get("pack_fingerprint"), dict)]
    checks.append(
        check_result(
            "plugin_variance.pack_fingerprint_stable",
            len(pack_shas) == expected_runs and unique(pack_shas) == [pack_fingerprint["sha256"]],
            f"observed={unique(pack_shas)}, expected={pack_fingerprint['sha256']}",
        )
    )

    package_shas = [summary.get("package_fingerprint_sha256") for summary in run_summaries]
    checks.append(
        check_result(
            "plugin_variance.package_fingerprint_stable",
            len(package_shas) == expected_runs and len(set(package_shas)) == 1 and package_shas[0],
            f"observed={unique(package_shas)}",
        )
    )

    marketplace_shas = [summary.get("marketplace_fingerprint_sha256") for summary in run_summaries]
    checks.append(
        check_result(
            "plugin_variance.marketplace_fingerprint_stable",
            len(marketplace_shas) == expected_runs and len(set(marketplace_shas)) == 1 and marketplace_shas[0],
            f"observed={unique(marketplace_shas)}",
        )
    )

    returncodes = [summary.get("cli_returncodes") for summary in run_summaries]
    checks.append(
        check_result(
            "plugin_variance.cli_returncodes_stable",
            len(returncodes) == expected_runs
            and len({tuple(codes) for codes in returncodes if isinstance(codes, list)}) == 1
            and all(isinstance(codes, list) and codes and all(code == 0 for code in codes) for codes in returncodes),
            f"returncodes={returncodes}",
        )
    )

    cli_signatures = [summary.get("cli_signature_sha256") for summary in run_summaries]
    checks.append(
        check_result(
            "plugin_variance.cli_outputs_stable_after_path_normalization",
            len(cli_signatures) == expected_runs and len(set(cli_signatures)) == 1 and cli_signatures[0],
            f"digests={unique(cli_signatures)}",
        )
    )

    prompt_signatures = [summary.get("prompt_discovery_sha256") for summary in run_summaries]
    prompt_visible = all(
        isinstance(summary.get("prompt_discovery"), dict)
        and summary["prompt_discovery"].get("plugin_visible") is True
        and summary["prompt_discovery"].get("evidence_first_visible") is True
        and "world-class-reviewer:world-class-reviewer" in summary["prompt_discovery"].get("skill_hits", [])
        for summary in run_summaries
    )
    checks.append(
        check_result(
            "plugin_variance.prompt_input_discovery_stable",
            prompt_visible and len(prompt_signatures) == expected_runs and len(set(prompt_signatures)) == 1 and prompt_signatures[0],
            f"digests={unique(prompt_signatures)}, visible={prompt_visible}",
        )
    )

    temp_home_ok = all(summary.get("temporary_codex_home") is True and summary.get("temporary_plugin_home") is True for summary in run_summaries)
    checks.append(
        check_result(
            "plugin_variance.temporary_state_only",
            temp_home_ok,
            "all child runs used .alf-runs plugin homes and temporary CODEX_HOME" if temp_home_ok else "one or more child runs used non-disposable state",
        )
    )

    discovered_skills = [summary.get("discovered_skills") for summary in run_summaries]
    checks.append(
        check_result(
            "plugin_variance.discovered_skills_stable",
            len(discovered_skills) == expected_runs and len({sha256_json(value) for value in discovered_skills}) == 1,
            f"digests={unique([sha256_json(value) for value in discovered_skills])}",
        )
    )

    score = sum(1 for check in checks if check["status"] == "pass")
    max_score = len(checks)
    if any(check["status"] == "blocked" for check in checks):
        verdict = "blocked"
    elif score == max_score:
        verdict = "pass"
    else:
        verdict = "fail"

    risks = [
        "This proves local disposable Codex plugin packaging repeatability only; it does not prove normal profile install, sharing, CI, cloud, mobile, or provider parity.",
        "CLI output comparison is path-normalized because each child run correctly uses a different disposable root.",
        "Prompt-input discovery is a model-context visibility check, not proof that a future model answer will be high quality.",
        "This gate still depends on the locally installed Codex CLI behavior and local auth availability.",
    ]
    if verdict != "pass":
        risks.insert(0, "Plugin packaging variance failed or was blocked; do not add a second-opinion evaluator or promote packaging yet.")

    return {
        "schema_version": "0.1.0",
        "agent_pack": pack.name,
        "task": "codex-plugin-packaging-variance-gate",
        "runtime": "adapters/codex/run_plugin_packaging_variance_gate.py",
        "started_at": started_at,
        "completed_at": utc_now(),
        "policy_decision": {
            "autonomy_tier": "A0-read-only",
            "decision": "allow",
            "reason": "Only repeated disposable plugin packaging gates and local receipt writing are allowed.",
        },
        "pack_fingerprint": pack_fingerprint,
        "thresholds": {
            "runs": expected_runs,
            "package_fingerprint_drift_allowed": 0,
            "marketplace_fingerprint_drift_allowed": 0,
            "cli_output_drift_allowed_after_path_normalization": 0,
            "prompt_input_discovery_drift_allowed": 0,
        },
        "evidence": [
            {
                "type": "child-plugin-packaging-gates",
                "source": "adapters/codex/run_plugin_packaging_gate.py --json",
                "summary": f"{len(run_summaries)} repeated plugin packaging gate run(s)",
            },
            {
                "type": "package-fingerprints",
                "source": "package_result.package_fingerprint.sha256",
                "summary": f"observed={unique(package_shas)}",
            },
            {
                "type": "cli-install-output-drift",
                "source": "codex_cli_smoke.commands stdout_json after path normalization",
                "summary": f"digests={unique(cli_signatures)}",
            },
            {
                "type": "prompt-input-discovery-drift",
                "source": "codex debug prompt-input",
                "summary": f"digests={unique(prompt_signatures)}",
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
            "package_fingerprints": package_shas,
            "marketplace_fingerprints": marketplace_shas,
            "cli_signature_digests": cli_signatures,
            "prompt_discovery_digests": prompt_signatures,
            "child_receipts": [summary.get("written_to") for summary in run_summaries],
        },
        "child_runs": run_summaries,
        "risks": risks,
        "memory_proposals": [],
        "self_improvement_proposals": [],
        "rollback": "Delete this plugin-packaging-variance-gate receipt directory plus the child plugin-packaging-gate receipt directories and .alf-runs child roots listed in child_runs.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run repeated disposable plugin packaging gates and compare drift")
    parser.add_argument("pack", type=Path, help="Path to an agent pack")
    parser.add_argument("--runs", type=int, default=3, help="Number of plugin packaging gates to run; minimum 2")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--no-write", action="store_true", help="Do not write parent or child gate receipts")
    parser.add_argument("--timeout", type=int, default=120, help="Timeout in seconds for each child packaging gate")
    args = parser.parse_args(argv)

    if args.runs < 2:
        raise SystemExit("--runs must be at least 2")

    adapter_root = Path(__file__).resolve().parent
    framework_root = adapter_root.parents[1]
    pack = args.pack.resolve()
    started_at = utc_now()
    safe_time = started_at.replace(":", "").replace("-", "")
    receipt_dir = pack / "receipts" / "runs" / f"{safe_time}.plugin-packaging-variance-gate"

    child_runs: list[dict[str, Any]] = []
    for run_number in range(1, args.runs + 1):
        child_cmd = [
            sys.executable,
            str(adapter_root / "run_plugin_packaging_gate.py"),
            str(pack),
            "--json",
            "--timeout",
            str(args.timeout),
        ]
        if args.no_write:
            child_cmd.append("--no-write")
        child = run_child(
            child_cmd,
            framework_root,
            args.timeout * 4,
        )
        child_runs.append(summarize_child_run(run_number, child))

    receipt = build_receipt(pack, started_at, child_runs, args.runs)
    if not args.no_write:
        receipt_path = receipt_dir / "run-receipt.json"
        receipt["written_to"] = str(receipt_path)
        write_json(receipt_path, receipt)

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

#!/usr/bin/env python3
"""Run the Codex plugin packaging promotion gate in a disposable home."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pack_fingerprint import compute_pack_fingerprint
from package_plugin import DEFAULT_MARKETPLACE_NAME, generate_plugin_package
from validate_plugin_package import discover_marketplace_skills, validate_marketplace_root


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


def parse_json_stdout(stdout: str) -> tuple[Any, str]:
    stripped = stdout.strip()
    if not stripped:
        return None, "stdout was empty"
    try:
        return json.loads(stripped), ""
    except json.JSONDecodeError as exc:
        return None, str(exc)


def run_command(cmd: list[str], cwd: Path, env: dict[str, str], timeout: int) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            env=env,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        stdout_json, parse_error = parse_json_stdout(completed.stdout)
        return {
            "cmd": cmd,
            "returncode": completed.returncode,
            "timed_out": False,
            "stdout_json": stdout_json,
            "stdout_parse_error": parse_error,
            "stdout_excerpt": completed.stdout.strip()[:2000],
            "stderr_excerpt": completed.stderr.strip()[:2000],
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "cmd": cmd,
            "returncode": 124,
            "timed_out": True,
            "stdout_json": None,
            "stdout_parse_error": "timeout",
            "stdout_excerpt": (exc.stdout if isinstance(exc.stdout, str) else "").strip()[:2000],
            "stderr_excerpt": (exc.stderr if isinstance(exc.stderr, str) else "").strip()[:2000],
        }
    except OSError as exc:
        return {
            "cmd": cmd,
            "returncode": 126,
            "timed_out": False,
            "stdout_json": None,
            "stdout_parse_error": str(exc),
            "stdout_excerpt": "",
            "stderr_excerpt": f"{type(exc).__name__}: {exc}",
        }


def resolve_codex_command() -> str:
    for candidate in ("codex.cmd", "codex.exe", "codex"):
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return "codex"


def latest_matching_variance_receipt(pack: Path, fingerprint: dict[str, Any]) -> tuple[dict[str, Any] | None, str]:
    runs = pack / "receipts" / "runs"
    if not runs.is_dir():
        return None, "receipts/runs is missing"
    candidates = sorted(runs.glob("*.variance-gate/run-receipt.json"), reverse=True)
    for candidate in candidates:
        try:
            receipt = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        dod = receipt.get("dod_score", {})
        receipt_fingerprint = receipt.get("pack_fingerprint", {})
        if (
            isinstance(dod, dict)
            and dod.get("verdict") == "pass"
            and isinstance(receipt_fingerprint, dict)
            and receipt_fingerprint.get("sha256") == fingerprint.get("sha256")
        ):
            receipt["path"] = str(candidate)
            return receipt, ""
    return None, "no passing variance receipt was bound to the current pack fingerprint"


def json_contains(value: Any, needles: list[str]) -> bool:
    if isinstance(value, str):
        lowered = value.lower()
        return all(needle.lower() in lowered for needle in needles)
    if isinstance(value, list):
        return any(json_contains(item, needles) for item in value)
    if isinstance(value, dict):
        return any(json_contains(item, needles) for item in value.values())
    return False


def run_codex_cli_smoke(
    marketplace_root: Path,
    state_root: Path,
    marketplace_name: str,
    plugin_name: str,
    skill_name: str,
    timeout: int,
) -> dict[str, Any]:
    codex_home = state_root / "codex-home"
    codex_home.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    codex = resolve_codex_command()
    commands = [
        [codex, "plugin", "marketplace", "add", str(marketplace_root), "--json"],
        [codex, "plugin", "marketplace", "list", "--json"],
        [codex, "plugin", "list", "--marketplace", marketplace_name, "--available", "--json"],
        [codex, "plugin", "add", f"{plugin_name}@{marketplace_name}", "--json"],
        [codex, "plugin", "list", "--marketplace", marketplace_name, "--json"],
        [codex, "debug", "prompt-input", "List active reusable review skills."],
    ]
    results = [run_command(command, marketplace_root, env, timeout) for command in commands]
    marketplace_added = results[0]["returncode"] == 0 and results[0]["stdout_json"] is not None
    marketplace_visible = results[1]["returncode"] == 0 and json_contains(results[1]["stdout_json"], [marketplace_name])
    plugin_available = results[2]["returncode"] == 0 and json_contains(results[2]["stdout_json"], [plugin_name])
    plugin_installed = results[3]["returncode"] == 0 and results[3]["stdout_json"] is not None
    plugin_listed_installed = results[4]["returncode"] == 0 and json_contains(results[4]["stdout_json"], [plugin_name])
    prompt_input_skill_visible = results[5]["returncode"] == 0 and json_contains(
        results[5]["stdout_json"],
        [skill_name, "Evidence-first expert reviewer"],
    )
    checks = [
        check_result("plugin.codex_cli.marketplace_add", marketplace_added, f"returncode={results[0]['returncode']}"),
        check_result("plugin.codex_cli.marketplace_visible", marketplace_visible, f"returncode={results[1]['returncode']}"),
        check_result("plugin.codex_cli.plugin_available", plugin_available, f"returncode={results[2]['returncode']}"),
        check_result("plugin.codex_cli.plugin_install", plugin_installed, f"returncode={results[3]['returncode']}"),
        check_result("plugin.codex_cli.plugin_listed_installed", plugin_listed_installed, f"returncode={results[4]['returncode']}"),
        check_result("plugin.codex_cli.prompt_input_skill_visible", prompt_input_skill_visible, f"returncode={results[5]['returncode']}"),
    ]
    return {
        "codex_home": str(codex_home),
        "commands": results,
        "checks": checks,
    }


def run_negative_fixtures(
    marketplace_root: Path,
    plugin_name: str,
    expected_skill: str,
    scratch_root: Path,
) -> dict[str, Any]:
    scenarios: list[dict[str, Any]] = []
    scratch_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="n-", dir=scratch_root) as temp_dir:
        temp_root = Path(temp_dir)

        def write_marketplace(root: Path, source_path: str = f"./plugins/{plugin_name}") -> None:
            write_json(
                root / ".agents" / "plugins" / "marketplace.json",
                {
                    "name": "negative",
                    "plugins": [
                        {
                            "name": plugin_name,
                            "source": {"source": "local", "path": source_path},
                            "policy": {"installation": "AVAILABLE", "authentication": "ON_INSTALL"},
                            "category": "Productivity",
                        }
                    ],
                },
            )

        def write_minimal_plugin(root: Path, frontmatter_name: str) -> None:
            plugin_root = root / "plugins" / plugin_name
            write_json(
                plugin_root / ".codex-plugin" / "plugin.json",
                {
                    "name": plugin_name,
                    "version": "0.1.0",
                    "description": "Negative fixture plugin",
                    "author": {"name": "Agent Launch Framework"},
                    "skills": "./skills/",
                    "interface": {
                        "displayName": "Negative Fixture",
                        "shortDescription": "Negative fixture",
                        "longDescription": "Negative fixture",
                        "developerName": "Agent Launch Framework",
                        "category": "Productivity",
                        "capabilities": ["Skills"],
                        "defaultPrompt": "Negative fixture.",
                    },
                },
            )
            skill_dir = plugin_root / "skills" / expected_skill
            skill_dir.mkdir(parents=True, exist_ok=True)
            skill_dir.joinpath("SKILL.md").write_text(
                f"""---
name: {frontmatter_name}
description: Negative fixture skill.
---

Fixture body.
""",
                encoding="utf-8",
            )

        missing_manifest = temp_root / "m1"
        write_marketplace(missing_manifest)
        (missing_manifest / "plugins" / plugin_name).mkdir(parents=True, exist_ok=True)
        ok, checks, _payload = validate_marketplace_root(
            missing_manifest,
            expected_plugin=plugin_name,
            expected_skills=[expected_skill],
        )
        scenarios.append(
            {
                "scenario": "missing-plugin-manifest",
                "expected_failure": "plugin.manifest.exists",
                "ok": ok,
                "result": check_result(
                    "plugin.selftest.missing_manifest",
                    (not ok) and any(check["status"] == "fail" and check["name"] == "plugin.manifest.exists" for check in checks),
                    f"validator_ok={ok}",
                ),
            }
        )

        bad_marketplace = temp_root / "m2"
        write_marketplace(bad_marketplace, "../outside")
        ok, checks, _payload = validate_marketplace_root(
            bad_marketplace,
            expected_plugin=plugin_name,
            expected_skills=[expected_skill],
        )
        scenarios.append(
            {
                "scenario": "unsafe-marketplace-path",
                "expected_failure": "source_path_safe",
                "ok": ok,
                "result": check_result(
                    "plugin.selftest.unsafe_marketplace_path",
                    (not ok)
                    and any(
                        check["status"] == "fail"
                        and ("source_path_safe" in check["name"] or "source_shape" in check["name"])
                        for check in checks
                    ),
                    f"validator_ok={ok}",
                ),
            }
        )

        broken_skill = temp_root / "m3"
        write_marketplace(broken_skill)
        write_minimal_plugin(broken_skill, "wrong-skill")
        ok, checks, _payload = validate_marketplace_root(
            broken_skill,
            expected_plugin=plugin_name,
            expected_skills=[expected_skill],
        )
        scenarios.append(
            {
                "scenario": "broken-skill-frontmatter",
                "expected_failure": "plugin.skills.expected",
                "ok": ok,
                "result": check_result(
                    "plugin.selftest.broken_skill_frontmatter",
                    (not ok) and any(check["status"] == "fail" and check["name"] == "plugin.skills.expected" for check in checks),
                    f"validator_ok={ok}",
                ),
            }
        )

    checks = [scenario["result"] for scenario in scenarios]
    return {
        "checks": checks,
        "scenarios": scenarios,
    }


def build_receipt(
    pack: Path,
    started_at: str,
    fingerprint: dict[str, Any],
    variance_receipt: dict[str, Any] | None,
    variance_error: str,
    package_result: dict[str, Any],
    cli_smoke: dict[str, Any] | None,
    negative: dict[str, Any],
    disposable_run_root: Path,
) -> dict[str, Any]:
    checks: list[dict[str, str]] = [
        check_result(
            "plugin.variance_receipt_bound",
            variance_receipt is not None,
            variance_receipt.get("path", "") if isinstance(variance_receipt, dict) else variance_error,
        ),
        check_result(
            "plugin.package_generated",
            package_result.get("ok") is True,
            package_result.get("plugin_root", package_result.get("error", "")),
        ),
        check_result(
            "plugin.marketplace_discovery",
            bool(package_result.get("discovered_skills")),
            f"skills={package_result.get('discovered_skills', [])}",
        ),
        check_result(
            "plugin.package_fingerprint",
            bool(package_result.get("package_fingerprint", {}).get("sha256")),
            package_result.get("package_fingerprint", {}).get("sha256", ""),
        ),
        check_result(
            "plugin.marketplace_fingerprint",
            bool(package_result.get("marketplace_fingerprint", {}).get("sha256")),
            package_result.get("marketplace_fingerprint", {}).get("sha256", ""),
        ),
    ]
    checks.extend(package_result.get("checks", []))
    checks.extend(negative.get("checks", []))
    if cli_smoke is None:
        checks.append(check_result("plugin.codex_cli.smoke", False, "codex CLI smoke was not run", blocked=True))
    else:
        checks.extend(cli_smoke.get("checks", []))

    pass_count = sum(1 for check in checks if check["status"] == "pass")
    max_count = len(checks)
    if any(check["status"] == "blocked" for check in checks):
        verdict = "blocked"
    elif pass_count == max_count:
        verdict = "pass"
    else:
        verdict = "fail"

    risks = [
        "This proves a disposable local Codex plugin package and marketplace only; it does not publish or share the plugin.",
        "Codex app visibility still requires a restart or new thread after real install.",
        "This does not prove CI, cloud, mobile, Claude, or local-LLM adapter parity.",
        "The CLI smoke uses a temporary CODEX_HOME and must not be confused with the user's normal Codex profile.",
    ]
    if verdict != "pass":
        risks.insert(0, "Plugin packaging did not fully pass; do not promote packaging or claim install readiness.")

    return {
        "schema_version": "0.1.0",
        "agent_pack": pack.name,
        "task": "codex-plugin-packaging-gate",
        "runtime": "adapters/codex/run_plugin_packaging_gate.py",
        "started_at": started_at,
        "completed_at": utc_now(),
        "policy_decision": {
            "autonomy_tier": "A0-read-only",
            "decision": "allow",
            "reason": "Only repo-local disposable plugin packaging, local validation, and temporary CODEX_HOME CLI smoke are allowed.",
        },
        "pack_fingerprint": fingerprint,
        "variance_receipt": {
            "path": variance_receipt.get("path") if isinstance(variance_receipt, dict) else None,
            "error": variance_error,
        },
        "package_result": package_result,
        "codex_cli_smoke": cli_smoke,
        "negative_fixtures": negative,
        "disposable_run_root": str(disposable_run_root),
        "evidence": [
            {
                "type": "pack-fingerprint",
                "source": str(pack),
                "summary": fingerprint["sha256"],
            },
            {
                "type": "disposable-marketplace",
                "source": package_result.get("marketplace_path", ""),
                "summary": f"marketplace={package_result.get('marketplace_name')}, plugin={package_result.get('plugin_name')}",
            },
            {
                "type": "skill-discovery",
                "source": "validate_plugin_package.py + optional codex debug prompt-input",
                "summary": f"discovered={package_result.get('discovered_skills', [])}",
            },
        ],
        "checks": checks,
        "dod_score": {
            "score": pass_count,
            "max_score": max_count,
            "verdict": verdict,
        },
        "risks": risks,
        "memory_proposals": [],
        "self_improvement_proposals": [],
        "rollback": "Delete this plugin-packaging-gate receipt directory and the disposable_run_root. No normal user Codex home or global plugin marketplace was mutated.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run disposable Codex plugin packaging proof")
    parser.add_argument("pack", type=Path, help="Path to an agent pack")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--no-write", action="store_true", help="Do not write receipt artifacts")
    parser.add_argument("--timeout", type=int, default=60, help="Timeout seconds for each Codex CLI smoke command")
    parser.add_argument("--skip-codex-cli-smoke", action="store_true", help="Diagnostic only; leaves gate blocked")
    parser.add_argument("--marketplace-name", default=DEFAULT_MARKETPLACE_NAME)
    args = parser.parse_args(argv)

    pack = args.pack.resolve()
    started_at = utc_now()
    safe_time = started_at.replace(":", "").replace("-", "")
    framework_root = Path(__file__).resolve().parents[2]
    disposable_run_root = framework_root / ".alf-runs" / f"{safe_time}.plugin-packaging-gate"
    if args.no_write:
        receipt_dir = disposable_run_root / "receipt"
    else:
        receipt_dir = pack / "receipts" / "runs" / f"{safe_time}.plugin-packaging-gate"
        receipt_dir.mkdir(parents=True, exist_ok=True)
    disposable_run_root.mkdir(parents=True, exist_ok=True)
    marketplace_root = disposable_run_root / "plugin-home"
    fingerprint = compute_pack_fingerprint(pack)
    try:
        variance_receipt, variance_error = latest_matching_variance_receipt(pack, fingerprint)
        package_result = generate_plugin_package(
            pack,
            marketplace_root,
            marketplace_name=args.marketplace_name,
            force=True,
        )
        discovered = package_result.get("discovered_skills", [])
        skill_name = str(discovered[0]["skill"]) if discovered else str(package_result.get("skills", [""])[0])
        negative = run_negative_fixtures(
            marketplace_root,
            str(package_result.get("plugin_name", pack.name)),
            skill_name,
            disposable_run_root / "negative-fixtures",
        )
        cli_smoke = None
        if not args.skip_codex_cli_smoke:
            cli_smoke = run_codex_cli_smoke(
                marketplace_root,
                disposable_run_root,
                str(package_result.get("marketplace_name", args.marketplace_name)),
                str(package_result.get("plugin_name", pack.name)),
                skill_name,
                args.timeout,
            )

        receipt = build_receipt(
            pack,
            started_at,
            fingerprint,
            variance_receipt,
            variance_error,
            package_result,
            cli_smoke,
            negative,
            disposable_run_root,
        )
        if not args.no_write:
            receipt_path = receipt_dir / "run-receipt.json"
            receipt["written_to"] = str(receipt_path)
            write_json(receipt_path, receipt)
        else:
            shutil.rmtree(disposable_run_root, ignore_errors=True)
    except Exception:
        if args.no_write:
            shutil.rmtree(disposable_run_root, ignore_errors=True)
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

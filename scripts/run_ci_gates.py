#!/usr/bin/env python3
"""Run Agent Launch Framework gates in the same order used by CI.

The static tier is dependency-free and should run on every fresh checkout. The
full tier also runs Codex-native behavior and plugin gates, so it requires a
working Codex CLI plus authentication.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


CODEX_REQUIRED_GATES = {
    "behavior_gate",
    "variance_gate",
    "plugin_packaging_variance",
}


def json_summary(stdout: str) -> str:
    stripped = stdout.strip()
    if not stripped:
        return "stdout=<empty>"
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped[-1200:]

    if not isinstance(payload, dict):
        return f"json={type(payload).__name__}"

    parts: list[str] = []
    if "ok" in payload:
        parts.append(f"ok={payload['ok']}")

    receipt = payload.get("receipt")
    if isinstance(receipt, dict):
        dod = receipt.get("dod_score")
        if isinstance(dod, dict):
            parts.append(f"dod={dod.get('score')}/{dod.get('max_score')} {dod.get('verdict')}")
        checks = receipt.get("checks")
        if isinstance(checks, list):
            statuses: dict[str, int] = {}
            for check in checks:
                if isinstance(check, dict):
                    statuses[str(check.get("status", "unknown"))] = statuses.get(str(check.get("status", "unknown")), 0) + 1
            if statuses:
                parts.append(f"checks={statuses}")
    else:
        checks = payload.get("checks")
        if isinstance(checks, list):
            parts.append(f"checks={len(checks)}")

    return " ".join(parts) if parts else stripped[:1200]


def run_command(root: Path, name: str, cmd: list[str], timeout: int) -> bool:
    print(f"::group::{name}")
    print("$ " + " ".join(cmd))
    completed = subprocess.run(
        cmd,
        cwd=root,
        text=True,
        capture_output=True,
        timeout=timeout,
        check=False,
    )
    print(f"returncode={completed.returncode}")
    if completed.stdout:
        print("stdout_summary=" + json_summary(completed.stdout))
    if completed.stderr:
        print("stderr_tail=" + completed.stderr.strip()[-2000:])
    print("::endgroup::")
    return completed.returncode == 0


def check_json_files(root: Path) -> bool:
    print("::group::json.syntax")
    ignored_parts = {".git", ".alf-runs", "__pycache__"}
    ok = True
    count = 0
    for path in sorted(root.rglob("*.json")):
        if ignored_parts.intersection(path.parts):
            continue
        if "receipts" in path.parts and "runs" in path.parts:
            continue
        count += 1
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - gate should report any parse failure.
            ok = False
            print(f"FAIL {path.relative_to(root).as_posix()}: {type(exc).__name__}: {exc}")
    print(f"checked={count}")
    print("::endgroup::")
    return ok


def require_codex_auth(root: Path) -> bool:
    print("::group::codex.environment")
    codex = shutil.which("codex") or shutil.which("codex.cmd") or shutil.which("codex.exe")
    print(f"codex={codex or '<missing>'}")
    if codex:
        if os.name == "nt":
            version = subprocess.run(f'"{codex}" --version', cwd=root, shell=True, text=True, capture_output=True, check=False)
        else:
            version = subprocess.run([codex, "--version"], cwd=root, text=True, capture_output=True, check=False)
        if version.stdout.strip():
            print(f"codex_version={version.stdout.strip()}")
        if version.stderr.strip():
            print(f"codex_version_stderr={version.stderr.strip()}")

    codex_home = Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex")
    has_auth_json = (codex_home / "auth.json").is_file()
    has_openai_key = bool(os.environ.get("OPENAI_API_KEY"))
    print(f"codex_home={codex_home}")
    print(f"auth_json_present={has_auth_json}")
    print(f"openai_api_key_present={has_openai_key}")
    print("::endgroup::")
    return bool(codex) and (has_auth_json or has_openai_key)


def build_commands(root: Path, pack: Path, timeout: int, plugin_timeout: int, tier: str) -> list[tuple[str, list[str], int]]:
    python_files = [str(path.relative_to(root)) for path in sorted((root / "adapters" / "codex").glob("*.py"))]
    base: list[tuple[str, list[str], int]] = [
        ("python.compile", [sys.executable, "-m", "py_compile", *python_files], 120),
        (
            "agent_pack.validate",
            [sys.executable, "adapters/codex/validate_agent_pack.py", str(pack), "--json"],
            120,
        ),
        (
            "static_eval",
            [sys.executable, "adapters/codex/run_pack_eval.py", str(pack), "--json", "--no-write"],
            120,
        ),
        (
            "harness_selftest",
            [sys.executable, "adapters/codex/run_harness_selftest.py", str(pack), "--json", "--no-write"],
            120,
        ),
    ]
    if tier == "static":
        return base

    full: list[tuple[str, list[str], int]] = [
        (
            "behavior_gate",
            [sys.executable, "adapters/codex/run_behavior_gate.py", str(pack), "--json", "--no-write", "--timeout", str(timeout)],
            timeout * 5,
        ),
        (
            "variance_gate",
            [sys.executable, "adapters/codex/run_variance_gate.py", str(pack), "--json", "--no-write", "--timeout", str(timeout)],
            timeout * 16,
        ),
        (
            "plugin_packaging_variance",
            [
                sys.executable,
                "adapters/codex/run_plugin_packaging_variance_gate.py",
                str(pack),
                "--json",
                "--no-write",
                "--timeout",
                str(plugin_timeout),
            ],
            plugin_timeout * 16,
        ),
    ]
    return base + full


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run ALF CI gates")
    parser.add_argument("--tier", choices=["static", "full"], default="static")
    parser.add_argument("--pack", type=Path, default=Path("agent-packs/world-class-reviewer"))
    parser.add_argument("--timeout", type=int, default=600, help="Per Codex behavior case timeout seconds")
    parser.add_argument("--plugin-timeout", type=int, default=120, help="Per Codex plugin CLI command timeout seconds")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    pack = args.pack if args.pack.is_absolute() else root / args.pack

    if not pack.exists():
        print(f"Pack not found: {pack}", file=sys.stderr)
        return 2

    ok = check_json_files(root)
    if args.tier == "full" and not require_codex_auth(root):
        print("Full tier requires codex on PATH and either OPENAI_API_KEY or CODEX_HOME/auth.json.", file=sys.stderr)
        return 2

    for name, cmd, timeout in build_commands(root, pack, args.timeout, args.plugin_timeout, args.tier):
        ok = run_command(root, name, cmd, timeout) and ok

    print(f"RESULT: {'PASS' if ok else 'FAIL'} tier={args.tier}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

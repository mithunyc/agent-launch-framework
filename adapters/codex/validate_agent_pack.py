#!/usr/bin/env python3
"""Validate an Agent Launch Framework pack for Codex use.

This validator intentionally uses only the Python standard library so a pack can
be checked on a clean workstation before any dependencies are installed.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


REQUIRED_TOP_LEVEL = {
    "id",
    "name",
    "version",
    "mission",
    "risk_default",
    "runtimes",
    "skills",
    "policies",
    "evals",
    "receipts",
    "memory",
    "self_improvement",
}

REQUIRED_POLICIES = {
    "policies/read-only.md",
    "policies/write-safe.md",
    "policies/secret-safe.md",
}

FORBIDDEN_CLAIMS = [
    "official openai",
    "guaranteed correctness",
    "zero risk",
    "fully autonomous without oversight",
    "ignore safety",
    "bypass approval",
]


def is_generated_receipt_artifact(pack: Path, path: Path) -> bool:
    try:
        path.relative_to(pack / "receipts" / "runs")
        return True
    except ValueError:
        return False


def read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def read_text(path: Path) -> str:
    data = read_bytes(path)
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} starts with a UTF-8 BOM")
    return data.decode("utf-8")


def parse_simple_manifest(path: Path) -> dict[str, Any]:
    """Parse the strict YAML subset used by agent.yaml.

    Supported shapes:
    key: scalar
    key:
      - item
    key:
      child: scalar
    """

    result: dict[str, Any] = {}
    lines = read_text(path).splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        if raw.startswith(" ") or ":" not in raw:
            i += 1
            continue

        key, value = raw.split(":", 1)
        key = key.strip()
        value = value.strip()
        if value:
            result[key] = value
            i += 1
            continue

        block: list[str] | dict[str, str] = []
        mapping: dict[str, str] = {}
        i += 1
        while i < len(lines) and (lines[i].startswith(" ") or not lines[i].strip()):
            child = lines[i].strip()
            if not child or child.startswith("#"):
                i += 1
                continue
            if child.startswith("- "):
                if mapping:
                    raise ValueError(f"{path}: mixed list and map under {key}")
                block.append(child[2:].strip())
            elif ":" in child:
                if block:
                    raise ValueError(f"{path}: mixed list and map under {key}")
                child_key, child_value = child.split(":", 1)
                mapping[child_key.strip()] = child_value.strip()
            i += 1
        result[key] = mapping if mapping else block
    return result


def parse_skill_frontmatter(path: Path) -> dict[str, str]:
    text = read_text(path)
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        raise ValueError(f"{path} frontmatter must start at byte 0 with ---")
    parts = re.split(r"\r?\n---\r?\n", text, maxsplit=1)
    if len(parts) != 2:
        raise ValueError(f"{path} frontmatter closing marker missing")
    frontmatter = parts[0].splitlines()[1:]
    data: dict[str, str] = {}
    for line in frontmatter:
        if ":" in line:
            key, value = line.split(":", 1)
            data[key.strip()] = value.strip().strip('"')
    return data


def add(checks: list[dict[str, str]], name: str, status: str, detail: str) -> None:
    checks.append({"name": name, "status": status, "detail": detail})


def validate_semantic_rubric(case: dict[str, Any]) -> tuple[bool, str]:
    rubric = case.get("semantic_rubric")
    if not isinstance(rubric, dict):
        return False, "semantic_rubric object missing"
    criteria = rubric.get("criteria")
    if not isinstance(criteria, list) or not criteria:
        return False, "semantic_rubric.criteria must be a non-empty list"
    min_score = rubric.get("min_score")
    if not isinstance(min_score, int) or min_score <= 0:
        return False, "semantic_rubric.min_score must be a positive integer"

    total_weight = 0
    for index, criterion in enumerate(criteria):
        if not isinstance(criterion, dict):
            return False, f"criterion {index} must be an object"
        if not isinstance(criterion.get("id"), str) or not criterion["id"]:
            return False, f"criterion {index} id missing"
        if not isinstance(criterion.get("description"), str) or not criterion["description"]:
            return False, f"criterion {criterion.get('id', index)} description missing"
        weight = criterion.get("weight", 1)
        if not isinstance(weight, int) or weight <= 0:
            return False, f"criterion {criterion['id']} weight must be a positive integer"
        total_weight += weight
        if "fields" in criterion and not isinstance(criterion["fields"], list):
            return False, f"criterion {criterion['id']} fields must be a list"
        for key in ["expected_verdicts", "must_include_any", "must_include_all", "must_not_include_any"]:
            if key in criterion and not isinstance(criterion[key], list):
                return False, f"criterion {criterion['id']} {key} must be a list"
        for key in ["min_items", "max_items"]:
            if key in criterion and not isinstance(criterion[key], dict):
                return False, f"criterion {criterion['id']} {key} must be an object"
        if not any(
            key in criterion
            for key in [
                "expected_verdicts",
                "must_include_any",
                "must_include_all",
                "must_not_include_any",
                "min_items",
                "max_items",
            ]
        ):
            return False, f"criterion {criterion['id']} has no assertion"

    if min_score > total_weight:
        return False, f"semantic_rubric.min_score {min_score} exceeds total weight {total_weight}"
    return True, f"{len(criteria)} criteria, threshold {min_score}/{total_weight}"


def validate_pack(pack: Path) -> tuple[bool, list[dict[str, str]]]:
    checks: list[dict[str, str]] = []
    pack = pack.resolve()

    if not pack.exists() or not pack.is_dir():
        add(checks, "pack.exists", "fail", f"Pack directory not found: {pack}")
        return False, checks

    manifest_path = pack / "agent.yaml"
    if not manifest_path.exists():
        add(checks, "manifest.exists", "fail", "agent.yaml is missing")
        return False, checks

    try:
        manifest = parse_simple_manifest(manifest_path)
        missing = sorted(REQUIRED_TOP_LEVEL - set(manifest))
        if missing:
            add(checks, "manifest.required_fields", "fail", f"Missing fields: {', '.join(missing)}")
        else:
            add(checks, "manifest.required_fields", "pass", "All required fields present")
    except Exception as exc:  # noqa: BLE001
        add(checks, "manifest.parse", "fail", str(exc))
        return False, checks

    pack_id = str(manifest.get("id", ""))
    if re.fullmatch(r"[a-z0-9][a-z0-9-]{2,80}", pack_id):
        add(checks, "manifest.id", "pass", pack_id)
    else:
        add(checks, "manifest.id", "fail", f"Invalid id: {pack_id}")

    risk_default = manifest.get("risk_default")
    if risk_default in {"read-only", "advisory", "write-safe", "deploy-safe"}:
        add(checks, "manifest.risk_default", "pass", str(risk_default))
    else:
        add(checks, "manifest.risk_default", "fail", f"Invalid risk_default: {risk_default}")

    skills = manifest.get("skills", [])
    if not isinstance(skills, list) or not skills:
        add(checks, "skills.list", "fail", "skills must be a non-empty list")
        skills = []
    else:
        add(checks, "skills.list", "pass", f"{len(skills)} skill(s)")

    for skill_name in skills:
        skill_dir = pack / "skills" / skill_name
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            add(checks, f"skill.{skill_name}.exists", "fail", f"Missing {skill_file}")
            continue
        try:
            frontmatter = parse_skill_frontmatter(skill_file)
            actual_name = frontmatter.get("name")
            if actual_name != skill_name:
                add(
                    checks,
                    f"skill.{skill_name}.frontmatter_name",
                    "fail",
                    f"name is {actual_name!r}, expected {skill_name!r}",
                )
            else:
                add(checks, f"skill.{skill_name}.frontmatter_name", "pass", actual_name)
            if frontmatter.get("description"):
                add(checks, f"skill.{skill_name}.description", "pass", "description present")
            else:
                add(checks, f"skill.{skill_name}.description", "fail", "description missing")
        except Exception as exc:  # noqa: BLE001
            add(checks, f"skill.{skill_name}.frontmatter", "fail", str(exc))

    for policy in sorted(REQUIRED_POLICIES):
        if (pack / policy).exists():
            add(checks, f"policy.{policy}", "pass", "present")
        else:
            add(checks, f"policy.{policy}", "fail", "missing")

    dod_path = pack / "dod.md"
    if dod_path.exists():
        dod_text = read_text(dod_path)
        criteria_count = len(re.findall(r"^\d+\.", dod_text, flags=re.MULTILINE))
        if criteria_count >= 3:
            add(checks, "dod.criteria", "pass", f"{criteria_count} criteria")
        else:
            add(checks, "dod.criteria", "fail", "Need at least 3 numbered criteria")
    else:
        add(checks, "dod.exists", "fail", "dod.md missing")

    cases_dir = pack / "evals" / "cases"
    case_files = sorted(cases_dir.glob("*.json")) if cases_dir.exists() else []
    if not case_files:
        add(checks, "evals.cases", "fail", "No eval case JSON files found")
    else:
        add(checks, "evals.cases", "pass", f"{len(case_files)} case(s)")
    for case_file in case_files:
        try:
            case = json.loads(read_text(case_file))
            required = {"id", "prompt", "risk_tags", "expected_behaviors", "failure_modes"}
            missing = sorted(required - set(case))
            if missing:
                add(checks, f"eval.{case_file.name}", "fail", f"Missing: {', '.join(missing)}")
            elif not case["expected_behaviors"] or not case["failure_modes"]:
                add(checks, f"eval.{case_file.name}", "fail", "Expected behaviors and failure modes must be non-empty")
            else:
                add(checks, f"eval.{case_file.name}", "pass", case["id"])
            automated = case.get("automated_checks")
            if automated is not None:
                if not isinstance(automated, dict):
                    add(checks, f"eval.{case_file.name}.automated_checks", "fail", "automated_checks must be an object")
                elif not any(key in automated for key in {"require_text_any", "require_text_all", "forbid_text_any"}):
                    add(
                        checks,
                        f"eval.{case_file.name}.automated_checks",
                        "fail",
                        "automated_checks needs at least one text check",
                    )
                else:
                    bad_lists = [
                        key
                        for key in ["require_text_any", "require_text_all", "forbid_text_any"]
                        if key in automated and not isinstance(automated[key], list)
                    ]
                    if bad_lists:
                        add(
                            checks,
                            f"eval.{case_file.name}.automated_checks",
                            "fail",
                            f"Text check fields must be lists: {', '.join(bad_lists)}",
                        )
                    else:
                        add(checks, f"eval.{case_file.name}.automated_checks", "pass", "mechanical checks present")
            rubric_ok, rubric_detail = validate_semantic_rubric(case)
            add(
                checks,
                f"eval.{case_file.name}.semantic_rubric",
                "pass" if rubric_ok else "fail",
                rubric_detail,
            )
        except Exception as exc:  # noqa: BLE001
            add(checks, f"eval.{case_file.name}", "fail", str(exc))

    receipt_path = pack / "receipts" / "template.run-receipt.json"
    if receipt_path.exists():
        try:
            receipt = json.loads(read_text(receipt_path))
            required_receipt = {
                "schema_version",
                "agent_pack",
                "task",
                "runtime",
                "evidence",
                "checks",
                "dod_score",
                "risks",
                "memory_proposals",
                "self_improvement_proposals",
                "rollback",
            }
            missing = sorted(required_receipt - set(receipt))
            if missing:
                add(checks, "receipt.template", "fail", f"Missing: {', '.join(missing)}")
            else:
                add(checks, "receipt.template", "pass", "required fields present")
        except Exception as exc:  # noqa: BLE001
            add(checks, "receipt.template", "fail", str(exc))
    else:
        add(checks, "receipt.template", "fail", "template.run-receipt.json missing")

    memory_path = pack / "memory" / "README.md"
    if memory_path.exists():
        memory_text = read_text(memory_path).lower()
        required_words = ["source", "confidence", "expiry", "reason"]
        missing_words = [word for word in required_words if word not in memory_text]
        if missing_words:
            add(checks, "memory.policy", "fail", f"Missing concepts: {', '.join(missing_words)}")
        else:
            add(checks, "memory.policy", "pass", "source/confidence/expiry/reason present")
    else:
        add(checks, "memory.policy", "fail", "memory/README.md missing")

    improve_path = pack / "self-improvement" / "README.md"
    if improve_path.exists():
        improve_text = read_text(improve_path).lower()
        required_words = ["proposal", "eval", "approval"]
        missing_words = [word for word in required_words if word not in improve_text]
        if missing_words:
            add(checks, "self_improvement.policy", "fail", f"Missing concepts: {', '.join(missing_words)}")
        else:
            add(checks, "self_improvement.policy", "pass", "proposal/eval/approval present")
    else:
        add(checks, "self_improvement.policy", "fail", "self-improvement/README.md missing")

    for text_file in pack.rglob("*"):
        if not text_file.is_file() or text_file.suffix.lower() not in {".md", ".yaml", ".yml", ".json", ".txt"}:
            continue
        if is_generated_receipt_artifact(pack, text_file):
            continue
        try:
            content = read_text(text_file).lower()
        except UnicodeDecodeError:
            continue
        for claim in FORBIDDEN_CLAIMS:
            if claim in content:
                add(checks, "unsafe_claims", "fail", f"{claim!r} found in {text_file.relative_to(pack)}")

    ok = all(check["status"] == "pass" for check in checks)
    return ok, checks


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate an Agent Launch Framework pack")
    parser.add_argument("pack", type=Path, help="Path to an agent pack")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    ok, checks = validate_pack(args.pack)
    if args.json:
        print(json.dumps({"ok": ok, "checks": checks}, indent=2))
    else:
        for check in checks:
            print(f"[{check['status'].upper()}] {check['name']}: {check['detail']}")
        print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

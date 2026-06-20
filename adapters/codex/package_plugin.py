#!/usr/bin/env python3
"""Generate a Codex plugin package from an Agent Launch Framework pack."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pack_fingerprint import compute_pack_fingerprint, compute_tree_fingerprint
from validate_agent_pack import parse_simple_manifest, read_text, validate_pack
from validate_plugin_package import discover_marketplace_skills, validate_marketplace_root


DEFAULT_MARKETPLACE_NAME = "alf-disposable"
DEFAULT_CATEGORY = "Productivity"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def safe_description(text: str, limit: int = 180) -> str:
    squashed = re.sub(r"\s+", " ", text).strip()
    if len(squashed) <= limit:
        return squashed
    return squashed[: limit - 1].rstrip() + "."


def display_name(value: str) -> str:
    return " ".join(part.capitalize() for part in re.split(r"[-_]+", value) if part)


def copytree_clean(source: Path, target: Path) -> None:
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".pytest_cache"),
    )


def append_packaged_reference_footer(skill_file: Path, pack_id: str) -> None:
    text = read_text(skill_file)
    footer = f"""

## Packaged Agent Pack References

This skill is packaged from Agent Launch Framework pack `{pack_id}`. When the
task touches risk, policy, definition of done, memory, self-improvement, or
runtime portability, read `references/agent-pack/README.md` and the relevant
files in that folder before making a recommendation.
"""
    if "## Packaged Agent Pack References" not in text:
        skill_file.write_text(text.rstrip() + footer + "\n", encoding="utf-8")


def copy_pack_references(pack: Path, skill_dir: Path, pack_id: str, fingerprint: dict[str, Any]) -> None:
    references = skill_dir / "references" / "agent-pack"
    references.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for relative in [
        "dod.md",
        "memory/README.md",
        "self-improvement/README.md",
        "policies/read-only.md",
        "policies/write-safe.md",
        "policies/secret-safe.md",
    ]:
        source = pack / relative
        if not source.is_file():
            continue
        target = references / relative.replace("/", "__")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(read_text(source), encoding="utf-8")
        copied.append(relative)

    readme = {
        "pack_id": pack_id,
        "purpose": "Runtime references copied from the canonical agent pack for Codex plugin use.",
        "source_fingerprint": {
            "algorithm": fingerprint["algorithm"],
            "sha256": fingerprint["sha256"],
            "file_count": fingerprint["file_count"],
        },
        "copied_files": copied,
        "instruction": (
            "Use these files as supporting references only. The canonical pack "
            "under agent-packs remains the source of truth."
        ),
        "hidden_eval_boundary": (
            "Eval cases and hidden semantic rubrics are intentionally not copied "
            "into runtime skill references. They remain harness-side grading inputs."
        ),
    }
    write_json(references / "README.md", readme)


def build_plugin_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    pack_id = str(manifest["id"])
    name = str(manifest["name"])
    mission = str(manifest["mission"])
    default_prompts = [
        f"Use {pack_id} to stress-test this decision.",
        "Review this plan with evidence and blockers.",
        "Audit repo truth before recommending action.",
    ]
    return {
        "name": pack_id,
        "version": str(manifest["version"]),
        "description": safe_description(mission),
        "author": {
            "name": "Agent Launch Framework",
        },
        "license": "UNLICENSED",
        "keywords": [
            "agent-pack",
            "codex",
            "review",
            "evidence",
            "adversarial",
        ],
        "skills": "./skills/",
        "interface": {
            "displayName": name,
            "shortDescription": safe_description(mission, 96),
            "longDescription": (
                f"{name} is an evidence-first, read-only-by-default Codex skill "
                "packaged from an Agent Launch Framework agent pack."
            ),
            "developerName": "Agent Launch Framework",
            "category": DEFAULT_CATEGORY,
            "capabilities": ["Skills", "Review", "Research"],
            "defaultPrompt": default_prompts,
        },
    }


def build_marketplace(marketplace_name: str, plugin_name: str) -> dict[str, Any]:
    return {
        "name": marketplace_name,
        "interface": {
            "displayName": display_name(marketplace_name),
        },
        "plugins": [
            {
                "name": plugin_name,
                "source": {
                    "source": "local",
                    "path": f"./plugins/{plugin_name}",
                },
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": DEFAULT_CATEGORY,
            }
        ],
    }


def ensure_clean_output(output_root: Path, plugin_name: str, force: bool) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    plugin_root = output_root / "plugins" / plugin_name
    marketplace = output_root / ".agents" / "plugins" / "marketplace.json"
    targets = [plugin_root, marketplace]
    existing = [target for target in targets if target.exists()]
    if existing and not force:
        raise FileExistsError(
            "Output root already contains generated plugin artifacts; use --force or choose a new output root: "
            + ", ".join(str(target) for target in existing)
        )
    for target in existing:
        resolved = target.resolve()
        try:
            resolved.relative_to(output_root.resolve())
        except ValueError as exc:
            raise RuntimeError(f"Refusing to remove path outside output root: {resolved}") from exc
        if target.is_dir():
            shutil.rmtree(target)
        else:
            target.unlink()


def generate_plugin_package(
    pack: Path,
    output_root: Path,
    *,
    marketplace_name: str = DEFAULT_MARKETPLACE_NAME,
    force: bool = False,
) -> dict[str, Any]:
    pack = pack.resolve()
    output_root = output_root.resolve()
    pack_ok, pack_checks = validate_pack(pack)
    if not pack_ok:
        return {
            "ok": False,
            "pack": str(pack),
            "output_root": str(output_root),
            "checks": pack_checks,
            "error": "pack validation failed",
        }

    manifest = parse_simple_manifest(pack / "agent.yaml")
    plugin_name = str(manifest["id"])
    skills = [str(skill) for skill in manifest.get("skills", [])]
    ensure_clean_output(output_root, plugin_name, force)

    fingerprint = compute_pack_fingerprint(pack)
    plugin_root = output_root / "plugins" / plugin_name
    (plugin_root / ".codex-plugin").mkdir(parents=True, exist_ok=True)
    write_json(plugin_root / ".codex-plugin" / "plugin.json", build_plugin_manifest(manifest))

    skills_root = plugin_root / "skills"
    for skill in skills:
        source = pack / "skills" / skill
        target = skills_root / skill
        copytree_clean(source, target)
        copy_pack_references(pack, target, plugin_name, fingerprint)
        append_packaged_reference_footer(target / "SKILL.md", plugin_name)

    write_json(
        plugin_root / "agent-pack-source.json",
        {
            "schema_version": "0.1.0",
            "generated_by": "adapters/codex/package_plugin.py",
            "source_pack_id": plugin_name,
            "source_pack_name": manifest["name"],
            "source_pack_version": manifest["version"],
            "source_pack_path": str(pack),
            "source_fingerprint": fingerprint,
            "included_skills": skills,
            "non_claims": [
                "This package is not an official OpenAI product.",
                "This package is not proof of cloud, mobile, or provider-adapter parity.",
                "This package does not grant write, deploy, secret, billing, or production authority.",
            ],
        },
    )

    marketplace = build_marketplace(marketplace_name, plugin_name)
    write_json(output_root / ".agents" / "plugins" / "marketplace.json", marketplace)

    validation_ok, validation_checks, _marketplace = validate_marketplace_root(
        output_root,
        expected_plugin=plugin_name,
        expected_skills=skills,
    )
    discovered = discover_marketplace_skills(output_root) if validation_ok else []
    package_fingerprint = compute_tree_fingerprint(plugin_root)
    marketplace_fingerprint = compute_tree_fingerprint(output_root)
    return {
        "ok": validation_ok,
        "pack": str(pack),
        "plugin_root": str(plugin_root),
        "marketplace_root": str(output_root),
        "marketplace_path": str(output_root / ".agents" / "plugins" / "marketplace.json"),
        "marketplace_name": marketplace_name,
        "plugin_name": plugin_name,
        "skills": skills,
        "source_fingerprint": fingerprint,
        "package_fingerprint": package_fingerprint,
        "marketplace_fingerprint": marketplace_fingerprint,
        "checks": validation_checks,
        "discovered_skills": discovered,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a Codex plugin package from an agent pack")
    parser.add_argument("pack", type=Path, help="Path to the agent pack")
    parser.add_argument("--output-root", type=Path, required=True, help="Disposable marketplace root to write")
    parser.add_argument("--marketplace-name", default=DEFAULT_MARKETPLACE_NAME)
    parser.add_argument("--force", action="store_true", help="Replace generated artifacts under output root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    result = generate_plugin_package(
        args.pack,
        args.output_root,
        marketplace_name=args.marketplace_name,
        force=args.force,
    )
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for check in result.get("checks", []):
            status = check.get("status", "unknown").upper()
            name = check.get("name", "?")
            detail = check.get("detail", check.get("evidence", ""))
            print(f"[{status}] {name}: {detail}")
        if result.get("plugin_root"):
            print(f"PLUGIN: {result['plugin_root']}")
        if result.get("marketplace_path"):
            print(f"MARKETPLACE: {result['marketplace_path']}")
        print(f"RESULT: {'PASS' if result.get('ok') else 'FAIL'}")
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())

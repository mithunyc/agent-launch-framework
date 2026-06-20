#!/usr/bin/env python3
"""Validate a generated Codex plugin package and local marketplace fixture.

This validator intentionally uses only the Python standard library so plugin
packaging can be tested in clean CI or disposable Codex homes before optional
plugin-creator dependencies are available.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import urlparse


SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)\."
    r"(0|[1-9]\d*)"
    r"(?:-(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*)(?:\."
    r"(?:0|[1-9]\d*|\d*[A-Za-z-][0-9A-Za-z-]*))*)?"
    r"(?:\+[0-9A-Za-z-]+(?:\.[0-9A-Za-z-]+)*)?$"
)
HEX_COLOR_RE = re.compile(r"^#[0-9A-F]{6}$", re.IGNORECASE)
PLUGIN_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{2,63}$")
TODO_MARKER = "[TODO:"
ALLOWED_INSTALL_POLICIES = {"NOT_AVAILABLE", "AVAILABLE", "INSTALLED_BY_DEFAULT"}
ALLOWED_AUTH_POLICIES = {"ON_INSTALL", "ON_USE"}


def read_text(path: Path) -> str:
    data = path.read_bytes()
    if data.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"{path} starts with a UTF-8 BOM")
    return data.decode("utf-8")


def read_json_object(path: Path) -> dict[str, Any]:
    payload = json.loads(read_text(path))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def add(checks: list[dict[str, str]], name: str, status: str, detail: str) -> None:
    checks.append({"name": name, "status": status, "detail": detail})


def reject_todo_markers(value: Any, path: str, checks: list[dict[str, str]]) -> None:
    if isinstance(value, str):
        if TODO_MARKER in value:
            add(checks, f"plugin.todo.{path}", "fail", "TODO placeholder remains")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            reject_todo_markers(item, f"{path}[{index}]", checks)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            reject_todo_markers(item, f"{path}.{key}", checks)


def normalize_contract_path(raw_path: Any) -> str | None:
    if not isinstance(raw_path, str):
        return None
    path = Path(raw_path)
    if path.is_absolute():
        return None
    normalized = PurePosixPath(raw_path.replace("\\", "/")).as_posix().rstrip("/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized or None


def parse_skill_frontmatter(path: Path) -> dict[str, str]:
    text = read_text(path)
    if not text.startswith("---\n") and not text.startswith("---\r\n"):
        raise ValueError("frontmatter must start at byte 0 with ---")
    parts = re.split(r"\r?\n---\r?\n", text, maxsplit=1)
    if len(parts) != 2:
        raise ValueError("frontmatter closing marker missing")
    frontmatter: dict[str, str] = {}
    for line in parts[0].splitlines()[1:]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip('"')
    return frontmatter


def require_string(payload: dict[str, Any], key: str, checks: list[dict[str, str]], prefix: str) -> str | None:
    value = payload.get(key)
    field = f"{prefix}.{key}" if prefix else key
    if not isinstance(value, str) or not value.strip():
        add(checks, f"plugin.{field}", "fail", "missing or empty string")
        return None
    add(checks, f"plugin.{field}", "pass", value.strip()[:160])
    return value


def validate_optional_https(payload: dict[str, Any], key: str, checks: list[dict[str, str]], prefix: str) -> None:
    value = payload.get(key)
    if value is None:
        return
    parsed = urlparse(value) if isinstance(value, str) else None
    ok = parsed is not None and parsed.scheme == "https" and bool(parsed.netloc)
    add(checks, f"plugin.{prefix}.{key}", "pass" if ok else "fail", str(value))


def validate_default_prompt(value: Any, checks: list[dict[str, str]]) -> None:
    if isinstance(value, str):
        ok = bool(value.strip()) and len(value) <= 128
        add(checks, "plugin.interface.defaultPrompt", "pass" if ok else "fail", "single prompt")
        return
    if isinstance(value, list):
        ok = 1 <= len(value) <= 3 and all(isinstance(item, str) and item.strip() and len(item) <= 128 for item in value)
        add(checks, "plugin.interface.defaultPrompt", "pass" if ok else "fail", f"{len(value)} prompt(s)")
        return
    add(checks, "plugin.interface.defaultPrompt", "fail", "must be a non-empty string or 1-3 strings")


def validate_asset_path(base_dir: Path, allowed_root: Path, raw_path: Any, label: str, checks: list[dict[str, str]]) -> None:
    if raw_path is None:
        return
    if not isinstance(raw_path, str) or not raw_path.strip():
        add(checks, label, "fail", "asset path must be a non-empty relative path")
        return
    candidate = PurePosixPath(raw_path.replace("\\", "/"))
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        add(checks, label, "fail", "asset path must stay inside plugin archive")
        return
    resolved = (base_dir / candidate.as_posix()).resolve()
    try:
        resolved.relative_to(allowed_root.resolve())
        inside = True
    except ValueError:
        inside = False
    ok = inside and resolved.is_file()
    add(checks, label, "pass" if ok else "fail", str(resolved))


def validate_plugin_root(
    plugin_root: Path,
    *,
    expected_name: str | None = None,
    expected_skills: list[str] | None = None,
) -> tuple[bool, list[dict[str, str]], dict[str, Any]]:
    checks: list[dict[str, str]] = []
    plugin_root = plugin_root.resolve()
    manifest_path = plugin_root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        add(checks, "plugin.manifest.exists", "fail", f"Missing {manifest_path}")
        return False, checks, {}

    try:
        manifest = read_json_object(manifest_path)
        add(checks, "plugin.manifest.json", "pass", "valid JSON object")
    except Exception as exc:  # noqa: BLE001
        add(checks, "plugin.manifest.json", "fail", str(exc))
        return False, checks, {}

    reject_todo_markers(manifest, "$", checks)
    allowed_keys = {
        "id",
        "name",
        "version",
        "description",
        "skills",
        "apps",
        "mcpServers",
        "interface",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
    }
    unknown = sorted(set(manifest) - allowed_keys)
    add(checks, "plugin.manifest.allowed_fields", "pass" if not unknown else "fail", f"unknown={unknown}")

    name = require_string(manifest, "name", checks, "")
    if name is not None:
        add(checks, "plugin.name.format", "pass" if PLUGIN_NAME_RE.fullmatch(name) else "fail", name)
    if expected_name is not None:
        add(checks, "plugin.name.expected", "pass" if name == expected_name else "fail", f"actual={name}, expected={expected_name}")
        add(checks, "plugin.folder_matches_name", "pass" if plugin_root.name == expected_name else "fail", plugin_root.name)

    version = require_string(manifest, "version", checks, "")
    if version is not None:
        add(checks, "plugin.version.semver", "pass" if SEMVER_RE.fullmatch(version) else "fail", version)
    require_string(manifest, "description", checks, "")

    author = manifest.get("author")
    if not isinstance(author, dict):
        add(checks, "plugin.author", "fail", "author must be an object")
    else:
        require_string(author, "name", checks, "author")
        validate_optional_https(author, "url", checks, "author")

    skills_path = normalize_contract_path(manifest.get("skills"))
    add(checks, "plugin.skills.path", "pass" if skills_path == "skills" else "fail", str(manifest.get("skills")))
    for key, expected_file in {"apps": ".app.json", "mcpServers": ".mcp.json"}.items():
        value = manifest.get(key)
        if value is None:
            continue
        normalized = normalize_contract_path(value)
        exists = (plugin_root / expected_file).is_file()
        add(checks, f"plugin.{key}.path", "pass" if normalized == expected_file and exists else "fail", str(value))

    interface = manifest.get("interface")
    if not isinstance(interface, dict):
        add(checks, "plugin.interface", "fail", "interface must be an object")
    else:
        allowed_interface = {
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "capabilities",
            "websiteURL",
            "privacyPolicyURL",
            "termsOfServiceURL",
            "brandColor",
            "composerIcon",
            "logo",
            "screenshots",
            "defaultPrompt",
            "default_prompt",
        }
        unknown_interface = sorted(set(interface) - allowed_interface)
        add(
            checks,
            "plugin.interface.allowed_fields",
            "pass" if not unknown_interface else "fail",
            f"unknown={unknown_interface}",
        )
        for field in ("displayName", "shortDescription", "longDescription", "developerName", "category"):
            require_string(interface, field, checks, "interface")
        capabilities = interface.get("capabilities")
        capabilities_ok = isinstance(capabilities, list) and all(isinstance(item, str) and item.strip() for item in capabilities)
        add(checks, "plugin.interface.capabilities", "pass" if capabilities_ok else "fail", str(capabilities))
        validate_default_prompt(interface.get("defaultPrompt", interface.get("default_prompt")), checks)
        brand_color = interface.get("brandColor")
        if brand_color is not None:
            add(checks, "plugin.interface.brandColor", "pass" if isinstance(brand_color, str) and HEX_COLOR_RE.fullmatch(brand_color) else "fail", str(brand_color))
        for field in ("websiteURL", "privacyPolicyURL", "termsOfServiceURL"):
            validate_optional_https(interface, field, checks, "interface")
        validate_asset_path(plugin_root, plugin_root, interface.get("composerIcon"), "plugin.interface.composerIcon", checks)
        validate_asset_path(plugin_root, plugin_root, interface.get("logo"), "plugin.interface.logo", checks)
        screenshots = interface.get("screenshots", [])
        if not isinstance(screenshots, list):
            add(checks, "plugin.interface.screenshots", "fail", "screenshots must be a list")
        else:
            for index, screenshot in enumerate(screenshots):
                validate_asset_path(plugin_root, plugin_root, screenshot, f"plugin.interface.screenshots[{index}]", checks)

    skills_root = plugin_root / "skills"
    if not skills_root.is_dir():
        add(checks, "plugin.skills.exists", "fail", f"Missing {skills_root}")
    else:
        skill_names: list[str] = []
        for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir() and not path.name.startswith(".")):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                add(checks, f"plugin.skill.{skill_dir.name}.exists", "fail", "SKILL.md missing")
                continue
            try:
                frontmatter = parse_skill_frontmatter(skill_file)
                skill_name = frontmatter.get("name")
                skill_names.append(str(skill_name))
                add(checks, f"plugin.skill.{skill_dir.name}.frontmatter", "pass", "frontmatter parsed")
                add(checks, f"plugin.skill.{skill_dir.name}.name", "pass" if skill_name == skill_dir.name else "fail", str(skill_name))
                add(checks, f"plugin.skill.{skill_dir.name}.description", "pass" if frontmatter.get("description") else "fail", "description present")
                disabled = frontmatter.get("disable-model-invocation") or frontmatter.get("disable_model_invocation")
                add(checks, f"plugin.skill.{skill_dir.name}.invocation_enabled", "pass" if disabled in {None, "", "false", "False"} else "fail", str(disabled))
            except Exception as exc:  # noqa: BLE001
                add(checks, f"plugin.skill.{skill_dir.name}.frontmatter", "fail", str(exc))
        if expected_skills is not None:
            missing = sorted(set(expected_skills) - set(skill_names))
            add(checks, "plugin.skills.expected", "pass" if not missing else "fail", f"missing={missing}, found={skill_names}")

    ok = all(check["status"] == "pass" for check in checks)
    return ok, checks, manifest


def marketplace_path(root: Path) -> Path:
    return root / ".agents" / "plugins" / "marketplace.json"


def validate_marketplace_root(
    root: Path,
    *,
    expected_plugin: str | None = None,
    expected_skills: list[str] | None = None,
) -> tuple[bool, list[dict[str, str]], dict[str, Any]]:
    checks: list[dict[str, str]] = []
    root = root.resolve()
    path = marketplace_path(root)
    if not path.is_file():
        add(checks, "marketplace.exists", "fail", f"Missing {path}")
        return False, checks, {}
    try:
        marketplace = read_json_object(path)
        add(checks, "marketplace.json", "pass", "valid JSON object")
    except Exception as exc:  # noqa: BLE001
        add(checks, "marketplace.json", "fail", str(exc))
        return False, checks, {}

    name = marketplace.get("name")
    add(checks, "marketplace.name", "pass" if isinstance(name, str) and name.strip() else "fail", str(name))
    interface = marketplace.get("interface")
    add(checks, "marketplace.interface", "pass" if interface is None or isinstance(interface, dict) else "fail", str(interface))
    plugins = marketplace.get("plugins")
    if not isinstance(plugins, list):
        add(checks, "marketplace.plugins", "fail", "plugins must be a list")
        return False, checks, marketplace
    add(checks, "marketplace.plugins", "pass", f"{len(plugins)} plugin(s)")

    found_expected = expected_plugin is None
    for index, entry in enumerate(plugins):
        if not isinstance(entry, dict):
            add(checks, f"marketplace.plugin[{index}]", "fail", "entry must be an object")
            continue
        plugin_name = entry.get("name")
        add(checks, f"marketplace.plugin.{index}.name", "pass" if isinstance(plugin_name, str) and PLUGIN_NAME_RE.fullmatch(plugin_name) else "fail", str(plugin_name))
        if plugin_name == expected_plugin:
            found_expected = True
        source = entry.get("source")
        if not isinstance(source, dict):
            add(checks, f"marketplace.plugin.{plugin_name}.source", "fail", "source must be an object")
            continue
        source_kind = source.get("source")
        source_path = source.get("path")
        source_ok = source_kind == "local" and isinstance(source_path, str) and source_path.startswith("./")
        add(checks, f"marketplace.plugin.{plugin_name}.source_shape", "pass" if source_ok else "fail", str(source))
        if source_ok:
            candidate = PurePosixPath(source_path.replace("\\", "/"))
            if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
                add(checks, f"marketplace.plugin.{plugin_name}.source_path_safe", "fail", source_path)
                continue
            plugin_root = (root / candidate.as_posix()).resolve()
            try:
                plugin_root.relative_to(root)
                inside = True
            except ValueError:
                inside = False
            add(checks, f"marketplace.plugin.{plugin_name}.source_path_safe", "pass" if inside else "fail", str(plugin_root))
            plugin_ok, plugin_checks, _manifest = validate_plugin_root(
                plugin_root,
                expected_name=str(plugin_name) if isinstance(plugin_name, str) else None,
                expected_skills=expected_skills if plugin_name == expected_plugin else None,
            )
            add(checks, f"marketplace.plugin.{plugin_name}.plugin_valid", "pass" if plugin_ok else "fail", f"{sum(1 for check in plugin_checks if check['status'] == 'pass')}/{len(plugin_checks)}")
            checks.extend(plugin_checks)
        policy = entry.get("policy")
        policy_ok = isinstance(policy, dict)
        add(checks, f"marketplace.plugin.{plugin_name}.policy", "pass" if policy_ok else "fail", str(policy))
        if policy_ok:
            add(checks, f"marketplace.plugin.{plugin_name}.policy.installation", "pass" if policy.get("installation") in ALLOWED_INSTALL_POLICIES else "fail", str(policy.get("installation")))
            add(checks, f"marketplace.plugin.{plugin_name}.policy.authentication", "pass" if policy.get("authentication") in ALLOWED_AUTH_POLICIES else "fail", str(policy.get("authentication")))
        category = entry.get("category")
        add(checks, f"marketplace.plugin.{plugin_name}.category", "pass" if isinstance(category, str) and category.strip() else "fail", str(category))

    if expected_plugin is not None:
        add(checks, "marketplace.expected_plugin", "pass" if found_expected else "fail", str(expected_plugin))
    ok = all(check["status"] == "pass" for check in checks)
    return ok, checks, marketplace


def discover_marketplace_skills(root: Path) -> list[dict[str, str]]:
    root = root.resolve()
    marketplace = read_json_object(marketplace_path(root))
    discovered: list[dict[str, str]] = []
    for entry in marketplace.get("plugins", []):
        if not isinstance(entry, dict):
            continue
        plugin_name = entry.get("name")
        source = entry.get("source", {})
        if not isinstance(plugin_name, str) or not isinstance(source, dict):
            continue
        source_path = source.get("path")
        if not isinstance(source_path, str):
            continue
        plugin_root = root / PurePosixPath(source_path.replace("\\", "/")).as_posix()
        skills_root = plugin_root / "skills"
        if not skills_root.is_dir():
            continue
        for skill_dir in sorted(path for path in skills_root.iterdir() if path.is_dir() and not path.name.startswith(".")):
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.is_file():
                continue
            frontmatter = parse_skill_frontmatter(skill_file)
            discovered.append(
                {
                    "marketplace": str(marketplace.get("name", "")),
                    "plugin": plugin_name,
                    "skill": str(frontmatter.get("name", skill_dir.name)),
                    "description": str(frontmatter.get("description", "")),
                    "path": str(skill_file.resolve()),
                }
            )
    return discovered


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a generated Codex plugin or marketplace root")
    parser.add_argument("path", type=Path, help="Plugin root or disposable marketplace root")
    parser.add_argument("--expected-plugin", help="Expected plugin name")
    parser.add_argument("--expected-skill", action="append", default=[], help="Expected skill name; repeatable")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    target = args.path.resolve()
    if (target / ".codex-plugin" / "plugin.json").is_file():
        ok, checks, manifest = validate_plugin_root(
            target,
            expected_name=args.expected_plugin,
            expected_skills=args.expected_skill or None,
        )
        payload = {"kind": "plugin", "ok": ok, "checks": checks, "manifest": manifest}
    else:
        ok, checks, marketplace = validate_marketplace_root(
            target,
            expected_plugin=args.expected_plugin,
            expected_skills=args.expected_skill or None,
        )
        discovered = []
        if ok:
            discovered = discover_marketplace_skills(target)
        payload = {
            "kind": "marketplace-root",
            "ok": ok,
            "checks": checks,
            "marketplace": marketplace,
            "discovered_skills": discovered,
        }

    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        for check in checks:
            print(f"[{check['status'].upper()}] {check['name']}: {check['detail']}")
        if payload.get("discovered_skills"):
            for skill in payload["discovered_skills"]:
                print(f"[DISCOVERED] {skill['skill']} from {skill['plugin']}: {skill['path']}")
        print(f"RESULT: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

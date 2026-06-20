#!/usr/bin/env python3
"""Compute stable fingerprints for canonical agent-pack and generated trees."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any


EXCLUDED_DIR_PARTS = {"__pycache__", ".pytest_cache"}
EXCLUDED_FILE_SUFFIXES = {".pyc"}


def is_generated_pack_artifact(pack: Path, path: Path) -> bool:
    try:
        path.relative_to(pack / "receipts" / "runs")
        return True
    except ValueError:
        return False


def iter_pack_files(pack: Path) -> list[Path]:
    pack = pack.resolve()
    files: list[Path] = []
    for candidate in pack.rglob("*"):
        if not candidate.is_file():
            continue
        if any(part in EXCLUDED_DIR_PARTS for part in candidate.parts):
            continue
        if candidate.suffix.lower() in EXCLUDED_FILE_SUFFIXES:
            continue
        if is_generated_pack_artifact(pack, candidate):
            continue
        files.append(candidate)
    return sorted(files, key=lambda path: path.relative_to(pack).as_posix())


def compute_path_content_fingerprint(
    root: Path,
    files: list[Path],
    *,
    algorithm: str = "sha256:path-and-content:v1",
    excluded: list[str] | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    digest = hashlib.sha256()
    file_count = 0
    byte_count = 0
    relative_files: list[str] = []
    for path in sorted(files, key=lambda item: item.relative_to(root).as_posix()):
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(data)
        digest.update(b"\0")
        file_count += 1
        byte_count += len(data)
        relative_files.append(relative)
    return {
        "algorithm": algorithm,
        "sha256": digest.hexdigest(),
        "file_count": file_count,
        "byte_count": byte_count,
        "excluded": excluded or ["__pycache__", "*.pyc", ".pytest_cache"],
        "files": relative_files,
    }


def iter_tree_files(root: Path) -> list[Path]:
    root = root.resolve()
    files: list[Path] = []
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        if any(part in EXCLUDED_DIR_PARTS for part in candidate.parts):
            continue
        if candidate.suffix.lower() in EXCLUDED_FILE_SUFFIXES:
            continue
        files.append(candidate)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def compute_tree_fingerprint(root: Path) -> dict[str, Any]:
    return compute_path_content_fingerprint(root, iter_tree_files(root))


def compute_pack_fingerprint(pack: Path) -> dict[str, Any]:
    pack = pack.resolve()
    return compute_path_content_fingerprint(
        pack,
        iter_pack_files(pack),
        excluded=["receipts/runs", "__pycache__", "*.pyc", ".pytest_cache"],
    )

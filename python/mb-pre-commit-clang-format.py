#!/usr/bin/env python3
"""
Run the newest clang-format cached by pre-commit.

This is handy when you want to reuse the same clang-format binary that
`pre-commit` already downloaded via `mirrors-clang-format`, without having to
remember where pre-commit hid it under its cache directory.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_MIRROR_URL = "https://github.com/pre-commit/mirrors-clang-format"
_VERSION_RE = re.compile(r"^v?([0-9]+(?:\.[0-9]+)*)$")


@dataclass(frozen=True)
class _Candidate:
    version: str
    version_key: tuple[int, ...]
    executable: Path
    repo_dir: Path


def _cache_roots() -> list[Path]:
    roots: list[Path] = []

    def _add(path: Path | None) -> None:
        if path is None:
            return
        resolved = path.expanduser()
        if resolved not in roots:
            roots.append(resolved)

    pre_commit_home = os.environ.get("PRE_COMMIT_HOME")
    if pre_commit_home:
        _add(Path(pre_commit_home))

    xdg_cache_home = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache_home:
        _add(Path(xdg_cache_home) / "pre-commit")

    home = Path.home()
    _add(home / ".cache" / "pre-commit")

    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        _add(Path(local_app_data) / "pre-commit")
    elif os.name == "nt":
        _add(home / "AppData" / "Local" / "pre-commit")

    return roots


def _iter_repo_dirs(cache_root: Path) -> list[Path]:
    if not cache_root.is_dir():
        return []
    return sorted(
        child for child in cache_root.iterdir() if child.is_dir() and child.name.startswith("repo")
    )


def _read_text_if_file(path: Path) -> str:
    if not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _is_clang_format_mirror(repo_dir: Path) -> bool:
    git_config = _read_text_if_file(repo_dir / ".git" / "config")
    if _MIRROR_URL in git_config:
        return True

    hooks_yaml = _read_text_if_file(repo_dir / ".pre-commit-hooks.yaml")
    if "id: clang-format" in hooks_yaml and "entry: clang-format" in hooks_yaml:
        return True

    readme = _read_text_if_file(repo_dir / "README.md")
    return "clang-format mirror" in readme.lower()


def _parse_version(text: str) -> tuple[int, ...] | None:
    match = _VERSION_RE.match(text.strip())
    if not match:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _read_repo_version(repo_dir: Path) -> tuple[str, tuple[int, ...]] | None:
    raw = _read_text_if_file(repo_dir / ".version").strip()
    if raw:
        key = _parse_version(raw)
        if key is not None:
            return raw, key
    return None


def _iter_executables(repo_dir: Path) -> list[Path]:
    executables: list[Path] = []
    for child in sorted(repo_dir.iterdir()):
        if not child.is_dir() or not child.name.startswith("py_env-"):
            continue
        for rel in ("bin/clang-format", "Scripts/clang-format.exe", "Scripts/clang-format"):
            candidate = child / rel
            if candidate.is_file():
                executables.append(candidate)
    return executables


def _discover_candidates() -> list[_Candidate]:
    candidates: list[_Candidate] = []
    for cache_root in _cache_roots():
        for repo_dir in _iter_repo_dirs(cache_root):
            if not _is_clang_format_mirror(repo_dir):
                continue
            version_info = _read_repo_version(repo_dir)
            if version_info is None:
                continue
            version, version_key = version_info
            for executable in _iter_executables(repo_dir):
                candidates.append(
                    _Candidate(
                        version=version,
                        version_key=version_key,
                        executable=executable,
                        repo_dir=repo_dir,
                    )
                )
    return candidates


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    candidates = _discover_candidates()
    if not candidates:
        print(
            "Could not find a cached clang-format from pre-commit.\n"
            "Run the clang-format hook once so pre-commit installs it, for example:\n"
            "  pre-commit run clang-format --all-files",
            file=sys.stderr,
        )
        return 1

    best = max(candidates, key=lambda c: (c.version_key, str(c.executable)))
    completed = subprocess.run([str(best.executable), *args], check=False)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
mb-pre-commit setup (CMake-agnostic).

Implements the same workflow as mb_pre_commit_setup() in mb-pre-commit.cmake:
venv + pinned pre-commit, custom or native hook install, optional example configs.

Lives next to the repo’s `cmake/` tree: default `--tool-root` is `<repo>/cmake`
(containing `pre-commit.in`). Intended for one-shot use after clone (no CMake),
and for CMake via execute_process().
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import stat
import subprocess
import sys
from pathlib import Path
from typing import NoReturn

_DEFAULT_PRE_COMMIT_VERSION = "4.5.1"
_SEMVER_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_MAJOR_PREFIX_RE = re.compile(r"^([0-9]+)")


def _default_tool_root() -> Path:
    """Sibling `cmake/` next to this file (`python/mb-pre-commit-setup.py`)."""
    return (Path(__file__).resolve().parent.parent / "cmake").resolve()


def _status(msg: str) -> None:
    print(msg, flush=True)


def _safe_rmtree(path: Path) -> None:
    """Remove a directory tree (e.g. failed/partial ``venv``). Handles mode bits and symlinks."""
    if not path.exists():
        return
    p = str(path.resolve())

    def _onexc(func, apath: str, exc: BaseException) -> None:
        if not isinstance(exc, (PermissionError, OSError)):
            raise exc
        try:
            os.chmod(apath, stat.S_IRWXU | stat.S_IRWXG | stat.S_IRWXO)
            func(apath)
        except OSError as e2:
            raise exc from e2

    def _onerror(
        func: object, apath: str, exc_info: tuple[type, BaseException, object]
    ) -> None:
        _onexc(func, apath, exc_info[1])  # type: ignore[arg-type]

    try:
        if sys.version_info >= (3, 12):
            shutil.rmtree(p, onexc=_onexc)
        else:
            shutil.rmtree(p, onerror=_onerror)
    except OSError:
        pass
    if os.path.exists(p):
        if os.name != "nt":
            subprocess.run(
                ["/bin/chmod", "-R", "u+w", p], check=False, capture_output=True
            )
            subprocess.run(["/bin/rm", "-rf", p], check=False)
        else:
            subprocess.run(
                ["cmd", "/c", "rmdir", "/s", "/q", p],
                check=False,
                shell=False,
            )


def _fatal(msg: str) -> NoReturn:
    print(msg, file=sys.stderr, flush=True)
    raise SystemExit(1)


def _venv_python_path(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts" / "python.exe"
    return venv_dir / "bin" / "python3"


def _venv_bin_dir(venv_dir: Path) -> Path:
    if os.name == "nt":
        return venv_dir / "Scripts"
    return venv_dir / "bin"


def _venv_site_packages(venv_dir: Path) -> Path:
    """Purelib site-packages inside an existing venv (POSIX vs Windows layout)."""
    if os.name == "nt":
        p = venv_dir / "Lib" / "site-packages"
        if p.is_dir():
            return p
    else:
        libs = list((venv_dir / "lib").glob("python*/site-packages"))
        if libs:
            return libs[0]
    _fatal(f"mb_pre_commit_setup: could not find site-packages under {venv_dir}")


def _venv_has_pip(venv_python: Path) -> bool:
    r = subprocess.run(
        [str(venv_python), "-m", "pip", "--version"],
        capture_output=True,
        check=False,
    )
    return r.returncode == 0


def _scrub_invalid_distribution_dirs(site: Path) -> None:
    """Remove pip temp / corrupted dirs (e.g. ``~ip``) that break upgrades and uninstall."""
    if not site.is_dir():
        return
    for child in list(site.iterdir()):
        if child.is_dir() and child.name.startswith("~"):
            shutil.rmtree(child, ignore_errors=True)


def _try_ensurepip_in_venv(venv_python: Path) -> bool:
    """Often works inside an existing ``--without-pip`` venv when venv-time ensurepip failed."""
    r = subprocess.run(
        [str(venv_python), "-m", "ensurepip", "--upgrade"],
        capture_output=True,
        check=False,
    )
    return r.returncode == 0 and _venv_has_pip(venv_python)


def _repair_pip_after_target_bootstrap(venv_python: Path, venv_dir: Path) -> None:
    """``pip install --target`` leaves metadata that breaks later ``pip install -U pip``; normalize."""
    site = _venv_site_packages(venv_dir)
    _scrub_invalid_distribution_dirs(site)
    r = subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--ignore-installed",
            "--upgrade",
            "--no-warn-script-location",
            "pip",
        ],
        check=False,
    )
    if r.returncode != 0:
        _fatal(
            "Could not normalize pip in the venv after --target bootstrap "
            "(try deleting .venv and re-running configure)."
        )


def _bootstrap_pip_into_venv(
    python_for_venv: Path, venv_dir: Path, venv_python: Path
) -> None:
    """When `venv` was created with --without-pip (e.g. broken ensurepip on some Pythons)."""
    site = _venv_site_packages(venv_dir)
    _status(
        "Bootstrapping pip into the venv with the build interpreter "
        f"(ensurepip unavailable in this environment): {site}"
    )
    r = subprocess.run(
        [
            str(python_for_venv),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--no-warn-script-location",
            "pip",
            "--target",
            str(site),
        ],
        check=False,
    )
    if r.returncode != 0:
        _fatal(
            "Failed to bootstrap pip into the venv. "
            f"Check that {python_for_venv} has pip (`python -m pip --version`)."
        )
    _repair_pip_after_target_bootstrap(venv_python, venv_dir)


def _which_git() -> str | None:
    return shutil.which("git")


def _git_hooks_dir(project_source: Path, git_exe: str) -> Path | None:
    """Resolve the effective hooks directory, including Git worktrees."""
    r = subprocess.run(
        [git_exe, "rev-parse", "--git-path", "hooks"],
        cwd=str(project_source),
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode != 0:
        return None
    raw = (r.stdout or "").strip()
    if raw == "":
        return None
    hooks = Path(raw)
    if not hooks.is_absolute():
        hooks = (project_source / hooks).resolve()
    return hooks


def _git_ok(project_source: Path) -> bool:
    git = _which_git()
    if not git:
        return False
    hooks_dir = _git_hooks_dir(project_source, git)
    return hooks_dir is not None and hooks_dir.is_dir()


def _resolve_path(p: str | Path, base: Path) -> Path:
    path = Path(p)
    if path.is_absolute():
        return path.resolve()
    return (base / path).resolve()


def _copy_if_different(src: Path, dst: Path) -> bool:
    """Copy src to dst if content differs. Returns True if a write occurred."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists() and src.read_bytes() == dst.read_bytes():
        return False
    shutil.copyfile(src, dst)
    return True


def _write_text_if_different(dst: Path, text: str, *, newline: str) -> bool:
    """Write text only when content differs. Returns True if a write occurred."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        try:
            if dst.read_text(encoding="utf-8") == text:
                return False
        except OSError:
            pass
    dst.write_text(text, encoding="utf-8", newline=newline)
    return True


def _chmod_exec_unix(path: Path) -> None:
    if os.name == "nt":
        return
    mode = path.stat().st_mode
    path.chmod(mode | 0o111)


def _configure_hook_template(
    template: Path,
    project_source_dir: Path,
    venv_python: Path,
    out: Path,
) -> None:
    text = template.read_text(encoding="utf-8")
    if "@PRE_COMMIT_VENV_PYTHON_FOR_HOOK@" not in text:
        _fatal(
            "mb_pre_commit_setup: hook template missing placeholder "
            "@PRE_COMMIT_VENV_PYTHON_FOR_HOOK@"
        )
    if "@PRE_COMMIT_VENV_PYTHON_REL@" not in text:
        _fatal(
            "mb_pre_commit_setup: hook template missing placeholder "
            "@PRE_COMMIT_VENV_PYTHON_REL@"
        )
    # Do not use Path.resolve() here: on macOS/Homebrew, .venv/bin/python3 is a symlink
    # into the Cellar; resolving replaces it with the real path and `python -m pre_commit`
    # then runs *outside* the venv (no pre_commit), matching the user's failure mode.
    abs_py = venv_python.absolute()
    abs_src = project_source_dir.absolute()
    venv_python_for_hook = abs_py.as_posix()
    try:
        rel = abs_py.relative_to(abs_src).as_posix()
    except ValueError:
        rel = ""
    text = text.replace("@PRE_COMMIT_VENV_PYTHON_REL@", rel)
    text = text.replace("@PRE_COMMIT_VENV_PYTHON_FOR_HOOK@", venv_python_for_hook)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8", newline="\n")


def _ensure_venv(python_for_venv: Path, venv_dir: Path, venv_python: Path) -> None:
    if venv_python.is_file():
        return
    _status(f"Creating Python virtual environment for pre-commit: {venv_dir}")

    # Prefer --without-pip first: some interpreters (e.g. Homebrew Python 3.14) fail during
    # venv's built-in ensurepip; that can leave a partial .venv that is hard to remove and
    # breaks a second attempt. A no-pip venv + ensurepip/bootstrap avoids that path.
    attempts: list[list[str]] = [
        [str(python_for_venv), "-m", "venv", "--without-pip", str(venv_dir)],
        [str(python_for_venv), "-m", "venv", str(venv_dir)],
    ]
    for i, cmd in enumerate(attempts):
        if venv_dir.exists():
            _safe_rmtree(venv_dir)
        if subprocess.run(cmd, check=False).returncode == 0:
            break
        if i == len(attempts) - 1:
            _fatal(
                f"Failed to create Python virtual environment: {venv_dir} "
                "(tried --without-pip and full venv / ensurepip)"
            )

    if not _venv_has_pip(venv_python):
        if not _try_ensurepip_in_venv(venv_python):
            _bootstrap_pip_into_venv(python_for_venv, venv_dir, venv_python)
        if not _venv_has_pip(venv_python):
            _fatal(
                f"pip is still unavailable in the venv after bootstrap: {venv_python}"
            )


def _installed_pre_commit_version(venv_python: Path) -> str | None:
    r = subprocess.run(
        [str(venv_python), "-m", "pre_commit", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    out = (r.stdout or "") + (r.stderr or "")
    m = _SEMVER_RE.search(out)
    return m.group(0) if m else None


def _pip_install_pre_commit(venv_python: Path, venv_dir: Path, version: str) -> None:
    _scrub_invalid_distribution_dirs(_venv_site_packages(venv_dir))
    _status(f"Installing pre-commit {version} into {venv_dir}")
    r = subprocess.run(
        [
            str(venv_python),
            "-m",
            "pip",
            "install",
            "--upgrade",
            "--ignore-installed",
            "pip",
            f"pre-commit=={version}",
        ],
        check=False,
    )
    if r.returncode != 0:
        _fatal(f"Failed to install pre-commit {version}")


def _ensure_pre_commit(venv_python: Path, venv_dir: Path, want_version: str) -> None:
    need_install = True
    installed = _installed_pre_commit_version(venv_python)
    if installed == want_version:
        need_install = False
    if need_install:
        _pip_install_pre_commit(venv_python, venv_dir, want_version)
    else:
        _status(f"pre-commit {want_version} already available in {venv_dir}")


def _git_config_core_hooks_path(project_source: Path, git_exe: str) -> str:
    r = subprocess.run(
        [git_exe, "config", "core.hooksPath"],
        cwd=str(project_source),
        capture_output=True,
        text=True,
        check=False,
    )
    return (r.stdout or "").strip()


def _install_custom_hook(
    project_source: Path,
    generated_hook: Path,
    git_exe: str,
) -> None:
    hooks_path = _git_config_core_hooks_path(project_source, git_exe)
    if hooks_path != "":
        _fatal(
            "Cowardly refusing to install hooks with `core.hooksPath` set.\n"
            "(As it wouldn't make sense to install something that won't be used.)\n"
            "Hint: `git config --unset-all core.hooksPath`"
        )
    hooks_dir = _git_hooks_dir(project_source, git_exe)
    if hooks_dir is None:
        _fatal(f"Could not resolve Git hooks directory in {project_source}")
    hook_target = hooks_dir / "pre-commit"
    _copy_if_different(generated_hook, hook_target)
    _chmod_exec_unix(hook_target)
    _status(f"Installed custom pre-commit hook: {hook_target}")


def _install_native_hook(project_source: Path, venv_python: Path) -> None:
    r = subprocess.run(
        [
            str(venv_python),
            "-m",
            "pre_commit",
            "install",
            "--install-hooks",
            "--hook-type",
            "pre-commit",
        ],
        cwd=str(project_source),
        check=False,
    )
    if r.returncode != 0:
        _fatal("pre-commit install failed")
    _status(f"Installed native pre-commit hook in {project_source}")


def _sh_single_quote(value: str) -> str:
    return "'" + value.replace("'", "'\"'\"'") + "'"


def _cmd_quote(value: str) -> str:
    return value.replace("%", "%%")


def _clang_format_wrapper_path(tool_root: Path) -> Path:
    return (tool_root.parent / "python" / "mb-pre-commit-clang-format.py").resolve()


def _clang_format_launcher_path(venv_dir: Path) -> Path:
    bindir = _venv_bin_dir(venv_dir)
    if os.name == "nt":
        return bindir / "mb-pre-commit-clang-format.cmd"
    return bindir / "mb-pre-commit-clang-format"


def _install_clang_format_launcher(
    tool_root: Path, venv_dir: Path, venv_python: Path
) -> Path:
    wrapper = _clang_format_wrapper_path(tool_root)
    if not wrapper.is_file():
        _fatal(f"mb_pre_commit_setup: clang-format wrapper not found: {wrapper}")

    launcher = _clang_format_launcher_path(venv_dir)
    if os.name == "nt":
        text = (
            "@echo off\r\n"
            f'"{_cmd_quote(str(venv_python))}" '
            f'"{_cmd_quote(str(wrapper))}" %*\r\n'
        )
        wrote = _write_text_if_different(launcher, text, newline="\r\n")
    else:
        text = (
            "#!/usr/bin/env sh\n"
            f"exec {_sh_single_quote(str(venv_python))} "
            f'{_sh_single_quote(str(wrapper))} "$@"\n'
        )
        wrote = _write_text_if_different(launcher, text, newline="\n")
        _chmod_exec_unix(launcher)

    if wrote:
        _status(f"Installed clang-format launcher: {launcher}")
    else:
        _status(f"clang-format launcher already available: {launcher}")
    return launcher


def _parse_major(version: str) -> int:
    m = _MAJOR_PREFIX_RE.match(version.strip())
    if not m:
        _fatal(
            f"mb_pre_commit_setup: could not parse major from "
            f"PRE_COMMIT_VERSION={version!r}"
        )
    return int(m.group(1))


def _best_example_config(configs_root: Path, pc_major: int) -> tuple[int, Path] | None:
    best_n = 0
    best_src: Path | None = None
    if not configs_root.is_dir():
        return None
    for child in sorted(configs_root.iterdir()):
        if not child.is_dir():
            continue
        m = re.fullmatch(r"v([0-9]+)", child.name)
        if not m:
            continue
        vn = int(m.group(1))
        if vn < 1 or vn > pc_major or vn <= best_n:
            continue
        candidate = child / ".pre-commit-config.yaml"
        if candidate.is_file():
            best_n = vn
            best_src = candidate
    if best_src is None:
        return None
    return best_n, best_src


def _install_example_configs(
    configs_root: Path,
    project_source: Path,
    pre_commit_version: str,
) -> None:
    pc_major = _parse_major(pre_commit_version)
    picked = _best_example_config(configs_root, pc_major)
    if not picked:
        return
    best_n, best_src = picked
    dest = project_source / ".pre-commit-config.yaml"
    shutil.copyfile(best_src, dest)
    _status(f"Installed example pre-commit config (configs/v{best_n}) -> {dest}")
    md_src = best_src.parent / ".markdownlint.yaml"
    if md_src.is_file():
        md_dest = project_source / ".markdownlint.yaml"
        shutil.copyfile(md_src, md_dest)
        _status(
            f"Installed example markdownlint config (configs/v{best_n}) -> {md_dest}"
        )


def run(
    *,
    project_source_dir: Path,
    project_binary_dir: Path,
    mode: str,
    pre_commit_version: str,
    venv_dir: Path,
    install_example_config: bool,
    tool_root: Path,
    python_for_venv: Path,
) -> int:
    mode_u = mode.upper()
    if mode_u not in ("CUSTOM", "NATIVE"):
        _fatal(
            f"mb_pre_commit_setup: invalid PRE_COMMIT_MODE={mode!r}, "
            "expected CUSTOM or NATIVE"
        )

    project_source_dir = project_source_dir.resolve()
    project_binary_dir = project_binary_dir.resolve()
    venv_dir = venv_dir.resolve()

    hook_template = tool_root / "pre-commit.in"
    configs_root = tool_root.parent / "configs"
    generated_hook = project_binary_dir / "pre-commit"

    if not _git_ok(project_source_dir):
        _status(
            f"Git checkout not detected in {project_source_dir}; "
            "skipping pre-commit setup"
        )
        return 0

    if not hook_template.is_file():
        _fatal(f"mb_pre_commit_setup: hook template not found: {hook_template}")

    venv_python = _venv_python_path(venv_dir)

    _configure_hook_template(
        hook_template,
        project_source_dir,
        venv_python,
        generated_hook,
    )
    _ensure_venv(python_for_venv, venv_dir, venv_python)
    _ensure_pre_commit(venv_python, venv_dir, pre_commit_version)
    _install_clang_format_launcher(tool_root, venv_dir, venv_python)

    git_exe = _which_git()
    assert git_exe  # guarded by _git_ok

    if mode_u == "CUSTOM":
        _install_custom_hook(project_source_dir, generated_hook, git_exe)
    else:
        _install_native_hook(project_source_dir, venv_python)

    if install_example_config:
        _install_example_configs(configs_root, project_source_dir, pre_commit_version)

    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Install mb-pre-commit venv, hooks, and optional example configs."
    )
    p.add_argument(
        "--project-source-dir",
        default=".",
        help="Project root (git work tree). Default: current directory.",
    )
    p.add_argument(
        "--project-binary-dir",
        default=None,
        help=(
            "Directory for generated hook file (pre-commit). "
            "Default: <project-source-dir>/.mb-pre-commit-gen"
        ),
    )
    p.add_argument(
        "--mode",
        default="CUSTOM",
        help="CUSTOM or NATIVE (default: CUSTOM).",
    )
    p.add_argument(
        "--version",
        dest="pre_commit_version",
        default=_DEFAULT_PRE_COMMIT_VERSION,
        help=f"pre-commit package version (default: {_DEFAULT_PRE_COMMIT_VERSION}).",
    )
    p.add_argument(
        "--venv-dir",
        default=None,
        help="Virtualenv path. Default: <project-source-dir>/.venv",
    )
    p.add_argument(
        "--tool-root",
        default=None,
        help=(
            "Directory containing pre-commit.in (default: ../cmake relative to this script)."
        ),
    )
    p.add_argument(
        "--python",
        dest="python_for_venv",
        default=None,
        help="Python interpreter used to create the venv (default: sys.executable).",
    )
    p.set_defaults(install_example_config=True)
    p.add_argument(
        "--install-example-config",
        dest="install_example_config",
        action="store_true",
        help="Install example .pre-commit-config.yaml / .markdownlint.yaml (default: on).",
    )
    p.add_argument(
        "--no-install-example-config",
        dest="install_example_config",
        action="store_false",
        help="Do not install example configs.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    tool_root = (
        Path(args.tool_root).resolve() if args.tool_root else _default_tool_root()
    )
    python_for_venv = (
        Path(args.python_for_venv).resolve()
        if args.python_for_venv
        else Path(sys.executable).resolve()
    )

    cwd = Path.cwd().resolve()
    project_source = _resolve_path(args.project_source_dir, cwd)
    if args.project_binary_dir is None:
        project_binary = (project_source / ".mb-pre-commit-gen").resolve()
    else:
        project_binary = _resolve_path(args.project_binary_dir, cwd)

    venv_dir = (
        _resolve_path(args.venv_dir, project_source)
        if args.venv_dir
        else (project_source / ".venv").resolve()
    )

    return run(
        project_source_dir=project_source,
        project_binary_dir=project_binary,
        mode=args.mode,
        pre_commit_version=args.pre_commit_version,
        venv_dir=venv_dir,
        install_example_config=bool(args.install_example_config),
        tool_root=tool_root,
        python_for_venv=python_for_venv,
    )


if __name__ == "__main__":
    raise SystemExit(main())

# pre-commit

[![CI][badge-ci]][workflow-ci]
[![Pre-commit][badge-pre-commit]][workflow-pre-commit]
[![Actionlint][badge-actionlint]][workflow-actionlint]
[![License][badge-license]](LICENSE)
[![CMake][badge-cmake]][cmake-presets]
[![Release][badge-release]][releases]

The kind of pre-commit out-of-the-box setup everybody wants,
making cmake users especially happy, but also usable via one-shot
`$ ./python/mb-pre-commit-setup.py`.

By default, you get pre-commit behavior without annoying
failing commits (except markdown or things not fixable automatically)
and manual amends or separate formatting commits.

One drawback: the custom commit hook won't work properly for code
changes within submodules. To help a bit with that, repos
typically developed as submodules can be configured to get
their own sweep target at least, see PRE_COMMIT_TOOL_SWEEP_TARGET.

## Usage, quick start

```
include(FetchContent)

FetchContent_Declare(
    mb_pre_commit
    GIT_REPOSITORY https://github.com/devmarkusb/pre-commit.git
    GIT_TAG v1.4.0
)

FetchContent_MakeAvailable(mb_pre_commit)

mb_pre_commit_setup()
```

Or without CMake:

```
./python/mb-pre-commit-setup.py
```

### What it does, and alternative setup

`FetchContent_MakeAvailable` runs this dependency’s root [`CMakeLists.txt`](CMakeLists.txt), which pulls in
[`cmake/mb-pre-commit.cmake`][mb-pre-commit-cmake]. You never need `${mb-pre-commit_SOURCE_DIR}` in your own CMake for
the default integration.

**Vendoring (no FetchContent):** add `cmake/` to [`CMAKE_MODULE_PATH`][cmake-module-path] and `include(mb-pre-commit)`,
or `include(/path/to/pre-commit/cmake/mb-pre-commit.cmake)`.

[mb-pre-commit-cmake]: cmake/mb-pre-commit.cmake
[cmake-module-path]: https://cmake.org/cmake/help/latest/variable/CMAKE_MODULE_PATH.html

A starter [`.pre-commit-config.yaml`](https://pre-commit.com/) is **copied to the repository root on every CMake
configure** (overwriting any existing file there) from the newest matching entry under [`configs/vN/`](configs/v4/) in
this repo: `N` is the pre-commit **major** that directory targets, and CMake picks the largest `vN` with `N` less than
or equal to your `PRE_COMMIT_VERSION` major (default `4.5.1` uses `configs/v4`). Add `v5`, … later when you want configs
that assume newer pre-commit majors. If no `vN` qualifies, nothing is installed. Set
`PRE_COMMIT_INSTALL_EXAMPLE_CONFIG OFF` on `mb_pre_commit_setup()` to skip this entirely. Without a config file, the
**CUSTOM** hook exits successfully and does nothing; **NATIVE** mode uses whatever `pre-commit install` would normally
expect.

Hook templates and example configs resolve from this package’s directory even when your project’s `CMakeLists.txt` lives
elsewhere (`FetchContent`, `include`, …).

## Run pre-commit on all files (`mb-pre-commit-sweep`)

When Git-based setup runs (same cases as hook install), you get a CMake target named **`mb-pre-commit-sweep`**. If that
name is already taken, it is **`mb_pre_commit_sweep`** instead.

From your build directory:

```bash
cmake --build . --target mb-pre-commit-sweep
```

That runs `pre-commit run --all-files` with the same venv and repo root as the hook, so you get a full-tree check
without remembering flags or paths. Disable the target with `PRE_COMMIT_SWEEP_TARGET OFF`, or override the name with
`PRE_COMMIT_SWEEP_TARGET my-lint-all` or just `sweep`.

### Optional: sweep this package’s checkout (`PRE_COMMIT_TOOL_SWEEP_TARGET`)

The main sweep uses **`PROJECT_SOURCE_DIR`** as its working directory. When the current repo is a **submodule** (or
`PROJECT_SOURCE_DIR` points at an outer repo), you may also want a full-tree run **inside this package’s tree**.

Pass **`PRE_COMMIT_TOOL_SWEEP_TARGET <name>`** to register a second `add_custom_target` with that name, same venv and
command as above, but with working directory set to **this** checkout. **Omit the argument** if you do not need that
target; `OFF` means the same as omitting it.

Example:

```cmake
mb_pre_commit_setup(PRE_COMMIT_TOOL_SWEEP_TARGET mb-pre-commit-sweep-tool-repo)
```

## If customization is needed

```
mb_pre_commit_setup(
    PROJECT_SOURCE_DIR "${CMAKE_SOURCE_DIR}"
    PROJECT_BINARY_DIR "${CMAKE_BINARY_DIR}"
    PRE_COMMIT_MODE CUSTOM
    PRE_COMMIT_VERSION 4.5.1
    PRE_COMMIT_VENV_DIR "${CMAKE_SOURCE_DIR}/.venv"
    PRE_COMMIT_INSTALL_EXAMPLE_CONFIG ON
)
```

These are the defaults, by the way.

## What you get in detail

On **CMake configure**, `mb_pre_commit_setup()` can:

- Ensure a **project-local Python venv** exists (default: `<project>/.venv`).
- **Pin and install** the `pre-commit` package with pip (`PRE_COMMIT_VERSION`, default `4.5.1`), upgrading only when the
  version does not match.
- Install a **Git `pre-commit` hook** under `.git/hooks/` in the project you point at (`PROJECT_SOURCE_DIR`, default
  `CMAKE_SOURCE_DIR`).
- Register a **`mb-pre-commit-sweep`** CMake target that runs **pre-commit on all files**
  (`pre-commit run --all-files`) from `PROJECT_SOURCE_DIR` (see above).
- Optionally, register **another** sweep target (`PRE_COMMIT_TOOL_SWEEP_TARGET`) that runs the same command from **this
  package’s root** (parent of `cmake/`); see **Optional: sweep this package’s checkout** under [Run pre-commit on all
  files](#run-pre-commit-on-all-files-mb-pre-commit-sweep).

If the tree is not a normal Git checkout (no `.git` or `.git/hooks`), setup is **skipped** with a status
message—configure still succeeds.

**Requirements:** `find_package(Python3 REQUIRED COMPONENTS Interpreter)` must succeed (used to create the venv). Git
must be discoverable when a checkout exists. The **CUSTOM** hook is a **Bash** script (`read -d ''` for NUL-delimited
paths, `pipefail`); it needs Bash in `PATH` when Git runs hooks (typical on Unix; on Windows use Git Bash or another
environment where the hook’s `#!/usr/bin/env bash` resolves). It also uses `xargs` and `mktemp`.

This project’s CMake module uses APIs that require **CMake 3.21+** (`file(COPY_FILE)`, `file(CHMOD)`). The
[`CMakePresets.json`](CMakePresets.json) in this repository targets **CMake 4.0+** (preset schema version 10).

## `mb_pre_commit_setup` options

| Argument                            | Default                       | Meaning                                                                                                                                                                  |
|-------------------------------------|-------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `PROJECT_SOURCE_DIR`                | `CMAKE_SOURCE_DIR`            | Root of the Git repo where `.git` lives and hooks are installed.                                                                                                         |
| `PROJECT_BINARY_DIR`                | `CMAKE_BINARY_DIR`            | Where the generated hook file is written before install (`pre-commit` file).                                                                                             |
| `PRE_COMMIT_MODE`                   | `CUSTOM`                      | `CUSTOM` or `NATIVE` (see below).                                                                                                                                        |
| `PRE_COMMIT_VERSION`                | `4.5.1`                       | Exact `pre-commit` version installed in the venv via pip.                                                                                                                |
| `PRE_COMMIT_VENV_DIR`               | `${PROJECT_SOURCE_DIR}/.venv` | Virtualenv path; `Scripts/python.exe` on Windows, `bin/python3` otherwise.                                                                                               |
| `PRE_COMMIT_INSTALL_EXAMPLE_CONFIG` | `ON`                          | When `ON`, copies the best matching `configs/vN/.pre-commit-config.yaml` to `${PROJECT_SOURCE_DIR}/.pre-commit-config.yaml` on each configure (overwrites).              |
| `PRE_COMMIT_SWEEP_TARGET`           | `mb-pre-commit-sweep`         | Name of the `add_custom_target` that runs `pre-commit run --all-files`. Set to `OFF` to skip. If the default name is taken, the target is `mb_pre_commit_sweep` instead. |
| `PRE_COMMIT_TOOL_SWEEP_TARGET`      | `*(unset)*`                   | Optional second sweep: cwd = this package root. Same venv. Omit or `OFF` for no target.                                                                                  |

Relative paths for `PROJECT_SOURCE_DIR` / `PROJECT_BINARY_DIR` / `PRE_COMMIT_VENV_DIR` are resolved against
`CMAKE_SOURCE_DIR`, `CMAKE_BINARY_DIR`, and `PROJECT_SOURCE_DIR` respectively, matching CMake’s usual behavior.

## `PRE_COMMIT_MODE`: `CUSTOM` vs `NATIVE`

### `CUSTOM` (default)

CMake **configures** `cmake/pre-commit.in` into `${PROJECT_BINARY_DIR}/pre-commit`, then **copies** it to
`${PROJECT_SOURCE_DIR}/.git/hooks/pre-commit` when the content differs. On non-Windows hosts the hook is marked
executable.

The hook is a small Bash script that:

- Runs only on **staged** paths (`git diff --cached`, added/copied/modified/renamed, existing files only).
- If **`.pre-commit-config.yaml`** is missing, it exits **0** (no-op).
- Invokes `python -m pre_commit run --hook-stage pre-commit --files …` on that list, preferring the venv interpreter
  when it exists and is executable, else `python3` / `python`.
- If the first run **fails**, it **re-stages** paths that still exist on disk and runs again—so auto-fix hooks can
  succeed without you running `git add` manually.

Configure is set to **re-run** if `pre-commit.in` changes (`CMAKE_CONFIGURE_DEPENDS`).

### `NATIVE`

Runs `python -m pre_commit install --install-hooks --hook-type pre-commit` from `PROJECT_SOURCE_DIR`, using the same
venv. You get upstream’s installed hook and default behavior instead of the custom staged-files / retry script.

## Contributing and releases

The canonical example hook list for packaging is [`configs/v4/.pre-commit-config.yaml`](configs/v4/.pre-commit-config.yaml).
The copy at the repository root is kept **byte-identical** (CI fails on drift) so local `pre-commit` runs and packaged
configs stay aligned; edit `configs/v4/` first, then sync the root file.

Maintainers can create an annotated release tag and push it to `origin` with [`scripts/git-tag`](scripts/git-tag): it
refuses a dirty working tree or an existing tag, then runs `git tag -a` with message `Release <tag>` and `git push
origin <tag>` (use `--no-push` for a local tag only). Example:

```bash
./scripts/git-tag v1.2.0
```

**Consumer projects:** this helper is not wired through CMake or FetchContent; it is a small standalone script (stdlib
only). If you want the same workflow downstream, copy it into your repository, vendor it under `scripts/`, or fetch a
pinned revision from this repo’s raw URL and run it from your `PATH`. A [`git
alias`](https://git-scm.com/docs/git-config#Documentation/git-config.txt-alias) pointing at a checked-out or local copy
is another lightweight option.

<!-- Badge targets (reference links keep the intro row within MD013 line length). -->

[badge-ci]: https://github.com/devmarkusb/pre-commit/actions/workflows/ci.yml/badge.svg?branch=main
[workflow-ci]: https://github.com/devmarkusb/pre-commit/actions/workflows/ci.yml
[badge-pre-commit]: https://github.com/devmarkusb/pre-commit/actions/workflows/pre-commit.yml/badge.svg?branch=main
[workflow-pre-commit]: https://github.com/devmarkusb/pre-commit/actions/workflows/pre-commit.yml
[badge-actionlint]: https://github.com/devmarkusb/pre-commit/actions/workflows/actionlint.yml/badge.svg?branch=main
[workflow-actionlint]: https://github.com/devmarkusb/pre-commit/actions/workflows/actionlint.yml
[badge-license]: https://img.shields.io/badge/license-BSL--1.0-blue.svg
[badge-cmake]: https://img.shields.io/badge/CMake-≥%203.21-064F8C?logo=cmake&logoColor=white
[cmake-presets]: https://cmake.org/cmake/help/latest/manual/cmake-presets.7.html
[badge-release]: https://img.shields.io/github/v/tag/devmarkusb/pre-commit?label=release&logo=github
[releases]: https://github.com/devmarkusb/pre-commit/releases

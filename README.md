# pre-commit

[![CI][badge-ci]][workflow-ci]
[![Pre-commit][badge-pre-commit]][workflow-pre-commit]
[![Actionlint][badge-actionlint]][workflow-actionlint]
[![License][badge-license]](LICENSE)
[![CMake][badge-cmake]][cmake-presets]
[![Release][badge-release]][releases]

Out-of-the-box pre-commit for CMake projects (or one-shot `./python/mb-pre-commit-setup.py`). The default
**CUSTOM** hook runs on staged files, re-stages after auto-fixes, and avoids failed commits for fixable
issues—except markdown and other non-auto-fixable hooks. The shipped example config includes Python hooks
(ruff + pyupgrade).

**Submodules:** Git runs hooks from the submodule’s own `.git`, not the parent’s. Call
**`mb_pre_commit_setup_subdirectory()`** from each submodule’s `CMakeLists.txt` (parent still needs
`mb_pre_commit` via FetchContent). Each tree gets its own `.venv` and hook. **`PRE_COMMIT_TOOL_SWEEP_TARGET`**
is different: it sweeps **this mb-pre-commit package checkout** in `_deps`, not an arbitrary consumer
submodule.

## Quick start

```cmake
include(FetchContent)

FetchContent_Declare(
    mb_pre_commit
    GIT_REPOSITORY https://github.com/devmarkusb/pre-commit.git
    GIT_TAG v1.4.0
)

FetchContent_MakeAvailable(mb_pre_commit)

mb_pre_commit_setup_project()
```

`mb_pre_commit_setup_project()` picks top-level vs subdirectory setup via
`CMAKE_SOURCE_DIR STREQUAL CMAKE_CURRENT_SOURCE_DIR` (prefer over `PROJECT_IS_TOP_LEVEL`, which stays `ON`
in `add_subdirectory()` trees without their own `project()`). In submodules with their own config, use:

```cmake
mb_pre_commit_setup_project(PRE_COMMIT_INSTALL_EXAMPLE_CONFIG OFF)
```

That yields sweep target `mb-pre-commit-sweep-<dir>` (basename of the calling `CMakeLists.txt` folder,
e.g. `mb-pre-commit-sweep-devenv`). Call `mb_pre_commit_setup()` or `mb_pre_commit_setup_subdirectory()`
explicitly if you prefer.

Without CMake: `./python/mb-pre-commit-setup.py`

After setup, the venv includes a launcher for the newest `clang-format` cached by pre-commit:

```bash
./.venv/bin/mb-pre-commit-clang-format --version   # Windows: .venv\Scripts\mb-pre-commit-clang-format.cmd
```

(`./python/mb-pre-commit-clang-format.py` remains for direct use.)

## Integration

`FetchContent_MakeAvailable` runs this repo’s [`CMakeLists.txt`](CMakeLists.txt), which pulls in
[`cmake/mb-pre-commit.cmake`][mb-pre-commit-cmake]—no `${mb-pre-commit_SOURCE_DIR}` needed.

**Vendoring:** add `cmake/` to [`CMAKE_MODULE_PATH`][cmake-module-path] and `include(mb-pre-commit)`, or
`include(/path/to/pre-commit/cmake/mb-pre-commit.cmake)`.

[mb-pre-commit-cmake]: cmake/mb-pre-commit.cmake
[cmake-module-path]: https://cmake.org/cmake/help/latest/variable/CMAKE_MODULE_PATH.html

On configure, a starter [`.pre-commit-config.yaml`](https://pre-commit.com/) is **copied to the project
root** (overwriting any existing file) from the best match under [`configs/vN/`](configs/v4/): largest `vN`
with `N` ≤ your `PRE_COMMIT_VERSION` major (default `4.5.1` → `configs/v4`). Add `v5`, … for newer
pre-commit majors. If none qualify, nothing is installed. Set `PRE_COMMIT_INSTALL_EXAMPLE_CONFIG OFF` to
skip. Without a config, **CUSTOM** exits 0 (no-op); **NATIVE** uses whatever `pre-commit install` expects.
Templates and configs resolve from this package’s directory regardless of where your `CMakeLists.txt`
lives.

## Sweep targets

When Git setup runs, you get **`mb-pre-commit-sweep`** (`mb_pre_commit_sweep` if the name is taken):

```bash
cmake --build . --target mb-pre-commit-sweep
```

Runs `pre-commit run --all-files` with the same venv and repo root as the hook. Disable with
`PRE_COMMIT_SWEEP_TARGET OFF`; rename with `PRE_COMMIT_SWEEP_TARGET <name>`.

**`PRE_COMMIT_TOOL_SWEEP_TARGET <name>`** adds a second sweep at **this package’s checkout** (same
venv/command, cwd = this tree). Omit or `OFF` for none. Skipped when `PROJECT_SOURCE_DIR` is already this
checkout and the main sweep is enabled. If main sweep is `OFF` but tool sweep is set, you get one sweep for
this tree only.

```cmake
mb_pre_commit_setup(PRE_COMMIT_TOOL_SWEEP_TARGET mb-pre-commit-sweep-tool-repo)
```

## Configure behavior

On **CMake configure**, `mb_pre_commit_setup()` (when Git hooks are available):

- Creates a project-local venv (default `<project>/.venv`).
- Pins `pre-commit` via pip (`PRE_COMMIT_VERSION`, default `4.5.1`); upgrades only when mismatched.
- Installs a Git `pre-commit` hook into the effective hooks dir (`git rev-parse --git-path hooks`; works
  with worktrees).
- Registers sweep target(s) as above.

Non-Git trees (or unresolvable hooks dir): setup skipped, configure succeeds.

**Requirements:** `find_package(Python3 REQUIRED COMPONENTS Interpreter)`; Git when a checkout exists.
**CUSTOM** hook is Bash (`pipefail`, `read -d ''`, `xargs`, `mktemp`)—needs Bash on `PATH` when Git runs
hooks (Git Bash on Windows). Module needs **CMake 3.21+**; this repo’s [`CMakePresets.json`](CMakePresets.json)
targets **CMake 4.0+**.

## Options

All defaults shown in the explicit call below:

```cmake
mb_pre_commit_setup(
    PROJECT_SOURCE_DIR "${CMAKE_SOURCE_DIR}"
    PROJECT_BINARY_DIR "${CMAKE_BINARY_DIR}"
    PRE_COMMIT_MODE CUSTOM
    PRE_COMMIT_VERSION 4.5.1
    PRE_COMMIT_VENV_DIR "${CMAKE_SOURCE_DIR}/.venv"
    PRE_COMMIT_INSTALL_EXAMPLE_CONFIG ON
)
```

| Argument                            | Default                       | Meaning                                                                                                                                                                  |
|-------------------------------------|-------------------------------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| `PROJECT_SOURCE_DIR`                | `CMAKE_SOURCE_DIR`            | Git repo root for hooks.                                                                                                                                                 |
| `PROJECT_BINARY_DIR`                | `CMAKE_BINARY_DIR`            | Generated hook written here before install.                                                                                                                              |
| `PRE_COMMIT_MODE`                   | `CUSTOM`                      | `CUSTOM` or `NATIVE` (below).                                                                                                                                            |
| `PRE_COMMIT_VERSION`                | `4.5.1`                       | Exact pip version in venv.                                                                                                                                               |
| `PRE_COMMIT_VENV_DIR`               | `${PROJECT_SOURCE_DIR}/.venv` | `Scripts/python.exe` (Windows) or `bin/python3`.                                                                                                                         |
| `PRE_COMMIT_INSTALL_EXAMPLE_CONFIG` | `ON`                          | Refresh `.pre-commit-config.yaml` from `configs/vN/`.                                                                                                                    |
| `PRE_COMMIT_SWEEP_TARGET`           | `mb-pre-commit-sweep`         | `add_custom_target` for `--all-files`; `OFF` to skip. Falls back to `mb_pre_commit_sweep` if name taken.                                                                 |
| `PRE_COMMIT_TOOL_SWEEP_TARGET`      | `*(unset)*`                   | Second sweep at this package root when `PROJECT_SOURCE_DIR` is elsewhere. Omit/`OFF`: none.                                                                              |

**`mb_pre_commit_setup_subdirectory`:** same options; `PROJECT_*` default to `CMAKE_CURRENT_*`,
`PRE_COMMIT_INSTALL_EXAMPLE_CONFIG` defaults `OFF`, sweep defaults to `mb-pre-commit-sweep-<dir>` (basename
of `CMAKE_CURRENT_LIST_DIR`).

Relative `PROJECT_SOURCE_DIR` / `PROJECT_BINARY_DIR` / `PRE_COMMIT_VENV_DIR` resolve against
`CMAKE_SOURCE_DIR`, `CMAKE_BINARY_DIR`, and `PROJECT_SOURCE_DIR`.

Cache **`MB_PRE_COMMIT_SETUP_LAYOUT`**: `AUTO` (default), `TOP_LEVEL`, or `SUBDIRECTORY` — force layout in
tests/CI.

## `PRE_COMMIT_MODE`

### `CUSTOM` (default)

Configures `cmake/pre-commit.in` → `${PROJECT_BINARY_DIR}/pre-commit`, copies to hooks dir when content
differs (executable on non-Windows). The hook:

- Runs on **staged** paths only (added/copied/modified/renamed, existing files).
- Exits **0** if `.pre-commit-config.yaml` is missing.
- Runs `python -m pre_commit run --hook-stage pre-commit --files …` (venv python if available, else
  `python3`/`python`).
- On failure, **re-stages** surviving paths and retries (auto-fix without manual `git add`).

Re-configures when `pre-commit.in` changes (`CMAKE_CONFIGURE_DEPENDS`).

### `NATIVE`

Runs `python -m pre_commit install --install-hooks --hook-type pre-commit` from `PROJECT_SOURCE_DIR` with
the same venv—upstream hook and behavior.

## Contributing and releases

Canonical hooks: [`configs/v4/.pre-commit-config.yaml`](configs/v4/.pre-commit-config.yaml). Root
[`.pre-commit-config.yaml`](.pre-commit-config.yaml) is a **symlink** for Dependabot/CI; consumers get a
file copy from CMake. Edit `configs/v4/` only.

Release tags via [`scripts/git-tag`](scripts/git-tag) (clean tree required; `--no-push` for local only):

```bash
./scripts/git-tag --bump patch   # v3.0.0 -> v3.0.1
./scripts/git-tag --bump minor   # v3.0.0 -> v3.1.0
./scripts/git-tag v1.2.0
```

Not wired through CMake; copy/vendor/fetch or use a
[`git alias`](https://git-scm.com/docs/git-config#Documentation/git-config.txt-alias) downstream.

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

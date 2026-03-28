# pre-commit
The kind of pre-commit out-of-the-box setup everybody wants, cmake users exclusively for now.

By default, you get pre-commit behavior without annoying
failing commits and manual amends or separate formatting
commits.

## Usage, quick start

```
include(FetchContent)

FetchContent_Declare(
    mb-pre-commit
    GIT_REPOSITORY https://github.com/devmarkusb/pre-commit.git
    GIT_TAG v1.0.0
)

FetchContent_MakeAvailable(mb-pre-commit)

mb_pre_commit_setup()
```

### What it does, alternatives

`FetchContent_MakeAvailable` runs this dependency’s root [`CMakeLists.txt`](CMakeLists.txt), which pulls in [`cmake/mb-pre-commit.cmake`](cmake/mb-pre-commit.cmake). You never need `${mb-pre-commit_SOURCE_DIR}` in your own CMake for the default integration.

**Vendoring (no FetchContent):** add `cmake/` to [`CMAKE_MODULE_PATH`](https://cmake.org/cmake/help/latest/variable/CMAKE_MODULE_PATH.html) and `include(mb-pre-commit)`, or `include(/path/to/pre-commit/cmake/mb-pre-commit.cmake)`.

Add a [`.pre-commit-config.yaml`](https://pre-commit.com/) at the repository root. Without it, the **CUSTOM** hook exits successfully and does nothing; **NATIVE** mode uses whatever `pre-commit install` would normally expect.

## If customization is needed

```
mb_pre_commit_setup(
    PROJECT_SOURCE_DIR "${CMAKE_SOURCE_DIR}"
    PROJECT_BINARY_DIR "${CMAKE_BINARY_DIR}"
    PRE_COMMIT_MODE CUSTOM
    PRE_COMMIT_VERSION 4.5.1
    PRE_COMMIT_VENV_DIR "${CMAKE_SOURCE_DIR}/.venv"
)
```
These are the defaults, by the way.

## What you get in detail

On **CMake configure**, `mb_pre_commit_setup()` can:

- Ensure a **project-local Python venv** exists (default: `<project>/.venv`).
- **Pin and install** the `pre-commit` package with pip (`PRE_COMMIT_VERSION`, default `4.5.1`), upgrading only when the version does not match.
- Install a **Git `pre-commit` hook** under `.git/hooks/` in the project you point at (`PROJECT_SOURCE_DIR`, default `CMAKE_SOURCE_DIR`).

If the tree is not a normal Git checkout (no `.git` or `.git/hooks`), setup is **skipped** with a status message—configure still succeeds.

**Requirements:** `find_package(Python3 REQUIRED COMPONENTS Interpreter)` must succeed (used to create the venv). Git must be discoverable when a checkout exists. The hook script uses POSIX `sh`, `xargs`, and `mktemp` (typical on Unix; on Windows, **CUSTOM** mode is aimed at environments that run the hook as a shell script, e.g. Git Bash).


## `mb_pre_commit_setup` options

| Argument | Default | Meaning |
|----------|---------|---------|
| `PROJECT_SOURCE_DIR` | `CMAKE_SOURCE_DIR` | Root of the Git repo where `.git` lives and hooks are installed. |
| `PROJECT_BINARY_DIR` | `CMAKE_BINARY_DIR` | Where the generated hook file is written before install (`pre-commit` file). |
| `PRE_COMMIT_MODE` | `CUSTOM` | `CUSTOM` or `NATIVE` (see below). |
| `PRE_COMMIT_VERSION` | `4.5.1` | Exact `pre-commit` version installed in the venv via pip. |
| `PRE_COMMIT_VENV_DIR` | `${PROJECT_SOURCE_DIR}/.venv` | Virtualenv path; `Scripts/python.exe` on Windows, `bin/python3` otherwise. |

Relative paths for `PROJECT_SOURCE_DIR` / `PROJECT_BINARY_DIR` / `PRE_COMMIT_VENV_DIR` are resolved against `CMAKE_SOURCE_DIR`, `CMAKE_BINARY_DIR`, and `PROJECT_SOURCE_DIR` respectively, matching CMake’s usual behavior.

## `PRE_COMMIT_MODE`: `CUSTOM` vs `NATIVE`

### `CUSTOM` (default)

CMake **configures** `cmake/pre-commit.in` into `${PROJECT_BINARY_DIR}/pre-commit`, then **copies** it to `${PROJECT_SOURCE_DIR}/.git/hooks/pre-commit` when the content differs. On non-Windows hosts the hook is marked executable.

The hook is a small `sh` script that:

- Runs only on **staged** paths (`git diff --cached`, added/copied/modified/renamed, existing files only).
- If **`.pre-commit-config.yaml`** is missing, it exits **0** (no-op).
- Invokes `python -m pre_commit run --hook-stage pre-commit --files …` on that list, preferring the venv interpreter when it exists and is executable, else `python3` / `python`.
- If the first run **fails**, it **re-stages** paths that still exist on disk and runs again—so auto-fix hooks can succeed without you running `git add` manually.

Configure is set to **re-run** if `pre-commit.in` changes (`CMAKE_CONFIGURE_DEPENDS`).

### `NATIVE`

Runs `python -m pre_commit install --install-hooks --hook-type pre-commit` from `PROJECT_SOURCE_DIR`, using the same venv. You get upstream’s installed hook and default behavior instead of the custom staged-files / retry script.


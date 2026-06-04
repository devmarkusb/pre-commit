# Agent instructions (mb-pre-commit)

Portable instructions for AI agents working in this repository. Tool-specific files (`CLAUDE.md`, `.cursor/rules/`) are thin adapters only.

## Project overview

**mb-pre-commit** is a CMake module and optional Python setup script that installs a project-local Python venv, pins `pre-commit`, installs a Git hook (custom Bash script or native `pre-commit install`), and exposes a CMake sweep target (`mb-pre-commit-sweep`) to run hooks on all files.

Consumers integrate via `FetchContent` + `mb_pre_commit_setup_project()`, or run `./python/mb-pre-commit-setup.py` without CMake. This repo dogfoods its own module in root `CMakeLists.txt`.

**Stack:** CMake (module requires 3.21+; presets target CMake 4.0+), Python 3 (venv + setup script), Bash (hook template), YAML (pre-commit config). No compiled application code—`LANGUAGES NONE`.

## Build commands

From the repository root (requires CMake ≥ 4.0 and Ninja for default presets):

```bash
cmake --preset default          # or: ci | release | dev-verbose | unix-makefiles
cmake --build --preset default
```

Workflow presets (configure + build):

```bash
cmake --workflow --preset dev     # default Debug
cmake --workflow --preset ship    # release
cmake --workflow --preset ci      # strict CI-like configure + build
```

CMake configure also creates/updates `.venv`, installs the Git hook when `.git` exists, and registers `mb-pre-commit-sweep`.

**Without CMake:**

```bash
./python/mb-pre-commit-setup.py
```

## Test commands

There is no separate unit-test suite. Validation is integration-style:

```bash
# Match CI: configure, build, full pre-commit sweep
cmake --preset ci
cmake --build --preset ci
cmake --build --preset ci --target mb-pre-commit-sweep

# Symlink integrity (root config must match shipped example)
cmp -s configs/v4/.pre-commit-config.yaml .pre-commit-config.yaml

# Hook installed after configure
test -f .git/hooks/pre-commit
```

**Pre-commit only** (uses hook environments under `~/.cache/pre-commit` when run via the action; locally use venv or `pre-commit` on PATH):

```bash
pre-commit run --all-files
```

## Formatting and linting

Hooks are defined in `configs/v4/.pre-commit-config.yaml` (root `.pre-commit-config.yaml` is a **symlink** to that file). Run via sweep or pre-commit:

| Tool | Scope |
|------|--------|
| pre-commit-hooks | YAML/JSON, EOF, whitespace, symlinks, etc. |
| markdownlint-cli | `*.md` (config: `.markdownlint.yaml`) |
| codespell | text |
| ruff + ruff-format | `python/` |
| pyupgrade | Python ( `--py310-plus` ) |
| gersemi | `*.cmake` |
| clang-format | C/C++ (when present) |

Preferred local path after CMake configure:

```bash
cmake --build --preset default --target mb-pre-commit-sweep
```

Edit hook versions in **`configs/v4/`** only, not by breaking the root symlink.

## Architecture and important directories

| Path | Role |
|------|------|
| `cmake/mb-pre-commit.cmake` | `mb_pre_commit_setup()`, subdirectory/project helpers |
| `cmake/pre-commit.in` | Bash hook template (configured into build dir, copied to `.git/hooks`) |
| `python/mb-pre-commit-setup.py` | CMake-free setup; mirrors CMake logic |
| `python/mb-pre-commit-clang-format.py` | Repo-local clang-format launcher (venv also gets `mb-pre-commit-clang-format`) |
| `configs/v4/` | Canonical shipped `.pre-commit-config.yaml` and `.markdownlint.yaml` |
| `CMakePresets.json` | Presets: `default`, `ci`, `release`, `dev-verbose`, `unix-makefiles`, `xcode`, `vs2022` |
| `CMakeLists.txt` | Top-level dogfood; calls `mb_pre_commit_setup_project(PRE_COMMIT_INSTALL_EXAMPLE_CONFIG OFF)` |
| `scripts/git-tag` | Maintainer release tagging (stdlib Python); not wired through CMake |
| `.github/workflows/` | `ci.yml`, `pre-commit.yml`, `actionlint.yml` |
| `build/` | Generated; gitignored |

**Cache variable:** `MB_PRE_COMMIT_SETUP_LAYOUT` (`AUTO` | `TOP_LEVEL` | `SUBDIRECTORY`) forces layout in tests/CI.

## Coding conventions

- **CMake:** `include_guard(GLOBAL)`; `cmake_parse_arguments` for public APIs; status via `message(STATUS ...)`. Format with **gersemi** (via pre-commit). Requires CMake 3.21 APIs (`file(COPY_FILE)`, `file(CHMOD)`).
- **Python:** stdlib-only in shipped scripts; type hints and `from __future__ import annotations` in `mb-pre-commit-setup.py`. **Ruff** + **pyupgrade** via pre-commit.
- **Hook script:** Bash with `pipefail`; staged-files only; retries after re-stage on failure (CUSTOM mode).
- **Docs:** README is the user-facing contract; keep `configs/v4` and README in sync when behavior changes.
- **Releases:** Annotated tags via `./scripts/git-tag --bump patch|minor|major` or `./scripts/git-tag vX.Y.Z` (clean tree required).

## Testing expectations

Before claiming work is done:

1. If CMake or hook behavior changed: run `cmake --preset ci` and `cmake --build --preset ci --target mb-pre-commit-sweep`.
2. If `configs/v4` or markdown rules changed: ensure `cmp` check passes and markdownlint still passes on README.
3. If `.github/workflows` changed: actionlint must pass (workflow runs on path filter).

Do not add a heavyweight test framework unless the user asks; extend CI smoke steps instead.

## Files and directories agents must not edit without explicit approval

- `.github/workflows/**` (CI/release automation)—unless the task is explicitly about CI
- `.github/dependabot.yml`
- `build/**`, `.venv/**`, `__pycache__/**`, `.ruff_cache/**`
- `.git/hooks/pre-commit` (generated by configure)
- Root `.pre-commit-config.yaml` as a regular file (it is a symlink; edit `configs/v4/`)
- `CMakeUserPresets.json` (local, gitignored)
- Annotated release tags / `git push --tags` without explicit request

## Security and privacy constraints

- Do not commit secrets, tokens, or local env files.
- Do not add repo-level MCP servers with broad filesystem, shell, browser, or credential access unless the user explicitly requests and accepts the risk.
- Hook and setup scripts invoke `git`, `pip`, and `pre-commit` with network access when installing hook environments—normal for this project; do not broaden that surface without reason.
- `scripts/git-tag` pushes to `origin` by default; use `--no-push` when a local-only tag is intended.

## Review checklist before final response

- [ ] Changes match the actual layout above (especially `configs/v4` vs root symlink).
- [ ] If CMake API or defaults changed, README tables/sections updated.
- [ ] Ran or described verification: at minimum sweep or relevant `cmp`/actionlint when touching those areas.
- [ ] No edits under forbidden paths unless the user requested them.
- [ ] No large generic boilerplate added to agent config files.

# SmartCatalog Developer Guide

[Documentation index](README.md)

## Prerequisites

- Windows
- Python 3.13.x (`.python-version` records the validated patch version)
- PowerShell
- Network access for first-time dependency installation

## Setup and run

```powershell
.\tools\setup.ps1
.\.venv-agent\Scripts\python.exe run.py
```

The default Agent mode creates or reuses `.venv-agent`, installs the complete
`requirements-dev.txt` lock, and runs validation. Runtime and Build modes use
separate `.venv-runtime` and `.venv-build` environments so developer packages
cannot leak into application or release environments. Use `-Clean` to recreate
the selected environment from its lock.

For repeatable offline setup, populate the ignored wheelhouse while online,
then use it without package-index access:

```powershell
.\tools\setup.ps1 -Mode Agent -RefreshWheelhouse
.\tools\setup.ps1 -Mode Agent -Clean -Offline
```

Direct dependency intent lives in `requirements.in`, `requirements-dev.in`,
and `requirements-build.in`. Their matching `.txt` files are generated locks;
update them only through `.\tools\lock.ps1` under Python 3.13.

Python 3.13 is the locally validated baseline and the only interpreter used by
Windows CI. Validate frozen builds and UI smoke tests on that interpreter.

Normal startup is:

```text
run.py
  -> smartcatalog.main.start_ui()
  -> AppState
  -> CatalogDB
  -> create_main_window()
```

Read [ARCHITECTURE.md](ARCHITECTURE.md) before changing workflow boundaries or
persistence behavior.

## Project layout

```text
src/smartcatalog/
├── domain/       persisted/UI models
├── db/           schema, path mapping, repositories, CatalogDB facade
├── loader/       PDF and Excel parsing
├── services/     UI-independent workflows
├── ui/           Tkinter composition, controllers, dialogs, widgets
└── utils/        shared policies and workbook/package helpers
```

## Minimum validation

Run from the repository root:

```powershell
.\tools\check.ps1
```

The script prefers `.venv-agent\Scripts\python.exe`, with legacy-environment
fallbacks, and otherwise uses `python` from `PATH`. It verifies Python and
installed dependency consistency, compiles and imports the application, runs
conservative Ruff checks and the complete discovered test suite, checks staged
and unstaged patch whitespace, validates UTF-8 repository text and local
Markdown links, and reports worktree status. Test discovery output is the
source of truth for the current test count. See [TESTING.md](TESTING.md) for
test categories and known behaviors.

## Safe development rules

- Never inspect or use `to_integrate/`.
- Do not use the live catalog database as test data.
- Use temporary directories and generated fixtures for database, PDF, Excel,
  image, backup, and export tests.
- Treat `config/`, `input/`, `output/`, `build/`, and `dist/` as runtime,
  generated, or user-data areas.
- Preserve UTF-8 source and Vietnamese UI text exactly.
- Keep Tkinter access on the UI thread.
- Keep SQLite connection ownership and commit behavior explicit.
- Preserve source and frozen-executable paths.

The complete mandatory rules are in [AGENTS.md](../AGENTS.md).

## Build and release

```powershell
.\tools\setup.ps1 -Mode Build
.\build_exe.ps1
```

The script:

1. validates the repository virtual environment;
2. cleans the exact repository `dist\` directory;
3. writes PyInstaller intermediates to `build\`;
4. writes the release to `dist\SmartCatalog\`;
5. copies the runtime icon and branding asset.

Distribute the complete `dist\SmartCatalog\` folder. See
[BUILD_EXE.md](../BUILD_EXE.md) for the clean-install checklist,
existing-client data-preservation procedure, and licensing note.

## Before submitting a change

1. Review `git status --short`.
2. Confirm every changed file belongs to the task.
3. Run the minimum validation.
4. Run focused disposable-data tests for changed workflows.
5. Smoke-test affected UI behavior when feasible.
6. Document anything not tested.

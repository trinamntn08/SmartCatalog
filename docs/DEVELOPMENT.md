# SmartCatalog Developer Guide

[Documentation index](README.md)

## Prerequisites

- Windows
- Python
- PowerShell
- Dependencies listed in `requirements.txt`

## Setup and run

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

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
python -m compileall -q run.py src tests
.\venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'src'); import smartcatalog; import smartcatalog.main"
.\venv\Scripts\python.exe -m unittest discover -s tests -v
git diff --check
git status --short
```

The current baseline is 89 passing tests.

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

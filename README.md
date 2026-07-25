# SmartCatalog

SmartCatalog is a Windows-first Python/Tkinter application for importing,
reviewing, editing, and exporting a medical product catalog.

## Development setup

From PowerShell in the repository root:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python run.py
```

If activation is blocked, change the execution policy only for the current
PowerShell process:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
```

## Windows executable

Use the checked-in PyInstaller build:

```powershell
.\build_exe.ps1
```

Deliver the complete `dist\SmartCatalog\` directory, including `_internal`.
See [BUILD_EXE.md](BUILD_EXE.md) for build, validation, delivery, and licensing
details.

## Architecture and maintenance

- [Contributor guide](AGENTS.md)
- [Architecture](docs/ARCHITECTURE.md)
- [Refactor state](docs/REFACTOR_STATE.md)
- [Refactor plan](docs/REFACTOR_PLAN.md)
- [Refactor baseline and validation](docs/REFACTOR_BASELINE.md)
- [Phase 14 validation evidence](docs/FINAL_VALIDATION.md)
- [Post-refactor cleanup audit](docs/POST_REFACTOR_CLEANUP.md)

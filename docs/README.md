# SmartCatalog Documentation

Use this page to find the right document quickly.

## For application users

- [User guide](USER_GUIDE.md) — everyday PDF, Excel, item, image, backup, and
  export workflows.
- [Windows release instructions](../BUILD_EXE.md) — how maintainers build and
  package the client application.

## For developers

- [Developer guide](DEVELOPMENT.md) — setup, validation, project layout, and
  safe change workflow.
- [Architecture](ARCHITECTURE.md) — runtime layers, dependencies, persistence,
  and major data flows.
- [Testing guide](TESTING.md) — test categories, local commands, and explicitly
  tracked known behaviors.
- [Contributor rules](../AGENTS.md) — mandatory repository and data-safety
  constraints.

## Completed refactor records

These documents are historical evidence. They explain why the current
architecture exists; they are not step-by-step instructions for new work.

- [Refactor state](REFACTOR_STATE.md)
- [Refactor plan](REFACTOR_PLAN.md)
- [Baseline and checkpoint history](REFACTOR_BASELINE.md)
- [Final validation](FINAL_VALIDATION.md)
- [Post-refactor cleanup](POST_REFACTOR_CLEANUP.md)
- [Legacy module disposition](LEGACY_MODULE_DISPOSITION.md)
- [Error and resource audit](ERROR_HANDLING_AUDIT.md)
- [Naming and encoding audit](NAMING_ENCODING_AUDIT.md)

## Source of truth

- Current application behavior: tracked source and automated tests.
- Current contributor policy: `AGENTS.md`.
- Current architecture: `docs/ARCHITECTURE.md`.
- Current build process: `build_exe.ps1` and `BUILD_EXE.md`.
- Historical decisions: refactor and audit documents listed above.

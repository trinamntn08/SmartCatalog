# SmartCatalog Testing Guide

[Documentation index](README.md) · [Developer guide](DEVELOPMENT.md)

## Test categories

- **Regression tests** assert intended behavior and should fail when that
  behavior regresses.
- **Characterization tests** preserve observed behavior while risky code is
  being understood or refactored. Their names do not imply that every asserted
  behavior is desirable.
- **Known-behavior tests** intentionally preserve a confirmed defect until a
  separately scoped fix changes both the implementation and the expectation.
  Each one must reference a stable entry below.

Use generated fixtures and disposable directories. Tests must not inspect or
modify the live catalog, imported documents, branding, or runtime assets.

## Known behaviors

| ID | Area | Current behavior | Resolution rule |
| --- | --- | --- | --- |
| KB-001 | PDF import | The extracted PNG is written, but caller-owned asset/link rows are rolled back when the connection closes. | Fix in a separately scoped persistence change, then replace the known-behavior assertion with the intended committed-link result. |

Do not add an entry merely to make a failing test pass. First confirm whether
the failure is a regression, an obsolete characterization, or a real defect.

## Local commands

```powershell
.\tools\setup.ps1
.\tools\check.ps1
```

The canonical check includes dependency consistency, compilation, imports,
Ruff, the discovered suite, architecture-boundary enforcement, patch
whitespace, UTF-8 text checks, and local Markdown-link validation. Windows CI
runs the same Agent setup on Python 3.10 and the Python 3.13 migration target.

Regenerate all dependency locks after deliberately changing an input file:

```powershell
.\tools\lock.ps1
```

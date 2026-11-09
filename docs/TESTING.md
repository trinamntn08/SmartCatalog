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
runs the same Agent setup on Python 3.13.

Release packaging tests use synthetic runnable folders to check required
components, exclusion of runtime/agent files, complete ZIP contents, SHA-256,
and preservation of an earlier delivery. They do not substitute for launching
the built EXE or inspecting exports in desktop Excel.

For an actual build check without replacing the usual output:

```powershell
.\build_exe.ps1 -OutputRoot .cache\release-verification
```

Use a new/empty output root, extract its ZIP to a separate disposable location,
and check first launch, catalog restart, images, PDF/Excel workflows, and paths.
Never smoke-test with live data or ship a folder that has been launched.
See [BUILD_EXE.md](../BUILD_EXE.md) for packaging and upgrade checks.

The opt-in Tk benchmark is separate from unit discovery:

```powershell
.\.venv-agent\Scripts\python.exe tests/benchmark_performance.py --items 10000
```

It uses generated data and requires a desktop. Compare on the same machine and
interpreter; wall-clock thresholds do not belong in the regression suite.
See [PERFORMANCE_REVIEW.md](PERFORMANCE_REVIEW.md) for the measured baseline.

Regenerate all dependency locks after deliberately changing an input file:

```powershell
.\tools\lock.ps1
```

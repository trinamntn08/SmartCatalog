# Test scope

The repository-root `AGENTS.md` remains authoritative. These additional rules
apply to changes under `tests/`.

- Use `TemporaryProject`, `tempfile`, generated workbooks/PDFs/images, or other
  disposable fixtures. Never read or mutate the live `config/database/` tree.
- Regression tests describe intended behavior. Characterization tests record
  observed compatibility behavior and do not automatically declare it correct.
- A test that intentionally preserves a known defect must reference a stable
  `KB-###` entry in `docs/TESTING.md`. Do not hide a new defect by merely naming
  it "current behavior".
- Test discovery output is authoritative; do not hard-code a suite-wide count
  in current documentation.
- Keep UI-independent services importable in headless tests and mock Tk dialogs
  only at controller/view boundaries.

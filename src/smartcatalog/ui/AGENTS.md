# UI scope

The repository-root `AGENTS.md` remains authoritative. These additional rules
apply to changes under `src/smartcatalog/ui/`.

- Keep `main_window.py` focused on widget composition and bindings. Reusable
  panel behavior belongs in controllers; UI-independent workflows belong in
  services.
- Do not add raw SQL to UI code. Extend the persistence facade or repository
  layer and call it through the established state/database dependency.
- Access Tk widgets and variables only on the UI thread. Workers communicate
  through `root.after(...)`, `_safe_ui`, `_ui_call`, or the established event
  and decision pattern.
- Retain strong references to displayed `ImageTk.PhotoImage` objects.
- Preserve dirty-state prompts, selection, image order, and source/frozen path
  behavior. Report any affected interactive workflow that was not smoke-tested.

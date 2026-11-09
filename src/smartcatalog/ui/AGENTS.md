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
- `start_ui()` owns the initial catalog refresh after showing the splash.
  Preserve debounced search, cache invalidation through text values, and the
  single page-image request made by form reload. Do not restore redundant work.
- Document controls as actually displayed. The backup and refresh toolbar
  buttons currently exist without being packed into the visible toolbar.
- Preserve dirty-state prompts, selection, image order, and source/frozen path
  behavior. Report any affected interactive workflow that was not smoke-tested.

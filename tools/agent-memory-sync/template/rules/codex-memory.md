## Shared memory (same store Claude Code uses)

Long-term knowledge lives in the memory repo's `memory/` folder (one fact per markdown
file, indexed by `MEMORY.md`), synced between machines and shared with Claude Code.
Per-repo notes live in `projects/<repo>/`.

- **At the start of a task, read `memory/MEMORY.md`** (path at the end of this file) and
  open any file whose one-line hook looks relevant. Also read `projects/<repo>/MEMORY.md`
  when working inside that repo. Treat these as background that may be stale: verify file
  names, flags and paths before relying on them.
- **When you learn something durable** (a preference or correction, a decision or
  constraint not visible in the code, a pointer to an external resource), save it:

  ```markdown
  ---
  name: <short-kebab-case-slug>
  description: <one-line summary used to decide relevance>
  metadata:
    type: user | feedback | project | reference
  ---

  <the fact; for feedback/project add **Why:** and **How to apply:** lines>
  ```

  Then add one line to the matching `MEMORY.md`: `- [Title](file.md) — hook`.
  Update an existing file instead of creating a duplicate. Never store secrets.
- Sync runs automatically (hooks and a timer). To force it: `agent-memory-sync`.

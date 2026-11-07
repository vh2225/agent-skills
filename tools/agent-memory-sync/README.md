# agent-memory-sync

One memory store for Claude Code and Codex, shared across your machines through a **private** git repo.

- Claude Code keeps per-folder memory in `~/.claude/projects/<encoded path>/memory/`. This tool folds each of those into your memory repo and replaces it with a symlink, so Claude reads and writes the repo without knowing.
- Codex gets `~/.codex/AGENTS.md`, generated from `rules/shared.md` plus `rules/codex-memory.md`, which tells it to read and write the same memory files.
- Each run commits local changes, `pull --rebase`s, pushes, and regenerates the Codex file. It is idempotent, takes a lock, and always exits 0, so it is safe in hooks and timers. `MEMORY.md` uses git's union merge, so two machines adding index lines never conflict. When two machines have different files with the same name, the local copy is kept as `<name>.from-<host>.md` and flagged in the index for you to reconcile.

## Layout

| Memory repo path | Comes from |
|---|---|
| `memory/` | sessions started in your code folder (`AGENT_MEMORY_CODE_DIR`, default `~/github`) |
| `projects/home/` | sessions started in `~` |
| `projects/<name>/` | sessions started in `<code folder>/<name>` |
| `rules/shared.md` | your global rules, for both agents |
| `rules/codex-memory.md` | Codex-only memory instructions |

## Setup

1. Create a **private** repo for your memory (it will hold personal notes; never make it public). Clone it to `<code folder>/agent-memory` (or set `AGENT_MEMORY_DIR`).
2. Copy `template/.gitattributes` and `template/rules/` into it and commit.
3. Put `bin/agent-memory-sync` on your PATH and run it once. Existing memory folders are kept beside their new links as `memory.pre-sync.<timestamp>`.
4. Add `@<memory repo>/rules/shared.md` to `~/.claude/CLAUDE.md`.
5. Run it from Claude Code hooks (`SessionStart`, and `Stop` in the background) and a 10-minute timer (launchd or a systemd user timer). Back up your settings first.

Environment: `AGENT_MEMORY_CODE_DIR`, `AGENT_MEMORY_DIR`, `AGENT_MEMORY_HOST` (name used in commit messages and collision files).

Test: `bash tests/test_sync.sh` (simulates two machines sharing one remote).

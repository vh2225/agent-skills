# agent-skills

Skills, rules and small tools I use every day with Claude Code and Codex, cleaned up for anyone to reuse.

| Path | What it is |
|---|---|
| [`skills/product-demo-video`](skills/product-demo-video) | A Claude Code skill that records a real web app in Chrome and turns it into a narrated tutorial video (local AI voice, step labels, subtitles, 1080p mp4). |
| [`rules/safety.md`](rules/safety.md) | Guardrail rules for coding agents: destructive git, git identity, secrets, browser automation pitfalls. |
| [`rules/working-rules.md`](rules/working-rules.md) | Working habits: draft before send, re-decide on new information, sourced status answers, parking blocked work. |
| [`tools/agent-memory-sync`](tools/agent-memory-sync) | One memory store for Claude Code and Codex, synced across machines through a private git repo. |
| [`scripts/leak_guard.py`](scripts/leak_guard.py) | The scanner that keeps personal and organization data out of this repo (see [SECURITY.md](SECURITY.md)). |

## Use

- **Skill:** `cp -R skills/product-demo-video ~/.claude/skills/`, then follow its README.
- **Rules:** copy into `~/.claude/CLAUDE.md` or `~/.codex/AGENTS.md`, or import with `@<path>/rules/safety.md` in Claude Code. Edit freely; they are opinions.
- **Memory sync:** see its README. Keep the memory repo private.

## Contributing

Issues and pull requests are welcome. Every commit passes the leak guard locally and in CI.

## License

MIT, see [LICENSE](LICENSE).

# Safety rules for coding agents

Drop-in rules for Claude Code (`~/.claude/CLAUDE.md`, or import with `@path/to/safety.md`) and Codex (`~/.codex/AGENTS.md`). They explain the intent behind guardrails, so a blocked command gets clear handling instead of a retry loop.

## Opening files

When a file is finished (document, report, spreadsheet), ask before opening it. Never run `open` on it without a yes.

## Destructive git

Never run destructive git commands (`push --force`, `reset --hard`, `checkout .`, `restore .`, `clean -f`, `branch -D`) unless explicitly asked. Never skip hooks (`--no-verify`, `--no-gpg-sign`). Never force-push to `main` or `master`. Make new commits rather than amending, unless amending is explicitly requested.

## Git identity

Commit with plain `git commit`. Never pass `-c user.name=... -c user.email=...` or `--author`. The machine's git config is the source of truth; if a repo needs a different identity, set it in that repo's config (or with `includeIf`), not per command. An email the agent happens to know (for example the account it is signed in with) is not the user's commit identity, and commits authored with an unknown email are attributed to nobody on GitHub.

## Sensitive files

Never read, display, or include the contents of `.env` files, private keys, or credential files. If a task needs an environment value, ask the user for that specific value.

## External commands

Do not use `sudo`. Do not pipe `curl` or `wget` output into a shell. Do not change system-level configuration (`crontab`, `launchctl`, `defaults write`, systemd units) without explicit direction.

## Test-driven development

For a new feature, write a failing test first (red), then the minimum code to pass (green), then refactor. For a bug, first add a failing test that reproduces it. When refactoring, keep tests green; if a test encodes a detail you are changing, update it to assert the same user-facing intent. Never weaken or delete a test just to get green.

## Browser automation: look before concluding

When a browser action fails or a page seems broken, take a screenshot before forming any theory. Accessibility-tree reads and JS probes can report "element not found" or an empty body for a page that rendered fine, because they read a stale or pre-render snapshot. Never report a cause for a browser failure without having looked at the page.

Coordinates go stale when the window resizes or the layout shifts, and the automation tool's click frame can differ from the page's `window.innerWidth`. Take each click coordinate from a fresh screenshot, never reuse one across steps, and when a click seems to do nothing, suspect the coordinate frame before concluding the site is broken.

## Typing into web apps with keyboard shortcuts

Apps like webmail treat single keys as commands (archive, delete, report spam). If focus is not where you think, typed text fires shortcuts on whatever is open. Focus the editable element and insert text with one scripted call (for example `document.execCommand('insertText', ...)` on the focused `contenteditable`), then read the text back before going further. Confirm recipient chips exist before sending.

## Uploads of sensitive files

Never script drag-and-drop uploads of files that hold credentials or personal data. Drop targets can resolve to the row under the pointer (a shared folder) rather than the current view. Let the user upload those files by hand.

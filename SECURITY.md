# Security and leak prevention

This repo is public and is assembled from private working setups, so every change is checked for data that must not be published.

## Layers

1. **`scripts/leak_guard.py`** (run by the pre-commit and pre-push hooks and by CI):
   - generic rules: real-looking email addresses, private and CGNAT IP addresses, tailnet hostnames, personal home paths, secret-shaped strings;
   - a **private denylist** of names (people, organizations, products, places, hosts) kept outside the repo. Findings print only `denylist term #N`, never the term.
   - file names and commit messages are checked too.
2. **gitleaks** on staged changes (pre-commit) and the full history (pre-push, CI).
3. **Commit metadata:** the pre-push hook and CI reject any commit whose author or committer email is not a GitHub noreply address.
4. **GitHub:** secret scanning and push protection are enabled on the repository.

A reviewed false positive can be marked with `leak-guard: allow` on the same line.

## Setup after cloning

```
brew install gitleaks            # or your platform's package
git config core.hooksPath .githooks
git config user.email <id>+<user>@users.noreply.github.com
mkdir -p ~/.config/leak-guard && chmod 700 ~/.config/leak-guard
$EDITOR ~/.config/leak-guard/denylist.txt   # one private term per line, chmod 600
```

For CI, store the same list in a repository secret named `LEAK_GUARD_DENYLIST`.

## Reporting

If you find something here that looks like personal or private data, or a security problem, please open a private security advisory on this repository rather than a public issue.

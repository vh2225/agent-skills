# Security and leak prevention

This repo is public and is assembled from private working setups, so every change is checked for data that must not be published.

## Layers

1. **`scripts/leak_guard.py`**:
   - generic rules: real-looking email addresses, private, CGNAT and IPv6 private addresses, tailnet hostnames, personal home paths (macOS, Linux, Windows), secret-shaped strings;
   - a **private denylist** of names (people, organizations, products, places, hosts) kept outside the repo. Matching ignores case, full-width forms and invisible characters. Findings print only `denylist term #N`, and a path containing a term is printed redacted;
   - binary files are rejected unless reviewed and listed in `.leak-guard-binaries` (they are still searched for denylist terms and secret shapes);
   - `--history` mode checks every blob, path, commit message and author/committer name in all local refs, so content that was added and later removed is still caught.
2. **Hooks:** pre-commit runs the scanner on staged content plus gitleaks; pre-push runs `--history`, gitleaks over the full history, and rejects any commit email that is not a GitHub noreply address. Both refuse to pass without a non-empty private denylist.
3. **CI** runs the tests, the generic rules over the full history, gitleaks and the noreply check. The private denylist is deliberately not stored in GitHub (not even as a secret), so CI cannot check private terms; the local hooks do.
4. **GitHub:** secret scanning and push protection are enabled on the repository.

A reviewed generic false positive can be marked with `leak-guard: allow` on the same line. Denylist matches cannot be silenced inline.

Limits: the scanner reads text. It cannot see personal data inside images, audio or video, or in archives. Keep such files out of the repo.

## Setup after cloning

```
brew install gitleaks            # or your platform's package
git config core.hooksPath .githooks
git config user.email "YOUR_ID+YOUR_USER@users.noreply.github.com"
mkdir -p ~/.config/leak-guard && chmod 700 ~/.config/leak-guard
touch ~/.config/leak-guard/denylist.txt && chmod 600 ~/.config/leak-guard/denylist.txt
# then add one private term per line to that file
```

## Reporting

If you find something here that looks like personal or private data, or a security problem, please open a private security advisory on this repository rather than a public issue.

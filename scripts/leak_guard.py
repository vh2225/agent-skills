#!/usr/bin/env python3
"""leak-guard: block personal, organization and secret data from entering this public repo.

Two layers:
  1. Generic rules (in this file, public): real-looking emails, private/CGNAT/ULA IPs,
     tailnet hostnames, personal home paths, and common secret shapes.
  2. A PRIVATE denylist of names you never want published (people, companies,
     products, hostnames, places). It is read from LEAK_GUARD_DENYLIST (content)
     or LEAK_GUARD_DENYLIST_FILE (default ~/.config/leak-guard/denylist.txt) and is
     never stored in the repo. Findings never print a denylist term: matches show
     "denylist term #N", and a path containing a term is shown redacted.

Usage:
  leak_guard.py [--require-denylist] FILE...   scan files (paths relative to the repo root)
  leak_guard.py [--require-denylist] --staged  scan the git index (pre-commit)
  leak_guard.py [--require-denylist] --all     scan every tracked file
  leak_guard.py [--require-denylist] --history scan every blob, path, commit message and
                                                author/committer name in all local refs

Exit codes: 0 clean, 1 findings, 2 setup error.

A reviewed generic false positive can be silenced with "leak-guard: allow" on the same
line. Denylist matches can never be silenced inline. Binary files are rejected unless
their path is listed in .leak-guard-binaries (they are still searched for denylist terms
and secret shapes).
"""
import hashlib
import os
import re
import subprocess
import sys
import unicodedata

ALLOW_MARK = "leak-guard: allow"
BINARY_LIST = ".leak-guard-binaries"

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
EMAIL_OK = re.compile(
    r"(@((.+\.)?example\.(com|org|net)|users\.noreply\.github\.com|localhost)$)"
    r"|^(noreply@anthropic\.com|noreply@openai\.com|noreply@github\.com|git@github\.com)$",
    re.I,
)
IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")
IPV6_PRIVATE = re.compile(r"(?<![0-9A-Fa-f:])(f[cd][0-9a-f]{2}|fe80):[0-9a-f:]*", re.I)
TAILNET = re.compile(r"\b[\w-]+\.ts\.net\b", re.I)
HOME = re.compile(r"(/Users|/home)/([A-Za-z0-9._-]+)")
WIN_HOME = re.compile(r"\b[A-Za-z]:\\+Users\\+([A-Za-z0-9._ -]+)", re.I)
HOME_OK = {"you", "user", "username", "me", "name", "node", "runner", "ubuntu", "<you>", "<user>", "public", "default"}
SECRETS = [
    re.compile(r"\bghp_[A-Za-z0-9]{30,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{30,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
# zero-width and other invisible format characters used to split words
INVISIBLE = re.compile("[­᠎​-‏‪-‮⁠-⁤﻿]")


def normalize(s):
    return INVISIBLE.sub("", unicodedata.normalize("NFKC", s)).casefold()


def private_ip(m):
    a, b, c, d = (int(x) for x in m.groups())
    if max(a, b, c, d) > 255:
        return False
    return (
        a == 10
        or (a == 172 and 16 <= b <= 31)
        or (a == 192 and b == 168)
        or (a == 100 and 64 <= b <= 127)  # CGNAT, used by Tailscale
        or (a == 169 and b == 254)
    )


def load_denylist():
    text = os.environ.get("LEAK_GUARD_DENYLIST")
    if text is None:
        path = os.environ.get("LEAK_GUARD_DENYLIST_FILE", os.path.expanduser("~/.config/leak-guard/denylist.txt"))
        try:
            with open(path, encoding="utf-8") as f:
                text = f.read()
        except OSError:
            return None
    terms = [normalize(t.strip()) for t in text.splitlines()]
    return [t for t in terms if t and not t.startswith("#")]


def deny_hits(text, terms):
    low = normalize(text)
    return [f"denylist term #{i}" for i, t in enumerate(terms or [], 1) if t in low]


def generic_hits(line):
    if ALLOW_MARK in line:
        return []
    found = []
    for m in EMAIL.finditer(line):
        if not EMAIL_OK.search(m.group(0)):
            found.append("email")
    if any(private_ip(m) for m in IPV4.finditer(line)) or IPV6_PRIVATE.search(line):
        found.append("private-ip")
    if TAILNET.search(line):
        found.append("tailnet hostname")
    if any(m.group(2).lower() not in HOME_OK for m in HOME.finditer(line)):
        found.append("home-path")
    if any(m.group(1).strip().lower() not in HOME_OK for m in WIN_HOME.finditer(line)):
        found.append("home-path")
    if any(rx.search(line) for rx in SECRETS):
        found.append("secret-shaped string")
    return found


def secret_hits(text):
    return ["secret-shaped string"] if any(rx.search(text) for rx in SECRETS) else []


def display(name, terms):
    """A path safe to print: redacted if it contains a denylist term."""
    if deny_hits(name, terms):
        return "<path redacted:" + hashlib.sha256(name.encode()).hexdigest()[:8] + ">"
    return name


def reviewed_binaries():
    try:
        with open(BINARY_LIST, encoding="utf-8") as f:
            return {l.strip() for l in f if l.strip() and not l.startswith("#")}
    except OSError:
        return set()


def scan(name, data, terms, binaries):
    """Return [(line, rule)] for one file's path and content."""
    findings = [(0, r) for r in deny_hits(name, terms) + generic_hits(name)]
    if b"\x00" in data:
        if name not in binaries:
            findings.append((0, f"binary file (review it, then list its path in {BINARY_LIST})"))
        for enc in ("utf-8", "utf-16-le", "utf-16-be", "latin-1"):
            text = data.decode(enc, errors="ignore").replace("\x00", "\n")
            findings += [(0, r) for r in deny_hits(text, terms) + secret_hits(text)]
            for line in text.splitlines():
                findings += [(0, r) for r in generic_hits(line.replace(ALLOW_MARK, ""))]
        return sorted(set(findings))
    text = data.decode("utf-8", errors="replace")
    for n, line in enumerate(text.splitlines(), 1):
        findings += [(n, r) for r in deny_hits(line, terms) + generic_hits(line)]
    return findings


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def history_items():
    """Every blob reachable from any local ref (with its path), plus commit metadata."""
    items, seen = [], set()
    for line in git("rev-list", "--all", "--objects").decode("utf-8", "replace").splitlines():
        sha, _, path = line.partition(" ")
        if not path or sha in seen:
            continue
        seen.add(sha)
        if git("cat-file", "-t", sha).strip() != b"blob":
            items.append((path, b""))  # tree: check the directory name only
            continue
        items.append((path, git("cat-file", "blob", sha)))
    # every path that ever existed (rev-list names each object only once, so a renamed
    # file with unchanged content would otherwise hide its old name)
    paths = set()
    for commit in git("rev-list", "--all").decode().split():
        paths.update(git("ls-tree", "-r", "-t", "--name-only", "-z", commit).decode("utf-8", "replace").split("\0"))
    items += [(p, b"") for p in sorted(paths) if p]
    log = git("log", "--all", "--format=commit %h%n%an <%ae>%n%cn <%ce>%n%B%n")
    items.append(("(commit metadata)", log))
    refs = git("for-each-ref", "--format=%(refname)%0a%(taggername) %(taggeremail)%0a%(contents)")
    items.append(("(refs and tags)", refs))
    return items


def main(argv):
    require = "--require-denylist" in argv
    args = [a for a in argv if a != "--require-denylist"]
    terms = load_denylist()
    if not terms:
        msg = "leak-guard: no private denylist terms found (LEAK_GUARD_DENYLIST, LEAK_GUARD_DENYLIST_FILE or ~/.config/leak-guard/denylist.txt)"
        if require:
            print(msg + "; refusing to pass without it.", file=sys.stderr)
            return 2
        print(msg + "; running generic rules only.", file=sys.stderr)
        terms = []

    if args[:1] == ["--staged"]:
        names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0")
        items = [(n, git("show", f":{n}")) for n in names if n]
    elif args[:1] == ["--all"]:
        names = git("ls-files", "-z").decode().split("\0")
        items = []
        for n in names:
            if not (n and os.path.isfile(n)):
                continue
            try:
                with open(n, "rb") as f:
                    items.append((n, f.read()))
            except OSError as e:
                print(f"leak-guard: cannot read {display(n, terms)}: {e.strerror}", file=sys.stderr)
                return 2
    elif args[:1] == ["--history"]:
        items = history_items()
    else:
        items = []
        for p in args:
            rel = os.path.relpath(p)
            name = os.path.basename(p) if rel.startswith("..") else rel
            try:
                with open(p, "rb") as f:
                    items.append((name, f.read()))
            except OSError as e:
                print(f"leak-guard: cannot read {display(name, terms)}: {e.strerror}", file=sys.stderr)
                return 2

    binaries = reviewed_binaries()
    findings = []
    for name, data in items:
        findings += [(display(name, terms), n, r) for n, r in scan(name, data, terms, binaries)]
    for name, n, rule in findings:
        print(f"{name}:{n}: {rule}")
    if findings:
        print(f"leak-guard: {len(findings)} finding(s). Remove them, or mark a reviewed generic false positive with '{ALLOW_MARK}'.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except subprocess.CalledProcessError:
        # never print the failing command: its arguments can contain private paths
        print("leak-guard: a git command failed; run inside a git repository and retry.", file=sys.stderr)
        sys.exit(2)

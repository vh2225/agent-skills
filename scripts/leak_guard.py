#!/usr/bin/env python3
"""leak-guard: block personal, organization and secret data from entering this public repo.

Two layers:
  1. Generic rules (in this file, public): real-looking emails, private/CGNAT IPs,
     tailnet hostnames, personal home paths, and common secret shapes.
  2. A PRIVATE denylist of names you never want published (people, companies,
     products, hostnames, addresses). It is read from LEAK_GUARD_DENYLIST (content)
     or LEAK_GUARD_DENYLIST_FILE (default ~/.config/leak-guard/denylist.txt) and is
     never stored in the repo. Matches print only "denylist term #N", never the term.

Usage:
  leak_guard.py [--require-denylist] FILE...   scan files
  leak_guard.py [--require-denylist] --staged  scan the git index (pre-commit)
  leak_guard.py [--require-denylist] --all     scan every tracked file

Exit codes: 0 clean, 1 findings, 2 setup error.
Silence a reviewed false positive with "leak-guard: allow" on the same line.
"""
import os
import re
import subprocess
import sys

ALLOW_MARK = "leak-guard: allow"

EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@([A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
EMAIL_OK = re.compile(
    r"@((.+\.)?example\.(com|org|net)|users\.noreply\.github\.com|anthropic\.com|"
    r"openai\.com|localhost)$|^git@github\.com$|^noreply@github\.com$",
    re.I,
)
IPV4 = re.compile(r"(?<![\d.])(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})(?![\d.])")
TAILNET = re.compile(r"\b[\w-]+\.ts\.net\b", re.I)
HOME = re.compile(r"(/Users|/home)/([A-Za-z0-9._-]+)")
HOME_OK = {"you", "user", "username", "me", "name", "node", "runner", "ubuntu", "<you>", "<user>"}
SECRETS = [
    re.compile(r"\bghp_[A-Za-z0-9]{30,}"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{30,}"),
    re.compile(r"\bsk-(ant-)?[A-Za-z0-9_-]{30,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]


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
    terms = [t.strip().lower() for t in text.splitlines()]
    return [t for t in terms if t and not t.startswith("#")]


def check_line(line, terms):
    if ALLOW_MARK in line:
        return []
    found = []
    for m in EMAIL.finditer(line):
        if not EMAIL_OK.search(m.group(0)):
            found.append("email")
    for m in IPV4.finditer(line):
        if private_ip(m):
            found.append("private-ip")
    if TAILNET.search(line):
        found.append("tailnet hostname")
    for m in HOME.finditer(line):
        if m.group(2).lower() not in HOME_OK:
            found.append("home-path")
    for rx in SECRETS:
        if rx.search(line):
            found.append("secret-shaped string")
    low = line.lower()
    for i, t in enumerate(terms or [], 1):
        if t in low:
            found.append(f"denylist term #{i}")
    return found


def scan(name, data, terms):
    findings = []
    for rule in check_line(os.path.basename(name), terms):
        findings.append((name, 0, rule))
    if b"\x00" in data[:8000]:
        return findings  # binary
    text = data.decode("utf-8", errors="replace")
    for n, line in enumerate(text.splitlines(), 1):
        for rule in check_line(line, terms):
            findings.append((name, n, rule))
    return findings


def git(*args):
    return subprocess.run(["git", *args], capture_output=True, check=True).stdout


def main(argv):
    require = "--require-denylist" in argv
    args = [a for a in argv if a != "--require-denylist"]
    terms = load_denylist()
    if terms is None:
        msg = "leak-guard: no private denylist found (set LEAK_GUARD_DENYLIST_FILE or create ~/.config/leak-guard/denylist.txt)"
        if require:
            print(msg + "; refusing to pass without it.", file=sys.stderr)
            return 2
        print(msg + "; running generic rules only.", file=sys.stderr)

    items = []
    if args[:1] == ["--staged"]:
        names = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z").decode().split("\0")
        items = [(n, git("show", f":{n}")) for n in names if n]
    elif args[:1] == ["--all"]:
        names = git("ls-files", "-z").decode().split("\0")
        items = [(n, open(n, "rb").read()) for n in names if n and os.path.isfile(n)]
    else:
        items = [(p, open(p, "rb").read()) for p in args]

    findings = []
    for name, data in items:
        findings += scan(name, data, terms)
    for name, n, rule in findings:
        print(f"{name}:{n}: {rule}")
    if findings:
        print(f"leak-guard: {len(findings)} finding(s). Remove them, or mark a reviewed false positive with '{ALLOW_MARK}'.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

"""Tests for scripts/leak_guard.py. Run: python3 -m unittest discover -s tests"""
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "scripts", "leak_guard.py")


def scan(text, denylist=None, name="sample.md"):
    """Write text to a temp file, run the guard on it, return (exit_code, output)."""
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, name)
        with open(path, "w") as f:
            f.write(text)
        env = dict(os.environ)
        env.pop("LEAK_GUARD_DENYLIST", None)
        dl = os.path.join(d, "denylist.txt")
        with open(dl, "w") as f:
            f.write(denylist or "")
        env["LEAK_GUARD_DENYLIST_FILE"] = dl
        p = subprocess.run([sys.executable, GUARD, path], capture_output=True, text=True, env=env)
        return p.returncode, p.stdout + p.stderr


class Generic(unittest.TestCase):
    def assertFlags(self, text, rule=None):
        code, out = scan(text)
        self.assertEqual(code, 1, f"expected a finding for {text!r}, got: {out}")
        if rule:
            self.assertIn(rule, out)

    def assertClean(self, text):
        code, out = scan(text)
        self.assertEqual(code, 0, f"expected clean for {text!r}, got: {out}")

    def test_real_email_flagged(self):
        self.assertFlags("mail jane.doe@acme-corp.com today", "email")  # leak-guard: allow (test fixture)

    def test_placeholder_emails_allowed(self):
        self.assertClean("you@example.com, a@b.example.org, noreply@anthropic.com, 1+me@users.noreply.github.com")

    def test_private_ips_flagged(self):
        for ip in ["192.168.1.20", "10.0.4.7", "172.20.1.1", "100.101.102.103"]:  # leak-guard: allow (test fixture)
            self.assertFlags(f"host {ip}:22", "private-ip")

    def test_public_and_loopback_ips_allowed(self):
        self.assertClean("bind 127.0.0.1 or 0.0.0.0; dns 8.8.8.8; version 1.2.3.4")

    def test_tailnet_names_flagged(self):
        self.assertFlags("open http://box.tail1234.ts.net:3000", "tailnet")  # leak-guard: allow (test fixture)

    def test_home_paths_flagged(self):
        self.assertFlags("see /Users/jdoe/notes.md", "home-path")  # leak-guard: allow (test fixture)
        self.assertFlags("see /home/jdoe/notes.md", "home-path")  # leak-guard: allow (test fixture)

    def test_placeholder_home_paths_allowed(self):
        self.assertClean("see ~/notes.md, $HOME/x, /Users/you/x, /home/you/x, /home/node/work")

    def test_secret_shapes_flagged(self):
        for s in ["ghp_" + "a" * 36, "github_pat_" + "B" * 40, "sk-ant-" + "c" * 40,
                  "AKIA" + "ABCDEFGHIJKLMNOP", "xoxb-1234-5678-abcdefgh",  # leak-guard: allow (test fixture)
                  "-----BEGIN " + "OPENSSH PRIVATE KEY-----"]:  # leak-guard: allow (test fixture)
            self.assertFlags(f"token = {s}", "secret")

    def test_inline_allow(self):
        self.assertClean("ping 192.168.1.1  # leak-guard: allow (documented example)")


class Denylist(unittest.TestCase):
    def test_private_term_flagged_case_insensitive(self):
        code, out = scan("Deployed for MegaCorp internal", denylist="megacorp\n")
        self.assertEqual(code, 1, out)

    def test_term_itself_never_printed(self):
        code, out = scan("Secret project Bluebird here", denylist="# comment\nbluebird\n")
        self.assertEqual(code, 1, out)
        self.assertNotIn("bluebird", out.lower())
        self.assertIn("denylist", out)

    def test_comments_and_blanks_ignored(self):
        code, out = scan("nothing to see", denylist="# just a comment\n\n")
        self.assertEqual(code, 0, out)

    def test_denylist_from_env_content(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.md")
            open(path, "w").write("hello zanzibar")
            env = dict(os.environ, LEAK_GUARD_DENYLIST="zanzibar\n", LEAK_GUARD_DENYLIST_FILE=os.path.join(d, "missing"))
            p = subprocess.run([sys.executable, GUARD, path], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)

    def test_filename_checked_too(self):
        code, out = scan("clean body", denylist="bluebird\n", name="bluebird-notes.md")
        self.assertEqual(code, 1, out)


class Modes(unittest.TestCase):
    def test_binary_files_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "img.png")
            open(path, "wb").write(b"\x89PNG\x00\x00192.168.1.1")
            env = dict(os.environ, LEAK_GUARD_DENYLIST_FILE=os.path.join(d, "missing"))
            env.pop("LEAK_GUARD_DENYLIST", None)
            p = subprocess.run([sys.executable, GUARD, path], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_staged_mode_scans_index_content(self):
        with tempfile.TemporaryDirectory() as d:
            run = lambda *a: subprocess.run(a, cwd=d, capture_output=True, text=True)
            run("git", "init", "-q")
            open(os.path.join(d, "x.md"), "w").write("server 10.1.2.3\n")  # leak-guard: allow (test fixture)
            run("git", "add", "x.md")
            open(os.path.join(d, "x.md"), "w").write("clean now\n")  # working tree differs from index
            env = dict(os.environ, LEAK_GUARD_DENYLIST_FILE=os.path.join(d, "missing"))
            env.pop("LEAK_GUARD_DENYLIST", None)
            p = subprocess.run([sys.executable, GUARD, "--staged"], cwd=d, capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 1, p.stdout + p.stderr)

    def test_require_denylist_fails_when_missing(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "a.md"); open(path, "w").write("ok")
            env = dict(os.environ, LEAK_GUARD_DENYLIST_FILE=os.path.join(d, "missing"))
            env.pop("LEAK_GUARD_DENYLIST", None)
            p = subprocess.run([sys.executable, GUARD, "--require-denylist", path], capture_output=True, text=True, env=env)
            self.assertEqual(p.returncode, 2, p.stdout + p.stderr)


if __name__ == "__main__":
    unittest.main()

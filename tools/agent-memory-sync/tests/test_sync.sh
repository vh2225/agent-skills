#!/usr/bin/env bash
# Simulates two machines sharing one remote. Run: tests/test_sync.sh
set -u
HERE=$(cd "$(dirname "$0")/.." && pwd)
SYNC="$HERE/bin/agent-memory-sync"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
fail=0; ok(){ echo "ok   - $1"; }; bad(){ echo "FAIL - $1"; fail=1; }

git init -q --bare -b main "$T/remote.git"
git clone -q "$T/remote.git" "$T/seed" 2>/dev/null
mkdir -p "$T/seed/memory" "$T/seed/rules"
printf -- '- [A](a.md) — a\n' > "$T/seed/memory/MEMORY.md"; echo a > "$T/seed/memory/a.md"
echo "# Rules" > "$T/seed/rules/shared.md"
cp "$HERE/template/.gitattributes" "$T/seed/" 2>/dev/null
(cd "$T/seed" && git add -A && git -c user.name=t -c user.email=t@t commit -qm seed && git push -q origin main)

# machine = its own HOME with a clone and a Claude projects dir
enc(){ printf '%s' "$1" | sed 's/[^A-Za-z0-9]/-/g'; }
mk(){ local h="$T/$1" e; e=$(enc "$T/$1"); mkdir -p "$h/github" "$h/.codex" "$h/.claude/projects/$e-github/memory" "$h/.claude/projects/$e-github-proj/memory" "$h/.claude/projects/-tmp-scratch/memory"
  git clone -q "$T/remote.git" "$h/github/agent-memory"
  (cd "$h/github/agent-memory" && git config user.name "$1" && git config user.email "$1@t"); }
mk mac; mk nas
EM=$(enc "$T/mac"); EN=$(enc "$T/nas")
run(){ HOME="$T/$1" AGENT_MEMORY_HOST="$1" "$SYNC" >"$T/$1.log" 2>&1; }

# pre-existing local memory on the NAS, including a name collision
echo nas-only > "$T/nas/.claude/projects/$EN-github/memory/n.md"
echo different > "$T/nas/.claude/projects/$EN-github/memory/a.md"
printf -- '- [N](n.md) — n\n' > "$T/nas/.claude/projects/$EN-github/memory/MEMORY.md"

run mac; run nas; run mac
M=$T/mac/.claude/projects; N=$T/nas/.claude/projects
[ -L "$M/$EM-github/memory" ] && ok "main memory dir symlinked on mac" || bad "main memory dir symlinked on mac"
[ -L "$N/$EN-github-proj/memory" ] && ok "project memory dir symlinked on nas" || bad "project memory dir symlinked on nas"
[ ! -L "$M/-tmp-scratch/memory" ] && ok "scratch dirs left alone" || bad "scratch dirs left alone"
[ -f "$M/$EM-github/memory/n.md" ] && ok "nas memory reaches mac" || bad "nas memory reaches mac"
[ "$(cat "$M/$EM-github/memory/a.md")" = a ] && ok "collision keeps shared copy" || bad "collision keeps shared copy"
ls "$M/$EM-github/memory/" | grep -q '^a\.from-nas\.md$' && ok "collision preserves nas copy" || bad "collision preserves nas copy"
grep -q 'n.md' "$M/$EM-github/memory/MEMORY.md" && grep -q 'a.md' "$M/$EM-github/memory/MEMORY.md" && ok "MEMORY.md indexes merged" || bad "MEMORY.md indexes merged"

# concurrent index edits on both machines merge without conflict
echo b > "$M/$EM-github/memory/b.md"; printf -- '- [B](b.md) — b\n' >> "$M/$EM-github/memory/MEMORY.md"
echo c > "$N/$EN-github/memory/c.md"; printf -- '- [C](c.md) — c\n' >> "$N/$EN-github/memory/MEMORY.md"
run mac; run nas; run mac
grep -q 'b.md' "$N/$EN-github/memory/MEMORY.md" && grep -q 'c.md' "$M/$EM-github/memory/MEMORY.md" && ok "concurrent index edits merge" || bad "concurrent index edits merge"
[ -f "$M/$EM-github-proj/memory" ] || [ -d "$M/$EM-github-proj/memory" ] && ok "project dir resolvable" || bad "project dir resolvable"

# codex gets rules + memory protocol
grep -q '# Rules' "$T/mac/.codex/AGENTS.md" && grep -q 'github/agent-memory/memory/MEMORY.md' "$T/mac/.codex/AGENTS.md" && ok "codex AGENTS.md generated" || bad "codex AGENTS.md generated"

# idle run makes no commit
before=$(git -C "$T/mac/github/agent-memory" rev-list --count HEAD); run mac
[ "$before" = "$(git -C "$T/mac/github/agent-memory" rev-list --count HEAD)" ] && ok "idle sync makes no commit" || bad "idle sync makes no commit"

# code folder other than ~/github (AGENT_MEMORY_CODE_DIR)
mkdir -p "$T/alt/.codex"; git clone -q "$T/remote.git" "$T/alt/agent-memory"
EA=$(enc "$T/alt/code"); mkdir -p "$T/alt/.claude/projects/$EA/memory" "$T/alt/.claude/projects/$EA-web/memory"
echo alt > "$T/alt/.claude/projects/$EA-web/memory/w.md"
HOME="$T/alt" AGENT_MEMORY_HOST=alt AGENT_MEMORY_DIR="$T/alt/agent-memory" AGENT_MEMORY_CODE_DIR="$T/alt/code" "$SYNC" >"$T/alt.log" 2>&1
[ -L "$T/alt/.claude/projects/$EA/memory" ] && ok "custom code dir: main memory linked" || bad "custom code dir: main memory linked"
[ -f "$T/alt/agent-memory/projects/web/w.md" ] && ok "custom code dir: project memory folded in" || bad "custom code dir: project memory folded in"
grep -q "$T/alt/agent-memory/memory/MEMORY.md" "$T/alt/.codex/AGENTS.md" && ok "codex path follows AGENT_MEMORY_DIR" || bad "codex path follows AGENT_MEMORY_DIR"

# never fails the caller even when the remote is gone
mv "$T/remote.git" "$T/gone.git"; HOME="$T/mac" "$SYNC" >/dev/null 2>&1 && ok "offline sync exits 0" || bad "offline sync exits 0"
exit $fail

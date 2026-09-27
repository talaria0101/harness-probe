#!/bin/sh
# Stage 1 environment probe for a harness/cage. POSIX sh, no dependencies.
# Usage: sh probe.sh > probe-report.txt 2>&1
# Every check prints PASS/FAIL/DENIED plus captured evidence. Read the output
# before planning any tool attempts.

say() { printf '\n=== %s ===\n' "$1"; }

say "identity"
id 2>&1
echo "uid=$(id -u) cwd=$(pwd) date=$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
uname -a 2>&1

say "resource limits"
ulimit -a 2>&1

say "harness env vars"
env | grep -iE '^(PI_|CLAUDE|CODEX|OPENCODE|KIMI|KAGE|AGENT|MODEL|PROVIDER)' 2>/dev/null || echo "(none matched)"

say "native-looking binaries"
for b in rg fd fdfind grep find ls git jj gh node bun npx python3 pip3 cargo rustc \
         ast-grep sg jq curl wget pwsh powershell clangd rust-analyzer \
         typescript-language-server gopls pyright jdtls gdb lldb semgrep \
         crontab systemd-run script socat tar zip unzip file make cmake zig cc gcc; do
  p=$(command -v "$b" 2>/dev/null)
  if [ -n "$p" ]; then echo "OK     $b -> $p"; else echo "MISS   $b"; fi
done

say "network: outbound https"
code=$(curl -sS -o /dev/null -w '%{http_code}' --max-time 10 https://api.github.com 2>&1) \
  && echo "api.github.com -> HTTP $code" || echo "api.github.com FAILED: $code"
env | grep -i proxy || echo "(no proxy vars set)"

say "network: loopback bind (expect DENIED in cages)"
python3 - <<'EOF' 2>&1
import socket
s = socket.socket()
try:
    s.bind(('127.0.0.1', 0)); print("BIND OK (getsockname:", s.getsockname(), ")")
except OSError as e:
    print("BIND DENIED:", e)
s.close()
EOF

say "network: unix socket bind+listen"
python3 - <<'EOF' 2>&1
import socket, os, tempfile
p = os.path.join(tempfile.gettempdir(), f"probe-{os.getpid()}.sock")
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(p); s.listen(1)
    print("UNIX SOCK OK")
    s.close(); os.unlink(p)
except OSError as e:
    print("UNIX SOCK FAILED:", e)
EOF

say "network: stdio child pipe"
printf 'ping' | timeout 5 cat 2>&1 && echo " <- stdio roundtrip OK" || echo "stdio FAILED"

say "pty availability (expect absent in cages)"
python3 -c "import pty; pty.spawn(['true'])" 2>&1 | tail -1
ls -d /dev/pts 2>/dev/null || echo "/dev/pts absent"

say "processes: daemons (cron, etc)"
ps aux 2>/dev/null | grep -iE 'cron|atd|systemd' | grep -v grep || echo "(no cron/atd/systemd visible)"

say "dev tree: /dev/pts /proc/net /dev/shm /tmp writability"
ls -d /proc/net >/dev/null 2>&1 && echo "/proc/net OK" || echo "/proc/net MISSING"
df -h /tmp /dev/shm 2>/dev/null | tail -3
echo test > /tmp/probe-write && rm /tmp/probe-write && echo "/tmp writable"

say "toolchain smoke: does cc actually compile"
cat > /tmp/probe-t.c <<'EOF'
int main(void){return 42;}
EOF
if command -v cc >/dev/null 2>&1; then
  cc /tmp/probe-t.c -o /tmp/probe-t 2>/dev/null && /tmp/probe-t; echo "cc compile+run rc=$?"
else
  echo "(no cc)"
fi
rm -f /tmp/probe-t.c /tmp/probe-t

say "done"
echo "Add harness-specific checks below this line: session file format, RPC docs,"
echo "extension API on disk, registration array in source."

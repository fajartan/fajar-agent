#!/usr/bin/env sh
#  FAJAR-AGENT web installer (macOS / Linux).
#  Pakai:  curl -fsSL https://<HOST>/install.sh | sh
#  Setelah itu cukup ketik:  fajar
#  Ganti fajartan/fajar-agent (atau host sendiri) sebelum publikasi.
set -eu

REPO_RAW="${FAJAR_REPO:-https://raw.githubusercontent.com/fajartan/fajar-agent/main}"
DEST="${FAJAR_HOME:-$HOME/.fajar-agent}"
BIN="$HOME/.local/bin"

say() { printf "\033[33m==> %s\033[0m\n" "$1"; }

# 1) Python
PY=""
for c in python3 python; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -z "$PY" ] && { echo "[!] Python 3 tidak ada. Install dulu."; exit 1; }
say "Python: $PY"

# 2) unduh + ekstrak payload (self-extracting installer) ke $DEST
say "mengunduh FAJAR-AGENT -> $DEST"
mkdir -p "$DEST"
if command -v curl >/dev/null 2>&1; then curl -fsSL "$REPO_RAW/setup-bugbounty.sh" -o "$DEST/setup.sh";
elif command -v wget >/dev/null 2>&1; then wget -qO "$DEST/setup.sh" "$REPO_RAW/setup-bugbounty.sh";
else echo "[!] butuh curl atau wget"; exit 1; fi
( cd "$DEST" && sh setup.sh "$DEST" >/dev/null 2>&1 || bash setup.sh "$DEST" )

BB="$DEST/bb.py"
[ -f "$BB" ] || BB="$DEST/bugbounty-framework/bb.py"
[ -f "$BB" ] || { echo "[!] bb.py tak ketemu setelah ekstrak"; exit 1; }

# 3) dependensi TUI (best-effort)
"$PY" -m pip install --user --upgrade textual rich >/dev/null 2>&1 || \
"$PY" -m pip install --user --break-system-packages textual rich >/dev/null 2>&1 || true

# 4) launcher global 'fajar'
mkdir -p "$BIN"
cat > "$BIN/fajar" <<EOF
#!/usr/bin/env sh
exec "$PY" "$BB" "\$@"
EOF
chmod +x "$BIN/fajar"

# 5) pastikan ~/.local/bin di PATH
case ":$PATH:" in
  *":$BIN:"*) : ;;
  *) for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
       [ -f "$rc" ] && ! grep -q '.local/bin' "$rc" && printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc";
     done
     say "PATH ditambah ~/.local/bin (buka terminal baru)";;
esac

echo ""
say "SELESAI. Buka terminal baru, lalu ketik:  fajar"
echo "    fajar             # TUI FAJAR-AGENT"
echo "    fajar llm -i      # agent chat bertahap   |   fajar find   |   fajar telegram"

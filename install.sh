#!/usr/bin/env sh
#  FAJAR-AGENT web installer (macOS / Linux).
#  Pakai:  curl -fsSL https://raw.githubusercontent.com/fajartan/fajar-agent/main/install.sh | sh
#  Setelah itu cukup ketik:  fajar
set -eu

USER_REPO="${FAJAR_REPO:-fajartan/fajar-agent}"
BRANCH="${FAJAR_BRANCH:-main}"
DEST="${FAJAR_HOME:-$HOME/.fajar-agent}"
BIN="$HOME/.local/bin"
say() { printf "\033[33m==> %s\033[0m\n" "$1"; }

# 1) Python
PY=""
for c in python3 python; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -z "$PY" ] && { echo "[!] Python 3 tidak ada. Install dulu."; exit 1; }
say "Python: $PY"

# 2) unduh arsip repo (flat, tanpa folder bersarang) -> $DEST
say "mengunduh FAJAR-AGENT ($USER_REPO@$BRANCH) -> $DEST"
TMP="$(mktemp -d)"
URL="https://codeload.github.com/$USER_REPO/tar.gz/refs/heads/$BRANCH"
if command -v curl >/dev/null 2>&1; then curl -fsSL "$URL" -o "$TMP/src.tgz";
elif command -v wget >/dev/null 2>&1; then wget -qO "$TMP/src.tgz" "$URL";
else echo "[!] butuh curl atau wget"; exit 1; fi
mkdir -p "$DEST"
tar -xzf "$TMP/src.tgz" -C "$TMP"
SRC="$(find "$TMP" -maxdepth 1 -type d -name '*-*' | head -n1)"
[ -d "$SRC" ] || SRC="$TMP/$(ls "$TMP" | grep -v src.tgz | head -n1)"
cp -R "$SRC"/. "$DEST"/
rm -rf "$TMP"
[ -f "$DEST/bb.py" ] || { echo "[!] bb.py tak ketemu setelah unduh"; exit 1; }

# 3) dependensi TUI (best-effort)
"$PY" -m pip install --user --upgrade textual rich >/dev/null 2>&1 || \
"$PY" -m pip install --user --break-system-packages textual rich >/dev/null 2>&1 || true

# 4) launcher global 'fajar'
mkdir -p "$BIN"
cat > "$BIN/fajar" <<EOF
#!/usr/bin/env sh
exec "$PY" "$DEST/bb.py" "\$@"
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
echo "    fajar update      # (git pull bila di-clone) — atau jalankan installer lagi"

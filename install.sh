#!/usr/bin/env sh
#  FAJAR-AGENT web installer (macOS / Linux).
#  Pakai:  curl -fsSL https://raw.githubusercontent.com/fajartan/fajar-agent/main/install.sh | sh
#  Setelah itu cukup ketik:  fajar
set -eu

USER_REPO="${FAJAR_REPO:-fajartan/fajar-agent}"
BRANCH="${FAJAR_BRANCH:-main}"
DEST="${FAJAR_HOME:-$HOME/.fajar-agent}"
BIN="$HOME/.local/bin"
step() { printf "\r\033[K\033[33m==> %s\033[0m" "$1"; }   # satu baris, ditimpa tiap langkah
fail() { printf "\r\033[K\033[31m[!] %s\033[0m\n" "$1"; exit 1; }

# 1) Python
PY=""
for c in python3 python; do command -v "$c" >/dev/null 2>&1 && { PY="$c"; break; }; done
[ -z "$PY" ] && fail "Python 3 tidak ada. Install dulu."
step "[1/4] Python siap ($PY)"

# 2) unduh arsip repo -> DEST
step "[2/4] mengunduh FAJAR-AGENT..."
TMP="$(mktemp -d)"
URL="https://codeload.github.com/$USER_REPO/tar.gz/refs/heads/$BRANCH"
if command -v curl >/dev/null 2>&1; then curl -fsSL "$URL" -o "$TMP/src.tgz" || fail "gagal unduh (cek internet/DNS)";
elif command -v wget >/dev/null 2>&1; then wget -qO "$TMP/src.tgz" "$URL" || fail "gagal unduh (cek internet/DNS)";
else fail "butuh curl atau wget"; fi

# 3) ekstrak + pasang
step "[3/4] memasang berkas..."
mkdir -p "$DEST"
tar -xzf "$TMP/src.tgz" -C "$TMP"
SRC="$(find "$TMP" -maxdepth 1 -type d -name '*-*' | head -n1)"
[ -d "$SRC" ] || SRC="$TMP/$(ls "$TMP" | grep -v src.tgz | head -n1)"
cp -R "$SRC"/. "$DEST"/
rm -rf "$TMP"
[ -f "$DEST/bb.py" ] || fail "bb.py tak ketemu setelah unduh"

# 4) dependensi + launcher
step "[4/4] dependensi (textual) & perintah 'fajar'..."
"$PY" -m pip install --user --upgrade textual rich >/dev/null 2>&1 || \
"$PY" -m pip install --user --break-system-packages textual rich >/dev/null 2>&1 || true
mkdir -p "$BIN"
cat > "$BIN/fajar" <<EOF
#!/usr/bin/env sh
exec "$PY" "$DEST/bb.py" "\$@"
EOF
chmod +x "$BIN/fajar"
PATHNOTE=""
case ":$PATH:" in
  *":$BIN:"*) : ;;
  *) for rc in "$HOME/.bashrc" "$HOME/.zshrc" "$HOME/.profile"; do
       [ -f "$rc" ] && ! grep -q '.local/bin' "$rc" && printf '\nexport PATH="$HOME/.local/bin:$PATH"\n' >> "$rc";
     done
     PATHNOTE=" (buka terminal baru dulu)";;
esac

# --- selesai: HAPUS baris proses, tampilkan hasil akhir saja (bersih) ---
printf "\r\033[K"
printf "\033[32m✓ FAJAR-AGENT terpasang\033[0m di %s\n" "$DEST"
printf "  Ketik:  \033[1mfajar\033[0m%s\n" "$PATHNOTE"
printf "  \033[2mfajar llm -i · fajar find · fajar telegram · fajar update · fajar --version\033[0m\n"

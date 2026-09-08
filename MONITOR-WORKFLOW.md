# MONITOR-WORKFLOW — Pencari Target Harian (otonom, tuas WHEN)
### Dokumen pendamping #13 dari FRAMEWORK-BUGBOUNTY-AI.md
Cara pakar menemukan target **tiap hari secara otomatis**: mesin menarik data → AI ranking → manusia memutuskan. Ini operasionalisasi tuas **WHEN** ([[ANTI-DUP-PLAYBOOK]]) — jadi yang **pertama** di program/aset baru = anti-dupe paling ampuh. Tool: `tools/daily-target-finder.py`.

---

## 1. Apa yang dilakukan
`daily-target-finder.py` menarik dataset **arkadiyt/bounty-targets-data** (scope harian H1/Bugcrowd/YesWeHack), memfilter **berbayar + wildcard**, lalu **diff vs kemarin** untuk mendeteksi:
- **PROGRAM BARU** (belum ada kemarin) — prioritas #1.
- **ASET BARU** ditambahkan ke scope program lama (scope change) — prioritas #2.
Output: `<OUT>/YYYY-MM-DD.md`, `latest.md`, `latest.json` — dibaca AI tiap pagi.

Contoh nyata (uji 2026-09-08): mendeteksi program baru *Anduril*, *Wolt* + scope-change *Twilio* (`*.sip.*.twilio.com`).

## 2. Cara pakai (di Linux)
```bash
# sekali jalan (run pertama = baseline; besok baru muncul yg baru)
python3 tools/daily-target-finder.py
cat ~/bb-targets/latest.md
```
Konfigurasi lewat env (opsional):
```bash
export BBTF_OUT=~/bb-targets                 # folder output
export BBTF_PLATFORMS=hackerone,bugcrowd,yeswehack
export BBTF_WILDCARD=1                        # 1=wajib wildcard, 0=semua
export BBTF_MIN_BOUNTY=0                      # mis. 500 utk saring bounty kecil
```

## 3. Jadwalkan harian (cron)
```bash
crontab -e
# jalan tiap pagi 08:00, log ke file
0 8 * * * BBTF_OUT=$HOME/bb-targets /usr/bin/python3 $HOME/bugbounty-framework/tools/daily-target-finder.py >> $HOME/bb-targets/run.log 2>&1
```
> Butuh: python3 (stdlib saja) + internet. Tidak menyentuh target — hanya baca dataset publik.

## 4. Loop harian AI (yang bikin "otonom")
Tiap pagi, beri AI perintah singkat:
```
Baca ~/bb-targets/latest.md. Ranking PROGRAM BARU + SCOPE CHANGE pakai EXPERT-TACTICS + ANTI-DUP:
buang recon-findable & brand ramai; utamakan niche + butuh-pemahaman + wildcard. 
Sarankan top-3 + alasan. Untuk #1, siapkan langkah SCOPE-GATE (aku tempel policy-nya).
```
AI = lapisan **filter/rank/brief**; keputusan & hunting tetap di 3 GATE ([[AUTONOMOUS-OPERATOR]]).

## 5. (Opsional) Kirim notifikasi Telegram/Discord
Pakai `notify` (ProjectDiscovery) atau curl webhook:
```bash
# contoh Discord webhook (ringkas hasil)
python3 tools/daily-target-finder.py
head -40 ~/bb-targets/latest.md | curl -s -F "file=@-;filename=targets.md" <DISCORD_WEBHOOK_URL>
```

## 5b. TUI interaktif (`bbtui.py`) — full-screen modern (Textual)
TUI full-screen: splash banner → dashboard + tabel program berbingkai + panel detail scope + run-log live.
```bash
pip install --user --break-system-packages textual   # (atau apt install python3-textual)
python3 tools/bbtui.py
```
**Keybindings:** `↑/↓` pindah · `/` cari · `r` refresh · `s` settings (kriteria: platform/min-bounty/wildcard + provider enrichment) · `?` bantuan · `q` keluar.
**Aksi tool pada program tersorot (target auto-terisi, bisa diedit/ketik manual):**
- `e` **Recon** — pilih profil: passive / **standard (extract web: httpx+katana+JS+endpoint)** / deep → hasil ~/bb-recon/
- `m` **Monitor** — subdomain baru → ~/bb-monitor/
- `d` **Dedup** — kelas bug yang sudah dilaporkan → known-issues.md
Fitur lain: search nama/scope, detail scope lengkap (data recon), enrichment (jina gratis/firecrawl/serper/h1api).
- **Mode TANPA API key (default):** semua browse/search/detail jalan penuh dari dataset gratis. Enrichment pakai **`jina`** (r.jina.ai) yang **GRATIS tanpa key**.
- **Mode DENGAN API key (opsional, untuk launch/total-paid/#reports):** pilih provider di Settings —
  `firecrawl` (freemium), `scraperapi` / `scrapingbee` (murah, free tier), `serper` (search murah), `h1api` (GRATIS resmi HackerOne, butuh user+token, khusus H1).
- API key disimpan lokal di `~/.config/bbtui/config.json` (chmod 600), tidak pernah dibagikan.
- Enrichment = best-effort (scrape/parse halaman) untuk data yang tak ada di dataset (launch/paid/#reports); tetap verifikasi di halaman program.

## 5c. Tool pendukung rangkaian (di `tools/`)
Menutup loop find → recon → dedup → hunt:
- **`asset-monitor.py`** — pantau **subdomain BARU** pada target terpilih (pasif: crt.sh + subfinder), diff harian → uji duluan (tuas WHEN level aset, paling anti-dupe). Cron: `0 9 * * * python3 tools/asset-monitor.py <domain>`.
- **`recon.py`** — orkestrasi recon pasif/ringan (subfinder→gau→httpx→katana→jsleak→gf) ke `<out>/<domain>/recon/` + `summary.md`. `--passive` = hanya sumber pasif. ⚠️ httpx/katana mengirim ke target → pastikan in-scope & scanning diizinkan.
- **`dedup.py`** — otomasi DEDUP-GATE: tarik disclosed reports (jina gratis / serper) → ringkas kelas bug yang sudah RAMAI vs area perawan. `python3 tools/dedup.py <handle>`. Best-effort (prior report privat tak terlihat) → gabung dengan strategi WHERE/WHEN.

## 6. Catatan jujur
- **Run pertama = baseline** (belum ada "baru"); nilai muncul mulai hari ke-2. Konsistensi harian = kuncinya.
- Dataset tidak punya "jumlah hunter". Proxy "sepi" = **program baru + aset baru** (fresh). Tetap **verifikasi di platform** (Hacktivity/resolved) sebelum commit.
- Dataset update ~harian; kalau sumber down, script lapor error & tetap simpan yang berhasil.
- Ini **penemuan target**, bukan exploitasi. Hunting mengikuti FRAMEWORK + 3 GATE.

Terkait: [[ANTI-DUP-PLAYBOOK]] (WHERE/WHEN) · [[PROGRAM-SELECTION]] · [[EXPERT-TACTICS]] · [[AUTONOMOUS-OPERATOR]] · [[AI-OPERATING-RULES]]

# ANTI-DUP-PLAYBOOK — Menghindari Duplikat
### Dokumen pendamping #6 dari FRAMEWORK-BUGBOUNTY-AI.md
Duplikat = temuan benar tapi **telat** (bukan invalid). Pemula sering 40–60% dup; target ≤~21%. Ini alur AI membantu menekan dup (FRAMEWORK Bab 5). AI menganalisa data; manusia mengeksekusi akses ([[AI-OPERATING-RULES]] Bab 1).

---

## DEDUP-GATE (WAJIB — jalankan SEBELUM recon & sebelum submit)
Ini gerbang keras. Agen/AI tidak boleh lanjut ke recon berat atau submit tanpa lulus gate ini.

**Sebelum mulai target:**
1. Tarik **disclosed reports / Hacktivity** program → daftar **kelas bug + endpoint yang SUDAH dilaporkan**.
2. Pilih **surface laporan-rendah / fitur baru** (mis. Whatnot: `api`=0, `auction`/`live`=1). Hindari surface ramai.
3. Simpan ke `recon/known-issues.md`.

**Sebelum mengerjakan tiap hipotesis — NOVELTY SCORE (butuh ≥7/10 baru lanjut):**
| + poin | Kriteria |
|---|---|
| +3 | Surface perawan / fitur baru (laporan 0–1, changelog terbaru) |
| +2 | Butuh kedalaman (authz-depth, business logic, multi-step) — bukan bug obvious |
| +2 | Ada chain (low→high) atau impact di atas temuan mentah |
| +1 | Endpoint tidak ada di JS publik / tidak terlihat di UI |
| +1 | Klien lain (mobile/legacy API) yang beda dari web |
| +1 | Tidak muncul di disclosed reports |
| −3 | Bug obvious di surface ramai (login IDOR profil, CSRF email, XSS search) |
| −3 | Murni output scanner (nuclei/generic) tanpa analisa |
Skor <7 → **jangan kerjakan / jangan submit** (calon dupe). Skor ≥7 → lanjut.

## DIAGNOSA: kenapa 3 laporan berturut dupe? (isi jujur)
Centang yang benar untuk tiap laporan dupe-mu:
- [ ] Bug **obvious** (login/IDOR profil/CSRF email/XSS search) → semua orang tes ini duluan.
- [ ] Surface **ramai** (www/brand utama) bukan API/service perawan.
- [ ] **Tidak cek disclosed/hacktivity** sebelum tes.
- [ ] **Lambat** — tes fitur lama, bukan fitur baru yang baru rilis.
- [ ] **Dangkal** — berhenti di temuan mentah, tidak digali jadi chain/impact unik.
→ **Tindakan wajib:** pindah ke surface novelty ≥7 (perawan + kedalaman + chain). Untuk kasusmu sekarang: fokus `api.whatnot.com` / `auction-service` / `live-service`, tipe bug **authz-depth / business-logic bidding**, bukan bug generik.

## HEURISTIK "RECON-FINDABLE = RISIKO DUPE TINGGI" (dari 5 dupe lapangan)
Bukti nyata: 5 laporan valid → SEMUA dupe (2 kalah 7 & 39 hari; prior report **PRIVAT**, tak terlihat). Pelajaran keras:
- Bug yang ketemu lewat **langkah standar** (curl SAML/metadata, hit 1 endpoint, enum ID berurutan, output nuclei mentah) = **ratusan hunter lain juga nemu** → hampir pasti dupe di program matang.
- **DEDUP-by-hacktivity TIDAK cukup** — prior report sering privat, jadi "cek disclosed dulu" tak menyelamatkan; harus dicegah lewat pemilihan surface.

**Skor recon-findability tiap temuan (sebelum kerjakan/lapor):**
- Ketemu dalam **<3 langkah standar** DAN aset lama/matang → **STOP** (asumsikan sudah ada).
- **Layak lanjut hanya jika:** (a) aset/fitur **BARU** (berpotensi kamu pertama), ATAU (b) butuh **kedalaman/chain/pemahaman alur** (bukan one-shot).

## 3 TUAS ANTI-DUPE (WHERE / WHAT / WHEN)
- **WHERE** — pindah dari program besar-publik-matang ke **program baru/kecil / VDP hall-of-fame kecil / private invite**. Sedikit hunter = bug recon-findable masih perawan.
- **WHAT** — berhenti di bug recon-findable; kejar **chain multi-langkah & business logic** yang butuh pemahaman (tool & hunter cepat melewatkannya).
- **WHEN** — jadi **PERTAMA** di aset/fitur baru: monitor perubahan scope/subdomain/fitur, uji dalam **jam**, bukan minggu.

---

## Langkah 1 — Riset "sudah ditemukan" SEBELUM menguji area umum
- Kumpulkan sinyal publik: disclosed reports/hacktivity program, changelog/blog rilis fitur, CVE terkait tech-stack, writeup publik target.
- (Jika perlu web) minta manusia jalankan / gunakan tool web yang tersedia untuk menarik daftar disclosed reports program. AI merangkum jadi **peta "sudah ditemukan"**.
- Output: file `recon/known-issues.md` berisi: kelas bug yang sudah dilaporkan, endpoint/fitur yang sudah ramai, tanggal, pola.

## Langkah 2 — Petakan "zona ramai" vs "zona perawan"
| Zona ramai (hindari kecuali fitur baru) | Zona perawan (prioritaskan) |
|---|---|
| Login bypass, IDOR profil user, CSRF email change, XSS search | Fitur baru/terbaru (changelog), API service/mobile/legacy |
| Bug obvious di endpoint utama | Fungsi tak populer, authz-depth, business logic |
| Payload generik di form umum | Chain low→high, field yang jarang diuji |

## Langkah 3 — Taktik anti-dup (FRAMEWORK Bab 5 & 13)
1. **Cek disclosed reports dulu** → jangan ulang yang sudah ada.
2. **Kejar fitur baru** segera: monitor subdomain baru, title/status/tech baru, changelog. "Yang berubah sejak kemarin" > surface lama ramai.
3. **Masuk lebih dalam** ke fungsi tak populer; **chain** beberapa low→high (unik, jarang dup).
4. **Cek klien lain:** mobile/legacy API sering simpan alur lama yang web sudah di-harden; feature flag berbeda.
5. **Authz-depth:** matriks aktor×aksi mengungkap kombinasi yang tak pernah didemo (jarang dilaporkan).
6. **Pilih program kompetisi rendah / scope jelas / fitur banyak** ([[PROGRAM-SELECTION]]).

## Langkah 4 — Gate per kandidat report (isi sebelum lapor)
```
KANDIDAT: <ID hipotesis> — <kelas bug> @ <endpoint>
- Sudah ada di disclosed/known-issues? : tidak / ya(<link>) → jika ya: STOP atau cari angle impact lebih kuat
- Area ini "obvious/ramai"? : ya/tidak → jika ya: apakah di FITUR BARU? kalau bukan, risiko dup tinggi
- Bisa dinaikkan jadi chain/impact unik? : <ide>
- Endpoint sejenis sudah diuji (isu sistemik)? : <daftar>
- Verdict: lanjut lapor / perdalam dulu / drop
```

## Langkah 5 — Jika tetap kena duplikat (after-action)
Catat di [[LEARNING-LOG]]: kenapa telat? area terlalu obvious? lambat lapor? program terlalu ramai? → sesuaikan pemilihan target & kecepatan. Duplikat pun mengajarkan pola target.

Terkait: [[FRAMEWORK-BUGBOUNTY-AI]] Bab 5/13 · [[PROGRAM-SELECTION]] · [[LEARNING-LOG]] · [[REPORT-KIT]]

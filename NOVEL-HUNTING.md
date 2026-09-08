# NOVEL-HUNTING — Berburu Bug Tidak Umum
### Dokumen pendamping #11 dari FRAMEWORK-BUGBOUNTY-AI.md
Tujuan: mengarahkan AI/agen mencari bug yang **jarang ditemukan orang** — bukan bug umum yang berisiko duplikat. Ini **strategi positif** pelengkap [[ANTI-DUP-PLAYBOOK]] (yang berisi gate/filter). Lahir dari fakta lapangan: 5 laporan valid user semuanya dupe karena bug-nya **umum / recon-findable**.

---

## 1. Prinsip inti
- **Bug umum = mudah ditemukan = ratusan hunter menemukannya = dupe.**
- **Bug tidak-umum = butuh pemahaman / urutan / kombinasi = sedikit yang menemukannya = valid.**
- Aturan emas: **kalau bug bisa ditemukan TANPA memahami produk** (satu langkah, output scanner, curl endpoint) → asumsikan sudah ada, **skip** (di aset matang).

## 2. Taksonomi: HINDARI (umum) vs KEJAR (tidak umum)
| Kelas | Bentuk UMUM (risiko dupe — hindari) | Bentuk TIDAK UMUM (kejar) |
|---|---|---|
| XSS | reflected di search param | DOM XSS via postMessage/chain, stored di alur multi-step, XSS di fitur BARU |
| IDOR | read profil/order by id berurutan | **write/state-change** cross-tenant; IDOR di langkah ke-3 workflow; objek di export/webhook/async job |
| Auth | `alg:none`, missing-auth 1 endpoint | race di reset/checkout, OAuth code-binding, 2FA state edge, rotasi sesi setelah privilege change |
| SSRF | `url=` → metadata | SSRF via redirect/DNS-rebind di importer; blind SSRF via webhook sekunder |
| Info disc | versi/path/username (sering Informative) | secret/token/**cross-tenant data** yang benar-benar sensitif |
| Business logic | coupon reuse | **chain multi-fitur**, urutan state aneh, interaksi 2 fitur, manipulasi uang/payout |
| Config | test cert / header hilang (recon-findable) | hanya layak kalau aset **BARU** |

## 3. Di mana bug tidak-umum tinggal
1. **Business logic & state machine** — urutan aksi yang tak diniatkan bisnis.
2. **Chain** — low + low → high (open-redirect→SSRF, IDOR→ATO, XSS→RCE).
3. **Second-order / data-flow** — input disimpan lalu dipakai ulang di tempat lain.
4. **Interaksi antar-fitur** — fitur A memengaruhi fitur B (mis. invite ↔ billing ↔ role).
5. **Edge-case auth/session/tenant** — removed user, revoked invite, cross-tenant depth.
6. **Fitur BARU / undocumented / mobile-legacy** — belum banyak diuji.
7. **Async / webhook / export / background job** — sering luput authz.
8. **GraphQL mutation authz depth** — field nested & mutation tersembunyi.

## 4. Cara menemukannya (BUKAN scanning)
- Pahami produk seperti **user + developer**: petakan workflow, state, role, objek, uang.
- Untuk tiap *value*: aturan apa yang melindunginya? siapa boleh? berapa kali? urutan apa yang diasumsikan? apa berubah sesudahnya?
- Uji **kombinasi yang tak pernah didemo** (matriks role × aksi × state).
- Lakukan aksi di **urutan aneh**; ulangi; batalkan di tengah; jalankan **paralel** (race).
- Lacak data dari **input → simpan → dipakai ulang** (second-order).
- Bandingkan **klien berbeda** (web vs mobile vs API lama) — asumsi sering beda.

## 5. Filter sebelum dikerjakan (gabung dengan ANTI-DUP)
```
Recon-findable (ketemu <3 langkah standar, aset matang)? -> SKIP
Butuh pemahaman/urutan/kombinasi/chain?                  -> KANDIDAT BAGUS
Novelty score >=7 (ANTI-DUP)?                             -> LANJUT
Aset/fitur BARU?                                          -> boleh walau agak umum (berpotensi pertama)
```

## 6. Untuk agen otonom (wajib)
Di FASE 4, agen **WAJIB**:
- Prioritaskan hipotesis dari kategori "tidak umum" (§2 kolom kanan, §3).
- **Turunkan/buang** hipotesis recon-findable di aset matang.
- Jika **semua** hipotesis di sebuah surface adalah recon-findable & aset matang → **berhenti & lapor ke manusia**: "surface ini kemungkinan sudah dipetakan; saran: pindah (WHERE) atau perdalam ke business-logic/chain (WHAT)."
- Setiap kandidat report harus lolos: **tidak recon-findable + novelty ≥7 + impact nyata**.

> Ringkas: **jangan cari yang gampang & rame. Cari yang butuh mikir.** Itu yang tidak dupe.

Terkait: [[ANTI-DUP-PLAYBOOK]] · [[AUTONOMOUS-OPERATOR]] · [[VERIFY-BEFORE-SUBMIT]] · [[FRAMEWORK-BUGBOUNTY-AI]] Bab 4/6

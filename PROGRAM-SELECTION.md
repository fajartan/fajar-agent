# PROGRAM-SELECTION — Memilih Program & Target
### Dokumen pendamping #9 dari FRAMEWORK-BUGBOUNTY-AI.md
Pemilihan target = separuh kemenangan (FRAMEWORK Bab 3-Day 4, Bab 5). Baca scope dulu, bukan tabel bounty. Tujuan awal bukan bug terbesar, tapi memahami satu aplikasi nyata dengan baik.

---

## Kriteria pilih program (skor tiap kandidat)
| Kriteria | Bagus (nilai tinggi) | Hindari |
|---|---|---|
| Scope | jelas, wildcard/luas, banyak fitur | kabur/sempit |
| Kompetisi | program baru / kurang populer / service API perawan | brand terkenal, ribuan hunter |
| Triage | responsif, komunikasi hormat, contoh dipublikasi | lambat, sepi |
| Duplicate rate | rendah | 90%+ |
| Akses | akun tes bisa dibuat tanpa approval lama | butuh approval berbelit |
| Fitur bernilai | users, roles, files, billing, invite, settings | statis/minim fitur |
| Aturan | larangan jelas & bisa dipatuhi | melarang hampir semua teknik |

## Sinyal kualitas (dari buku)
- Respons terbaru, out-of-scope jelas, contoh laporan, komunikasi hormat.
- Jika melarang automated scanning / DoS / social engineering / testing production payment → itu **mendefinisikan rencana tes**, bukan alasan melanggar.

## Target yang ramah pembelajaran
Marketplace, collaboration tools, education, SaaS dashboard — karena punya users, roles, files, billing, invitations, settings (banyak trust boundary & authz edge).

## Alur seleksi (untuk AI)
```
1. tarik daftar kandidat (platform) + baca scope masing-masing
2. skor pakai tabel di atas → shortlist 1-3
3. cek disclosed reports (ANTI-DUP) → zona ramai vs perawan
4. cek tech-stack (FRAMEWORK Bab 11) → cocok dgn kekuatan/spesialisasi?
5. NahamSec: pilih SATU program, ~10 hari pahami cara kerjanya, get good on 1 bug
6. buat TARGET-WORKSPACE, isi scope.md, jalankan SCOPE-GATE
```

## Spesialisasi (setelah fondasi)
API/GraphQL, mobile, cloud, business-logic → kompetisi lebih rendah dari generalis web app. Pilih yang kamu nikmati & sering berhasil (FRAMEWORK Bab 12).

## Catatan target aktif (isi)
| Target | Platform | Scope | Kompetisi | Alasan pilih | Status |
|---|---|---|---|---|---|
| <mis. Whatnot> | H1 | <...> | rendah (API perawan) | <...> | riset/aktif |

Terkait: [[FRAMEWORK-BUGBOUNTY-AI]] Bab 3/5/11/12 · [[ANTI-DUP-PLAYBOOK]] · [[TARGET-WORKSPACE]] · [[LEARNING-LOG]]

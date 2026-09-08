# VERIFY-BEFORE-SUBMIT — Gerbang Verifikasi
### Dokumen pendamping #7 dari FRAMEWORK-BUGBOUNTY-AI.md
Sebelum laporan disubmit, AI **wajib** menjalankan pass ini sebagai **triager skeptis (adversarial)**. Tujuan: bunuh false-positive & halusinasi ([[AI-OPERATING-RULES]] Bab 3). Jika ada item GAGAL → jangan lanjut submit; perbaiki atau drop.

---

## A. Realitas & bukti (anti-halusinasi)
- [ ] Setiap klaim teknis punya **artefak nyata** (req/resp/screenshot/tool output), bukan ingatan. Label [FAKTA] terverifikasi.
- [ ] Endpoint/parameter/versi/CVE yang disebut benar-benar ada di artefak (tidak dikarang).
- [ ] Bukan sekadar 1 anomali: ada **baseline vs perilaku berubah** yang direproduksi.
- [ ] PoC sudah **direproduksi manusia**, bukan disalin dari template.

## B. Impact benar-benar ada (bukan "secara teori")
- [ ] Menyeberang trust boundary nyata (data/aksi milik pihak lain, atau privilege naik) — bukan data yang memang publik/intended.
- [ ] Bisa dieksploitasi tanpa syarat tak realistis (bukan butuh social engineering berat / akses fisik / self-only).
- [ ] Contoh lawan: reflected XSS butuh korban klik? info disclosure benar sensitif? IDOR mengembalikan data privat, bukan profil publik?
- [ ] **FILTER IMPACT-CLASS (wajib):** kelas data/aksi ini BUKAN yang sudah diputus program sebagai **Informative / non-sensitif**. Cek disclosed/hacktivity program. Contoh lapangan: Whatnot memutuskan buyer username & user ID = **non-sensitif** → seluruh kelas "GraphQL leak username/ID" jadi Informative, konsisten. Jika kelas temuanmu sudah "mati" di program ini (pernah diputus Informative) → **jangan submit**, ganti kelas/impact.
- [ ] **FILTER RECON-FINDABLE (wajib):** temuan ini BUKAN tipe yang ketemu dalam <3 langkah standar di aset matang (lihat [[ANTI-DUP-PLAYBOOK]]). Jika recon-findable & aset lama → risiko dupe tinggi → jangan submit kecuali aset baru/ada kedalaman.

## C. Skeptic pass (mainkan peran triager yang menolak)
Tanyakan dan jawab jujur:
- "Kenapa ini BUKAN bug / bukan impact?" → jika ada jawaban kuat, tangani atau drop.
- "Apakah ini accepted risk / defense-in-depth / by-design?"
- "Apakah severity terlalu tinggi untuk impact nyata?" (kalibrasi ke [[REPORT-KIT]] CVSS)
- "2-click atau butuh interaksi berlebih?" (sering ditolak)

## D. Scope, dedup, etika
- [ ] SCOPE-GATE PASS (aset in-scope, tidak melanggar prohibited) — [[AI-OPERATING-RULES]] Bab 2.
- [ ] Anti-dup dicek ([[ANTI-DUP-PLAYBOOK]] gate per kandidat).
- [ ] Hanya akun sendiri; tidak ada data user asli yang disentuh/disimpan; PII diredaksi.
- [ ] Tidak ada aksi destruktif/DoS; PoC minimal (mis. shell dihapus, tidak dump baris).

## E. Kualitas laporan
- [ ] Steps to Reproduce bisa diikuti orang lain tanpa menebak (sebut akun userA/userB).
- [ ] Impact dinyatakan konkret & tidak dilebih-lebihkan.
- [ ] Remediation praktis disertakan; severity/CVSS wajar & vektor ditulis.
- [ ] Sudah dinaikkan impact/chain bila memungkinkan ([[FRAMEWORK-BUGBOUNTY-AI]] Bab 6).

## Verdikt
```
VERIFY: [LOLOS / TAHAN]
- A bukti: ok/masalah<...>
- B impact: ok/masalah<...>
- C skeptic: bertahan? ya/tidak <alasan>
- D scope/dedup/etika: ok/masalah<...>
- E kualitas: ok/masalah<...>
- verdict: siap submit (butuh konfirmasi manusia) / perbaiki dulu / drop
```
Jika LOLOS → minta **konfirmasi eksplisit manusia** untuk submit ([[AI-OPERATING-RULES]] Bab 4). AI tidak submit sendiri.

Terkait: [[FRAMEWORK-BUGBOUNTY-AI]] Bab 6/7 · [[AI-OPERATING-RULES]] Bab 3/4 · [[REPORT-KIT]] · [[ANTI-DUP-PLAYBOOK]]

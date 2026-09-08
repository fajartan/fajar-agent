# REPORT-KIT — Template Laporan, CVSS & Triage
### Dokumen pendamping #5 dari FRAMEWORK-BUGBOUNTY-AI.md
Untuk FASE 5 (FRAMEWORK Bab 7). Severity berdasar **impact nyata**, bukan tipe bug. Sebelum submit wajib lewat [[VERIFY-BEFORE-SUBMIT]] & konfirmasi manusia ([[AI-OPERATING-RULES]] Bab 4).

---

## Template laporan (semua severity)
```markdown
Title: [Vuln Type] in [Endpoint] leads to [Impact]
Severity: [Critical/High/Medium/Low]  (CVSS: <skor> — <vektor>)

## Summary
Satu paragraf: apa kerentanannya & dampak bisnisnya.

## Description
Cara kerja + endpoint rentan + root cause + cara eksploitasi. Tandai fakta vs asumsi.

## Steps to Reproduce
1. Navigate ke [URL]
2. [aksi spesifik — sebut akun: userA/userB]
3. [aksi lanjutan]
4. Observe [hasil konkret]

## Impact
Data apa yang diakses · aksi apa yang bisa dilakukan · user siapa terdampak · sistem apa.
(Nyatakan dampak nyata, tanpa melebih-lebihkan.)

## Proof of Concept
[screenshot/video/kode]. authz → alur 2-akun · SQLi → paired request · CSRF → HTML PoC · SSRF → callback log.
(Redaksi PII/secret pihak ketiga.)

## Remediation
- Rekomendasi utama
- Alternatif
- Defense tambahan

## References
OWASP · CWE-<id> · disclosed report sejenis (jika ada)
```

## Panduan CVSS 3.1 cepat (untuk menaksir severity)
Metrik dasar (AV/AC/PR/UI/S/C/I/A). Heuristik cepat:
- **Critical (9.0–10):** RCE, auth bypass total, SSRF→cloud metadata/creds, SQLi dump massal.
- **High (7.0–8.9):** ATO 0/1-click, IDOR write/PII massal, stored XSS ke banyak user, SSRF internal.
- **Medium (4.0–6.9):** reflected XSS (butuh interaksi), IDOR read terbatas, CSRF aksi sedang, info disclosure bermakna.
- **Low (0.1–3.9):** self-XSS-adjacent, disclosure minor, missing header tanpa impact langsung.
Gunakan kalkulator resmi (FIRST CVSS) untuk vektor final; tulis vektor di laporan. Ingat: severity = **impact + likelihood** di lingkungan program, bukan sekadar nama bug.

## Kalibrasi khusus (dari buku)
- Duplicate = benar tapi telat (bukan invalid). Informative = nyata tapi impact lemah/accepted risk/OOS/defense-in-depth.
- ATO by interaksi: 0-click > 1-click; **2-click sering ditolak** (terlalu banyak interaksi) — kalibrasi kelayakan sebelum submit.
- Naikkan impact dulu (FRAMEWORK Bab 6): IDOR → dokumentasikan PII persis; cek pola sistemik di endpoint sejenis; rangkai chain (prasyarat→aksi→outcome).

## Kalimat balasan triage (FRAMEWORK Bab 7 / Day 13)
- Saat severity diperdebatkan → beri **bukti reach tambahan** (mis. blind-extract nama tabel `admin_users` untuk tunjukkan query menyentuh area di luar akun sendiri) + usulan fix. Jangan emosional.
- Contoh nada: "Terima kasih atas review-nya. Untuk memperjelas impact: dengan langkah berikut, akun userB (bukan pemilik) dapat [aksi] terhadap objek userA — bukti terlampir (timestamp/req/resp). Ini melampaui izin normal member. Saran perbaikan: [fix]."
- Respons cepat, akui limitasi bila benar, terima keputusan akhir program. Disclosure publik hanya sesuai policy (umumnya ≥90 hari via mediasi).

## Checklist pra-submit (ringkas — detail di VERIFY-BEFORE-SUBMIT)
- [ ] SCOPE-GATE PASS · bukti reproducible oleh orang lain · impact dinyatakan jelas
- [ ] anti-dup dicek ([[ANTI-DUP-PLAYBOOK]]) · severity/CVSS wajar · PII diredaksi
- [ ] konfirmasi manusia untuk submit

Terkait: [[FRAMEWORK-BUGBOUNTY-AI]] Bab 6/7 · [[VERIFY-BEFORE-SUBMIT]] · [[ANTI-DUP-PLAYBOOK]] · [[AI-OPERATING-RULES]]

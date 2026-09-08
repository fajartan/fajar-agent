# WEB-VULN-CLASSES — Peta Kelas Kerentanan Web (untuk hunting terarah & anti-lewat)

Skill ini dipakai agent di tahap ANALISA & RENCANA agar tidak melewatkan kelas bug. Untuk pengujian **yang diizinkan** (program bug bounty in-scope) saja. Tiap kelas: **di mana dicari · cara uji (1-variabel, dgn baseline) · sinyal · dampak · catatan anti-dup**.

## 1. Broken Access Control / IDOR (paling sering & bernilai)
- Cari: endpoint dgn ID objek (`/api/users/{id}`, `/invoices/{id}`, UUID, cookie, body, header).
- Uji: 2 akun (A capture → B replay ID objek A, dua arah). Ganti `?user_id=1→admin`, `POST /users/123→/users/admin`.
- Sinyal: data akun lain terbaca/terubah tanpa error.
- Dampak: naikkan dgn PII konkret; uji endpoint sejenis massal.
- Anti-dup: kombinasi endpoint+aksi yang jarang disebut di disclosed reports.

## 2. Authentication & Session / JWT
- Cari: login, reset password, MFA, remember-me, OAuth callback, token.
- Uji: JWT `alg:none`/kunci lemah/`kid` injection; token tak invalidasi saat logout/ganti password; reset-token bocor di response/URL; race pada OTP.
- Dampak: account takeover (ATO) = tinggi.

## 3. SSRF
- Cari: fitur fetch URL (webhook, import-by-URL, PDF/HTML render, image proxy, preview).
- Uji: arahkan ke collaborator/metadata (`169.254.169.254`), cek blind via OOB DNS/HTTP.
- Dampak: akses internal/metadata cloud = kritis. Anti-dup: parser/format non-obvious (gopher, redirect chain, DNS rebinding).

## 4. Injection (SQLi/NoSQL/Command/SSTI/XXE)
- SQLi: parameter ke query; uji error/boolean/time-based; konfirmasi perilaku, bukan versi.
- SSTI: input direfleksikan di template (`{{7*7}}`, `${7*7}`).
- XXE: endpoint terima XML/SVG/DOCX; entity eksternal + OOB.
- Command inj: fitur yg memanggil sistem (ping, convert, export).

## 5. XSS (reflected/stored/DOM)
- Cari: input terefleksi/tersimpan; sink DOM (`innerHTML`, `document.write`, `eval`).
- Uji: konteks-aware payload; utamakan stored & DOM (impact lebih tinggi, sering less-dup).
- Dampak: naikkan ke ATO/CSRF-bypass, bukan sekadar `alert(1)`.

## 6. CSRF / CORS / Clickjacking
- CSRF: aksi state-changing tanpa token/SameSite. CORS: `Access-Control-Allow-Origin` reflektif + credentials. 
- Anti-dup: chain ke aksi sensitif (ganti email → ATO).

## 7. File Upload / Path Traversal / LFI
- Cari: upload avatar/dokumen, download by path, import.
- Uji: ekstensi/mime bypass, `../`, null byte, SVG→XSS, polyglot.

## 8. Business Logic & Race Condition
- Cari: kupon, saldo, kuota, transfer, workflow multi-step.
- Uji: negatif/overflow nilai, lompat langkah, replay, **race** (kirim paralel → double-spend).
- Anti-dup: logika unik aplikasi → paling jarang duplikat, bernilai tinggi.

## 9. Info Disclosure & Secrets
- Cari: JS bundle (endpoint/kunci), `.git`, backup, verbose error, API doc, `.env`, source map.
- Alat: analisa JS (mantra/jsleak), gau/wayback, nuclei exposures.

## 10. Misconfig / Takeover / Dependency
- Subdomain takeover (CNAME dangling), S3 bucket terbuka, panel default-cred, CVE komponen (konfirmasi perilaku).

---
**Disiplin (VERIFY-BEFORE-SUBMIT):** 1 anomali ≠ temuan → butuh baseline + perubahan terreproduksi. Selalu jalankan dedup + cek recon-findable sebelum submit. Naikkan impact & chaining sebelum lapor. Lihat [[PAYLOAD-CHEATSHEET]], [[VERIFY-BEFORE-SUBMIT]], [[ANTI-DUP-PLAYBOOK]].

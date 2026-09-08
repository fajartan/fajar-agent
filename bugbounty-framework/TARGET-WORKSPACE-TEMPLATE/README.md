# TARGET-WORKSPACE (template)
### Dokumen pendamping #2 dari FRAMEWORK-BUGBOUNTY-AI.md
Kerangka kerja **per-target**. Salin folder ini menjadi `<nama-target>/` (mis. `whatnot/`, `varonis/`) tiap kali memulai target baru, lalu isi. Ini operasionalisasi disiplin dokumentasi FRAMEWORK Bab 8. AI membaca file di sini sebagai sumber kebenaran target (bukan ingatan); manusia mengisinya dengan artefak nyata.

## Cara pakai (untuk AI)
1. Pastikan `scope.md` sudah diisi policy mentah → jalankan SCOPE-GATE ([[AI-OPERATING-RULES]] Bab 2).
2. Bangun `endpoints.md` & `authz-matrix.md` dari artefak recon (bukan tebakan).
3. Setiap ide tes ditulis di `hypotheses.md` format: `Hipotesis → Tes(1 variabel) → Hasil(vs baseline) → Next`.
4. Simpan setiap bukti ke `evidence/` (request/response/timestamp/label akun). Redaksi PII pihak ketiga.
5. Draft laporan di `reports/`. Sebelum submit → [[VERIFY-BEFORE-SUBMIT]].

## Struktur
```
<target>/
  scope.md          # policy mentah + in/out scope + prohibited + aset
  accounts.md       # akun tes MILIK SENDIRI (userA/userB/admin) + catatan
  recon/            # output recon (subs, live, alljs, urls, screenshots)
  endpoints.md      # tabel: method | path | param | auth | response fields
  authz-matrix.md   # matriks aktor x aksi (siapa boleh apa)
  hypotheses.md     # Hipotesis → Tes → Hasil → Next
  evidence/         # bukti per-finding (req/resp/timestamp/akun/screenshot)
  reports/          # draft laporan per finding
```

Terkait: [[FRAMEWORK-BUGBOUNTY-AI]] Bab 8 · [[AI-OPERATING-RULES]] · [[RECON-RUNBOOK]] · [[VERIFY-BEFORE-SUBMIT]]


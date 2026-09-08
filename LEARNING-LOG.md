# LEARNING-LOG — After-Action & Pelacakan Kemajuan
### Dokumen pendamping #8 dari FRAMEWORK-BUGBOUNTY-AI.md
Loop belajar: tiap hasil (valid/dup/informative/ditolak) dicatat supaya tes berikutnya makin tajam (FRAMEWORK Bab 0 & 12). AI memelihara file ini bersama manusia dan memakainya untuk menyesuaikan strategi.

---

## Ledger laporan
| Tgl | Target | Kelas bug | Severity | Hasil | Bounty | Waktu | Catatan singkat |
|---|---|---|---|---|---|---|---|
| <...> | <...> | <IDOR/XSS/...> | <...> | valid/dup/informative/rejected | <...> | <jam> | <...> |

## Analisa hasil (isi tiap beberapa laporan)
**Kenapa duplikat?** (pilih & catat pola)
- [ ] area terlalu obvious (login/IDOR profil/CSRF email)
- [ ] lambat lapor · [ ] program terlalu ramai · [ ] tidak cek disclosed dulu
→ tindakan: <mis. mulai dari fitur baru, cek hacktivity dulu>

**Kenapa informative?**
- [ ] impact lemah · [ ] accepted risk · [ ] out-of-scope · [ ] defense-in-depth
→ tindakan: <fokus impact yang jelas cross-boundary>

**Kenapa rejected?**
- [ ] bukti tak lengkap · [ ] scope salah · [ ] model risiko program beda
→ tindakan: <perkuat reproduksi/impact; baca policy lebih teliti>

## Kelemahan berulang (yang sering aku lewatkan)
| Kelas bug / skill | Frekuensi terlewat | Rencana perbaikan (lab/latihan) |
|---|---|---|
| <mis. authz-depth> | <...> | <PortSwigger lab X, ulang matriks> |

## Alokasi waktu (kalibrasi realistis, FRAMEWORK Bab 12)
Referensi: recon ~20% · active testing ~50% · learning ~20% · report ~10%.
| Minggu | Recon | Testing | Learning | Report | Catatan |
|---|---|---|---|---|---|
| <...> |  |  |  |  |  |

## Review mingguan (cegah burnout — sesi terstruktur)
- Apa yang berhasil? <...>
- Apa yang buang waktu? <...>
- Fokus minggu depan (1 target, 1-2 kelas bug): <...>

Terkait: [[FRAMEWORK-BUGBOUNTY-AI]] Bab 12 · [[ANTI-DUP-PLAYBOOK]] · [[PROGRAM-SELECTION]]

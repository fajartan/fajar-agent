# EXPERT-TACTICS — Taktik Pakar: Bug Tidak-Umum & Minim Duplikat
### Dokumen pendamping #12 dari FRAMEWORK-BUGBOUNTY-AI.md
Kumpulan tips & trik **bersumber dari pakar/komunitas** (bukan karangan) untuk mencari bug jarang-ditemukan & menekan duplikat. AI/agen **wajib** menerapkan ini di FASE 4 & saat memilih strategi. Melengkapi [[NOVEL-HUNTING]] & [[ANTI-DUP-PLAYBOOK]].
Sumber utama: NahamSec, Jason Haddix (TBHM), Intigriti, Bugcrowd, riset bl4de, writeup praktisi (tautan di bagian bawah).

---

## Realita duplikat (kalibrasi, dari komunitas)
- Pemula: **50–80%** laporan dupe/ditolak; hunter berpengalaman **20–40%**. Ini **normal**, bukan tanda gagal.
- Dupe tidak bisa 0 (orang lain bisa submit 5 menit sebelum kamu). Yang bisa ditekan: **dupe yang obvious**.
- **Reframe:** "rejection is information, not judgment." Tiap dupe = data untuk menyesuaikan strategi. (Intigriti/as93; Bugcrowd)

## TAKTIK 1 — Spesialisasi mendalam, bukan lari tool (NahamSec)
> "The secret isn't running more tools or testing more programs — it's developing deep expertise that sets you apart."
- Akar dupe: mengejar **easy-win yang sama** dengan semua orang (OTP/rate-limit bypass, business-logic generik, XSS/CSRF/subdomain permukaan).
- **Aksi AI:** pilih **1 kelas bug untuk dikuasai** + **1 produk untuk dipahami tuntas**. Jadi *power user*: paham SEMUA fitur, quirk, dan perilaku yang diniatkan. Bug unik lahir dari keahlian, bukan dari banyaknya scan.

## TAKTIK 2 — Metodologi unik = edge (Intigriti, Jason Haddix/TBHM)
> "A unique methodology will reduce duplicates because competing hunters won't find the same bugs as you."
- Dua arketipe pakar (pilih & perdalam salah satu, jangan setengah-setengah):
  1. **Recon-heavy:** scope wildcard, kumpulkan data berhari-hari (search engine, Shodan/Censys, asset discovery mendalam) → temukan aset yang orang lain lewatkan.
  2. **App-deep:** menyelam ke aplikasi utama, baca semua JS, uji **setiap** fitur & fungsi.
- **Aksi AI:** bangun urutan langkah **milik sendiri** yang berulang & sedikit berbeda dari checklist umum. Jangan sekadar meniru metodologi orang.

## TAKTIK 3 — Recon dalam SEBELUM menyerang (Intigriti, TBHM)
> "Read their documentation, understand roles & privileges, do info gathering for 1–2 days before you start attacking."
- Jebakan: langsung daftar akun lalu cek CSRF/XSS/subdomain permukaan → panen dupe.
- **Aksi AI:** sebelum tes, **baca dokumentasi/API docs**, petakan **peran & privilege user**, pahami workflow & alur uang. Baru rumuskan hipotesis spesifik.

## TAKTIK 4 — Business logic = anti-dupe by nature (praktisi)
> "Business logic bugs are app-specific and not discoverable by generic scanners."
- Karena spesifik aplikasi, **sulit diduplikat** & tak ketangkap scanner.
- Fokus bernilai tinggi: **payments** (dampak finansial langsung), **user data** (akses/ubah tak sah), **privileged actions** (fungsi admin/role: user management, config change).
- **Aksi AI:** untuk tiap value → tanya: aturan apa yang melindunginya? siapa boleh? berapa kali? urutan apa yang diasumsikan? Uji manipulasi workflow yang tak diniatkan.

## TAKTIK 5 — Buru "bug tetangga" saat kena dupe (riset bl4de)
> "It's common to end up with a dupe only to realize there's another vuln right beside it."
- Contoh: Stored XSS di layar yang sama bila input tak disanitasi; WAF-bypass dari trik sintaks yang membuka XSS yang tadinya gagal.
- **Aksi AI:** setiap kali dupe/temuan, **jangan langsung pindah** — periksa fitur/parameter di sekitarnya untuk bug kedua yang lebih jarang.

## TAKTIK 6 — Pelajari disclosed reports untuk cari "wilayah tak tersentuh" (bl4de, Intigriti)
- Guna disclosed: bukan cuma hindari mengulang, tapi **identifikasi area/pola yang kurang diperhatikan** = ladang subur.
- **Aksi AI:** baca disclosed report program → petakan area **yang sudah ramai** (hindari) vs **yang jarang disebut** (kejar).

## TAKTIK 7 — Template laporan untuk kelas berulang (praktisi)
- Kecepatan = penting (first-to-report menang). Siapkan template untuk kelas bug "paling sering" kamu; bug custom tetap butuh writeup custom.
- **PERINGATAN keras:** selalu **ganti URL/domain** di template — salah domain = laporan langsung invalid.

## TAKTIK 8 — Angka realistis & mental (Bugcrowd, komunitas)
- Duplikat itu **struktural**: hanya laporan pertama yang dibayar (asal reproducible). Kamu tak bisa tahu orang lain sudah submit.
- Jangan patah semangat; tiap dupe membuktikan **metodologimu menemukan bug nyata** — tinggal perbaiki *timing/surface/kedalaman*.

---

## DIREKTIF UNTUK AI/AGEN (paksa terapkan)
Di FASE 4 & pemilihan strategi, AI WAJIB:
1. **Tolak easy-win generik** di program ramai (TAKTIK 1) — kecuali aset baru.
2. Bekerja dari **pemahaman produk** (TAKTIK 3–4): peta role/privilege/workflow/uang → hipotesis spesifik, bukan payload buta.
3. Prioritaskan **business logic & chain** (TAKTIK 4, [[NOVEL-HUNTING]]).
4. Saat dupe/temuan → **buru bug tetangga** (TAKTIK 5) sebelum pindah.
5. Konsultasi **disclosed reports** untuk memilih area jarang-tersentuh (TAKTIK 6).
6. Terapkan **metodologi unik** yang berulang (TAKTIK 2), bukan checklist umum.
7. Perlakukan dupe sebagai **data** → catat di [[LEARNING-LOG]], sesuaikan WHERE/WHAT/WHEN.
> Prinsip pemersatu semua pakar: **"Unique bugs come from unique expertise and methodology, not from running the same automated tools everyone else runs."**

## Sumber
- NahamSec — Why hunters keep finding duplicates and how to stop: https://www.nahamsec.com/posts/why-bug-bounty-hunters-keep-finding-duplicates-and-how-to-stop
- Intigriti — Crafting your bug bounty methodology: https://www.intigriti.com/researchers/blog/hacking-tools/crafting-your-bug-bounty-methodology-a-complete-guide-for-beginners
- Bugcrowd — The Three Principles of Bug Bounty Duplicates: https://www.bugcrowd.com/blog/the-three-principles-of-bug-bounty-duplicates/
- Jason Haddix — The Bug Hunter's Methodology (TBHM), Philosophy: https://github.com/jhaddix/tbhm/blob/master/01_Philosophy.md
- bl4de — How to deal with dupes: https://github.com/bl4de/research/blob/master/how_to_deal_with_dupes/hot_to_deal_with_dupes.md
- Handling Duplicates, Rejections, and Disputes: https://bug-bounties.as93.net/learn/handling-duplicates-rejections-and-disputes/
- Business logic writeups (praktisi): https://itsravikiran25.medium.com/business-logic-failed-defense-vulnerability-in-bug-bounty-4ab932a1a200

Terkait: [[NOVEL-HUNTING]] · [[ANTI-DUP-PLAYBOOK]] · [[AUTONOMOUS-OPERATOR]] · [[PROGRAM-SELECTION]] · [[LEARNING-LOG]]

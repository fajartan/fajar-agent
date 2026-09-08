# Accounts — <target>

> HANYA akun tes milik sendiri. Jangan pernah menyentuh akun/PII user asli.
> Untuk uji authz/IDOR butuh minimal 2 akun (A & B) + admin bila ada.

## Identitas HackerOne (standing — berlaku semua target)
- **HackerOne username:** `researcher`  (dipakai untuk atribusi laporan)
- **Email alias HackerOne:** `researcher@wearehackerone.com` — meneruskan ke email terdaftar di H1. Pakai alias ini untuk mendaftar akun tes agar identitas terikat ke H1 dan email pribadi tidak terekspos ke target.
- **Password/2FA/token:** JANGAN disimpan di file ini. Simpan di password manager. AI tidak menangani kredensial mentah ([[AI-OPERATING-RULES]] Bab 6). Membuat akun & mengisi password = dilakukan manusia sendiri.

## Akun tes per target (plus-addressing: 1 inbox, banyak akun)
| Label | Email | Role | Catatan |
|---|---|---|---|
| userA | `researcher+<target>A@wearehackerone.com` | member | akun utama pengujian |
| userB | `researcher+<target>B@wearehackerone.com` | member | uji horizontal (IDOR/authz) |
| admin | `researcher+<target>admin@wearehackerone.com` | admin/team-admin | jika program mengizinkan |

> **Catatan plus-addressing:** sebagian situs menolak karakter `+`. Jika ditolak, fallback berurutan:
> 1. Plus-addressing pada email pribadi terdaftar: `<email-pribadi>+<target>A@gmail.com` (Gmail mendukung `+`).
> 2. Alias/inbox terpisah khusus testing.
> Selalu verifikasi dulu bahwa target menerima `+` sebelum bergantung padanya.

## Catatan per target
- Onboarding/verifikasi email selesai? <...>
- Program mengizinkan akun admin/tim? <cek scope.md>
- Token/session disimpan aman (password manager), tidak pernah masuk ke laporan mentah / evidence tanpa redaksi.


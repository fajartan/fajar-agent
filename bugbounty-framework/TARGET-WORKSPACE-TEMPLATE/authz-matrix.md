# Authorization Matrix — <target>

> Silang aktor x aksi (FRAMEWORK Bab 4.3). Isi tiap sel: ✅ boleh (intended) / ❌ harus ditolak / ⚠️ diuji-hasil-mengejutkan.
> Check yang hilang biasa bersembunyi di kombinasi yang tak pernah didemo.

Objek: **<mis. Document / Order / Team / Invoice>**

| Aktor \ Aksi | read | create | update | delete | share | export | invite | approve | bill | admin |
|---|---|---|---|---|---|---|---|---|---|---|
| owner |  |  |  |  |  |  |  |  |  |  |
| invited user |  |  |  |  |  |  |  |  |  |  |
| team admin |  |  |  |  |  |  |  |  |  |  |
| normal member |  |  |  |  |  |  |  |  |  |  |
| logged-out |  |  |  |  |  |  |  |  |  |  |
| removed user |  |  |  |  |  |  |  |  |  |  |

## Temuan authz (ringkas)
- <aktor> bisa <aksi> pada objek <aktor lain> → [HIPOTESIS/FAKTA] → bukti di `evidence/` → dampak: <PII/kontrol> → lihat `reports/`.

## Catatan uji
- Metode 2-akun: A buat objek + capture request → B replay dgn ID objek A (dua arah A→B, B→A).
- Uji juga vertical (member → fungsi admin) & missing function-level (UI sembunyi, API terima).


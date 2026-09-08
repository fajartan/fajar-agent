# RECON-RUNBOOK — Runbook Command Recon
### Dokumen pendamping #3 dari FRAMEWORK-BUGBOUNTY-AI.md
Kumpulan pipeline command siap-copy (dari FRAMEWORK Bab 3, 9, 13). **AI memandu; manusia menjalankan** command aktif di lingkungannya (lihat [[AI-OPERATING-RULES]] Bab 1). Semua terikat SCOPE-GATE & disiplin automation FRAMEWORK Bab 2 (rate-limit, scope file, dry-run, output rapi). Jangan scanner agresif di program live tanpa izin tertulis.

> Konvensi: ganti `<target>` / `<URL>` sesuai scope. Simpan output ke `TARGET-WORKSPACE/<target>/recon/`.

---

## FASE 1 — Passive recon (tanpa traffic ke target)
```bash
# Certificate transparency (subdomain)
# buka: https://crt.sh/?q=%25.<target>.com   → salin ke crt.txt

# Google dorking (jalankan manual di browser)
# site:<target>.com filetype:pdf
# site:<target>.com inurl:admin
# site:<target>.com intitle:"index of"
# site:<target>.com ext:php inurl:?

# GitHub recon (manual): cari nama perusahaan/domain/produk → API key, kredensial, domain internal, Postman

# Wayback / gau (URL historis)
echo "<target>.com" | gau > recon/gau_urls.txt
```

## FASE 2 — Active recon (terkontrol)
```bash
# Subdomain enumeration
subfinder -d <target>.com -silent -o recon/subs_subfinder.txt
assetfinder --subs-only <target>.com > recon/subs_assetfinder.txt
amass enum -passive -d <target>.com -o recon/subs_amass.txt
cat recon/subs_*.txt | sort -u > recon/subs_all.txt

# Resolusi + cek live
cat recon/subs_all.txt | dnsx -silent -a -resp -o recon/subs_resolved.txt
cat recon/subs_resolved.txt | httpx -silent -status-code -title -tech-detect -follow-redirects -o recon/live.txt
cat recon/live.txt | aquatone -out recon/screenshots/     # opsional visual

# Fingerprint cepat satu host
whatweb <URL>
wafw00f <URL>     # CDN vs origin
```

## FASE 3 — Scanning terkontrol
```bash
# Nuclei terarah (bukan blind full-scan)
nuclei -l recon/live.txt -t cves/ -severity critical,high -o recon/nuclei_cve.txt
nuclei -l recon/live.txt -t exposures/ -t misconfiguration/ -o recon/nuclei_misc.txt

# Directory discovery ber-rate-limit
ffuf -u <URL>/FUZZ -w /usr/share/seclists/Discovery/Web-Content/raft-large-directories.txt \
     -mc 200,301,302,401,403 -fc 404 -rate 100 -o recon/ffuf.json
# alternatif rekursif: feroxbuster -u <URL> --rate-limit 100
```

## JS-RECON PIPELINE (FRAMEWORK Bab 13.3) — cari secret/endpoint di JS
```bash
# 1. crawl semua JS
katana -u <URL> -d 5 -jc | grep '\.js$' | tee recon/alljs.txt
cat recon/alljs.txt | wc -l
# 2. tambah dari gau, gabung unik
echo "<URL>" | gau | grep '\.js$' | anew recon/alljs.txt
# 3. filter live
cat recon/alljs.txt | uro | sort -u | httpx-toolkit -mc 200 -o recon/js_filtered.txt
# 4. cari leak
cat recon/js_filtered.txt | jsleak -s -l -k
cat recon/js_filtered.txt | mantra          # API key di JS
# 5. credential disclosure (opsional)
cat recon/js_filtered.txt | nuclei -t credentials-disclosure-all.yaml -c 30
# ekstrak endpoint: LinkFinder / getJS / ekstensi Endpointer di browser
```

## RECON-COMBO (peta menyeluruh, FRAMEWORK Bab 13.4)
```bash
subfinder -d <target>.com -silent | anew recon/subs.txt
# subdomain fuzzing (opsional): ffuf -w subdomains.txt -u https://FUZZ.<target>.com
cat recon/subs.txt | httpx -silent -o recon/subs_live.txt
# jalur URL historis → filter → pola vuln
echo "<target>.com" | gau | uro | httpx -silent -mc 200 | anew recon/urls_filtered.txt
cat recon/urls_filtered.txt | gf ssrf     # atau: xss, redirect, sqli, lfi ...
# jalur direktori
dirsearch -u <URL> -o recon/dirsearch.txt
```

## IP & OPEN PORTS "LostSec 2026" (FRAMEWORK Bab 13.5)
```bash
chaos -d <target>.com -o recon/target.txt
httpx-toolkit -l recon/target.txt -ip | sed -nE 's/.*\[([0-9.].*)\]$/\1/p' > recon/ip.txt
cat recon/ip.txt | sort -u | wc -l
cat recon/ip.txt | sort -u > recon/ips.txt
naabu -l recon/ips.txt -top-ports 100 -rate 1500 -verify -silent -o recon/naabu.txt
python naabutonmap.py -i recon/naabu.txt        # script custom → report
cat recon/naabu.txt | nuclei -tags cve -s medium,high,critical -o recon/naabu_nuclei.txt
```

## Content discovery multi-wordlist (FRAMEWORK Appendix)
```bash
for wl in \
  /usr/share/wordlists/dirb/common.txt \
  /usr/share/seclists/Discovery/Web-Content/directory-list-2.3-medium.txt ; do
    ffuf -u "<URL>/FUZZ" -w "$wl" -mc 200,204,301,302,307,401,403 -fc 404 -rate 100 \
         -o "recon/ffuf_$(basename $wl).json"
done
jq -s 'add' recon/ffuf_*.json > recon/all_findings.json
```

## Setelah recon — WAJIB ubah jadi hipotesis
Recon bukan daftar host; ubah tiap temuan jadi baris di `hypotheses.md` (FRAMEWORK Bab 1):
`aset/endpoint → kenapa menarik → tes 1-variabel → hasil → next`. Contoh: "JS sebut `/api/internal/reports` → cek eksistensi, siapa boleh panggil, apakah authz ditegakkan".

Terkait: [[FRAMEWORK-BUGBOUNTY-AI]] Bab 3/9/13 · [[AI-OPERATING-RULES]] · [[TARGET-WORKSPACE]] · [[ANTI-DUP-PLAYBOOK]]

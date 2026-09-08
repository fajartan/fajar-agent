#!/usr/bin/env python3
"""dedup v2 — DEDUP-GATE: apa yang SUDAH dilaporkan di program (biar tak mengulang).

Menarik disclosed reports via jina (GRATIS) / serper, mengekstrak JUDUL laporan → klasifikasi
per-laporan (bukan sekadar keyword), + frekuensi endpoint + isyarat severity.
Output known-issues.md: kelas RAMAI (hindari/angle unik) vs kelas & area PERAWAN (kejar).

Pakai:
  python3 dedup.py <handle|url> [--provider jina|serper] [--serper-key KEY] [--pages N] [--out FILE]
Contoh: python3 dedup.py whatnot
Butuh: python3 (stdlib) + internet. Best-effort (prior report PRIVAT tak terlihat).
"""
import re, os, sys, json, argparse, urllib.request

CLASSES = {
    "idor/bola/authz": ["idor", "bola", "insecure direct object", "authorization", "access control", "broken access", "authz", "privilege"],
    "xss": ["xss", "cross-site scripting", "cross site scripting", "html injection"],
    "ssrf": ["ssrf", "server-side request", "server side request"],
    "sqli": ["sql injection", "sqli"],
    "rce": ["rce", "remote code", "code execution", "command injection"],
    "csrf": ["csrf", "cross-site request"],
    "auth/takeover": ["account takeover", " ato", "auth bypass", "authentication bypass", "2fa", "otp", "oauth", "saml", "jwt", "session"],
    "info-disclosure": ["information disclosure", "info leak", "sensitive", "exposure", "leak", "exposed"],
    "business-logic": ["business logic", "race condition", "price", "coupon", "payment", "refund"],
    "subdomain-takeover": ["subdomain takeover", "dangling", "cname takeover"],
    "open-redirect": ["open redirect"],
    "upload/xxe/traversal": ["file upload", "xxe", "path traversal", "lfi", "directory traversal"],
    "graphql": ["graphql", "introspection"],
    "misconfig/cors": ["cors", "misconfiguration", "security header", "clickjack"],
}
SEVS = ["critical", "high", "medium", "low"]

def fetch_jina(url):
    req = urllib.request.Request("https://r.jina.ai/" + url, headers={"User-Agent": "bbdedup/2.0"})
    return urllib.request.urlopen(req, timeout=90).read().decode("utf-8", "replace")

def fetch_serper(name, key, pages):
    out = []
    for pg in range(max(1, pages)):
        data = json.dumps({"q": f'site:hackerone.com/reports {name}', "num": 20, "page": pg + 1}).encode()
        req = urllib.request.Request("https://google.serper.dev/search", data=data,
                                     headers={"X-API-KEY": key, "Content-Type": "application/json"})
        d = json.loads(urllib.request.urlopen(req, timeout=60).read())
        out += [(x.get("title", "") + " :: " + x.get("snippet", "")) for x in d.get("organic", [])]
    return "\n".join(out)

def classify(title):
    t = title.lower()
    return [k for k, ws in CLASSES.items() if any(w in t for w in ws)]

def extract_titles(text):
    kws = [w for ws in CLASSES.values() for w in ws]
    titles, seen = [], set()
    for ln in text.splitlines():
        ln = re.sub(r"\s+", " ", ln).strip(); low = ln.lower()
        if 12 < len(ln) < 160 and any(w in low for w in kws) and low not in seen:
            seen.add(low); titles.append(ln)
    return titles

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("program")
    ap.add_argument("--provider", default="jina", choices=["jina", "serper"])
    ap.add_argument("--serper-key", default="")
    ap.add_argument("--pages", type=int, default=1)
    ap.add_argument("--file", default="", help="baca file hacktivity yg kamu simpan (PALING AKURAT)")
    ap.add_argument("--out", default="known-issues.md")
    a = ap.parse_args()
    handle = a.program.rstrip("/").split("/")[-1]
    hurl = (a.program.rstrip("/") if a.program.startswith("http") else f"https://hackerone.com/{handle}") + "/hacktivity?type=complete"

    if a.file:
        text = open(a.file, encoding="utf-8", errors="replace").read(); src = "file:" + os.path.basename(a.file)
    else:
        print(f"[*] tarik disclosed: {handle} via {a.provider} ...")
        try:
            text = fetch_serper(handle, a.serper_key, a.pages) if a.provider == "serper" else fetch_jina(hurl)
        except Exception as ex:
            sys.exit(f"[!] gagal: {ex}\n    coba: --provider serper --serper-key <KEY>  atau --file <hacktivity.txt> (paling akurat).")
        src = a.provider
    titles = extract_titles(text)
    # fallback otomatis: jina lemah + ada serper key -> perkaya
    if len(titles) < 3 and a.serper_key and not a.file and a.provider != "serper":
        try:
            text += "\n" + fetch_serper(handle, a.serper_key, a.pages); src += "+serper"; titles = extract_titles(text)
        except Exception: pass
    # tally per-laporan
    cls_reports = {k: 0 for k in CLASSES}
    for t in titles:
        for k in classify(t): cls_reports[k] += 1
    cls_reports = {k: v for k, v in sorted(cls_reports.items(), key=lambda x: -x[1]) if v > 0}
    # severity hint
    low_all = text.lower()
    sev = {s: low_all.count(s) for s in SEVS if low_all.count(s)}
    # endpoint frequency
    paths = {}
    for m in re.findall(r"/[a-z0-9_\-./]{3,50}", low_all):
        if not m.endswith((".js", ".css", ".png", ".jpg", ".svg")):
            paths[m] = paths.get(m, 0) + 1
    top_paths = sorted(paths.items(), key=lambda x: -x[1])[:25]
    quiet = [k for k in CLASSES if k not in cls_reports]

    L = [f"# Known Issues v2 (DEDUP-GATE) — {handle}",
         f"Sumber: {src} · judul terdeteksi: {len(titles)} · best-effort (verifikasi manual).",
         "\n## Kelas bug SUDAH dilaporkan (≈jumlah laporan) — RAMAI, butuh angle unik/hindari"]
    L += [f"- {k}: ~{v} laporan" for k, v in cls_reports.items()] or ["- (tak terdeteksi — data mungkin tak ter-render)"]
    L.append("\n## Kelas TIDAK terlihat di sample — potensi lebih perawan (prioritas)")
    L += [f"- {k}" for k in quiet] or ["- —"]
    if sev:
        L.append("\n## Isyarat severity (frekuensi kata)")
        L += [f"- {s}: {c}" for s, c in sorted(sev.items(), key=lambda x: -x[1])]
    L.append("\n## Endpoint/path paling sering disebut (sudah digarap → cari yang JARANG)")
    L += [f"- {p}  (x{c})" for p, c in top_paths] or ["- —"]
    if titles[:15]:
        L.append("\n## Contoh judul laporan terdeteksi")
        L += [f"- {t}" for t in titles[:15]]
    L.append("\n---\n⚠️ Prior report H1 sering PRIVAT & tak muncul di sini → dedup ini TIDAK menjamin bebas dupe. "
             "Gabungkan dgn WHERE/WHEN (program sepi + aset baru, asset-monitor.py) & NOVEL-HUNTING (bug butuh-pemahaman).")
    open(a.out, "w", encoding="utf-8").write("\n".join(L))
    print(f"[+] -> {a.out}  (ramai teratas: {', '.join(list(cls_reports)[:5]) or '-'})")

if __name__ == "__main__":
    main()

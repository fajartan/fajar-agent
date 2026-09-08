#!/usr/bin/env python3
"""recon v3 — pipeline recon lengkap (setara reconftw core), profil passive/standard/deep.

Tahap (per profil):
  passive  : subdomain MULTI-SUMBER pasif (subfinder/assetfinder/crt.sh/otx/chaos) + URL arsip (gau/wayback)
             — TIDAK mengirim ke target.
  standard : + dnsx resolve, httpx live, crawl (katana), JS mining (getJS/jsleak/mantra), gf patterns.
  deep     : + screenshots (gowitness/aquatone), content-discovery (feroxbuster/ffuf), port (naabu),
             nuclei (exposures/misconfig/cve low-noise), param-mining (arjun).
Output rapi + summary.md. Notif opsional saat selesai (env BBRECON_WEBHOOK / BBRECON_TG_TOKEN+CHAT).

Pakai: python3 recon.py <domain> [--out DIR] [--profile passive|standard|deep] [--rate N] [--brute WORDLIST]
⚠️ standard/deep mengirim request ke target — pastikan IN-SCOPE & scanning diizinkan.
"""
import os, sys, ssl, json, shutil, subprocess, argparse, datetime, urllib.request, urllib.parse
import concurrent.futures as cf

UA = {"User-Agent": "Mozilla/5.0 (bbrecon/3)"}
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE
def have(t): return shutil.which(t) is not None
def _http(u, timeout=45):
    return urllib.request.urlopen(urllib.request.Request(u, headers=UA), timeout=timeout, context=CTX).read().decode("utf-8", "replace")

def sh(cmd, outfile=None, inp=None, timeout=1800, append=False):
    print(f"  $ {' '.join(cmd)}")
    try:
        r = subprocess.run(cmd, input=inp, capture_output=True, text=True, timeout=timeout)
        if outfile and r.stdout:
            open(outfile, "a" if append else "w", encoding="utf-8").write(r.stdout)
        return r.stdout
    except Exception as e:
        print(f"    [!] {cmd[0]} gagal: {e}"); return ""
def lines(f): return [l.strip() for l in open(f, encoding="utf-8") if l.strip()] if os.path.exists(f) else []

# ---- sumber subdomain pasif ----
def s_subfinder(d): return {l.lower() for l in sh(["subfinder", "-d", d, "-silent"]).splitlines()} if have("subfinder") else set()
def s_assetfinder(d): return {l.lower() for l in sh(["assetfinder", "--subs-only", d]).splitlines()} if have("assetfinder") else set()
def s_chaos(d): return {l.lower() for l in sh(["chaos", "-d", d, "-silent"]).splitlines()} if (have("chaos") and os.environ.get("CHAOS_KEY")) else set()
def s_crtsh(d):
    try:
        return {n.strip().lstrip("*.").lower() for e in json.loads(_http(f"https://crt.sh/?q=%25.{d}&output=json"))
                for n in str(e.get("name_value", "")).splitlines() if n.strip().lstrip("*.").lower().endswith(d) and " " not in n}
    except Exception: return set()
def s_otx(d):
    try:
        j = json.loads(_http(f"https://otx.alienvault.com/api/v1/indicators/domain/{d}/passive_dns"))
        return {r.get("hostname", "").lower().lstrip("*.") for r in j.get("passive_dns", []) if r.get("hostname", "").lower().endswith(d)}
    except Exception: return set()

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("domain"); ap.add_argument("--out", default=os.path.expanduser("~/bb-recon"))
    ap.add_argument("--profile", choices=["passive", "standard", "deep"], default="standard")
    ap.add_argument("--rate", type=int, default=100); ap.add_argument("--brute", default="")
    ap.add_argument("--header", action="append", default=[], help="header utk authenticated crawl (boleh berkali)")
    ap.add_argument("--cookie", default="", help="Cookie utk authenticated crawl")
    a = ap.parse_args()
    d = a.domain.strip().lower()
    rec = os.path.join(a.out, d, "recon"); os.makedirs(rec, exist_ok=True)
    p = lambda f: os.path.join(rec, f)
    HDR = []
    for h in a.header: HDR += ["-H", h]
    if a.cookie: HDR += ["-H", f"Cookie: {a.cookie}"]
    print(f"==> recon v3 [{a.profile}] {d} -> {rec}" + ("  [authenticated]" if HDR else ""))

    # 1) SUBDOMAIN (multi-sumber pasif, paralel)
    subs = set()
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs = [ex.submit(fn, d) for fn in (s_subfinder, s_assetfinder, s_chaos, s_crtsh, s_otx)]
        for fu in futs:
            try: subs |= {x for x in fu.result() if x.endswith(d)}
            except Exception: pass
    open(p("subs.txt"), "w", encoding="utf-8").write("\n".join(sorted(subs)))
    print(f"    subdomains: {len(subs)}")
    # DNS brute opsional
    if a.brute and have("dnsx") and os.path.exists(a.brute):
        extra = sh(["dnsx", "-silent", "-d", d, "-w", a.brute]);
        if extra: open(p("subs.txt"), "a", encoding="utf-8").write("\n" + extra)

    # 2) URL arsip (pasif)
    urls = (sh(["gau", d]) if have("gau") else "") + (sh(["waybackurls", d]) if have("waybackurls") else "")
    if urls:
        open(p("urls_raw.txt"), "w", encoding="utf-8").write(urls)
        sh(["uro"], p("urls.txt"), inp=urls) if have("uro") else open(p("urls.txt"), "w", encoding="utf-8").write(urls)
    print(f"    urls: {len(lines(p('urls.txt')))}")

    if a.profile != "passive":
        sub_in = "\n".join(sorted(subs))
        # 3) resolve + live
        if have("dnsx") and subs: sh(["dnsx", "-silent", "-a", "-resp"], p("resolved.txt"), inp=sub_in)
        if have("httpx") and subs:
            sh(["httpx", "-silent", "-status-code", "-title", "-tech-detect", "-cdn", "-location", "-rate-limit", str(a.rate)] + HDR, p("live.txt"), inp=sub_in)
        print(f"    live: {len(lines(p('live.txt')))}")
        # 4) JS mining (authenticated bila --header/--cookie)
        js = set(l for l in sh(["katana", "-u", f"https://{d}", "-d", "2", "-jc", "-silent"] + HDR).splitlines() if l.endswith(".js")) if have("katana") else set()
        if have("getJS"): js |= {l for l in sh(["getJS", "--url", f"https://{d}"]).splitlines() if l.endswith(".js")}
        js |= {l for l in lines(p("urls.txt")) if l.endswith(".js")}
        open(p("alljs.txt"), "w", encoding="utf-8").write("\n".join(sorted(js)))
        print(f"    js: {len(js)}")
        if js:
            livejs = sh(["httpx", "-silent", "-mc", "200"], inp="\n".join(sorted(js))) if have("httpx") else "\n".join(js)
            if have("jsleak"): sh(["jsleak", "-s", "-l", "-k"], p("jsleak.txt"), inp=livejs)
            if have("mantra"): sh(["mantra"], p("mantra.txt"), inp=livejs)
        # 5) gf patterns
        if have("gf") and os.path.exists(p("urls.txt")):
            for pat in ("ssrf", "xss", "redirect", "sqli", "idor", "lfi", "ssti", "rce"):
                sh(["gf", pat], p(f"gf_{pat}.txt"), inp="\n".join(lines(p("urls.txt"))))

    if a.profile == "deep":
        print("    [deep] screenshots + content-discovery + ports + nuclei + params")
        live_hosts = "\n".join(l.split()[0] for l in lines(p("live.txt")))
        # screenshots
        if live_hosts and have("gowitness"):
            open(p("_hosts.txt"), "w", encoding="utf-8").write(live_hosts)
            sh(["gowitness", "scan", "file", "-f", p("_hosts.txt"), "--screenshot-path", p("screens")], timeout=1200) \
                or sh(["gowitness", "file", "-f", p("_hosts.txt")], timeout=1200)
        elif live_hosts and have("aquatone"):
            sh(["aquatone", "-out", p("aquatone")], inp=live_hosts, timeout=1200)
        # content discovery
        wl = next((w for w in ("/usr/share/seclists/Discovery/Web-Content/raft-large-directories.txt",
                               os.path.expanduser("~/seclists/Discovery/Web-Content/raft-large-directories.txt")) if os.path.exists(w)), "")
        if have("feroxbuster"):
            sh(["feroxbuster", "-u", f"https://{d}", "--silent", "--rate-limit", str(a.rate)] + (["-w", wl] if wl else []), p("content.txt"), timeout=1800)
        elif have("ffuf") and wl:
            sh(["ffuf", "-u", f"https://{d}/FUZZ", "-w", wl, "-mc", "200,301,302,401,403", "-rate", str(a.rate), "-s"], p("content.txt"), timeout=1800)
        # ports
        if have("naabu") and subs: sh(["naabu", "-silent", "-top-ports", "100", "-rate", "1000"], p("ports.txt"), inp="\n".join(sorted(subs)), timeout=1200)
        # nuclei low-noise
        if have("nuclei") and live_hosts:
            sh(["nuclei", "-silent", "-t", "http/exposures/", "-t", "http/misconfiguration/", "-t", "http/cves/",
                "-severity", "medium,high,critical", "-rate-limit", str(a.rate)], p("nuclei.txt"), inp=live_hosts, timeout=2400)
        # param mining
        if have("arjun"): sh(["arjun", "-u", f"https://{d}", "-oT", p("params.txt")], timeout=900)

    _summary(rec, d, a.profile)

def _summary(rec, d, profile):
    def n(f):
        fp = os.path.join(rec, f); return sum(1 for _ in open(fp, encoding="utf-8")) if os.path.exists(fp) else 0
    gf = ", ".join(f"{x}={n(f'gf_{x}.txt')}" for x in ('ssrf', 'xss', 'redirect', 'sqli', 'idor', 'lfi', 'ssti', 'rce'))
    L = [f"# Recon v3 — {d} — {datetime.date.today().isoformat()} (profil: {profile})",
         f"- subdomains: {n('subs.txt')} | live: {n('live.txt')} | resolved: {n('resolved.txt')}",
         f"- urls: {n('urls.txt')} | js: {n('alljs.txt')} | jsleak: {n('jsleak.txt')} | mantra: {n('mantra.txt')}",
         f"- gf: {gf}",
         f"- content: {n('content.txt')} | ports: {n('ports.txt')} | nuclei: {n('nuclei.txt')} | params: {n('params.txt')}",
         "\nLangkah: ubah temuan -> hipotesis (NOVEL-HUNTING) utamakan endpoint jarang & butuh-pemahaman;",
         "cross-check dedup.py sebelum dalami. (Automation != findings — pointing matters.)"]
    rep = "\n".join(L)
    open(os.path.join(rec, "summary.md"), "w", encoding="utf-8").write(rep)
    print("==> selesai. Ringkasan: " + os.path.join(rec, "summary.md"))
    # notif opsional
    hook = os.environ.get("BBRECON_WEBHOOK"); tok = os.environ.get("BBRECON_TG_TOKEN"); chat = os.environ.get("BBRECON_TG_CHAT")
    msg = f"[recon {profile}] {d}: subs {n('subs.txt')}, live {n('live.txt')}, nuclei {n('nuclei.txt')}"
    try:
        if hook: urllib.request.urlopen(urllib.request.Request(hook, data=json.dumps({"content": msg}).encode(), headers={"Content-Type": "application/json"}), timeout=15)
        if tok and chat: urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage?%s" % (tok, urllib.parse.urlencode({"chat_id": chat, "text": msg})), timeout=15)
    except Exception: pass

if __name__ == "__main__":
    main()

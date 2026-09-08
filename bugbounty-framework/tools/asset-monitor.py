#!/usr/bin/env python3
"""asset-monitor v2 — pantau subdomain BARU per target (multi-sumber pasif, ala pakar).

Sumber pasif (gabungan, tahan-gagal): subfinder · crt.sh · hackertarget · AlienVault OTX · Wayback CDX.
Diff vs run sebelumnya → subdomain baru → (opsional) httpx probe + notifikasi webhook.
Tuas WHEN level aset (anti-dupe): jadi orang pertama menguji host baru.

Pakai:
  python3 asset-monitor.py <domain> [domain2 ...] [--probe] [--out DIR]
Env opsional:
  BBAM_WEBHOOK   URL webhook Discord/Slack (kirim ringkasan subdomain baru)
  CHAOS_KEY      pakai chaos (bila terpasang) sbg sumber tambahan
Cron: 0 9 * * * python3 asset-monitor.py example.com >> ~/bb-monitor/run.log 2>&1
Butuh: python3 (stdlib) + internet. subfinder/httpx/chaos opsional.
"""
import json, os, sys, ssl, time, shutil, subprocess, argparse, datetime, urllib.request, urllib.parse

UA = {"User-Agent": "Mozilla/5.0 (bbam/2.0)"}
CTX = ssl.create_default_context(); CTX.check_hostname = False; CTX.verify_mode = ssl.CERT_NONE

def _get(url, timeout=45):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout, context=CTX).read().decode("utf-8", "replace")

def src_crtsh(d):
    for _ in range(2):
        try:
            out = set()
            for e in json.loads(_get(f"https://crt.sh/?q=%25.{d}&output=json")):
                for n in str(e.get("name_value", "")).splitlines():
                    n = n.strip().lstrip("*.").lower()
                    if n.endswith(d) and " " not in n: out.add(n)
            return out
        except Exception: time.sleep(2)
    return set()

def src_hackertarget(d):
    try:
        return {ln.split(",")[0].strip().lower() for ln in _get(f"https://api.hackertarget.com/hostsearch/?q={d}").splitlines()
                if ln and "," in ln and ln.split(",")[0].strip().lower().endswith(d)}
    except Exception: return set()

def src_otx(d):
    try:
        j = json.loads(_get(f"https://otx.alienvault.com/api/v1/indicators/domain/{d}/passive_dns"))
        return {r.get("hostname", "").lower().lstrip("*.") for r in j.get("passive_dns", []) if r.get("hostname", "").lower().endswith(d)}
    except Exception: return set()

def src_wayback(d):
    try:
        import re
        txt = _get(f"http://web.archive.org/cdx/search/cdx?url=*.{d}&output=text&fl=original&collapse=urlkey&limit=8000")
        hosts = set()
        for u in txt.splitlines():
            m = re.search(r"https?://([^/:]+)", u)
            if m and m.group(1).lower().endswith(d): hosts.add(m.group(1).lower())
        return hosts
    except Exception: return set()

def src_subfinder(d):
    if not shutil.which("subfinder"): return set()
    try:
        r = subprocess.run(["subfinder", "-d", d, "-silent"], capture_output=True, text=True, timeout=300)
        return {l.strip().lower() for l in r.stdout.splitlines() if l.strip().endswith(d)}
    except Exception: return set()

def src_chaos(d):
    if not shutil.which("chaos") or not os.environ.get("CHAOS_KEY"): return set()
    try:
        r = subprocess.run(["chaos", "-d", d, "-silent"], capture_output=True, text=True, timeout=180)
        return {l.strip().lower() for l in r.stdout.splitlines() if l.strip().endswith(d)}
    except Exception: return set()

SOURCES = [("subfinder", src_subfinder), ("crt.sh", src_crtsh), ("hackertarget", src_hackertarget),
           ("otx", src_otx), ("wayback", src_wayback), ("chaos", src_chaos)]

def gather(d):
    allsubs, per = set(), {}
    for name, fn in SOURCES:
        s = fn(d); per[name] = len(s); allsubs |= s
        print(f"    {name:12s}: {len(s)}")
    return allsubs, per

def probe(hosts):
    if not hosts or not shutil.which("httpx"): return ""
    try:
        r = subprocess.run(["httpx", "-silent", "-status-code", "-title", "-tech-detect", "-cdn"],
                           input="\n".join(sorted(hosts)), capture_output=True, text=True, timeout=300)
        return r.stdout.strip()
    except Exception: return ""

def notify(text):
    hook = os.environ.get("BBAM_WEBHOOK")   # Discord/Slack webhook
    if hook:
        try:
            urllib.request.urlopen(urllib.request.Request(hook, data=json.dumps({"content": text[:1900]}).encode(),
                                   headers={"Content-Type": "application/json"}), timeout=20)
        except Exception as e: print(f"    [!] discord gagal: {e}")
    tok, chat = os.environ.get("BBAM_TG_TOKEN"), os.environ.get("BBAM_TG_CHAT")   # Telegram
    if tok and chat:
        try:
            urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage?%s" % (tok, urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]})), timeout=20)
        except Exception as e: print(f"    [!] telegram gagal: {e}")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("domains", nargs="+"); ap.add_argument("--probe", action="store_true")
    ap.add_argument("--out", default=os.path.expanduser("~/bb-monitor"))
    a = ap.parse_args()
    today = datetime.date.today().isoformat()
    for domain in a.domains:
        d = domain.strip().lower(); base = os.path.join(a.out, d); os.makedirs(base, exist_ok=True)
        snap = os.path.join(base, "known.txt")
        prev = {l.strip() for l in open(snap, encoding="utf-8")} if os.path.exists(snap) else set()
        print(f"[{d}] mengumpulkan sumber pasif...")
        cur, per = gather(d)
        if not cur:
            print(f"[{d}] tidak ada data (semua sumber gagal)."); continue
        new = sorted(cur - prev); first = not prev
        open(snap, "w", encoding="utf-8").write("\n".join(sorted(cur)))
        rep = [f"# Asset Monitor — {d} — {today}",
               f"Total subdomain: {len(cur)} | baru: {len(new)}" + ("  (baseline)" if first else ""),
               "Sumber: " + ", ".join(f"{k}={v}" for k, v in per.items())]
        probed = ""
        if new and not first:
            rep += ["\n## 🆕 SUBDOMAIN BARU (uji duluan — anti-dupe)"] + [f"- {h}" for h in new]
            if a.probe:
                probed = probe(new)
                if probed: rep += ["\n## Live check subdomain baru\n```", probed, "```"]
            notify(f"🆕 {len(new)} subdomain baru di {d}:\n" + "\n".join(new[:25]))
        elif first:
            rep.append("\n> baseline disimpan; subdomain baru muncul mulai run berikutnya.")
        else:
            rep.append("\n_(tidak ada subdomain baru)_")
        os.makedirs(os.path.join(base, "history"), exist_ok=True)
        open(os.path.join(base, "history", f"{today}.md"), "w", encoding="utf-8").write("\n".join(rep))
        open(os.path.join(base, "latest.md"), "w", encoding="utf-8").write("\n".join(rep))
        print(f"[{d}] total={len(cur)} baru={len(new)} -> {base}/latest.md")

if __name__ == "__main__":
    main()

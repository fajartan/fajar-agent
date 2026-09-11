#!/usr/bin/env python3
"""FAJAR-AGENT (bbtui) -- TUI modern (Textual): harness bug bounty 5 platform + recon/monitor/dedup + LLM agent.

Full-screen: sidebar (stats+filter), DataTable program, panel detail scope, run-log streaming.
Keybindings: / cari - r refresh - e recon - m monitor - d dedup - s settings - q keluar.
Butuh: python3 + 'textual'  (pip install --user --break-system-packages textual  |  atau venv).
Data: arkadiyt/bounty-targets-data. Enrichment provider opsional (jina gratis/firecrawl/serper/h1api).
Companion headless: daily-target-finder.py
"""
import json, os, re, sys, base64, shlex, shutil, datetime, subprocess, urllib.request, urllib.parse

try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical, VerticalScroll, Center, Middle
    from textual.widgets import (Header, Footer, DataTable, Static, Input, RichLog, Label, Button, OptionList, ProgressBar, TextArea, Switch, Select, Tabs, Tab)
    from textual.message import Message
    from textual.widgets.option_list import Option
    from textual.screen import ModalScreen
    from textual.binding import Binding
    from textual import work
except ImportError:
    sys.exit("[!] butuh 'textual'. Pasang:  pip install --user --break-system-packages textual\n"
             "    (atau: python3 -m venv ~/.venv-bbtui && ~/.venv-bbtui/bin/pip install textual && ~/.venv-bbtui/bin/python bbtui.py)")

BASE = "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/{}_data.json"
DISCLOSE_URL = "https://raw.githubusercontent.com/disclose/diodb/master/program-list.json"  # 2400+ program independen/VDP/self-hosted
CFG_DIR = os.path.expanduser("~/.config/bbtui"); CFG = os.path.join(CFG_DIR, "config.json")
SEEN = os.path.join(CFG_DIR, "seen.json")  # baseline utk deteksi PROGRAM BARU antar sesi
STATUS = os.path.join(CFG_DIR, "status.json")  # status worklist per program: reviewed/working/skip
CACHE = os.path.join(CFG_DIR, "programs_cache.json")  # cache tarikan terakhir (start instan)
STALE_HOURS = 6  # cache lebih tua dari ini -> auto-refresh di latar saat start
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CFG = {"platforms": ["hackerone", "bugcrowd", "yeswehack", "intigriti", "federacy"],
               "require_wildcard": True, "min_bounty": 0, "asset_type": "", "mouse": True,
               # kriteria lanjutan (0/""/any = abaikan)
               "min_assets": 0, "max_assets": 0, "min_wildcards": 0, "managed_filter": "any",
               "min_sev": "", "min_efficiency": 0, "max_ttfr": 0, "max_ttb": 0, "min_quiet": 0, "sort": "platform",
               "enrich_provider": "jina",
               "firecrawl_api_key": "", "scraperapi_key": "", "serper_api_key": "", "h1_api_user": "", "h1_api_token": "",
               "bugcrowd_api_token": "", "intigriti_api_token": "", "yeswehack_api_token": "",  # disimpan; authed-pull penuh baru H1
               "telegram_token": "", "telegram_chat": "", "discord_webhook": "",
               # Telegram bot FAJAR-AGENT (pakai token+chat di atas)
               "telegram_bot_enabled": False, "telegram_allow_active": False, "telegram_allowlist": "",
               "llm_provider": "anthropic", "llm_model": "", "llm_base_url": "", "llm_api_key": "", "llm_context": 0,
               "mcp_servers": {},   # integrasi MCP: {"nama": {"command","args":[],"env":{},"trusted":false,"enabled":true}}
               "external_tools": {   # integrasi tool lain (jalan bila terpasang) -- {target}=domain {url} {handle}. Edit bebas.
                   # -- orkestrator recon --
                   "reconftw": "reconftw -d {target} -r",
                   "bbot": "bbot -t {target} -p subdomain-enum",
                   # -- enumerasi subdomain --
                   "subfinder": "subfinder -d {target} -silent",
                   "amass": "amass enum -passive -d {target}",
                   "assetfinder": "assetfinder --subs-only {target}",
                   "findomain": "findomain -t {target} -q",
                   "dnsx": "dnsx -d {target} -silent",
                   # -- probe & crawl --
                   "httpx": "httpx -u {url} -title -tech-detect -status-code -silent",
                   "katana": "katana -u {url} -silent -jc",
                   "gau": "gau {target}",
                   "waybackurls": "waybackurls {target}",
                   "hakrawler": "hakrawler -url {url} -depth 2",
                   "gospider": "gospider -s {url} -d 2",
                   "getjs": "getJS --url {url}",
                   # -- content discovery / fuzzing --
                   "ffuf": "ffuf -u {url}/FUZZ -w ~/seclists/Discovery/Web-Content/raft-medium-directories.txt",
                   "feroxbuster": "feroxbuster -u {url}",
                   "gobuster": "gobuster dir -u {url} -w ~/seclists/Discovery/Web-Content/common.txt",
                   "dirsearch": "dirsearch -u {url}",
                   # -- parameter mining --
                   "arjun": "arjun -u {url}",
                   "paramspider": "paramspider -d {target}",
                   # -- vuln scanner --
                   "nuclei": "nuclei -u {url} -severity medium,high,critical -silent",
                   "nikto": "nikto -h {url}",
                   "wpscan": "wpscan --url {url} --enumerate vp",
                   "testssl": "testssl {target}",
                   "wafw00f": "wafw00f {url}",
                   # -- XSS / SQLi / injeksi --
                   "dalfox": "dalfox url {url}",
                   "xsstrike": "xsstrike -u {url}",
                   "sqlmap": "sqlmap -u {url} --batch --level 2",
                   "ghauri": "ghauri -u {url} --batch",
                   "crlfuzz": "crlfuzz -u {url}",
                   # -- subdomain takeover --
                   "subzy": "subzy run --target {target}",
                   "subjack": "subjack -d {target} -ssl",
                   # -- secret / git --
                   "trufflehog": "trufflehog filesystem {target}",
                   "gitleaks": "gitleaks detect --source {target}",
                   # -- port scan --
                   "naabu": "naabu -host {target} -silent",
                   "nmap": "nmap -sV -T4 {target}",
                   "masscan": "masscan {target} -p1-65535 --rate 1000",
                   # -- screenshot --
                   "gowitness": "gowitness single {url}",
                   "aquatone": "aquatone-discover -d {target}",
                   # -- Burp Suite (GUI) --
                   # Burp itu GUI: pakai Repeater/Intruder manual. Baris ini contoh membuka Burp / Burp REST API bila diaktifkan.
                   "burpsuite": "BurpSuiteCommunity",
                   "burp_active_scan": "curl -s -X POST http://127.0.0.1:1337/v0.1/scan -d '{\"urls\":[\"{url}\"]}'",
                   # -- AI/agent framework (sesuaikan invocation asli) --
                   "hermes": "hermes scan {target}",
                   "neurosploit": "neurosploit --target {target}",
                   "hexstrike": "hexstrike-ai --target {target}",
               }}
SEV = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0, None: 0}
PROVIDERS = ["jina", "firecrawl", "scraperapi", "serper", "h1api"]
PLAT_ALL = ["hackerone", "bugcrowd", "yeswehack", "intigriti", "federacy", "disclose"]

def load_cfg():
    os.makedirs(CFG_DIR, exist_ok=True); c = dict(DEFAULT_CFG)
    if os.path.exists(CFG):
        try: c.update(json.load(open(CFG, encoding="utf-8")))
        except Exception: pass
    # gabungkan ext-tools default yg belum ada (tanpa menimpa kustom milik user)
    merged = dict(DEFAULT_CFG["external_tools"]); merged.update(c.get("external_tools") or {})
    c["external_tools"] = merged
    return c

def save_cfg(c):
    os.makedirs(CFG_DIR, exist_ok=True); json.dump(c, open(CFG, "w", encoding="utf-8"), indent=1)
    try: os.chmod(CFG, 0o600)
    except Exception: pass

def _get(url, headers=None, data=None, timeout=90):
    return urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers or {}), timeout=timeout).read().decode("utf-8", "replace")

def fetch(pf):
    url = DISCLOSE_URL if pf == "disclose" else BASE.format(pf)
    return json.loads(_get(url, headers={"User-Agent": "bbtui/3"}))
def is_wild(s): return isinstance(s, str) and "*" in s
def types_of(pr):
    t = set()
    for s in pr.get("scope", []):
        s = str(s).lower()
        if "play.google" in s or s.startswith("com.") or ".apk" in s or "android" in s: t.add("android")
        elif "apps.apple" in s or "itunes.apple" in s or "testflight" in s or (s.isdigit() and len(s) >= 6): t.add("ios")
        elif s.startswith("api.") or "/api" in s or ".api." in s: t.add("api")
        elif "." in s: t.add("web")
    return t or {"other"}

def reward(pr):
    # pakai .get(): program dari sumber non-standar (disclose/private/manual) bisa
    # kekurangan field, dan KeyError di sini mematikan /new + pembukaan layar chat.
    c = pr.get("cur", "$"); lo, hi = pr.get("bounty_min"), pr.get("bounty_max")
    if lo is not None and hi is not None: return f"{c}{lo}-{c}{hi}"
    if hi is not None: return f"<={c}{hi}"
    if lo is not None: return f">={c}{lo}"
    return "bounty" if pr.get("bounty") else "-"

def norm(pf, p):
    if pf == "hackerone":
        if p.get("submission_state") != "open": return None
        ins = (p.get("targets") or {}).get("in_scope", [])
        scope = [t.get("asset_identifier") for t in ins if t.get("asset_identifier")]
        wild = [t.get("asset_identifier") for t in ins if t.get("asset_type") == "WILDCARD" or is_wild(t.get("asset_identifier"))]
        mx = max((SEV.get((t.get("max_severity") or "").lower(), 0) for t in ins), default=0)
        sev = {v: k for k, v in SEV.items()}.get(mx, "-")
        return dict(platform="hackerone", key=f"h1|{p.get('handle')}", name=p.get("name"), url=p.get("url"),
                    bounty=bool(p.get("offers_bounties")), bounty_min=None, bounty_max=None, cur="$", maxsev=sev,
                    managed=bool(p.get("managed_program")), eff=p.get("response_efficiency_percentage"),
                    ttfr=p.get("average_time_to_first_program_response"), ttb=p.get("average_time_to_bounty_awarded"),
                    ttr=p.get("average_time_to_report_resolved"),
                    signal=f"1st~{p.get('average_time_to_first_program_response')}h resolve~{p.get('average_time_to_report_resolved')}h ttb~{p.get('average_time_to_bounty_awarded')}h eff{p.get('response_efficiency_percentage')}%",
                    scope=scope, wild=wild)
    if pf == "bugcrowd":
        ins = (p.get("targets") or {}).get("in_scope", [])
        ids = [x for x in ((t.get("target") or t.get("uri") or t.get("name")) for t in ins) if x]
        mp = p.get("max_payout") or 0
        return dict(platform="bugcrowd", key=f"bc|{p.get('name')}", name=p.get("name"), url=p.get("url"),
                    bounty=mp > 0, bounty_min=None, bounty_max=(mp or None), cur="$", maxsev="-", signal="-",
                    managed=bool(p.get("managed_by_bugcrowd")), eff=None, ttfr=None, ttb=None, ttr=None,
                    scope=ids, wild=[x for x in ids if is_wild(x)])
    if pf == "yeswehack":
        if not p.get("public") or p.get("disabled"): return None
        ins = (p.get("targets") or {}).get("in_scope", [])
        ids = [t.get("target") for t in ins if t.get("target")]
        return dict(platform="yeswehack", key=f"ywh|{p.get('id') or p.get('name')}", name=p.get("name"), url=p.get("url", ""),
                    bounty=bool(p.get("max_bounty")), bounty_min=(p.get("min_bounty") or None), bounty_max=(p.get("max_bounty") or None),
                    cur="$", maxsev="-", signal="-", managed=bool(p.get("managed")), eff=None, ttfr=None, ttb=None, ttr=None,
                    scope=ids, wild=[x for x in ids if is_wild(x)])
    if pf == "intigriti":
        if p.get("confidentiality_level") != "public": return None
        ins = (p.get("targets") or {}).get("in_scope", [])
        ids = [t.get("endpoint") for t in ins if t.get("endpoint")]
        mn = (p.get("min_bounty") or {}).get("value"); mx = (p.get("max_bounty") or {}).get("value")
        cur = {"USD": "$", "EUR": "EUR", "GBP": "£"}.get((p.get("max_bounty") or {}).get("currency") or "USD", "$")
        return dict(platform="intigriti", key=f"it|{p.get('handle') or p.get('id')}", name=p.get("name"), url=p.get("url", ""),
                    bounty=bool(mx), bounty_min=(mn or None), bounty_max=(mx or None), cur=cur, maxsev="-", signal="-",
                    managed=None, eff=None, ttfr=None, ttb=None, ttr=None,
                    scope=ids, wild=[x for x in ids if is_wild(x)])
    if pf == "federacy":
        if not p.get("offers_awards"): return None
        ins = (p.get("targets") or {}).get("in_scope", [])
        ids = [t.get("target") for t in ins if t.get("target")]
        return dict(platform="federacy", key=f"fd|{p.get('id') or p.get('name')}", name=p.get("name"), url=p.get("url", ""),
                    bounty=True, bounty_min=None, bounty_max=None, cur="$", maxsev="-", signal="-",
                    managed=None, eff=None, ttfr=None, ttb=None, ttr=None,
                    scope=ids, wild=[x for x in ids if is_wild(x)])
    if pf == "disclose":   # diodb -- program independen/self-hosted/VDP (scope tak terstruktur -> baca policy_url)
        pol = p.get("policy_url")
        if not pol or str(p.get("policy_url_status", "")).lower() == "dead": return None
        return dict(platform="disclose", key=f"dio|{p.get('program_name') or pol}", name=p.get("program_name") or pol,
                    url=pol, bounty=(str(p.get("offers_bounty", "")).lower() == "yes"), bounty_min=None, bounty_max=None,
                    cur="$", maxsev="-", signal=f"safe_harbor={p.get('safe_harbor','?')} swag={p.get('offers_swag')}",
                    managed=None, eff=None, ttfr=None, ttb=None, ttr=None, scope=[], wild=[])
    return None

def quiet_score(pr, is_new=False):
    """Skor 0-100 'anti-ramai' -- PROXY dari data yg benar2 ada (BUKAN jumlah hacker asli).
    Makin tinggi = makin mungkin sepi/minim-duplikat. Heuristik transparan (lihat PROGRAM-SELECTION.md)."""
    s = 0
    if is_new: s += 35                                    # sinyal anti-ramai terkuat yg kita punya
    if pr.get("managed") is False: s += 10                # unmanaged cenderung kurang di-highlight
    s += min(len(pr.get("wild", [])) * 4, 16)             # wildcard = surface luas
    s += min(len(pr.get("scope", [])) // 5, 15)           # scope besar
    if types_of(pr) & {"android", "ios", "api"}: s += 12  # aset niche = lebih jarang disentuh
    eff = pr.get("eff")
    if isinstance(eff, (int, float)) and eff < 60: s += 6  # program kurang 'dioptimalkan' = hype rendah
    ttb = pr.get("ttb")
    if isinstance(ttb, (int, float)) and ttb and ttb > 168: s += 6  # bayar lambat = peminat lebih sedikit
    return min(s, 100)

def _sev_rank(name):
    return SEV.get(str(name).lower(), 0)

def _num(cfg, k):
    try: return float(cfg.get(k) or 0)
    except Exception: return 0.0

def passes(pr, cfg):
    # PROGRAM PRIVATE (kamu diundang) = SELALU tampil. Filter anti-ramai (bounty/wildcard/
    # managed/quiet/assets) itu utk menyaring ribuan program PUBLIK; program yg kamu punya
    # akses khusus jangan pernah disembunyikan olehnya (dulu VDP-private dibuang oleh 'if not bounty').
    if "PRIVATE" in str(pr.get("signal", "")): return True
    if not pr["bounty"]: return False
    # disclose (VDP/independen, tak punya wildcard) = tampil walau wildcard wajib
    _relax = pr.get("platform") == "disclose"
    if cfg["require_wildcard"] and not pr["wild"] and not _relax: return False
    if cfg["min_bounty"] and pr["bounty_max"] is not None and pr["bounty_max"] < cfg["min_bounty"]: return False
    af = [x for x in str(cfg.get("asset_type", "")).lower().replace(" ", "").split(",") if x]
    if af:
        want = set(af)
        if "mobile" in want: want |= {"android", "ios"}
        if not (types_of(pr) & want): return False
    # --- kriteria lanjutan (semua opsional; 0/kosong = abaikan) ---
    na = len(pr.get("scope", [])); nw = len(pr.get("wild", []))
    if _num(cfg, "min_assets") and na < _num(cfg, "min_assets"): return False
    if _num(cfg, "max_assets") and na > _num(cfg, "max_assets"): return False
    if _num(cfg, "min_wildcards") and nw < _num(cfg, "min_wildcards"): return False
    mf = str(cfg.get("managed_filter", "any")).lower()
    if mf == "only" and pr.get("managed") is not True: return False
    if mf == "exclude" and pr.get("managed") is True: return False
    # Kriteria berbasis data yg tak semua platform punya = PASS-THROUGH:
    # hanya menyaring program yg PUNYA datanya; yg tak punya TIDAK dibuang.
    ms = str(cfg.get("min_sev", "")).lower().strip()
    if ms and ms in SEV:
        cs = str(pr.get("maxsev", "")).lower()
        if cs in SEV and cs not in ("none", "-") and SEV[cs] < SEV[ms]: return False
    eff = pr.get("eff")
    if _num(cfg, "min_efficiency") and isinstance(eff, (int, float)) and eff < _num(cfg, "min_efficiency"): return False
    if _num(cfg, "max_ttfr"):
        v = pr.get("ttfr")
        if isinstance(v, (int, float)) and v > _num(cfg, "max_ttfr"): return False
    if _num(cfg, "max_ttb"):
        v = pr.get("ttb")
        if isinstance(v, (int, float)) and v > _num(cfg, "max_ttb"): return False
    return True

def _api_test_one(name, fn):
    """Jalankan satu tes, seragamkan hasil -> (nama, status, detail)."""
    try:
        ok, detail = fn()
        return (name, "OK" if ok else "GAGAL", detail)
    except SystemExit as e:
        return (name, "GAGAL", str(e)[:120])
    except Exception as e:
        return (name, "GAGAL", f"{type(e).__name__}: {e}"[:120])

def api_test_all(cfg):
    """Tes tiap API key yang DIISI. Return list (nama, status, detail).

    status: OK (jalan) / GAGAL (error) / '-' (dilewati: kosong atau belum aktif).
    Request minimal & read-only. Baca nilai dari cfg (yg sudah diisi live sebelum tes).
    """
    res = []

    # --- HackerOne (user + token) ---
    u, t = cfg.get("h1_api_user"), cfg.get("h1_api_token")
    if t and not u:
        res.append(("HackerOne", "GAGAL", "h1_api_user KOSONG (isi username H1, bukan email)"))
    elif u and not t:
        res.append(("HackerOne", "GAGAL", "token kosong"))
    elif u and t:
        def _h1():
            hdr = _h1_auth_hdr(cfg)
            d = json.loads(_get("https://api.hackerone.com/v1/hackers/programs?page%5Bsize%5D=1", headers=hdr, timeout=25))
            n = len(d.get("data", []))
            return True, f"auth OK — akses {('>=1 program' if n else '0 program (belum di-invite?)')}"
        res.append(_api_test_one("HackerOne", _h1))
    else:
        res.append(("HackerOne", "-", "kosong"))

    # --- Intigriti ---
    it = cfg.get("intigriti_api_token")
    if it:
        def _it():
            d = json.loads(_get("https://api.intigriti.com/external/researcher/v1/programs?limit=1", headers=_bearer(it), timeout=25))
            items = d if isinstance(d, list) else (d.get("records") or d.get("data") or d.get("items") or [])
            return True, f"token OK — {len(items)} program terlihat"
        res.append(_api_test_one("Intigriti", _it))
    else:
        res.append(("Intigriti", "-", "kosong"))

    # --- YesWeHack ---
    yw = cfg.get("yeswehack_api_token")
    if yw:
        def _yw():
            d = json.loads(_get("https://api.yeswehack.com/programs?limit=1", headers=_bearer(yw), timeout=25))
            n = len(d.get("items") or [])
            return True, f"token OK — {n} program terlihat"
        res.append(_api_test_one("YesWeHack", _yw))
    else:
        res.append(("YesWeHack", "-", "kosong"))

    # --- LLM (provider+model+key+base) ---
    prov, model, base, key = _llm_creds(cfg)
    if key:
        def _llm():
            models = _llm_mod().fetch_models(prov, key, base)
            if models and not str(models[0]).startswith("["):
                hit = "model cocok" if any(model in str(m) for m in models) else f"model '{model}' TAK ada di daftar"
                return True, f"{prov} OK — {len(models)} model ({hit})"
            return False, str(models[0] if models else "tak ada model")
        res.append(_api_test_one(f"LLM ({prov})", _llm))
    else:
        res.append(("LLM", "-", "llm_api_key kosong"))

    # --- Firecrawl (dipakai /recon deep) ---
    fc = cfg.get("firecrawl_api_key")
    if fc:
        def _fc():
            # /v1/map endpoint ringan; 200/402 tetap berarti auth diterima
            try:
                _get("https://api.firecrawl.dev/v1/team/credit-usage",
                     headers={"Authorization": "Bearer " + fc}, timeout=20)
                return True, "token OK (kredit terbaca)"
            except urllib.error.HTTPError as e:
                if e.code in (200, 402):
                    return True, "token OK"
                if e.code in (401, 403):
                    return False, f"ditolak ({e.code})"
                return True, f"token diterima (HTTP {e.code})"
        res.append(_api_test_one("Firecrawl", _fc))
    else:
        res.append(("Firecrawl", "-", "kosong (opsional; utk /recon deep)"))

    # --- Telegram bot ---
    tg = cfg.get("telegram_token")
    if tg:
        def _tg():
            d = json.loads(_get(f"https://api.telegram.org/bot{tg}/getMe", timeout=20))
            if d.get("ok"):
                return True, "bot @" + str((d.get("result") or {}).get("username", "?"))
            return False, str(d.get("description", "ditolak"))
        res.append(_api_test_one("Telegram", _tg))
    else:
        res.append(("Telegram", "-", "kosong"))

    # --- catatan yang BELUM aktif ---
    if cfg.get("bugcrowd_api_token"):
        res.append(("Bugcrowd", "-", "disimpan tapi BELUM aktif (tak ada fetch)"))
    if cfg.get("serper_api_key"):
        res.append(("Serper", "-", "disimpan tapi BELUM aktif (enrich belum dipanggil)"))
    return res

def _h1_auth_hdr(cfg):
    u = cfg.get("h1_api_user"); t = cfg.get("h1_api_token")
    if not u or not t: return None
    return {"Authorization": "Basic " + base64.b64encode(f"{u}:{t}".encode()).decode(), "Accept": "application/json"}

def _h1_detail(handle, hdr):
    """Ambil scope terstruktur 1 program H1 (termasuk PRIVATE yg kamu diundang).

    PENTING: /programs/{handle} hanya memberi REFERENSI structured_scopes (id+type,
    tanpa attributes) -> dulu scope selalu KOSONG. Endpoint benar =
    /programs/{handle}/structured_scopes (berisi attributes penuh, ber-paginasi).
    """
    try:
        d = json.loads(_get(f"https://api.hackerone.com/v1/hackers/programs/{handle}", headers=hdr, timeout=30))
    except Exception:
        return None
    a = d.get("data", {}).get("attributes", {}) or {}
    assets = []
    url = f"https://api.hackerone.com/v1/hackers/programs/{handle}/structured_scopes?page%5Bsize%5D=100"
    for _pg in range(6):
        try:
            sd = json.loads(_get(url, headers=hdr, timeout=30))
        except Exception:
            break
        for s in sd.get("data", []):
            at = s.get("attributes", {}) or {}
            if at: assets.append(at)
        nxt = (sd.get("links") or {}).get("next")
        if not nxt: break
        url = nxt
    scope = [x.get("asset_identifier") for x in assets
             if x.get("asset_identifier") and x.get("eligible_for_submission", True)]
    wild = [x.get("asset_identifier") for x in assets
            if x.get("asset_identifier") and (x.get("asset_type") == "WILDCARD" or is_wild(x.get("asset_identifier")))]
    if not scope:                                  # fallback tahan-struktur
        scope = _walk_scope(d)
        wild = [i for i in scope if is_wild(i)]
    mx = max((SEV.get((x.get("max_severity") or "").lower(), 0) for x in assets), default=0)
    sev = {v: k for k, v in SEV.items()}.get(mx, "-")
    return dict(platform="hackerone", key=f"h1|{handle}", name="🔒 " + (a.get("name") or handle),
                url=f"https://hackerone.com/{handle}", bounty=bool(a.get("offers_bounties")), bounty_min=None,
                bounty_max=None, cur="$", maxsev=sev, managed=None, eff=None, ttfr=None, ttb=None, ttr=None,
                signal="PRIVATE / accessible (login API)", scope=scope, wild=wild)

def fetch_h1_private(cfg, have_keys, cap=60):
    """Tarik program yg BISA KAMU AKSES dari akun H1 (termasuk PRIVATE) via API resmi. Butuh h1_api_user+token."""
    hdr = _h1_auth_hdr(cfg)
    if not hdr: return {}, None
    url = "https://api.hackerone.com/v1/hackers/programs?page%5Bsize%5D=100"
    try:
        # 1) kumpulkan handle (murah) dari halaman list
        handles = []
        for _pg in range(8):
            d = json.loads(_get(url, headers=hdr, timeout=45))
            for it in d.get("data", []):
                h = (it.get("attributes", {}) or {}).get("handle")
                if h and f"h1|{h}" not in have_keys and h not in handles:
                    handles.append(h)
            if len(handles) >= cap: break
            nxt = (d.get("links") or {}).get("next")
            if not nxt: break
            url = nxt
        handles = handles[:cap]
        # 2) ambil detail PARALEL (dulu berurutan -> 60 request satu-satu = lambat)
        out = {pr["key"]: pr for pr in _parallel_detail(handles, lambda h: _h1_detail(h, hdr)) if pr}
        return out, None
    except Exception as e:
        return out if 'out' in dir() else {}, f"h1-api: {e}"

def _parallel_detail(items, fn, workers=10):
    """Jalankan fn(item) untuk banyak item secara paralel (I/O-bound: aman & jauh lebih cepat)."""
    from concurrent.futures import ThreadPoolExecutor
    if not items: return []
    with ThreadPoolExecutor(max_workers=min(workers, len(items))) as ex:
        return list(ex.map(fn, items))

def _bearer(tok):
    return {"Authorization": "Bearer " + tok, "Accept": "application/json"} if tok else None

_SCOPE_CONTAINER = re.compile(r"domain|target|scope|asset|endpoint", re.I)
def _looks_scope(v):
    if not isinstance(v, str): return False
    v = v.strip()
    if not v or len(v) > 200 or " " in v: return False
    if v.startswith(("http://", "https://", "*.", "*-", "com.", "android:", "ios:")): return True
    # domain / wildcard / IP
    return bool(re.match(r"^\*?[\w\-\*]+(\.[\w\-\*]+)+$", v))
def _walk_scope(obj, active=False, depth=0, out=None):
    """Telusuri JSON, ambil SEMUA string mirip-scope di dalam wadah domain/target/asset.
    Tahan perubahan struktur API (Intigriti sering bersarang: content.domains[].endpoint dll)."""
    if out is None: out = []
    if depth > 8: return out
    if isinstance(obj, dict):
        for k, v in obj.items():
            a = active or bool(_SCOPE_CONTAINER.search(str(k)))
            if a and isinstance(v, str) and _looks_scope(v):
                out.append(v.strip())
            else:
                _walk_scope(v, a, depth + 1, out)
    elif isinstance(obj, list):
        for x in obj:
            if active and isinstance(x, str) and _looks_scope(x): out.append(x.strip())
            else: _walk_scope(x, active, depth + 1, out)
    return out
def _intigriti_detail(handle, hdr):
    try:
        d = json.loads(_get(f"https://api.intigriti.com/external/researcher/v1/programs/{handle}", headers=hdr, timeout=30))
    except Exception:
        return [], []
    ids = []
    for v in _walk_scope(d):                       # dedup jaga urutan
        if v not in ids: ids.append(v)
    # buang URL milik intigriti sendiri (webLink program, bukan scope)
    ids = [v for v in ids if "intigriti.com" not in v]
    if not ids:                                    # diagnosa: simpan response mentah bila scope tetap 0
        try:
            if os.environ.get("FAJAR_DEBUG_SCOPE"):
                open(os.path.expanduser(f"~/fajar-intigriti-{re.sub(chr(92)+'W','_',str(handle))[:30]}.json"),
                     "w", encoding="utf-8").write(json.dumps(d, indent=2)[:20000])
        except Exception: pass
    return ids, [i for i in ids if is_wild(i)]

def fetch_intigriti_private(cfg, have_keys, cap=50):
    """Program akun Intigriti (termasuk PRIVATE) + scope via Personal Access Token. EKSPERIMENTAL."""
    tok = cfg.get("intigriti_api_token")
    if not tok: return {}, None
    hdr = _bearer(tok); out = {}
    try:
        d = json.loads(_get("https://api.intigriti.com/external/researcher/v1/programs?limit=500", headers=hdr, timeout=45))
        items = d if isinstance(d, list) else (d.get("records") or d.get("data") or d.get("items") or [])
        cand = []
        for it in items:
            handle = it.get("handle") or it.get("id") or it.get("programId") or it.get("name")
            if not handle or f"it|{handle}" in have_keys: continue
            cand.append((handle, it))
            if len(cand) >= cap: break
        def _build(pair):
            handle, it = pair
            scope, wild = _intigriti_detail(handle, hdr)
            url = it.get("webLink") or it.get("url") or f"https://app.intigriti.com/researcher/programs/{handle}"
            return dict(platform="intigriti", key=f"it|{handle}", name="🔒 " + str(it.get("name") or handle), url=url,
                        bounty=True, bounty_min=None, bounty_max=None, cur="$", maxsev="-", managed=None,
                        eff=None, ttfr=None, ttb=None, ttr=None, signal="PRIVATE/accessible (Intigriti token)",
                        scope=scope, wild=wild)
        out = {pr["key"]: pr for pr in _parallel_detail(cand, _build)}
        return out, None
    except Exception as e:
        return out, f"intigriti-api: {e}"

def _ywh_detail(slug, hdr):
    try:
        d = json.loads(_get("https://api.yeswehack.com/programs/" + slug, headers=hdr, timeout=30))
        scs = d.get("scopes") or []
        scope = [s.get("scope") for s in scs if s.get("scope")]
        wild = [s.get("scope") for s in scs if s.get("scope") and is_wild(s.get("scope"))]
        return scope, wild, d.get("bounty_reward_min"), d.get("bounty_reward_max")
    except Exception:
        return [], [], None, None

def fetch_ywh_private(cfg, have_keys, cap=50):
    """Program PRIVATE akun YesWeHack + scope via token (public sudah dari data publik)."""
    tok = cfg.get("yeswehack_api_token")
    if not tok: return {}, None
    hdr = _bearer(tok); out = {}
    try:
        d = json.loads(_get("https://api.yeswehack.com/programs?limit=100", headers=hdr, timeout=45))
        for it in (d.get("items") or []):
            slug = it.get("slug")
            if not slug or it.get("public"): continue   # publik sudah tercakup; ambil PRIVATE
            key = f"ywh|{slug}"
            if key in have_keys or key in out: continue
            scope, wild, bmin, bmax = _ywh_detail(slug, hdr)
            out[key] = dict(platform="yeswehack", key=key, name="🔒 " + (it.get("title") or slug),
                            url=f"https://yeswehack.com/programs/{slug}", bounty=bool(it.get("bounty")),
                            bounty_min=(bmin or None), bounty_max=(bmax or None), cur="$", maxsev="-", managed=None,
                            eff=None, ttfr=None, ttb=None, ttr=None, signal="PRIVATE/accessible (YWH token)",
                            scope=scope, wild=wild)
            if len(out) >= cap: break
        return out, None
    except Exception as e:
        return out, f"ywh-api: {e}"

def load_programs(cfg):
    cur, errs = {}, []
    all_public = set()   # SEMUA key publik (walau tersaring filter) -> dedup private yg benar
    for pf in cfg["platforms"]:
        try:
            for p in fetch(pf):
                pr = norm(pf, p)
                if not pr: continue
                all_public.add(pr["key"])
                if passes(pr, cfg): cur[pr["key"]] = pr
        except Exception as e:
            errs.append(f"{pf}: {e}")
    # + program PRIVATE dari akun (bila token diisi) -- SELALU beri feedback (masuk/ditolak/0)
    # supaya user tahu tokennya berfungsi atau tidak (dulu diam saja kalau gagal).
    def _pull(label, fn, *need):
        miss = [n for n in need if not cfg.get(n)]
        if miss: return                                  # token utama tak diisi -> lewati diam
        # dedup terhadap SEMUA publik (bukan cuma yg lolos filter) -> program publik
        # yg tersaring TIDAK re-muncul sbg 'private' (dulu linkedin/starbucks dsb dobel 🔒).
        priv, perr = fn(cfg, all_public | set(cur.keys()))
        if perr:
            errs.append(f"❌ {label}: {perr}"); return
        masuk = 0
        for k, pr in priv.items():
            if passes(pr, cfg): cur[k] = pr; masuk += 1
        ambil = len(priv)
        if ambil == 0:
            errs.append(f"⚠ {label}: token OK tapi 0 program diakses (cek izin/scope token, atau memang belum di-invite).")
        elif masuk < ambil:
            errs.append(f"🔒 {label}: +{masuk} tampil (dari {ambil}; sisanya tersaring filter — coba matikan 'wajib wildcard'/min-bounty).")
        else:
            errs.append(f"🔒 {label}: +{masuk} program private.")

    # HackerOne butuh user + token; kalau salah satu kosong -> beri tahu tepat
    if cfg.get("h1_api_token") and not cfg.get("h1_api_user"):
        errs.append("⚠ HackerOne: token diisi tapi 'h1_api_user' KOSONG — isi username H1-mu (bukan email) di Settings.")
    elif cfg.get("h1_api_user") and not cfg.get("h1_api_token"):
        errs.append("⚠ HackerOne: username diisi tapi token kosong.")
    else:
        _pull("HackerOne private", fetch_h1_private, "h1_api_user", "h1_api_token")
    _pull("Intigriti private", fetch_intigriti_private, "intigriti_api_token")
    _pull("YesWeHack private", fetch_ywh_private, "yeswehack_api_token")
    return cur, errs

# ---------- tool runner helpers ----------
def _tool(n): return os.path.join(SCRIPT_DIR, n)
def apex(pr):
    for w in pr.get("wild", []):
        w = w.lstrip("*.").strip("/")
        if "." in w and not w.replace(".", "").isdigit(): return w
    for s in pr.get("scope", []):
        s = re.sub(r"^https?://", "", str(s)).split("/")[0].lstrip("*.")
        if "." in s and not s.replace(".", "").isdigit(): return s
    return ""

# ---------- enrichment ----------
def enrich(pr, cfg):
    prov = cfg.get("enrich_provider", "jina"); url = pr["url"]
    if prov == "jina": text = _get("https://r.jina.ai/" + url, headers={"User-Agent": "bbtui"})
    elif prov == "firecrawl":
        text = json.loads(_get("https://api.firecrawl.dev/v1/scrape", headers={"Authorization": f"Bearer {cfg['firecrawl_api_key']}", "Content-Type": "application/json"},
                               data=json.dumps({"url": url, "formats": ["markdown"]}).encode())).get("data", {}).get("markdown", "")
    elif prov == "scraperapi": text = _get(f"http://api.scraperapi.com/?api_key={cfg['scraperapi_key']}&url=" + urllib.parse.quote(url, safe=""))
    elif prov == "serper":
        d = json.loads(_get("https://google.serper.dev/search", headers={"X-API-KEY": cfg["serper_api_key"], "Content-Type": "application/json"},
                            data=json.dumps({"q": f'{pr["name"]} bug bounty launch total paid reports'}).encode()))
        text = " ".join(x.get("snippet", "") for x in d.get("organic", []))
    elif prov == "h1api":
        if pr["platform"] != "hackerone": return "h1api hanya untuk HackerOne"
        h = pr["key"].split("|", 1)[1]; auth = base64.b64encode(f"{cfg['h1_api_user']}:{cfg['h1_api_token']}".encode()).decode()
        text = _get(f"https://api.hackerone.com/v1/hackers/programs/{h}", headers={"Authorization": "Basic " + auth, "Accept": "application/json"})
    else: return "provider tak dikenal"
    paid = "-"
    if re.search(r"paid|bounties|awarded", text, re.I):
        m = re.search(r"[\$EUR£]\s?\d[\d,\.]*\s*[km]?", text, re.I); paid = m.group(0) if m else "-"
    rep = (re.search(r"([\d,\.]+)\s*(?:reports?\s*resolved|resolved)", text, re.I) or [None, "-"])
    rep = rep.group(1) if hasattr(rep, "group") else "-"
    return f"provider={prov}\ntotal paid: {paid}\nreports resolved: {rep}"

def notify_channels(text, cfg):
    res = []
    tok, chat = cfg.get("telegram_token"), cfg.get("telegram_chat")
    if tok and chat:
        try:
            _get(f"https://api.telegram.org/bot{tok}/sendMessage?" + urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]}))
            res.append("telegram ok")
        except Exception as e: res.append(f"telegram gagal: {e}")
    hook = cfg.get("discord_webhook")
    if hook:
        try:
            _get(hook, headers={"Content-Type": "application/json"}, data=json.dumps({"content": text[:1900]}).encode())
            res.append("discord ok")
        except Exception as e: res.append(f"discord gagal: {e}")
    return res or ["belum ada channel (set Telegram/Discord di Settings)"]

PIPE_TAG = "# bbtui-pipeline"
def _crontab_read():
    try: return subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout
    except Exception: return ""
def _crontab_write(txt):
    try: subprocess.run(["crontab", "-"], input=txt, text=True, timeout=15); return True
    except Exception: return False
def _cron_line(hour):
    return f"0 {hour} * * * {sys.executable} {_tool('pipeline.py')} >> {os.path.expanduser('~/bb-pipeline.log')} 2>&1 {PIPE_TAG}"
def cron_install(hour):
    cur = _crontab_read()
    keep = [l for l in cur.splitlines() if PIPE_TAG not in l and l.strip()]
    keep.append(_cron_line(hour))
    return _crontab_write("\n".join(keep) + "\n")
def cron_remove():
    cur = _crontab_read()
    keep = [l for l in cur.splitlines() if PIPE_TAG not in l and l.strip()]
    return _crontab_write("\n".join(keep) + ("\n" if keep else ""))
def cron_active():
    return PIPE_TAG in _crontab_read()

# ================= UI =================
CSS = """
Screen { layout: vertical; background: $surface; }
#body { height: 1fr; padding: 0 1; }
#side { width: 32; padding: 1; border: round $primary; margin: 0 1 0 0; scrollbar-size: 0 0; }
#stat { height: auto; }
#tablewrap { width: 2fr; border: round $primary; }
#cattabs { height: 1; background: $surface; margin: 0 0 1 0; }
#detail { width: 1fr; border: round $accent; padding: 1; margin: 0 0 0 1; scrollbar-size: 0 0; }
DataTable { height: 1fr; background: $surface; scrollbar-size-vertical: 2; scrollbar-background: $panel; scrollbar-color: $accent; scrollbar-color-hover: $warning; scrollbar-color-active: $warning; }
DataTable > .datatable--header { text-style: bold; background: $primary; }
DataTable > .datatable--cursor { background: #1e40af; color: #ffffff; text-style: bold; }
#search { dock: bottom; display: none; border: round $accent; }
#search.on { display: block; }
.title { text-style: bold; color: $accent; }
SplashScreen { align: center middle; }
#splash { width: auto; height: auto; text-align: center; padding: 2 6; border: round $accent; background: $panel; }
ModalScreen { align: center middle; }
ModalScreen #stat { width: 84; max-height: 90%; border: round $accent; padding: 1 2; background: $panel; }
ModalScreen #stat Label { width: 100%; }
ModalScreen #stat Static { width: 100%; }
GuideScreen #guide { width: 96%; max-height: 94%; border: round $accent; padding: 1 2; background: $panel; }
GuideScreen #guide Static { width: 100%; }
#stat Horizontal { height: auto; align: left middle; margin: 1 0; }
.setbtns { height: auto; margin: 1 0; }
.setrow { height: auto; align: left middle; margin: 0; }
.setrow Switch { margin: 0 1 0 0; }
.setrow Label { width: auto; }
#stat Select { margin: 0 0 1 0; width: 62; }
#apires { height: auto; margin: 1 0; padding: 0 1; }
Button { height: 3; width: auto; min-width: 16; margin: 0 2 0 0; border: round $primary; }
#chatwrap { width: 100%; height: 100%; border: round $accent; background: $surface; layers: base pop; }
#chathdr { height: 1; background: $accent; color: $text; text-style: bold; padding: 0 1; }
#chatscroll { height: 1fr; background: $surface; scrollbar-size: 0 0; }
#chatlog { height: auto; padding: 0 1; }
#chatstatus { height: 1; color: $accent; padding: 0 1; }
#thinkwrap { height: 1; padding: 0 1; display: none; }
#thinkwrap.on { display: block; }
#thinklbl { width: auto; color: $accent; }
#thinkbar { width: auto; color: $accent; padding: 0 0 0 1; }
#chatbar { dock: bottom; height: 5; align-vertical: middle; }
#chatinput { width: 1fr; height: 5; border: round $accent; scrollbar-size: 0 0; }
#chatinput:focus { border: round $success; }
#chatbar Button { height: 3; min-width: 8; margin: 0; }
#reslist { height: auto; max-height: 22; border: round $primary; margin: 1 0; }
ContextMenuScreen { align: left top; background: $background 30%; }
#ctxlist { width: 34; height: auto; max-height: 16; border: round $accent; background: $panel; }
#slashbox { layer: pop; dock: bottom; offset: 0 -5; width: 100%; height: auto; max-height: 12; border: round $accent; background: $panel; display: none; }
#slashbox.on { display: block; }
"""

BANNER = (
    "██████╗ ██████╗ ████████╗██╗   ██╗██╗\n"
    "██╔══██╗██╔══██╗╚══██╔══╝██║   ██║██║\n"
    "██████╔╝██████╔╝   ██║   ██║   ██║██║\n"
    "██╔══██╗██╔══██╗   ██║   ██║   ██║██║\n"
    "██████╔╝██████╔╝   ██║   ╚██████╔╝██║\n"
    "╚═════╝ ╚═════╝    ╚═╝    ╚═════╝ ╚═╝"
)

class SplashScreen(ModalScreen):
    def compose(self) -> ComposeResult:
        yield Static(f"{AGENT_BANNER}\n\n"
                     f"[b]FAJAR-AGENT[/] v{AGENT_VERSION} -- [b]Bug-Bounty Hunting Harness[/]\n"
                     "[dim]5 platform - anti-dupe - recon - monitor - dedup - LLM agent[/]\n"
                     "[dim]owner: researcher[/]\n\n"
                     "[yellow]> tekan Enter untuk mulai[/]", id="splash")
    def on_key(self, event):
        event.stop(); self.app.pop_screen()

class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "tutup"), ("question_mark", "app.pop_screen", "tutup")]
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="stat"):
            yield Static(
                "[b cyan]FAJAR-AGENT -- Bantuan / Fitur[/]\n\n"
                "[b]Navigasi[/]\n"
                "  ^/v pindah baris   /  cari nama/scope   r  refresh   q  keluar   ?  bantuan\n"
                "  [yellow]b[/] view program BARU   [yellow]c[/] ganti urutan (platform->quiet->reward->assets)\n\n"
                "[b]WORKLIST[/] (status per program, TERSIMPAN antar sesi):\n"
                "  Kolom [b]S[/]: 🆕 baru  ·  [dim].[/] belum ditinjau  ·  👁 ditinjau  ·  🎯 dikerjakan  ·  🔕 skip\n"
                "  [yellow]v[/] 👁 ditinjau   [yellow]k[/] 🎯 dikerjakan   [yellow].[/] 🔕 skip (tekan lagi=kembalikan)   [yellow]Enter[/] buka=👁\n"
                "  [b]SOROT MOUSE[/] (klik+drag) atau [yellow]Space[/] = pilih MULTI - [yellow]a[/] semua - [yellow]Enter[/] MENU (ke semua terpilih) - [yellow]esc[/] batal\n"
                "  [dim]MENU (Enter/klik-kanan): status worklist + recon/monitor/dedup/workspace/notify/ext-tools/handoff + llm/strategist. Klik luar = tutup.\n"
                "  [yellow]f[/] ganti view (semua/baru/belum/ditinjau/kerja/skip)   recon/monitor/llm auto 🎯\n\n"
                "[b]Kolom Q = skor QUIET (anti-ramai, 0-100)[/] -- PROXY dari data nyata: baru + scope besar +\n"
                "  aset niche (android/ios/api) + unmanaged + program kurang 'dioptimalkan'. Makin tinggi = makin\n"
                "  mungkin sepi/minim-duplikat. [dim]Bukan hitungan hacker asli -- itu tak ada di data gratis.[/]\n\n"
                "[b]Aksi pada program tersorot[/] (target auto-terisi, bisa diedit/ketik manual):\n"
                "  [yellow]e[/] Recon      -> extract web: subdomain+httpx+katana+JS+endpoint+gf -> ~/bb-recon/\n"
                "                (pilih profil: passive / standard / deep)\n"
                "  [yellow]m[/] Monitor    -> pantau subdomain BARU (multi-sumber) -> ~/bb-monitor/ (cocok di-cron)\n"
                "  [yellow]d[/] Dedup      -> kelas bug yang SUDAH dilaporkan di program -> known-issues.md\n"
                "  [yellow]w[/] Workspace  -> buat folder target ~/bb-workspaces/<nama>/ (scope ter-seed)\n"
                "  [yellow]n[/] Notify     -> kirim program ini ke Telegram/Discord\n"
                "  [yellow]x[/] Ext-tools  -> jalankan tool lain (hermes/neurosploit/nuclei/sqlmap) via command template\n"
                "  [yellow]p[/] Pipeline   -> jalankan rangkaian OTOMATIS sekarang (finder->scope.md->dedup->recon)\n"
                "  [yellow]g[/] Jadwal     -> SCHEDULING: pasang/hapus cron pipeline harian (dari TUI)\n"
                "  [yellow]l[/] LLM Agent  -> CHAT harness bertahap (ala Hermes/OpenCode/Claude Code): goal -> tahap -> 'lanjut'.\n"
                "               status bar REAL (aktivitas-token-konteks%-auto-compact) - slash: /help /yolo /model /new\n"
                "               /clear /resume /memory /skills /tools /context /compact /status - ctrl+a yolo - ctrl+o model\n\n"
                "[b]Settings[/] ([yellow]s[/]):\n"
                "  KRITERIA: platform, min bounty, wajib-wildcard\n"
                "  ENRICHMENT: provider (jina gratis / firecrawl / serper / h1api) + API key\n"
                "  NOTIFIKASI: Telegram bot token+chat id, Discord webhook\n\n"
                "[b]External tools[/]: edit [b]~/.config/bbtui/config.json[/] -> external_tools {nama: \"cmd {target}\"}.\n"
                "[b]Kolom[/]: Program - Plat - Reward - WC(wildcard) - Aset - Sev.\n\n"
                "[b green]>> tekan [yellow]i[/] untuk PANDUAN LENGKAP[/] [dim](semua alur, perintah, aturan + infografis)[/]  ·  [dim]esc = tutup[/]"
            )
    def action_dummy(self): pass

class GuideScreen(ModalScreen):
    """PANDUAN LENGKAP — semua alur, perintah, aturan & desain FAJAR-AGENT dalam satu layar gulir.
    Dibuka dgn tombol [i] dari dashboard. Konten disusun per-seksi agar 1 error markup tak merusak semua."""
    BINDINGS = [("escape", "app.pop_screen", "tutup"), ("i", "app.pop_screen", "tutup"),
                ("q", "app.pop_screen", "tutup"),
                ("up", "su", "naik"), ("down", "sd", "turun"),
                ("pageup", "pu", "hal naik"), ("pagedown", "pd", "hal turun"),
                ("home", "top", "atas"), ("end", "bot", "bawah")]
    # \[..] = kurung LITERAL (mis. \[FAKTA]) supaya Rich tak menganggapnya tag markup lalu membuangnya.
    SECTIONS = [
        ("APA ITU FAJAR-AGENT",
         "Harness bug-bounty: dashboard pemilihan program + agent LLM yang memandu SELURUH\n"
         "rangkaian hunting secara BERTAHAP di bawah kendali penuh kamu.\n"
         "Filosofi: agent MENGANALISA & MEMANDU; [b]kamu yang mengeksekusi & submit[/]. Anti-duplikat\n"
         "(cari program/celah sepi) jadi fokus utama lewat skor Q."),
        ("ATURAN POKOK (KERAS — tak bisa ditawar)",
         "  [red]1[/] Agent [b]TIDAK PERNAH submit laporan[/] — draf disiapkan, pengiriman = kamu.\n"
         "  [red]2[/] Agent [b]TIDAK PERNAH kirim traffic exploit/serangan sendiri[/] — kamu yang jalankan.\n"
         "  [red]3[/] [b]TANPA password/token mentah[/] — hanya Personal Access Token yang kamu tempel di Settings.\n"
         "  [red]4[/] [b]SCOPE-GATE[/] sebelum langkah aktif; uji hanya dgn akun milikmu sendiri.\n"
         "  [red]5[/] Aksi aktif (kirim traffic, ext-tool) perlu [yellow]/yolo[/] ON — sengaja dibuat sadar."),
        ("PETA ALUR — INFOGRAFIS",
         "[b]Garis waktu end-to-end:[/]\n"
         "[dim]  ┌─[/][b] 1 START    [/][dim]TUI memuat program (cache instan, auto-refresh bila basi)[/]\n"
         "[dim]  │[/]\n"
         "[dim]  ├─[/][b] 2 PILIH    [/]sorot 1 lalu [yellow]l[/][dim]  ·  atau[/] [yellow]t[/] [dim]STRATEGIST →[/] [yellow]/pick <nama>[/]\n"
         "[dim]  │[/]\n"
         "[dim]  ├─[/][b] 3 HUNTING  [/][dim]brief → uji terpandu → verify → draf  (CHECKPOINT tiap tahap)[/]\n"
         "[dim]  │[/]\n"
         "[dim]  ├─[/][b] 4 EKSEKUSI [/][dim]KAMU jalankan uji/PoC, tempel hasil ke chat[/]\n"
         "[dim]  │[/]\n"
         "[dim]  └─[/][b] 5 SUBMIT   [/][red]KAMU yang kirim[/][dim] — agent tak pernah submit[/]\n\n"
         "[b]Dua mode LLM & handoff:[/]\n"
         "[dim]     DASHBOARD[/] [dim]— program + skor Q + worklist[/]\n"
         "[dim]       │[/]\n"
         "[dim]       ├─[/] tekan [yellow]l[/] [dim](sudah pilih)[/]  →  [b cyan]CO-PILOT[/] [dim]· 1 target · hunting[/]\n"
         "[dim]       │[/]\n"
         "[dim]       └─[/] tekan [yellow]t[/] [dim](belum pilih)[/] →  [b green]STRATEGIST[/] [dim]· lihat semua program[/]\n"
         "[dim]                                             │[/] [dim]rekomendasi 2-3 target + alasan[/]\n"
         "[dim]                                             ↓[/]\n"
         "[dim]                                       ketik[/] [yellow]/pick <nama>[/]\n"
         "[dim]                                             ↓[/]\n"
         "[dim]                                     [/][b cyan]CO-PILOT[/] [dim]— hunting PENUH (bukan cuma recon)[/]"),
        ("ALUR UTAMA (dari nol sampai laporan)",
         "  [b]1. MULAI[/]   jalankan TUI → dashboard memuat program (cache instan, auto-refresh bila basi).\n"
         "  [b]2. PILIH[/]   dua cara (lihat 'DUA MODE LLM'):\n"
         "            a) manual: sorot baris di tabel, tekan [yellow]l[/]\n"
         "            b) minta saran: tekan [yellow]t[/] (STRATEGIST) → agent rekomendasi → [yellow]/pick <nama>[/]\n"
         "  [b]3. HUNTING[/] agent jalan bertahap (TAHAP 1→…), berhenti di CHECKPOINT tiap tahap.\n"
         "  [b]4. EKSEKUSI[/] kamu jalankan uji/PoC yang diperintahkan, tempel hasilnya ke chat.\n"
         "  [b]5. VERIFY[/]  agent verifikasi + anti-dup + susun draf laporan.\n"
         "  [b]6. SUBMIT[/]  [b]kamu[/] yang kirim ke platform. Selesai."),
        ("DASHBOARD — navigasi & kolom",
         "  [yellow]↑/↓[/] pindah baris   [yellow]/[/] cari nama/scope   [yellow]r[/] refresh data   [yellow]q[/] keluar\n"
         "  [yellow]c[/] ganti urutan (platform→quiet→reward→assets)   [yellow]f[/] ganti view   [yellow]b[/] view BARU\n"
         "  Kolom: [b]S[/](status) · Program · Plat · Reward · WC(wildcard) · Aset · Sev · [b]Q[/]\n"
         "  [b]Q = skor QUIET (anti-ramai 0-100)[/]: proxy dari data nyata (baru + scope besar + aset niche\n"
         "  android/ios/api + unmanaged). Makin TINGGI = makin mungkin sepi/minim-duplikat.\n"
         "  [dim]Bukan hitungan hacker asli — itu tak tersedia di data gratis.[/]"),
        ("DASHBOARD — WORKLIST (status tersimpan antar sesi)",
         "  Ikon kolom S: 🆕 baru · [dim].[/] belum · 👁 ditinjau · 🎯 dikerjakan · 🔕 skip\n"
         "  [yellow]v[/] 👁 ditinjau   [yellow]k[/] 🎯 kerja   [yellow].[/] 🔕 skip (tekan lagi = kembalikan)\n"
         "  [yellow]Enter[/]/[yellow]Space[/] buka MENU pindah kategori (hormati multi-seleksi).\n"
         "  View 'semua' menyembunyikan skip; view 'skip' untuk mengembalikannya."),
        ("DASHBOARD — MULTI-SELEKSI (proses banyak sekaligus)",
         "  [b]Sorot mouse[/] (klik+drag) ATAU [yellow]Space[/] tandai baris   [yellow]a[/] pilih semua tampil   [yellow]esc[/] batal\n"
         "  Klik biasa = pindah kursor saja (tak menyeleksi). Seleksi kuning hanya saat di-DRAG.\n"
         "  [yellow]Enter[/] atau klik-kanan → MENU LENGKAP: status worklist · recon/monitor/dedup · workspace ·\n"
         "     notify · ext-tools · handoff pack · llm (hunting) · strategist — semua ke SEMUA yang terpilih.\n"
         "  [dim]Recon/monitor/dedup batch memakai profil PASIF (aman) untuk banyak target.[/]"),
        ("DUA MODE LLM — inti konsepnya",
         "  [b]DI DALAM[/] (tombol [yellow]l[/]) — sudah pilih target: agent fokus 1 program, scope resmi\n"
         "     otomatis dimuat, langsung menyusun HUNTING BRIEF. (multi-seleksi → bandingkan lalu mulai.)\n\n"
         "  [b]DI LUAR[/] (tombol [yellow]t[/]) — STRATEGIST, belum pilih target: agent menerima PORTFOLIO\n"
         "     (semua program dashboard, urut skor Q + status worklist) lalu [b]merekomendasikan 2-3 target[/]\n"
         "     terbaik beserta alasan (permukaan scope, kenapa sepi/anti-dup, jenis aset).\n\n"
         "  [b]HANDOFF[/]: dari STRATEGIST ketik [yellow]/pick <nama>[/] → scope resmi target disuntik →\n"
         "     lanjut rangkaian hunting PENUH (bukan berhenti di recon). Aktif-traffic & submit tetap kamu."),
        ("TAHAP HUNTING (model checkpoint)",
         "  DI DALAM satu tahap agent OTONOM (panggil tool aman berturut-turut). Antar tahap BERHENTI\n"
         "  di CHECKPOINT → kamu balas [b]lanjut[/] / [b]stop[/] / arahan.\n"
         "  TAHAP 1 HUNTING BRIEF  → memory/skill/dedup/recon-pasif → hipotesis prioritas (novel, anti-dup)\n"
         "  TAHAP 2 EKSEKUSI TERPANDU → langkah uji 1-variabel persis; traffic aktif = [b]kamu[/]\n"
         "  TAHAP 3 VERIFY & LAPORAN → analisa hasil tempelanmu → draf laporan\n"
         "  TAHAP 4 SUBMIT = [b]HANYA KAMU[/]"),
        ("AKSI CEPAT pada program tersorot (tombol dashboard)",
         "  [yellow]e[/] Recon     web extract: subdomain+httpx+katana+JS+endpoint+gf → ~/bb-recon/ (profil passive/standard/deep)\n"
         "  [yellow]m[/] Monitor   pantau subdomain BARU (multi-sumber) → ~/bb-monitor/ (cocok di-cron)\n"
         "  [yellow]d[/] Dedup     kelas bug yang SUDAH dilaporkan di program → known-issues.md\n"
         "  [yellow]w[/] Workspace folder target ~/bb-workspaces/<nama>/ (scope ter-seed)\n"
         "  [yellow]n[/] Notify    kirim program ini ke Telegram/Discord\n"
         "  [yellow]x[/] Ext-tools jalankan tool lain (hermes/neurosploit/nuclei/sqlmap) via command template\n"
         "  [yellow]p[/] Pipeline  rangkaian OTOMATIS sekarang (finder→scope.md→dedup→recon)\n"
         "  [yellow]g[/] Jadwal    pasang/hapus cron pipeline harian dari TUI"),
        ("PERINTAH SLASH (di dalam CHAT agent)",
         "  [b]hunting[/]  [yellow]/pick <nama>[/] pilih target strategist   [yellow]/target[/] lihat scope aktif\n"
         "            [yellow]/recon[/] [yellow]/monitor[/] [yellow]/dedup[/] [dim]<domain>[/]   [yellow]/stage[/] lanjut tahap   [yellow]/handoff[/] Handoff Pack\n"
         "            [yellow]/note <teks>[/] catat temuan   [yellow]/report[/] draf laporan   [yellow]/ext[/] ext-tools\n"
         "  [b]sesi[/]     [yellow]/resume[/] pilih riwayat   [yellow]/new[/] sesi baru   [yellow]/save[/] simpan   [yellow]/export[/] ke .md\n"
         "            [yellow]/clear[/] bersihkan layar   [yellow]/context[/] pemakaian token   [yellow]/compact[/] ringkas   [yellow]/add <path>[/] muat file\n"
         "  [b]agent[/]    [yellow]/yolo[/] izinkan aksi aktif   [yellow]/model[/] [yellow]/provider[/]   [yellow]/memory[/] [yellow]/skills[/] [yellow]/tools[/] [yellow]/mcp[/]\n"
         "  [dim]Sesi TERSIMPAN OTOMATIS tiap turn & saat keluar — /resume untuk lanjut.[/]"),
        ("TOMBOL di dalam CHAT",
         "  [yellow]Enter[/] kirim   [yellow]Alt+Enter[/] baris baru   [yellow]esc[/] stop proses   [yellow]Ctrl+Q[/] keluar sesi\n"
         "  [yellow]Ctrl+PgUp/PgDn[/] gulir   [yellow]F3[/] yolo   [yellow]Ctrl+O[/] model   [yellow]Ctrl+R[/] resume   [yellow]Ctrl+L[/] bersihkan\n"
         "  [yellow]Ctrl+C[/] salin tersorot   [yellow]Ctrl+V[/] tempel   [yellow]Ctrl+Click[/] buka URL"),
        ("SETTINGS (tombol s) — API key & kriteria",
         "  [b]LLM AGENT[/]  provider (anthropic/openai) + API key + model → wajib agar chat/strategist jalan.\n"
         "  [b]PROGRAM[/]    token platform: HackerOne (h1_api_user + h1_api_token), Intigriti, Bugcrowd →\n"
         "               menampilkan program PRIVATE (🔒) yang kamu punya akses.\n"
         "     [dim]h1_api_user = USERNAME HackerOne kamu (bukan email). Token dari hackerone.com/settings/api_token.[/]\n"
         "  [b]ENRICHMENT[/] jina(gratis)/firecrawl/serper untuk perkaya data scope.\n"
         "  [b]NOTIFIKASI[/] Telegram token+chat id, Discord webhook.\n"
         "  Tiap key ada tombol [yellow]Test API[/] (Ctrl+T) untuk cek benar-benar jalan."),
        ("FITUR AGENT LANJUTAN",
         "  [b]SKILLS[/]    playbook (program-selection, recon-runbook, web/api/mobile-vuln, anti-dup, report-kit)\n"
         "            dimuat on-demand; bisa pasang baru via /skill install (sumber tepercaya).\n"
         "  [b]MEMORI[/]   ingat lintas sesi (target/dedup/finding/learning) → anti-dup jangka panjang. /memory\n"
         "  [b]DELEGATE[/] sub-agen paralel (recon/dedup/analysis) untuk kerja besar.\n"
         "  [b]MCP[/]      sambung server MCP eksternal (/mcp connect).\n"
         "  [b]HANDOFF PACK[/] (/handoff) → burp-targets.txt + handoff.md: daftar target Burp + endpoint prioritas."),
        ("LOKASI DATA (Linux)",
         "  ~/.config/bbtui/config.json     konfigurasi & API key\n"
         "  ~/.config/bbtui/status.json     status worklist\n"
         "  ~/.config/bbtui/programs_cache.json  cache program (agar tak tarik ulang tiap mulai)\n"
         "  ~/.config/bbtui/agent-sessions/ riwayat chat (/resume)\n"
         "  ~/bb-recon/  ~/bb-monitor/  ~/bb-workspaces/   hasil recon/monitor/workspace"),
    ]
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="guide"):
            yield Static("[b cyan]╭─ FAJAR-AGENT · PANDUAN LENGKAP ─╮[/]\n"
                         "[dim]gulir: ↑/↓ · PgUp/PgDn · Home/End   ·   tutup: esc / i / q[/]", id="guidehdr")
            for title, body in self.SECTIONS:
                yield Static(f"\n[b yellow]▐ {title}[/]\n{body}")
            yield Static("\n[dim]FAJAR-AGENT — analisa & pandu; eksekusi & submit tetap di tanganmu. Selamat berburu.[/]\n")
    def _sc(self): return self.query_one("#guide", VerticalScroll)
    def action_su(self): self._sc().scroll_up(animate=False)
    def action_sd(self): self._sc().scroll_down(animate=False)
    def action_pu(self): self._sc().scroll_page_up(animate=False)
    def action_pd(self): self._sc().scroll_page_down(animate=False)
    def action_top(self): self._sc().scroll_home(animate=False)
    def action_bot(self): self._sc().scroll_end(animate=False)

class SettingsScreen(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "tutup"), ("ctrl+s", "save", "simpan"), ("ctrl+t", "test_api", "test API")]
    def __init__(self, cfg): super().__init__(); self.cfg = cfg
    KEY_IDS = ("h1t", "itt", "ywt", "bct", "fc", "sp", "ntg", "ndc", "lkey")
    def compose(self) -> ComposeResult:
        c = self.cfg
        with VerticalScroll(id="stat"):
            yield Label("[b cyan]SETTINGS[/]  ([b]Ctrl+S[/] simpan \u00b7 [b]Ctrl+T[/] test API \u00b7 esc batal)", classes="title")
            with Horizontal(classes="setbtns"):
                yield Button("\U0001f50c Test API", id="btntest", variant="primary")
                yield Button("\U0001f4be Simpan", id="btnsave", variant="success")
            with Horizontal(classes="setrow"):
                yield Switch(value=False, id="showkeys")
                yield Label(" tampilkan API key (buka penyamaran utk verifikasi tempelan)")
            yield Static("", id="apires")

            yield Label("\n[b yellow]-- LLM AGENT (otak otonom) --[/]")
            yield Label("provider")
            yield Select([("anthropic", "anthropic"), ("openai / kompatibel (Groq/OpenRouter/Ollama)", "openai")],
                         value=(c.get("llm_provider") or "anthropic"), allow_blank=False, id="lprov")
            yield Label("model (mis. claude-sonnet-5 / gpt-4o-mini / llama3.1)")
            yield Input(value=c.get("llm_model", ""), id="lmodel")
            yield Label("base_url (khusus openai-compatible, mis. http://localhost:11434/v1)")
            yield Input(value=c.get("llm_base_url", ""), id="lbase")
            yield Label("llm_api_key")
            yield Input(value=c.get("llm_api_key", ""), id="lkey", password=True)
            yield Label("llm_context (override window token; 0 = auto)")
            yield Input(value=str(c.get("llm_context", 0)), id="lctx")

            yield Label("\n[b yellow]-- API KEY PLATFORM --[/]  [dim](tekan Test API utk cek)[/]")
            yield Label("[b green]HackerOne[/] -- user+token tarik program yg BISA kamu akses (termasuk PRIVATE). Token: hackerone.com/settings/api_token")
            yield Label("h1_api_user [dim](username H1, BUKAN email)[/]")
            yield Input(value=c.get("h1_api_user", ""), id="h1u")
            yield Label("h1_api_token")
            yield Input(value=c.get("h1_api_token", ""), id="h1t", password=True)
            yield Label("[b green]intigriti_api_token[/] & [b green]yeswehack_api_token[/] [dim]-- tarik PRIVATE[/]")
            yield Input(value=c.get("intigriti_api_token", ""), id="itt", password=True)
            yield Input(value=c.get("yeswehack_api_token", ""), id="ywt", password=True)
            yield Label("[b green]firecrawl_api_key[/] [dim]-- dipakai /recon profil deep[/]")
            yield Input(value=c.get("firecrawl_api_key", ""), id="fc", password=True)
            yield Label("[yellow]bugcrowd_api_token -- BELUM aktif[/] [dim](publik sdh dimuat; private belum didukung)[/]")
            yield Input(value=c.get("bugcrowd_api_token", ""), id="bct", password=True)

            yield Label("\n[b yellow]-- KRITERIA PENCARIAN --[/]")
            yield Label("Platform (pisah koma): hackerone, bugcrowd, yeswehack, intigriti, federacy, disclose")
            yield Label("[dim]disclose = 2400+ VDP (matikan 'wajib wildcard' utk lihat). Private auto ikut bila token diisi.[/]")
            yield Input(value=",".join(c.get("platforms", [])), id="plat")
            yield Label("Min bounty (0 = semua)")
            yield Input(value=str(c.get("min_bounty", 0)), id="minb")
            with Horizontal(classes="setrow"):
                yield Switch(value=bool(c.get("require_wildcard")), id="wc")
                yield Label(" Wajib punya wildcard")
            yield Label("Jenis/fokus aset (kosong=semua; koma): web, android, ios, api, mobile")
            yield Input(value=c.get("asset_type", ""), id="atype")
            yield Label("Urutkan")
            yield Select([("platform", "platform"), ("quiet (anti-ramai)", "quiet"), ("reward", "reward"), ("assets", "assets")],
                         value=(c.get("sort") or "platform"), allow_blank=False, id="sort")

            yield Label("\n[b yellow]-- KRITERIA LANJUTAN (0/kosong/any = abaikan) --[/]")
            yield Label("[dim]Lintas-platform; kriteria khusus (sev/efficiency/waktu) hanya menyaring platform yg punya datanya (kini H1).[/]")
            yield Label("Min skor QUIET 0-100 (anti-ramai)")
            yield Input(value=str(c.get("min_quiet", 0)), id="mq")
            yield Label("Min / Max jumlah aset in-scope")
            yield Input(value=str(c.get("min_assets", 0)), id="mina")
            yield Input(value=str(c.get("max_assets", 0)), id="maxa")
            yield Label("Min jumlah wildcard")
            yield Input(value=str(c.get("min_wildcards", 0)), id="minw")
            yield Label("Program managed (H1/Bugcrowd)")
            yield Select([("any", "any"), ("hanya managed", "only"), ("kecuali managed", "exclude")],
                         value=(c.get("managed_filter") or "any"), allow_blank=False, id="mgd")
            yield Label("Min severity ceiling (H1)")
            yield Select([("(abaikan)", ""), ("low", "low"), ("medium", "medium"), ("high", "high"), ("critical", "critical")],
                         value=(c.get("min_sev") or ""), allow_blank=False, id="msev")
            yield Label("[dim]-- khusus HackerOne: --[/]")
            yield Label("Min response efficiency %")
            yield Input(value=str(c.get("min_efficiency", 0)), id="meff")
            yield Label("Max jam respon pertama / Max jam bayar")
            yield Input(value=str(c.get("max_ttfr", 0)), id="mttfr")
            yield Input(value=str(c.get("max_ttb", 0)), id="mttb")

            yield Label("\n[b yellow]-- NOTIFIKASI --[/]")
            yield Label("Telegram bot token")
            yield Input(value=c.get("telegram_token", ""), id="ntg", password=True)
            yield Label("Telegram chat id")
            yield Input(value=c.get("telegram_chat", ""), id="ntc")
            yield Label("Discord webhook URL")
            yield Input(value=c.get("discord_webhook", ""), id="ndc", password=True)

            yield Label("\n[b yellow]-- TELEGRAM BOT --[/]  [dim](jalankan: bb.py telegram)[/]")
            with Horizontal(classes="setrow"):
                yield Switch(value=bool(c.get("telegram_bot_enabled")), id="tgen")
                yield Label(" Aktifkan bot (master switch)")
            with Horizontal(classes="setrow"):
                yield Switch(value=bool(c.get("telegram_allow_active")), id="tgact")
                yield Label(" Default aksi-aktif/traffic saat bot mulai [dim](aman: OFF)[/]")
            yield Label("Allowlist chat id tambahan (koma; kosong = hanya owner)")
            yield Input(value=c.get("telegram_allowlist", ""), id="tgallow")

            mcps = c.get("mcp_servers") or {}
            yield Label(f"\n[dim]MCP: {len(mcps)} server. Edit di ~/.config/bbtui/config.json. Ext-tools: tekan x di layar utama.[/]")
            yield Label("[b green]> SIMPAN: Ctrl+S[/]  [dim]- esc = batal[/]")
    def on_switch_changed(self, ev):
        if ev.switch.id == "showkeys":
            for i in self.KEY_IDS:
                try: self.query_one("#" + i, Input).password = not ev.value
                except Exception: pass
    def on_input_submitted(self, _): self.action_save()
    def on_button_pressed(self, ev):
        if ev.button.id == "btnsave": self.action_save()
        elif ev.button.id == "btntest": self.action_test_api()
    def _cfg_live(self):
        """Salin cfg dgn nilai TERKINI dari field (bisa tes sebelum simpan)."""
        def g(i):
            try: return self.query_one("#" + i, Input).value.strip()
            except Exception: return ""
        c = dict(self.cfg)
        c["h1_api_user"] = g("h1u"); c["h1_api_token"] = g("h1t")
        c["intigriti_api_token"] = g("itt"); c["yeswehack_api_token"] = g("ywt")
        c["bugcrowd_api_token"] = g("bct"); c["firecrawl_api_key"] = g("fc")
        c["telegram_token"] = g("ntg")
        c["llm_provider"] = self._sel("lprov", c.get("llm_provider", "anthropic"))
        c["llm_model"] = g("lmodel") or c.get("llm_model", "")
        c["llm_base_url"] = g("lbase") or c.get("llm_base_url", "")
        c["llm_api_key"] = g("lkey") or c.get("llm_api_key", "")
        return c
    def action_test_api(self):
        try: self.query_one("#apires", Static).update("[cyan]🔌 menguji API… (baca nilai yang sekarang diisi)[/]")
        except Exception: pass
        self._run_api_test()
    @work(thread=True)
    def _run_api_test(self):
        cfg = self._cfg_live()
        rows = api_test_all(cfg)
        from rich.markup import escape as _e
        icon = {"OK": "[green]✓ OK[/]", "GAGAL": "[red]✗ GAGAL[/]", "-": "[dim]— lewati[/]"}
        lines = ["[b]HASIL TEST API[/]"]
        for name, st, detail in rows:
            lines.append(f"  {icon.get(st,st)}  [b]{_e(name)}[/]  [dim]{_e(detail)}[/]")
        ok = sum(1 for _, st, _ in rows if st == "OK")
        lines.append(f"[dim]{ok} aktif & jalan[/]")
        self.app.call_from_thread(self.query_one("#apires", Static).update, chr(10).join(lines))
    def _sw(self, i):
        try: return bool(self.query_one("#" + i, Switch).value)
        except Exception: return False
    def _sel(self, i, default=""):
        try:
            v = self.query_one("#" + i, Select).value
            return default if v is Select.BLANK else v
        except Exception: return default
    def action_save(self):
        def g(i):
            try: return self.query_one("#" + i, Input).value.strip()
            except Exception: return ""
        try:
            raw = [x.strip().lower() for x in g("plat").split(",") if x.strip()]
            plats = [x for x in raw if x in PLAT_ALL]
            ignored = [x for x in raw if x not in PLAT_ALL]
            self.cfg["platforms"] = plats or DEFAULT_CFG["platforms"]
            mb = g("minb")
            self.cfg["min_bounty"] = int(re.sub(r"[^\d]", "", mb) or 0)   # tahan input non-angka
            self.cfg["require_wildcard"] = self._sw("wc")
            self.cfg["asset_type"] = g("atype")
            digit = lambda i: int(re.sub(r"[^\d]", "", g(i)) or 0)
            self.cfg["min_quiet"] = digit("mq"); self.cfg["min_assets"] = digit("mina"); self.cfg["max_assets"] = digit("maxa")
            self.cfg["min_wildcards"] = digit("minw"); self.cfg["min_efficiency"] = digit("meff")
            self.cfg["max_ttfr"] = digit("mttfr"); self.cfg["max_ttb"] = digit("mttb")
            self.cfg["sort"] = self._sel("sort", "platform")
            self.cfg["managed_filter"] = self._sel("mgd", "any")
            self.cfg["min_sev"] = self._sel("msev", "")
            # enrich_provider & serper_api_key TAK lagi di UI (fitur enrich yatim) -> jaga nilai lama
            self.cfg["firecrawl_api_key"] = g("fc")
            self.cfg["h1_api_user"] = g("h1u"); self.cfg["h1_api_token"] = g("h1t")
            self.cfg["bugcrowd_api_token"] = g("bct"); self.cfg["intigriti_api_token"] = g("itt"); self.cfg["yeswehack_api_token"] = g("ywt")
            self.cfg["telegram_token"] = g("ntg"); self.cfg["telegram_chat"] = g("ntc"); self.cfg["discord_webhook"] = g("ndc")
            self.cfg["telegram_bot_enabled"] = self._sw("tgen")
            self.cfg["telegram_allow_active"] = self._sw("tgact")
            self.cfg["telegram_allowlist"] = g("tgallow")
            self.cfg["llm_provider"] = self._sel("lprov", "anthropic"); self.cfg["llm_model"] = g("lmodel")
            self.cfg["llm_base_url"] = g("lbase"); self.cfg["llm_api_key"] = g("lkey")
            self.cfg["llm_context"] = digit("lctx")
            save_cfg(self.cfg)
            self.app.pop_screen()
            if ignored:
                self.app.notify(f"! platform diabaikan (hanya {', '.join(PLAT_ALL)}): {', '.join(ignored)}", severity="warning")
            self.app.notify(f"✅ tersimpan -> {CFG} (tekan r untuk refresh)")
        except Exception as e:
            self.app.notify(f"❌ gagal simpan: {e}", severity="error")

class RunScreen(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "tutup")]
    def __init__(self, cmd, title): super().__init__(); self.cmd = cmd; self.title_ = title
    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(f"[b]{self.title_}[/b]  (esc=tutup)", classes="title")
            yield RichLog(highlight=True, markup=True, id="log", wrap=True)
    def on_mount(self): self.run_cmd()
    @work(thread=True)
    def run_cmd(self):
        log = self.query_one("#log", RichLog)
        self.app.call_from_thread(log.write, f"[dim]$ {' '.join(self.cmd)}[/]")
        try:
            proc = subprocess.Popen(self.cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                self.app.call_from_thread(log.write, line.rstrip())
            proc.wait()
            self.app.call_from_thread(log.write, f"[green]selesai (exit {proc.returncode})[/]")
        except Exception as e:
            self.app.call_from_thread(log.write, f"[red]{e}[/]")

class ToolScreen(ModalScreen):
    """Jalankan recon/monitor/dedup -- target dari pilihan ATAU ketik manual."""
    BINDINGS = [("escape", "app.pop_screen", "batal")]
    def __init__(self, kind, default=""): super().__init__(); self.kind = kind; self.default = default
    def compose(self) -> ComposeResult:
        with Vertical(id="stat"):
            yield Label(f"[b cyan]{self.kind.upper()}[/]  -- target dari pilihan atau ketik manual, lalu [b]Enter[/]", classes="title")
            hint = {"recon": "domain, mis. wolt.com", "monitor": "domain, mis. wolt.com", "dedup": "handle/URL, mis. whatnot"}[self.kind]
            yield Input(value=self.default, id="tgt", placeholder=hint)
            if self.kind == "recon":
                yield Label("Profil: [b]passive[/] (tak kirim) - [b]standard[/] (extract web: httpx+katana+JS+endpoint) - [b]deep[/] (scan)")
                yield Input(value="standard", id="prof")
                yield Static("[yellow]standard/deep mengirim request ke target -- pastikan in-scope.[/]")
            yield Static("[dim]Enter = jalankan - esc = batal[/]")
    def on_mount(self): self.query_one("#tgt", Input).focus()
    def on_input_submitted(self, _):
        tgt = self.query_one("#tgt", Input).value.strip()
        if not tgt:
            self.app.notify("target kosong"); return
        if self.kind == "recon":
            prof = self.query_one("#prof", Input).value.strip() or "standard"
            cmd = [sys.executable, _tool("recon.py"), tgt, "--profile", prof]; title = f"Recon {tgt} ({prof})"
        elif self.kind == "monitor":
            cmd = [sys.executable, _tool("asset-monitor.py"), tgt]; title = f"Monitor {tgt}"
        else:
            out = os.path.expanduser("~/bb-dedup-" + re.sub(r"\W", "_", tgt)[:40] + ".md")
            cmd = [sys.executable, _tool("dedup.py"), tgt, "--out", out]; title = f"Dedup {tgt}"
        self.app.pop_screen(); self.app.push_screen(RunScreen(cmd, title))

class ExternalToolsScreen(ModalScreen):
    """Integrasi tool bug hunting lain -- LIST + TAMBAH + HAPUS + JALANKAN, semua dari TUI."""
    BINDINGS = [("escape", "app.pop_screen", "batal")]
    def __init__(self, cfg, default=""): super().__init__(); self.cfg = cfg; self.default = default
    def compose(self) -> ComposeResult:
        ext = self.cfg.get("external_tools", {})
        with VerticalScroll(id="stat"):
            yield Label("[b cyan]EXTERNAL TOOLS[/] -- kelola & jalankan tool bug hunting lain", classes="title")
            yield Label("Target (dari pilihan / ketik manual):")
            yield Input(value=self.default, id="xtgt")
            if ext:
                yield Static("\n[b]Terdaftar:[/]")
                for i, (name, cmd) in enumerate(ext.items(), 1):
                    yield Static(f"  [yellow]{i}[/] [b]{name}[/]  [dim]{cmd}[/]")
            else:
                yield Static("\n[yellow]Belum ada tool. Tambahkan di bawah.[/]")
            yield Label("\n[b green]JALANKAN[/] -- nomor tool -> Enter:")
            yield Input(placeholder="mis. 1", id="xnum")
            yield Label("[b green]TAMBAH[/] -- format  [b]nama = perintah[/]  (pakai {target}/{url}/{handle}) -> Enter:")
            yield Input(placeholder="mis. sqlmap = sqlmap -u {url} --batch", id="xadd")
            yield Label("[b red]HAPUS[/] -- nomor tool -> Enter:")
            yield Input(placeholder="mis. 2", id="xdel")
            yield Static("\n[dim]Placeholder: {target}=domain - {url} - {handle}=nama program. Tersimpan ke ~/.config/bbtui/config.json. esc=tutup[/]")
    def on_mount(self):
        try: self.query_one("#xnum", Input).focus()
        except Exception: pass
    def _refresh(self):
        self.app.pop_screen(); self.app.push_screen(ExternalToolsScreen(self.cfg, self.default))
    def on_input_submitted(self, ev):
        iid = ev.input.id
        ext = self.cfg.setdefault("external_tools", {})
        if iid == "xadd":
            raw = ev.value.strip()
            if "=" not in raw: self.app.notify("format: nama = perintah"); return
            name, tmpl = raw.split("=", 1); name, tmpl = name.strip(), tmpl.strip()
            if not name or not tmpl: self.app.notify("nama/perintah kosong"); return
            ext[name] = tmpl; save_cfg(self.cfg); self.app.notify(f"✅ tool '{name}' ditambah"); self._refresh(); return
        if iid == "xdel":
            items = list(ext.items())
            try: idx = int(ev.value.strip()) - 1
            except Exception: self.app.notify("nomor tidak valid"); return
            if not (0 <= idx < len(items)): self.app.notify("nomor di luar daftar"); return
            gone = items[idx][0]; del ext[gone]; save_cfg(self.cfg); self.app.notify(f"x '{gone}' dihapus"); self._refresh(); return
        # default: jalankan (xnum)
        items = list(ext.items())
        if not items: self.app.notify("belum ada tool"); return
        try: idx = int(self.query_one("#xnum", Input).value.strip()) - 1
        except Exception: self.app.notify("isi nomor tool untuk menjalankan"); return
        if not (0 <= idx < len(items)): self.app.notify("nomor di luar daftar"); return
        tgt = self.query_one("#xtgt", Input).value.strip()
        if not tgt: self.app.notify("target kosong"); return
        name, tmpl = items[idx]
        cmd = tmpl.replace("{target}", tgt).replace("{url}", tgt if tgt.startswith("http") else "https://" + tgt).replace("{handle}", tgt)
        self.app.pop_screen(); self.app.push_screen(RunScreen(shlex.split(cmd), f"{name} - {tgt}"))

_LLM_MOD = None
def _llm_mod():
    """Muat modul llm_agent.py sebagai library (tanpa jalankan main), sekali lalu di-cache."""
    global _LLM_MOD
    if _LLM_MOD is None:
        import importlib.util
        p = _tool("llm_agent.py")
        spec = importlib.util.spec_from_file_location("llm_agent", p)
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); _LLM_MOD = m
    return _LLM_MOD

def _llm_creds(cfg):
    prov = (cfg.get("llm_provider") or "anthropic").lower()
    model = cfg.get("llm_model") or ("claude-sonnet-5" if prov == "anthropic" else "gpt-4o-mini")
    base = cfg.get("llm_base_url") or "https://api.openai.com/v1"
    key = cfg.get("llm_api_key") or os.environ.get("ANTHROPIC_API_KEY" if prov == "anthropic" else "OPENAI_API_KEY", "")
    return prov, model, base, key

class ModelPickerScreen(ModalScreen):
    """Ambil daftar model dari API provider (pakai kunci) lalu pilih -- bebas ganti model kapan saja."""
    BINDINGS = [("escape", "app.pop_screen", "tutup")]
    def __init__(self, cfg, on_pick): super().__init__(); self.cfg = cfg; self.on_pick = on_pick; self.models = []
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="stat"):
            yield Label("[b cyan]PILIH MODEL[/] -- diambil live dari provider via API key", classes="title")
            yield Static("mengambil daftar model...", id="mlist")
            yield Label("Ketik nomor / nama model -> Enter:")
            yield Input(placeholder="mis. 3  atau  claude-sonnet-5", id="mpick")
            yield Static("[dim]esc = tutup[/]")
    def on_mount(self): self.fetch()
    @work(thread=True)
    def fetch(self):
        prov, _model, base, key = _llm_creds(self.cfg)
        if not key:
            self.app.call_from_thread(self.query_one("#mlist", Static).update, "[red]belum ada API key (Settings).[/]"); return
        models = _llm_mod().fetch_models(prov, key, base)
        self.models = models
        txt = "\n".join(f"  [yellow]{i}[/] {m}" for i, m in enumerate(models, 1))
        self.app.call_from_thread(self.query_one("#mlist", Static).update, txt)
        self.app.call_from_thread(lambda: self.query_one("#mpick", Input).focus())
    def on_input_submitted(self, ev):
        v = ev.value.strip()
        if not v: return
        chosen = v
        if v.isdigit() and self.models and 1 <= int(v) <= len(self.models): chosen = self.models[int(v) - 1]
        self.cfg["llm_model"] = chosen; save_cfg(self.cfg)
        self.app.pop_screen(); self.on_pick(chosen); self.app.notify(f"model: {chosen}")

AGENT_NAME = "FAJAR-AGENT"
AGENT_VERSION = "1.1"
AGENT_TAGLINE = "Bug-Bounty Hunting Harness — bertahap, memori jangka panjang, kontrol manusia"
# logo "FAJAR" gradasi sunrise (kuning -> oranye), diakhiri wordmark AGENT
AGENT_BANNER = (
    "[b #ffd23f]███████╗ █████╗      ██╗ █████╗ ██████╗ [/]\n"
    "[b #ffb627]██╔════╝██╔══██╗     ██║██╔══██╗██╔══██╗[/]\n"
    "[b #ff9e2c]█████╗  ███████║     ██║███████║██████╔╝[/]\n"
    "[b #ff8c33]██╔══╝  ██╔══██║██   ██║██╔══██║██╔══██╗[/]\n"
    "[b #ff7a3d]██║     ██║  ██║╚█████╔╝██║  ██║██║  ██║[/]\n"
    "[b #ff6b45]╚═╝     ╚═╝  ╚═╝ ╚════╝ ╚═╝  ╚═╝╚═╝  ╚═╝[/]\n"
    "[dim]        🌅  A · G · E · N · T[/]"
)
TOOL_GROUPS = [
    ("program", ["list_programs", "new_programs", "program_detail"]),
    ("recon", ["recon", "read_recon", "monitor"]),
    ("anti-dup", ["dedup"]),
    ("ext-tools", ["list_ext_tools", "run_ext_tool"]),
    ("memory", ["memory_search", "memory_save", "memory_list"]),
    ("skills", ["list_skills", "load_skill"]),
    ("workspace", ["workspace", "save_note"]),
    ("notify", ["notify"]),
]

SLASH_HELP = [
    # -- hunting (menutup celah: dulu recon/dedup/monitor hanya ada di dashboard) --
    ("/pick <nama>", "[STRATEGIST] pilih target rekomendasi -> mulai rangkaian hunting penuh"),
    ("/target", "lihat target aktif + scope resmi yang dimuat ke konteks"),
    ("/recon [domain]", "jalankan recon (default: apex target aktif)"),
    ("/monitor [domain]", "pantau subdomain baru"),
    ("/dedup [handle]", "kelas bug yang SUDAH dilaporkan di program"),
    ("/stage", "suruh agent lanjut ke tahap berikutnya"),
    ("/retry", "kirim ulang pesan terakhir (kalau API error/timeout)"),
    ("/note <teks>", "catat temuan cepat ke workspace target (tanpa lewat agent)"),
    ("/report [save]", "susun draf laporan; 'save' menyimpan jawaban agent terakhir"),
    ("/handoff [domain]", "buat HANDOFF PACK: recon -> target Burp + endpoint prioritas"),
    ("/ext", "kelola & jalankan ext-tools (nuclei/sqlmap/burp/dll)"),
    # -- sesi & konteks --
    ("/resume", "pilih riwayat chat dari pop-up lalu lanjutkan"),
    ("/new", "sesi baru (reset percakapan; memori tetap)"),
    ("/save", "simpan sesi sekarang (biasanya tak perlu: sudah autosave)"),
    ("/export", "simpan percakapan ke file .md"),
    ("/clear", "bersihkan LAYAR saja (riwayat sesi tetap)"),
    ("/context", "pemakaian konteks (token/window)"),
    ("/compact", "ringkas konteks sekarang (hemat token)"),
    ("/add <path>", "masukkan file/folder ke konteks (drag path juga bisa)"),
    # -- agent & model --
    ("/yolo", "izinkan aksi aktif (kirim traffic) -- hati-hati"),
    ("/model [nama]", "ganti model (kosong = pilih dari daftar)"),
    ("/provider <anthropic|openai>", "ganti provider"),
    ("/memory [cari]", "lihat/cari memori jangka panjang"),
    ("/skills", "daftar skill/playbook"),
    ("/skill install <nama> <url|path>", "pasang skill baru"),
    ("/tools", "daftar tool yang dimiliki agent"),
    ("/mcp [connect]", "status / connect server MCP"),
    ("/status", "ringkasan kondisi agent"),
    ("/stop", "HENTIKAN proses agent yang sedang jalan (= esc)"),
    ("/help", "daftar perintah & tombol"),
    ("/quit", "keluar sesi chat (esc sengaja TIDAK menutup)"),
    # -- darurat/diagnosa --
    ("/redraw", "gambar ulang layar (bersihkan sisa render terminal)"),
    ("/mouse", "lepas/ambil mouse dari terminal"),
    ("/diag", "simpan laporan diagnosa + screenshot ke ~/"),
]

def classify_assets(scope):
    """Kelompokkan aset in-scope per jenis -> menentukan skill & pendekatan."""
    web, api, android, ios, other = [], [], [], [], []
    for s in scope:
        sl = str(s).lower()
        if "play.google" in sl or sl.startswith("com.") or ".apk" in sl or "/android" in sl: android.append(s)
        elif "apps.apple" in sl or "testflight" in sl or "itunes.apple" in sl or (sl.isdigit() and len(sl) >= 6): ios.append(s)
        elif sl.startswith("api.") or "/api" in sl or ".api." in sl or "graphql" in sl: api.append(s)
        elif "." in sl and " " not in sl: web.append(s)
        else: other.append(s)
    return {"web": web, "api": api, "android": android, "ios": ios, "other": other}

def escape_markup(t):
    """Amankan teks bebas sebelum dipakai di markup (kurung siku ditafsirkan sbg tag)."""
    from rich.markup import escape
    return escape(str(t))

def program_context(pr):
    """SKEMA EKSTRAKSI: ubah 1 program -> brief terstruktur utk LLM (sumber scope resmi + rute skill)."""
    g = classify_assets(pr.get("scope", []))
    present = [k for k in ("web", "api", "android", "ios", "other") if g[k]]
    skill_map = {"web": "web-vuln-classes", "api": "api-pentest", "android": "mobile-pentest", "ios": "mobile-pentest"}
    skills = sorted({skill_map[k] for k in present if k in skill_map}) or ["web-vuln-classes"]
    L = ["[TARGET CONTEXT] -- sumber scope RESMI dari TUI (jangan cari/riset ulang; jangan program_detail).",
         f"nama       : {pr.get('name')}",
         f"platform   : {pr.get('platform')}",
         f"url_rules  : {pr.get('url','')}",
         f"reward     : {reward(pr)}",
         f"max_sev    : {pr.get('maxsev','-')}   managed: {pr.get('managed')}",
         f"sinyal_h1  : {pr.get('signal','-')}",
         f"jenis_aset : {', '.join(present) or '-'}",
         f"skill_rute : {', '.join(skills)}  (muat via load_skill di tahap analisa/rencana)",
         f"wildcard ({len(pr.get('wild',[]))}):"]
    L += ["  - " + str(w) for w in pr.get("wild", [])[:40]] or ["  (tak ada)"]
    for k in present:
        L.append(f"aset {k} ({len(g[k])}):")
        L += ["  - " + str(x) for x in g[k][:50]]
        if len(g[k]) > 50: L.append(f"  ... +{len(g[k])-50} lagi")
    return "\n".join(L)

def _md_line(raw):
    """Konversi 1 baris markdown -> Rich markup rapi (buang '#', **tebal**, `kode`); escape '[..]' agar [FAKTA] tak hilang."""
    from rich.markup import escape
    import re as _re
    raw = raw.rstrip("\n")
    st = raw.lstrip()
    hashes = len(st) - len(st.lstrip("#"))
    def inline(s):
        s = _re.sub(r"\*\*(.+?)\*\*", r"[b]\1[/]", s)
        s = _re.sub(r"(?<!\*)\*(?!\s)([^*]+?)\*(?!\*)", r"[i]\1[/]", s)
        s = _re.sub(r"`([^`]+)`", r"[cyan]\1[/]", s)
        # URL -> link clickable (Ctrl+Click buka browser di terminal yg dukung)
        # nilai link WAJIB dikutip: markup Textual menolak nilai tak berkutip yang
        # memuat ':' dan '/' -> MarkupError, sehingga tiap jawaban ber-URL bikin crash.
        # Char class WAJIB kecualikan '\' dan '[' juga: teks sudah di-escape (mis. '['->'\['),
        # kalau '\[' ikut tertangkap ke URL, markup [link='...\[...'] jadi rusak -> crash.
        s = _re.sub(r"(https?://[^\s\[\]\)>'\"\\]+)", r"[link='\1'][u cyan]\1[/u cyan][/link]", s)
        return s
    if hashes and st[hashes:hashes + 1] == " ":            # heading -> tebal polos (tenang), tanpa '#'
        return "[b]" + inline(escape(st[hashes:].strip())) + "[/]"
    # bullet rapi
    body = escape(raw)
    body = _re.sub(r"^(\s*)[-*]\s+", r"\1* ", body)
    return inline(body)

def _markup_ok(s):
    """True bila string markup bisa diparse Textual. Dipakai utk menjaga log tak crash."""
    try:
        from textual.content import Content
        Content.from_markup(s); return True
    except Exception:
        return False

class SelectableLog(Static):
    """Kotak chat yg BISA DISELEKSI. Static hanya bisa diseleksi jika kontennya SATU markup string
    (bukan Group/Panel/Table). Jadi semua ditumpuk jadi satu string markup. auto-scroll ke bawah."""
    ALLOW_SELECT = True
    CAP = 260                                    # batas riwayat layar (biaya render TIAP flush ~linear thd ini)
    def __init__(self, *a, **k):
        super().__init__(*a, **k); self._lines = []; self._batching = False; self._pending = False
    def write(self, s=""):
        s = s if isinstance(s, str) else str(s)
        # SAFETY + PERF: baris tanpa '[' TAK MUNGKIN punya tag -> pasti valid, lewati parse.
        # Baris ber-'[' divalidasi; kalau rusak -> escape (tampil apa adanya), tak crash.
        if "[" in s and not _markup_ok(s):
            from rich.markup import escape
            s = escape(s)
        self._lines.append(s)
        if len(self._lines) > self.CAP: self._lines = self._lines[-self.CAP:]
        if not self._batching: self._schedule()
    def _schedule(self):
        # PERF: render ulang mem-parse SELURUH markup buffer (mahal saat panjang: ~50ms/800 baris).
        # Tulis beruntun (balasan agent + hasil tool) di-COALESCE jadi SATU render per frame,
        # bukan satu render per baris (dulu O(n^2): 800 baris = ~22 dtk). call_after_refresh
        # menggabungkan semua write dalam satu siklus refresh.
        if self._pending: return
        self._pending = True
        try: self.call_after_refresh(self._coalesced)
        except Exception: self._pending = False; self._flush()
    def _coalesced(self):
        self._pending = False; self._flush()
    def _flush(self):
        joined = "\n".join(self._lines)
        try:
            self.update(joined)                       # jalur normal (markup sudah divalidasi di write)
        except Exception:
            from rich.markup import escape             # jaring pengaman terakhir: JANGAN pernah crash
            try: self.update(escape(joined))
            except Exception: pass
        try: self.parent.scroll_end(animate=False)
        except Exception: pass
    def batch(self):
        # kumpulkan banyak write jadi SATU update+scroll (hindari badai render, mis. saat mount)
        log = self
        class _Ctx:
            def __enter__(s): log._batching = True
            def __exit__(s, *a): log._batching = False; log._flush()
        return _Ctx()
    def clear(self):
        self._lines = []; self._pending = False; self.update("")

class ChatBox(TextArea):
    """Kotak chat MULTI-BARIS, tinggi TETAP (rigid), gulir internal.

    Kenapa bukan Input satu-baris: Input merender SELURUH isi sebagai SATU baris.
    Baris itu gampang pas/melebihi lebar terminal -- selisih SATU sel saja (karakter
    lebar, atau font yang menggambar emoji 1 sel padahal dihitung 2) membuat terminal
    MEMBUNGKUS baris itu, sehingga teks 'menjorok ke bawah' dan seluruh layout
    tergeser (inilah glitch-nya). Di sini teks dibungkus DI DALAM kotak (soft_wrap)
    dan di-clip Textual, jadi tidak pernah ada satu baris raksasa.

    Enter = kirim.  Alt+Enter / Ctrl+J / Shift+Enter = baris baru.
    """
    class Submitted(Message):
        def __init__(self, value):
            super().__init__(); self.value = value

    def __init__(self, *a, **k):
        k.setdefault("soft_wrap", True)          # WAJIB: bungkus di dalam kotak
        k.setdefault("tab_behavior", "focus")    # Tab pindah fokus, bukan indent
        super().__init__(*a, **k)

    # -- kompatibel dgn kode yang memakai .value seperti Input --
    @property
    def value(self):
        return self.text
    @value.setter
    def value(self, v):
        self.text = v or ""
        try: self.move_cursor(self.document.end)
        except Exception: pass

    def _on_key(self, event):
        # prevent_default() memutus loop dispatch MRO supaya TextArea._on_key
        # bawaan tidak ikut jalan utk tombol yang kita tangani sendiri.
        if event.key == "enter":
            event.stop(); event.prevent_default()
            self.post_message(self.Submitted(self.text))
        elif event.key in ("shift+enter", "alt+enter", "ctrl+j"):
            event.stop(); event.prevent_default()
            self.insert(chr(10))
        # tombol lain dibiarkan -> TextArea._on_key jalan sendiri lewat MRO

    def _on_paste(self, event):
        event.stop(); event.prevent_default()
        txt = event.text or ""
        if txt:
            # normalkan akhir baris; NEWLINE DIPERTAHANKAN (kotak ini multi-baris).
            txt = txt.replace(chr(13) + chr(10), chr(10)).replace(chr(13), chr(10))
            # buang karakter kontrol (bisa mendesync kursor terminal), sisakan \n dan tab
            txt = "".join(c for c in txt if c in (chr(10), chr(9)) or ord(c) >= 32)
            self.insert(txt)
        try: self.screen.clear_selection()
        except Exception: pass
        try: self.app.call_after_refresh(self.app.action_redraw)
        except Exception: pass

class LlmChatScreen(ModalScreen):
    """Chat LLM ala Hermes/OpenCode/Claude Code -- status bar, slash-commands, alur BERTAHAP rapi."""
    BINDINGS = [("escape", "soft_escape", "stop"), ("ctrl+q", "quit_chat", "keluar"), ("ctrl+a", "toggle_active", "yolo"),
                ("ctrl+o", "pick_model", "model"), ("ctrl+r", "resume", "resume"), ("ctrl+l", "clear", "clear"),
                ("ctrl+pageup", "log_up", "gulir naik"), ("ctrl+pagedown", "log_down", "gulir turun"),
                ("ctrl+home", "log_home", "atas"), ("ctrl+end", "log_end", "bawah"),
                ("f3", "toggle_active", "yolo")]
    def __init__(self, cfg, target=None, targets=None, mode="target", portfolio="", pool=None):
        super().__init__(); self.cfg = cfg
        self.targets = targets if targets else ([target] if target else [])
        self.target = self.targets[0] if self.targets else None
        # MODE STRATEGIST ("di luar"): belum pilih target -> agent menganalisa SELURUH
        # portfolio (dari dashboard) lalu merekomendasikan target; handoff via /pick.
        self.strategist = (mode == "strategist")
        self.portfolio = portfolio or ""
        self.pool = pool or []            # daftar pr utk /pick (cari by nama)
        self.messages = None
        self.allow_gated = False; self.busy = False; self.activity = "idle"
        self.tok_in = 0; self.tok_out = 0; self.turns = 0
        self.ctx = 0; self.window = 0; self.compacts = 0; self._worker = None; self.t0 = None; self._suggest = ""
        self.sess_start = datetime.datetime.now(); self._tk = 0; self._last_agent = ""
        self.sid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + base64.b16encode(os.urandom(3)).decode().lower()
        # RIWAYAT SESI ala ChatGPT: tiap sesi id UNIK (sess_id) -> /new bikin sesi baru,
        # sesi lama TETAP tersimpan. target_slug utk mengelompokkan & auto-lanjut sesi terakhir.
        base = "strategist" if self.strategist else ((target.get("key") or target.get("name")) if target else "general")
        self.target_slug = re.sub(r"\W", "_", str(base))[:50]
        self.sess_id = self._new_sess_id()   # TETAP selama sesi -> chatting tak bikin sesi baru;
        #                                      hanya berubah lewat /new, /resume, /pick (handoff)
    def _new_sess_id(self):
        return "tui-%s-%s%s" % (self.target_slug, datetime.datetime.now().strftime("%Y%m%d_%H%M%S_"),
                                base64.b16encode(os.urandom(2)).decode().lower())
    THINK_KAO = ["(°□°)", "(￣▽￣)", "( ˘•ω•˘ )", "(⌐■_■)", "(¬_¬ )", "(๑•̀ㅂ•́)و", "(°▽°)", "( •̀ ω •́ )"]
    THINK_WORD = ["musing…", "berpikir…", "menganalisa…", "merangkai hipotesis…", "menimbang…",
                  "meracik payload…", "menyusun rencana…", "menelusuri scope…", "brainstorming…"]
    def compose(self) -> ComposeResult:
        _p, _m, _b, key = _llm_creds(self.cfg)
        with Vertical(id="chatwrap"):
            yield Static(self._headerline(), id="chathdr")
            with VerticalScroll(id="chatscroll"):
                yield SelectableLog(id="chatlog", markup=True)
            with Horizontal(id="thinkwrap"):    # indikator loading DI ATAS baris info
                yield Static("⏳ memproses", id="thinklbl")
                yield Static("", id="thinkbar")   # bar ASCII sendiri (ProgressBar Textual pakai U+2501/U+257A = ambiguous)
            yield Static(self._statusline(), id="chatstatus")
            yield OptionList(id="slashbox")
            with Horizontal(id="chatbar"):
                # variant diatur di _tick: merah HANYA saat sibuk. Warna harus menandakan
                # keadaan, bukan jadi hiasan -- tombol idle jangan paling mencolok di layar.
                yield Button("⏹", id="btnstop", variant="default")
                yield ChatBox(placeholder=("ketik goal, atau / untuk menu" if key else "set API key dulu (Settings s)"), id="chatinput")
                yield Button("➤ Kirim", id="btnsend", variant="success")
    def _headerline(self):
        prov, model, _b, _k = _llm_creds(self.cfg)
        yolo = "[black on yellow] ⚡YOLO [/]" if self.allow_gated else "[dim]aktif:off[/]"
        return f" ◤ {AGENT_NAME} v{AGENT_VERSION} ◢  [b]{model}[/] · {prov}  ·  [dim]{self.sid}[/]  {yolo}"
    @staticmethod
    def _h(n):
        return f"{n/1000:.1f}K" if n >= 1000 else str(int(n))
    def _ctxbar(self):
        if not self.window: return "ctx —"
        pct = min(100, int(self.ctx * 100 / self.window))
        fill = pct * 10 // 100
        col = "green" if pct < 60 else ("yellow" if pct < 85 else "red")
        bar = f"[{col}]" + "█" * fill + "[/]" + "░" * (10 - fill)
        return f"ctx {bar} {self._h(self.ctx)}/{self._h(self.window)} ({pct}%)"
    def _statusline(self):
        dot = {"idle": "[green]●[/]", "checkpoint": "[yellow]⏸[/]", "auto-compact": "[magenta]⟳[/]"}.get(self.activity, "[cyan]◉[/]")
        act = "idle" if not self.busy and self.activity in ("idle", "checkpoint") else self.activity
        tok = f"⇅ {self._h(self.tok_in)}/{self._h(self.tok_out)}"
        now = datetime.datetime.now()
        if self.busy and self.t0:
            el = (now - self.t0).total_seconds()
            clock = f"  │  ⏱ {el:.0f}s · {self.tok_out/max(el,1):.0f} t/s"
        else:
            up = int((now - self.sess_start).total_seconds())
            clock = f"  │  ⏱ sesi {up//60}m{up%60:02d}s"
        cmp = f"  │  [magenta]compact×{self.compacts}[/]" if self.compacts else ""
        return (f"{dot} [b]{act}[/]  │  {self._ctxbar()}  │  {tok} tok{clock}  │  turn {self.turns}{cmp}  │  "
                f"aktif {'[green]ON[/]' if self.allow_gated else '[red]OFF[/]'}  │  [dim]/ menu · esc stop · ^Q keluar[/]")
    @work(thread=True)
    def _load_window(self):
        try:  # override manual menang (llm_context di Settings; 0 = auto)
            ov = int(self.cfg.get("llm_context") or 0)
        except Exception:
            ov = 0
        if ov > 0:
            self.window = ov; self.app.call_from_thread(self._refresh_bars); return
        prov, model, base, key = _llm_creds(self.cfg)
        if not key: return
        try:
            w = _llm_mod().fetch_context_window(prov, model, key, base)
            if w and w > 0:
                self.window = w
                self.app.call_from_thread(self._refresh_bars)
        except (Exception, SystemExit):
            pass
    def _refresh_bars(self):
        self.query_one("#chathdr", Static).update(self._headerline())
        self.query_one("#chatstatus", Static).update(self._statusline())
    def _tick(self):
        # PERF: dulu tiap 0.7s SELALU render ulang header+status walau idle. Sekarang:
        # saat SIBUK animasi+status gerak tiap tick; saat IDLE cukup jarang (uptime) &
        # animasi dibersihkan SEKALI saat transisi -> tak ada repaint sia-sia tiap tick.
        try:
            wrap = self.query_one("#thinkwrap")
            lbl = self.query_one("#thinklbl", Static); bar = self.query_one("#thinkbar", Static)
        except Exception: return
        try:   # tombol stop: merah saat sibuk, redup saat idle
            btn = self.query_one("#btnstop", Button)
            want = "error" if self.busy else "default"
            if btn.variant != want: btn.variant = want
        except Exception: pass
        self._tk += 1
        if self.busy:
            kao = self.THINK_KAO[self._tk % len(self.THINK_KAO)]
            word = self.THINK_WORD[(self._tk // 2) % len(self.THINK_WORD)]
            lbl.update(f"[yellow]{kao}[/] [dim italic]{word}[/]")   # kaomoji + kata + bar di sebelah
            # bar berjalan, ASCII murni (lebar pasti 1 sel/karakter di semua terminal)
            n, blk, pos = 14, 3, self._tk % 14
            cells = "".join("█" if any((pos + i) % n == j for i in range(blk)) else "░" for j in range(n))
            bar.update(f"[dim]\\[{cells}][/dim]")   # \[ = kurung buka LITERAL (bukan tag); ] lone = literal
            if not getattr(self, "_anim_on", False): wrap.add_class("on"); self._anim_on = True
            self._refresh_bars()                       # jam/token bergerak saat sibuk
        else:
            if getattr(self, "_anim_on", False):       # transisi sibuk->idle: bersihkan SEKALI
                bar.update(""); wrap.remove_class("on"); self._anim_on = False
            if self._tk % 6 == 0: self._refresh_bars()  # idle: perbarui uptime tiap ~4s, bukan 0.7s
    def on_mount(self):
        log = self.query_one("#chatlog", SelectableLog)
        prov, model, _b, key = _llm_creds(self.cfg)
        la = _llm_mod()
        self.window = la.model_window(model)          # tebakan awal biar ctx bar langsung tampil
        self.set_interval(0.7, self._tick)            # jam sesi + animasi "loading" saat nunggu LLM
        self._load_window()                           # ambil window ASLI model dari provider (async)
        with log.batch():   # SATU update+scroll utk seluruh intro
            # Sengaja RINGKAS: daftar tools/skills itu materi rujukan, bukan info yang
            # dibutuhkan tiap membuka sesi -> pindah ke /tools, /skills, /help.
            names = [t["name"] for t in la.TOOLS]
            nx = len(self.cfg.get("external_tools", {}))
            try:
                mi = la.mem_list()
                nmem = mi.count(chr(10)) if (mi and "kosong" not in mi) else 0
            except Exception:
                nmem = 0
            log.write(AGENT_BANNER)
            log.write(f"[b]{AGENT_NAME}[/] v{AGENT_VERSION} [dim]·[/] {AGENT_TAGLINE}")
            # model/provider TIDAK diulang di sini: sudah permanen di header bar.
            log.write(f"[dim]{len(names)} tools · {len(la.SKILLS)} skills · {nx} ext-tools"
                      + (f" · {nmem} memori" if nmem else "") + "[/]")
            log.write("[dim]ketik[/] [yellow]/help[/] [dim]perintah & tombol[/] [dim]·[/] "
                      "[yellow]/tools[/] [yellow]/skills[/] [dim]daftar lengkap[/]")
            if not key:
                log.write("\n[red]⚠ belum ada API key[/] [dim]— Settings (s) → blok LLM AGENT[/]")
            inp = self.query_one("#chatinput", ChatBox)
            if self.target and key:
                nm = self.target.get("name")
                if len(self.targets) > 1:
                    names = ", ".join((t.get("name") or "?") for t in self.targets[:6])
                    log.write(f"\n[b green]🎯 {len(self.targets)} TARGET terpilih:[/] [dim]{names}"
                              + ("..." if len(self.targets) > 6 else "") + "[/]")
                else:
                    g = classify_assets(self.target.get("scope", []))
                    present = [k for k in ("web", "api", "android", "ios", "other") if g[k]]
                    log.write(f"\n[b green]🎯 {nm}[/] [dim]· {self.target.get('platform')} · "
                              f"{', '.join(present) or '-'} · wildcard {len(self.target.get('wild', []))} · "
                              f"sev {self.target.get('maxsev', '-')}[/]")
                # BUKA = SESI BARU (fresh). Riwayat lama TIDAK auto-dimuat; cukup dihint
                # -> buka lewat /resume. (sess_id sudah unik dari __init__.)
                self.messages = la.new_messages(prov == "anthropic")
                for _tg in self.targets:                       # suntik konteks SEMUA target terpilih
                    self.messages.append({"role": "user", "content": program_context(_tg)})
                hist = la.session_latest_for(self.target_slug) if len(self.targets) == 1 else None
                if hist:
                    log.write("[green]💾 ada sesi tersimpan utk target ini[/] [dim]— ketik[/] [yellow]/resume[/] [dim]utk buka riwayat[/]")
                log.write("\n[b yellow]⏸ sesi baru — menunggu perintahmu[/] [dim]— Enter kirim · / menu[/]")
                log.write(f"[dim]  saran: \"mulai hunting {nm}: SCOPE-GATE lalu HUNTING BRIEF\"[/]")
                if len(self.targets) > 1:
                    self._suggest = (f"bandingkan & prioritaskan {len(self.targets)} target ini dari scope-nya, "
                                     "lalu mulai dari yg paling menjanjikan: SCOPE-GATE + HUNTING BRIEF.")
                else:
                    self._suggest = (f"mulai hunting {nm}: SCOPE-GATE pakai TARGET CONTEXT lalu susun "
                                     "HUNTING BRIEF sesuai jenis aset.")
            elif self.strategist and key:
                # "DI LUAR": suntik portfolio -> agent jadi penasihat pemilihan target.
                self.messages = la.new_messages(prov == "anthropic")
                if self.portfolio:
                    self.messages.append({"role": "user", "content": self.portfolio})
                log.write(f"\n[b green]🧭 STRATEGIST[/] [dim]· belum pilih target · {len(self.pool)} program di meja[/]")
                log.write("[dim]  Aku analisa portfolio-mu (skor anti-ramai + status worklist) lalu[/]")
                log.write("[dim]  merekomendasikan target terbaik. Setuju? ketik[/] [yellow]/pick <nama>[/] [dim]→ mulai hunting penuh.[/]")
                log.write("\n[b yellow]⏸ siap menganalisa[/] [dim]— Enter kirim · / menu[/]")
                log.write("[dim]  saran: \"analisa portfolio & rekomendasikan 2-3 target terbaik\"[/]")
                self._suggest = ("analisa PORTFOLIO CONTEXT: rekomendasikan 2-3 target paling menjanjikan "
                                 "(anti-duplikat, permukaan scope luas, sepi) beserta ALASAN singkat tiap target; "
                                 "tutup dengan CHECKPOINT minta operator ketik /pick <nama>.")
            else:
                pass   # status bar sudah menampilkan "/ menu - esc stop - ^Q keluar" terus-menerus
        if self.cfg.get("mcp_servers"):
            log.write("[dim]🔌 menghubungkan server MCP...[/]"); self._mcp_connect()
        inp.focus()
    # ---- actions ----
    def on_button_pressed(self, ev):
        if ev.button.id == "btnsend":
            inp = self.query_one("#chatinput", ChatBox); v = inp.value.strip(); inp.value = ""
            if not v and self._suggest: v = self._suggest
            if v: self._submit(v)
        elif ev.button.id == "btnstop":
            self.action_stop()
    def action_stop(self):
        log = self.query_one("#chatlog", SelectableLog)
        if not self.busy:
            log.write("[dim]tak ada proses berjalan.[/]"); return
        try:
            if self._worker is not None: self._worker.cancel()
        except Exception: pass
        self.busy = False; self.activity = "idle"; self._refresh_bars()
        log.write("[yellow]# dihentikan. (request yg sudah terlanjur terkirim bisa selesai di belakang, hasilnya diabaikan)[/]")
    def _scroller(self):
        return self.query_one("#chatscroll")
    def action_log_up(self):
        try: self._scroller().scroll_page_up(animate=False)
        except Exception: pass
    def action_log_down(self):
        try: self._scroller().scroll_page_down(animate=False)
        except Exception: pass
    def action_log_home(self):
        try: self._scroller().scroll_home(animate=False)
        except Exception: pass
    def action_log_end(self):
        try: self._scroller().scroll_end(animate=False)
        except Exception: pass
    def _diag(self):
        log = self.query_one("#chatlog", SelectableLog)
        rep = _diag_report(self.app)
        txt = os.path.expanduser("~/fajar-diag.txt")
        try:
            with open(txt, "w", encoding="utf-8") as f:
                f.write(rep + chr(10))
        except Exception as e:
            log.write("[red]gagal tulis %s: %s[/]" % (txt, e))
            return
        svg = os.path.expanduser("~/fajar-diag.svg")
        try:
            self.app.save_screenshot(svg)
        except Exception:
            svg = "(screenshot gagal)"
        log.write("[b cyan]DIAG tersimpan[/]" + chr(10) + "  " + txt + chr(10) + "  " + svg)
        log.write("[dim]" + rep.replace("[", "\\[") + "[/]")
    def _export(self):
        log = self.query_one("#chatlog", SelectableLog)
        out = os.path.expanduser("~/fajar-chat-%s.md" % self.sid)
        try:
            with open(out, "w", encoding="utf-8") as f:
                f.write("# Percakapan %s - %s" % (AGENT_NAME, self.sid) + chr(10) * 2)
                for m in (self.messages or []):
                    c = m.get("content")
                    if not isinstance(c, str):
                        c = json.dumps(c, ensure_ascii=False)[:4000]
                    f.write("## %s" % m.get("role", "?") + chr(10) * 2 + c + chr(10) * 2)
                f.write(chr(10) + "---" + chr(10) + "# Layar chat (teks mentah)" + chr(10) * 2)
                for ln in log._lines:
                    f.write(ln + chr(10))
        except Exception as e:
            log.write("[red]gagal export: %s[/]" % e)
            return
        log.write("[b green]percakapan diekspor:[/] " + out + chr(10) +
                  "[dim]buka file itu lalu salin biasa - tak perlu seleksi di TUI.[/]")
    def action_soft_escape(self):
        # esc TIDAK langsung keluar. Sibuk -> stop. Tidak sibuk -> GAMBAR ULANG layar
        # (esc = refleks user saat layar berantakan) + ingatkan cara keluar, tanpa spam.
        if self.busy: self.action_stop(); return
        self.app.action_redraw()
        log = self.query_one("#chatlog", SelectableLog)
        msg = ("[dim]esc: layar digambar ulang. Keluar sesi chat: [b]Ctrl+Q[/] atau ketik [b]/quit[/] "
               "(esc sengaja tidak menutup agar tak salah pencet).[/]")
        if not log._lines or log._lines[-1] != msg: log.write(msg)   # jangan tumpuk baris sama
    def action_quit_chat(self):
        if self.busy: self.action_stop()
        self._autosave()
        self.app.pop_screen()
    def _autosave(self):
        """Simpan sesi tanpa berisik. Kembalikan path bila sukses, None bila tidak.
        Hanya simpan bila ADA percakapan nyata (turns>0) -> buka lalu tutup tanpa
        ngobrol TIDAK bikin riwayat kosong (cuma konteks target) memenuhi /resume."""
        try:
            if self.messages and self.turns > 0:
                return _llm_mod().session_save(self.sess_id, self.messages, target=self.target_slug)
        except Exception: pass
        return None
    def on_unmount(self):
        # jaminan simpan saat layar chat ditutup / app keluar tiba-tiba (chat terakhir tersimpan)
        self._autosave()
    # ---- actions ----
    def action_toggle_active(self):
        self.allow_gated = not self.allow_gated; self._refresh_bars()
        self.query_one("#chatlog", SelectableLog).write(f"[b]{'🟢 YOLO ON -- aksi kirim-traffic diizinkan' if self.allow_gated else '🔴 YOLO OFF -- aksi aktif ditolak'}[/]")
    def action_pick_model(self):
        def picked(mdl): self._refresh_bars(); self._load_window()   # window ikut model baru
        self.app.push_screen(ModelPickerScreen(self.cfg, picked))
    def action_clear(self):
        self.query_one("#chatlog", SelectableLog).clear(); self.query_one("#chatlog", SelectableLog).write("[dim]layar dibersihkan (percakapan & memori tetap).[/]")
    def action_resume(self):
        self.app.push_screen(ResumePickerScreen(self._resume_pick, current=self.sess_id))
    def _resume_pick(self, item):
        la = _llm_mod(); log = self.query_one("#chatlog", SelectableLog)
        msgs = la.session_load_path(item["path"])
        if not msgs:
            log.write("[yellow]riwayat itu kosong / gagal dibaca.[/]"); return
        self.messages = msgs
        # ikut pindah sess_id + target: kelanjutan chat tersimpan ke riwayat YANG DIPILIH,
        # bukan tercampur ke sesi target yang sedang dibuka.
        self.sess_id = item["sid"]
        if item.get("target"): self.target_slug = item["target"]
        self.turns = 0
        log.write("\n[dim]" + "\u2500" * 60 + "[/]")
        log.write(f"[b green]💾 melanjutkan riwayat[/] [b]{item['sid']}[/] "
                  f"[dim]({len(msgs)} pesan · disimpan {(item.get('saved') or '')[:16].replace('T', ' ')})[/]")
        self._render_history(msgs)
        log.write("[dim]" + "\u2500" * 60 + "[/]")
        log.write("[dim]tinggal lanjut ketik. Simpanan berikutnya masuk ke riwayat ini.[/]")
        self._refresh_bars()
    def _render_history(self, msgs):
        from rich.markup import escape
        log = self.query_one("#chatlog", SelectableLog)
        for msg in msgs:
            role = msg.get("role"); c = msg.get("content")
            if role == "user" and isinstance(c, str):
                if c.startswith("[TARGET CONTEXT]") or c.startswith("[ARTEFAK"):
                    log.write("[dim]  - (konteks target dimuat)[/]"); continue
                self._write_user(c[:1500])
            elif role == "assistant":
                text = ""
                if isinstance(c, list): text = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                elif isinstance(c, dict): text = c.get("content") or ""
                elif isinstance(c, str): text = c
                if text.strip(): self._write_agent(text)
            # pesan tool/tool_result (internal) dilewati agar transkrip bersih
    # ---- handoff strategist -> hunting satu target ----
    def _find_pool(self, arg):
        """Cari 1 program di pool by nama (cocok persis > awalan > substring)."""
        q = (arg or "").strip().lower()
        if not q: return None
        exact = [p for p in self.pool if (p.get("name") or "").lower() == q]
        if exact: return exact[0]
        starts = [p for p in self.pool if (p.get("name") or "").lower().startswith(q)]
        if starts: return starts[0]
        sub = [p for p in self.pool if q in (p.get("name") or "").lower()]
        return sub[0] if len(sub) == 1 else (sub[0] if sub else None)
    def _handoff(self, pr):
        """Serah-terima: strategist -> hunting PENUH satu target (scope resmi dari TUI)."""
        log = self.query_one("#chatlog", SelectableLog)
        prov, model, base, key = _llm_creds(self.cfg)
        if not key: log.write("[red]set API key dulu (Settings s)[/]"); return
        # promosikan sesi jadi per-target -> sesi hunting BARU (riwayat strategist tetap tersimpan)
        self.target = pr; self.targets = [pr]; self.strategist = False
        self.target_slug = re.sub(r"\W", "_", str(pr.get("key") or pr.get("name") or "target"))[:50]
        self.sess_id = self._new_sess_id()
        if self.messages is None:
            self.messages = _llm_mod().new_messages(prov == "anthropic")
        # suntik scope RESMI (SENYAP -> tak di-echo ke layar, cukup banner ringkas)
        self.messages.append({"role": "user", "content": program_context(pr)})
        nm = pr.get("name") or "-"
        g = classify_assets(pr.get("scope", [])); present = [k for k in ("web", "api", "android", "ios", "other") if g[k]]
        log.write("\n[dim]" + "─" * 40 + "[/]")
        log.write(f"[b green]🎯 HANDOFF → {nm}[/] [dim]· {pr.get('platform')} · {', '.join(present) or '-'} · "
                  f"wildcard {len(pr.get('wild', []))} · sev {pr.get('maxsev', '-')}[/]")
        log.write("[dim]scope resmi dimuat. Mulai rangkaian hunting penuh (checkpoint tiap tahap)...[/]")
        self._refresh_bars()
        kick = (f"mulai hunting {nm}: SCOPE-GATE pakai TARGET CONTEXT lalu susun HUNTING BRIEF sesuai jenis aset.")
        self._write_user(kick); self._send(kick)
    # ---- slash commands ----
    def _slash(self, raw):
        log = self.query_one("#chatlog", SelectableLog)
        parts = raw[1:].split(None, 1); cmd = parts[0].lower(); arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd in ("help", "?", "h"):
            # PERINTAH dulu, ringkasan TOMBOL/ALUR di AKHIR: log auto-scroll ke bawah,
            # jadi bagian paling sering dibutuhkan yang tersisa di layar.
            from rich.cells import cell_len as _cl
            wmax = max(_cl(c) for c, _ in SLASH_HELP)
            log.write("[b cyan]PERINTAH[/]")
            for c, d in SLASH_HELP:
                pad = " " * (wmax - _cl(c) + 2)      # rata kolom biar mudah dibaca
                # WAJIB escape: placeholder seperti [domain]/[cari] ditafsirkan Rich
                # sebagai tag markup lalu DIBUANG, jadi placeholder tak pernah tampil.
                log.write(f"  [yellow]{escape_markup(c)}[/]{pad}[dim]{escape_markup(d)}[/]")
            _n = chr(10)
            log.write(
                _n + "[b cyan]TOMBOL[/]" + _n +
                "  [yellow]Enter[/] kirim   [yellow]Alt+Enter[/] baris baru   "
                "[yellow]esc[/] stop   [yellow]Ctrl+Q[/] keluar" + _n +
                "  [yellow]Ctrl+PgUp/PgDn[/] gulir chat   [yellow]F3[/] yolo   "
                "[yellow]Ctrl+O[/] model   [yellow]Ctrl+R[/] resume   [yellow]Ctrl+L[/] bersihkan" + _n +
                "  [yellow]Ctrl+C[/] salin tersorot   [yellow]Ctrl+V[/] tempel   "
                "[yellow]Ctrl+Click[/] buka URL" + _n +
                _n + "[b cyan]ALUR[/]  [dim]tiap tahap berhenti di CHECKPOINT — ketik[/] [b]lanjut[/]" + _n +
                "  target → recon → analisa → rencana → verifikasi → draf laporan → [b]submit = kamu[/]" + _n +
                "  [dim]aksi kirim-traffic perlu[/] [b]/yolo[/] [dim]ON[/]")
        elif cmd in ("yolo", "active", "a"): self.action_toggle_active()
        elif cmd == "model":
            if arg: self.cfg["llm_model"] = arg; save_cfg(self.cfg); self._refresh_bars(); self._load_window(); log.write(f"[green]model -> {arg} (memuat context window...)[/]")
            else:
                log.write("[dim]membuka daftar model dari provider... (esc utk batal)[/]")
                self.action_pick_model()
        elif cmd == "provider":
            if arg in ("anthropic", "openai"):
                self.cfg["llm_provider"] = arg; save_cfg(self.cfg); self._refresh_bars(); log.write(f"[green]provider -> {arg}[/]")
            else:
                log.write(f"[yellow]provider sekarang: {self.cfg.get('llm_provider','anthropic')}. Pakai: /provider anthropic | openai[/]")
        elif cmd in ("new", "reset"):
            # SESI BARU: id baru -> sesi lama TETAP tersimpan sbg riwayat (/resume utk buka lagi)
            self.messages = None; self.tok_in = self.tok_out = self.turns = 0; self.ctx = 0; self.t0 = None
            self.sess_id = self._new_sess_id(); self._refresh_bars()
            if self.target:   # sesi baru tetap bawa scope target
                self.messages = _llm_mod().new_messages(_llm_creds(self.cfg)[0] == "anthropic")
                self.messages.append({"role": "user", "content": program_context(self.target)})
                log.write(f"[b]-- sesi baru untuk {self.target.get('name')} --[/] [dim](scope dimuat ulang; sesi lama tersimpan di /resume)[/]")
            else:
                log.write("[b]-- sesi baru --[/] [dim](sesi lama tersimpan di /resume; memori tetap)[/]")
        elif cmd == "clear":
            self.action_clear(); log.write("[dim]layar chat dibersihkan (riwayat sesi TETAP tersimpan).[/]")
        elif cmd == "resume": self.action_resume()
        elif cmd in ("pick", "gas"):
            if not self.pool:
                log.write("[yellow]/pick hanya di mode STRATEGIST (buka lewat tombol [b]t[/] di dashboard).[/]"); return
            if not arg:
                log.write("[yellow]pakai:[/] [b]/pick <nama program>[/] [dim](cukup sebagian nama, mis. /pick whatnot)[/]"); return
            pr = self._find_pool(arg)
            if not pr:
                near = ", ".join((p.get("name") or "?") for p in self.pool[:8])
                log.write(f"[yellow]'{arg}' tak cocok di portfolio.[/] [dim]teratas: {near}...[/]"); return
            self._handoff(pr)
        elif cmd == "save":
            if not self.messages:
                log.write("[yellow]belum ada percakapan untuk disimpan.[/]")
            else:
                path = self._autosave()
                if path:
                    log.write(f"[green]sesi disimpan[/] ({len(self.messages)} pesan) [dim]-> {path}[/]"
                              f"\n[dim]Sesi juga TERSIMPAN OTOMATIS tiap selesai satu turn dan saat kamu keluar. "
                              f"Buka lagi dengan [b]/resume[/].[/]")
                else:
                    log.write("[red]GAGAL menyimpan sesi[/] [dim](cek izin tulis ~/.config/bbtui/agent-sessions)[/]")
        elif cmd == "memory":
            out = _llm_mod().mem_search(arg) if arg else _llm_mod().mem_list()
            log.write("[b cyan]🧠 memori:[/]\n" + out[:1500])
        elif cmd in ("add", "read", "ingest", "upload"):
            if not arg: log.write("[yellow]pakai: /add <path-file-atau-folder>[/]"); return
            self._ingest_path(arg)
        elif cmd == "mcp":
            if arg.lower().startswith("connect"):
                log.write("[cyan]~ connect server MCP...[/]"); self._mcp_connect()
            else:
                log.write("[b cyan]MCP:[/]\n" + _llm_mod().mcp_status())
        elif cmd == "skills": log.write("[b cyan]skills:[/]\n" + _llm_mod().t_list_skills())
        elif cmd == "skill":
            sp = arg.split(None, 2)
            if len(sp) >= 3 and sp[0].lower() == "install":
                r = _llm_mod().t_install_skill(name=sp[1], source=sp[2])
                log.write("[green]" + r + "[/]" if "terpasang" in r else "[yellow]" + r + "[/]")
            else: log.write("[yellow]pakai: /skill install <nama> <url|path>[/]")
        elif cmd == "tools": log.write("[b cyan]tools agent:[/] " + ", ".join(t["name"] for t in _llm_mod().TOOLS))
        elif cmd == "status":
            p, mdl, _b, k = _llm_creds(self.cfg)
            log.write(f"[b]status:[/] model={mdl} provider={p} key={'ada' if k else 'BELUM'} yolo={'ON' if self.allow_gated else 'off'} "
                      f"turn={self.turns} token_in/out={self.tok_in}/{self.tok_out} ctx={self.ctx}/{self.window} compactx{self.compacts} sibuk={self.busy}")
        elif cmd == "context":
            win = self.window or _llm_mod().model_window(_llm_creds(self.cfg)[1])
            est = _llm_mod().estimate_ctx(self.messages) if self.messages else 0
            log.write(f"[b]konteks:[/] terpakai~{self.ctx or est} tok / window {win} tok ({int((self.ctx or est)*100/win)}%). Auto-compact di ~75%.")
        elif cmd == "compact":
            if not self.messages or len(self.messages) < 3: log.write("[yellow]konteks masih pendek.[/]"); return
            p, mdl, base, k = _llm_creds(self.cfg)
            log.write("[magenta]~ meringkas konteks...[/]"); self._do_compact(p, mdl, base, k)
        elif cmd == "target":
            if not self.target:
                log.write("[yellow]tak ada target aktif.[/] [dim]Pilih program di layar utama lalu tekan[/] [b]l[/].")
            else:
                log.write("[b green]🎯 target aktif:[/] " + str(self.target.get("name")))
                log.write("[dim]" + escape_markup(program_context(self.target)) + "[/]")
        elif cmd in ("recon", "monitor", "dedup"):
            d = arg or (apex(self.target) if self.target else "")
            if cmd == "dedup" and not arg and self.target:
                d = self.target.get("key") or self.target.get("name") or ""
            if not d:
                log.write(f"[yellow]pakai: /{cmd} <target>[/] [dim](tak ada target aktif utk default)[/]")
            else:
                log.write(f"[cyan]membuka {cmd}[/] [dim]{d} -- esc utk batal[/]")
                self.app.push_screen(ToolScreen(cmd, d))
        elif cmd == "retry":
            last = None
            for m in reversed(self.messages or []):
                if m.get("role") != "user": continue
                t = _llm_mod()._msg_text(m.get("content"))
                if t.startswith("[TARGET CONTEXT]") or t.startswith("[ARTEFAK"): continue
                last = t; break
            if not last:
                log.write("[yellow]belum ada pesan untuk dikirim ulang.[/]")
            elif self.busy:
                log.write("[yellow]agent masih sibuk -- tekan esc dulu.[/]")
            else:
                # buang pesan user terakhir supaya tidak dobel di konteks
                for k in range(len(self.messages) - 1, -1, -1):
                    if self.messages[k].get("role") == "user":
                        del self.messages[k]; break
                log.write(f"[cyan]kirim ulang:[/] [dim]{escape_markup(last[:80])}[/]")
                self._submit(last)
        elif cmd == "note":
            if not arg:
                log.write("[yellow]pakai: /note <teks temuan>[/] [dim](tersimpan ke workspace target)[/]")
            else:
                prog = (self.target or {}).get("name") or "umum"
                stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
                r = _llm_mod().t_save_note(program=prog, text=f"- [{stamp}] {arg}", kind="note")
                log.write(f"[green]📝 catatan tersimpan[/] [dim]{escape_markup(r)}[/]")
        elif cmd == "report":
            if arg.lower().startswith("save"):
                if not self._last_agent:
                    log.write("[yellow]belum ada jawaban agent untuk disimpan.[/]")
                else:
                    prog = (self.target or {}).get("name") or "umum"
                    r = _llm_mod().t_save_note(program=prog, text=self._last_agent, kind="report")
                    log.write(f"[green]📄 draf laporan tersimpan[/] [dim]{escape_markup(r)}[/]")
            else:
                # tugas agent: muat playbook laporan, JANGAN submit (submit tetap milik user)
                self._submit("susun DRAF LAPORAN untuk temuan sejauh ini: muat skill report-kit dan "
                             "verify, ikuti templatenya (ringkasan, dampak, langkah reproduksi "
                             "1-variabel, bukti, saran perbaikan), dan cek anti-duplikat. "
                             "JANGAN submit ke platform -- berhenti di CHECKPOINT supaya saya review. "
                             "Setelah itu saya simpan dengan /report save.")
        elif cmd == "handoff":
            d = arg or (apex(self.target) if self.target else "")
            if not d:
                log.write("[yellow]pakai: /handoff <domain>[/] [dim](atau pilih target dulu)[/]")
            else:
                log.write(f"[cyan]menyusun handoff pack[/] [dim]{d}...[/]")
                r = _llm_mod().t_handoff(d)
                log.write("[green]" + escape_markup(r) + "[/]" if "PACK dibuat" in r
                          else "[yellow]" + escape_markup(r) + "[/]")
        elif cmd in ("ext", "ext-tools", "exttools"):
            d = arg or (apex(self.target) if self.target else "")
            log.write("[cyan]membuka ext-tools[/] [dim]" + (d or "tanpa target") + " -- esc utk batal[/]")
            self.app.push_screen(ExternalToolsScreen(self.cfg, d))
        elif cmd == "stage": self._submit("lanjut ke tahap berikutnya sesuai urutan; kalau tahap sekarang belum kelar, selesaikan lalu checkpoint.")
        elif cmd == "stop": self.action_stop()
        elif cmd == "redraw":
            self.app.action_redraw(); log.write("[dim]layar digambar ulang penuh.[/]")
        elif cmd == "mouse":
            self.app.action_mouse_toggle()
            on = getattr(self.app, "_mouse_app", True)
            log.write("[dim]mouse: " + ("dipegang APP (klik tombol jalan)" if on else "dilepas ke TERMINAL (seleksi teks native)") + ".[/]")
        elif cmd == "diag": self._diag()
        elif cmd == "export": self._export()
        elif cmd in ("quit", "exit", "q", "keluar"):
            if self.busy: self.action_stop()
            log.write("[dim]keluar sesi chat...[/]"); self.app.pop_screen()
        else: log.write(f"[yellow]perintah '/{cmd}' tak dikenal. /help utk daftar.[/]")
    @work(thread=True)
    def _mcp_connect(self):
        log = self.query_one("#chatlog", SelectableLog)
        try:
            rep = _llm_mod().mcp_connect_all(self.cfg)
            for line in rep: self.app.call_from_thread(log.write, "  [dim]MCP * " + line + "[/]")
            if not rep: self.app.call_from_thread(log.write, "[dim]tak ada server MCP di config.[/]")
        except Exception as e:
            self.app.call_from_thread(log.write, f"[red]MCP gagal: {e}[/]")
    def _ingest_path(self, raw):
        la = _llm_mod(); log = self.query_one("#chatlog", SelectableLog)
        p = os.path.expanduser(raw.strip().strip('"').strip("'"))
        if os.path.isdir(p): content = la.t_ingest_folder(p); label = f"FOLDER {p}"
        elif os.path.isfile(p): content = la.t_read_file(p); label = f"FILE {p}"
        else: log.write(f"[yellow]path tak ditemukan: {raw}[/]"); return
        prov = _llm_creds(self.cfg)[0]
        if self.messages is None: self.messages = la.new_messages(prov == "anthropic")
        self.messages.append({"role": "user", "content": f"[ARTEFAK DI-UPLOAD: {label}]\n{content}"})
        try: la.session_save(self.sess_id, self.messages, target=self.target_slug)
        except Exception: pass
        log.write(f"[green]📎 ditambahkan ke konteks:[/] {label} [dim]({len(content)} char)[/]. "
                  "Beri instruksi (mis. 'cari endpoint & secret di artefak ini').")
    # ---- palette slash (autocomplete) ----
    def _slash_box(self):
        try: return self.query_one("#slashbox", OptionList)
        except Exception: return None
    def on_input_changed(self, ev):
        if getattr(ev.input, "id", None) != "chatinput": return
        self._slash_filter(ev.value)
    def on_text_area_changed(self, ev):
        if getattr(ev.text_area, "id", None) != "chatinput": return
        self._slash_filter(ev.text_area.text)
    def _slash_filter(self, v):
        box = self._slash_box()
        if box is None: return
        v = v or ""
        if v.startswith("/"):
            q = v[1:].split()[0].lower() if len(v) > 1 else ""
            box.clear_options()
            name_hits, desc_hits = [], []
            for c, d in SLASH_HELP:
                cmd = c.split()[0]                      # token perintah, mis. /model
                if q in cmd[1:].lower(): name_hits.append((c, d, cmd))   # match NAMA command dulu
                elif q in d.lower(): desc_hits.append((c, d, cmd))       # baru deskripsi
            for c, d, cmd in name_hits + desc_hits:
                # escape: placeholder [domain]/[cari] dst kalau tidak di-escape akan
                # dianggap tag markup oleh OptionList lalu hilang dari daftar.
                box.add_option(Option(f"{escape_markup(c)}  --  {escape_markup(d)}", id=cmd))
            if box.option_count:
                box.add_class("on"); box.highlighted = 0
            else:
                box.remove_class("on")
        else:
            box.remove_class("on")
    def _fill_slash(self, run=False):
        box = self._slash_box()
        if not box or not box.has_class("on") or box.highlighted is None: return False
        opt = box.get_option_at_index(box.highlighted); cmd = opt.id or opt.prompt.split()[0]
        box.remove_class("on")
        inp = self.query_one("#chatinput", ChatBox)
        if run: inp.value = ""; self._submit(cmd)
        else: inp.value = cmd + " "; inp.focus()
        return True
    def on_key(self, ev):
        box = self._slash_box()
        if not box or not box.has_class("on"): return
        if ev.key == "down": box.action_cursor_down(); ev.stop(); ev.prevent_default()
        elif ev.key == "up": box.action_cursor_up(); ev.stop(); ev.prevent_default()
        elif ev.key == "tab": self._fill_slash(run=False); ev.stop(); ev.prevent_default()
        elif ev.key == "escape": box.remove_class("on"); ev.stop(); ev.prevent_default()
    def on_option_list_option_selected(self, ev):   # klik mouse pada opsi
        if ev.option_list.id == "slashbox": self._fill_slash(run=True)
    def on_chat_box_submitted(self, ev):
        self._do_submit(ev.value)
    def on_input_submitted(self, ev):
        self._do_submit(ev.value)
    def _do_submit(self, raw):
        box = self._slash_box()
        if box and box.has_class("on"):   # palette aktif
            val = (raw or "").strip(); tok = val.split()[0].lower() if val else ""
            known = {c.split()[0] for c, _d in SLASH_HELP}
            if tok in known:                       # yg diketik PERSIS sebuah command -> jalankan itu (+ argnya)
                self._clear_box(); box.remove_class("on"); self._slash(val); return
            self._fill_slash(run=True); return     # cuma prefix -> jalankan yg ter-highlight
        text = (raw or "").strip(); self._clear_box()
        if not text and self._suggest: text = self._suggest
        if text: self._submit(text)
    def _clear_box(self):
        try: self.query_one("#chatinput", ChatBox).value = ""
        except Exception: pass
    def _submit(self, text):
        log = self.query_one("#chatlog", SelectableLog)
        if text.startswith("/"): self._slash(text); return          # slash SELALU jalan (walau sibuk)
        if self.busy:
            log.write("[yellow]⏳ agent masih memproses -- tunggu CHECKPOINT, atau tekan #/esc untuk stop.[/]"); return
        cand = text.strip().strip('"').strip("'")                   # drag-drop path -> ingest
        if (os.sep in cand or cand.startswith("~")) and os.path.exists(os.path.expanduser(cand)):
            log.write(f"\n[b green]📎 upload[/] {cand}"); self._ingest_path(cand); return
        self._write_user(text)
        self._send(text)
    # ---- render jawaban agent: prosa rapi + tabel markdown jadi Rich Table ----
    @staticmethod
    def _is_row(l): return l.strip().count("|") >= 2
    @staticmethod
    def _is_sep(l):
        s = l.strip().strip("|")
        return bool(s) and all(set(c.strip()) <= set("-:") and c.strip() for c in s.split("|"))
    def _box_width(self):
        """Lebar isi kotak chat. Dipakai utk panjang garis kurung."""
        try:
            w = self.query_one("#chatlog", SelectableLog).content_size.width
        except Exception:
            w = 0
        return max(28, min(w or 78, 220))
    def _write_box(self, label, inner, color):
        """Gambar kotak berkurung sebagai TEKS.

        Bukan Rich Panel: Panel/Group membuat Static tak bisa diseleksi, jadi seluruh
        kotak dirakit sebagai satu markup string. Sisi kanan sengaja dibiarkan terbuka
        supaya baris panjang yang membungkus tidak merusak bingkai.
        """
        from rich.cells import cell_len
        W = self._box_width()
        head = "╭─ %s " % label
        dash = max(0, W - cell_len(head) - 1)
        out = ["", "[%s]╭─[/] [b %s]%s[/] [%s]%s╮[/]" % (color, color, label, color, "─" * dash)]
        for ln in inner:
            if ln and "[" in ln and not _markup_ok(ln):  # 1 baris rusak -> escape baris ITU saja,
                from rich.markup import escape            # bingkai & baris lain tetap ber-format
                ln = escape(ln)
            out.append(("[%s]│[/] " % color) + ln if ln else "[%s]│[/]" % color)
        out.append("[%s]╰%s╯[/]" % (color, "─" * max(0, W - 2)))
        self.query_one("#chatlog", SelectableLog).write(chr(10).join(out))
    def _write_user(self, text):
        from rich.markup import escape
        self._write_box("▶ kamu", [escape(l) for l in (text.splitlines() or [""])], "green")
    def _table_text(self, rows):
        # Tabel markdown -> teks rata kolom yg MUAT di kotak chat. Kolom terlebar
        # dikecilkan & sel panjang DIBUNGKUS (word-wrap) jadi beberapa baris ->
        # tak lagi meluber/berantakan saat ada kolom "alasan" yg panjang.
        from rich.markup import escape
        import textwrap
        def clean(c):                                  # buang penanda markdown di sel (**tebal**, `kode`)
            c = c.strip()
            c = re.sub(r"\*\*(.+?)\*\*", r"\1", c); c = re.sub(r"`([^`]+)`", r"\1", c)
            return c.strip()
        cells = lambda r: [clean(c) for c in r.strip().strip("|").split("|")]
        hdr = cells(rows[0]); n = len(hdr)
        data = [(cells(r) + [""] * n)[:n] for r in rows[1:]]
        w = [len(hdr[i]) for i in range(n)]            # lebar alami tiap kolom
        for row in data:
            for i in range(n): w[i] = max(w[i], len(row[i]))
        box = self._box_width() - 2                    # sisakan utk prefix "│ "
        avail = max(12, box - 3 * (n - 1))             # ' │ ' antar kolom
        floor = [max(3, min(len(hdr[i]) or 3, 12)) for i in range(n)]
        guard = 0
        while sum(w) > max(avail, sum(floor)) and guard < 20000:   # kecilkan kolom TERLEBAR dulu
            j = max(range(n), key=lambda i: w[i] - floor[i])
            if w[j] <= floor[j]: break
            w[j] -= 1; guard += 1
        def wrap_cell(txt, width):
            if not txt: return [""]
            return textwrap.wrap(txt, width=max(1, width), break_long_words=True, break_on_hyphens=False) or [""]
        def render(rowcells, bold=False):
            stacks = [wrap_cell(rowcells[i], w[i]) for i in range(n)]
            height = max(len(s) for s in stacks)
            lines = []
            for k in range(height):
                seg = [(stacks[i][k] if k < len(stacks[i]) else "") for i in range(n)]
                ln = " │ ".join(seg[i] + " " * (w[i] - len(seg[i])) for i in range(n))
                lines.append(("[b]" + escape(ln) + "[/]") if bold else escape(ln))
            return lines
        out = render(hdr, bold=True)
        out.append("[dim]" + escape("─┼─".join("─" * x for x in w)) + "[/]")
        for row in data: out += render(row)
        return "\n".join(out)
    def _write_agent(self, body):
        self._last_agent = body
        inner = []
        lines = body.splitlines(); n = len(lines); i = 0
        while i < n:
            if self._is_row(lines[i]) and i + 1 < n and self._is_sep(lines[i + 1]):
                j = i + 2
                while j < n and self._is_row(lines[j]) and not self._is_sep(lines[j]): j += 1
                inner.extend(self._table_text([lines[i]] + lines[i + 2:j]).split(chr(10))); i = j
            else:
                ln = lines[i]
                if not ln.strip(): inner.append("")
                elif "CHECKPOINT" in ln: inner.append("[black on cyan] " + ln.strip().lstrip("#").strip() + " [/]")
                else: inner.append(_md_line(ln))
                i += 1
        self._write_box("🤖 agent", inner, "cyan")
    def _send(self, text):
        prov, model, base, key = _llm_creds(self.cfg)
        if not key: self.app.notify("set API key dulu (Settings s)"); return
        self._suggest = ""   # saran goal terpakai sekali
        self.busy = True; self.activity = "berpikir"; self.turns += 1; self.t0 = datetime.datetime.now(); self._refresh_bars()
        self._worker = self._run_stage(text, prov, model, base, key)
    @work(thread=True)
    def _do_compact(self, prov, model, base, key):
        la = _llm_mod(); log = self.query_one("#chatlog", SelectableLog)
        # PENTING: _http_json melempar SystemExit (turunan BaseException), jadi
        # 'except Exception' TIDAK menangkapnya. Tanpa penjaga ini, error API bikin
        # worker menabrak dgn traceback alih-alih pesan ramah.
        try:
            before = la.estimate_ctx(self.messages)
            self.messages[:] = la.compact(self.messages, prov, model, key, base)
            self.ctx = la.estimate_ctx(self.messages); self.compacts += 1
            self.app.call_from_thread(log.write, f"[magenta]v konteks diringkas: ~{before} -> ~{self.ctx} tok.[/]")
            self.app.call_from_thread(self._refresh_bars)
        except (Exception, SystemExit) as e:
            from rich.markup import escape as _e
            self.app.call_from_thread(log.write, f"[red]! gagal meringkas konteks: {_e(str(e))}[/]")
    @work(thread=True)
    def _run_stage(self, text, prov, model, base, key):
        log = self.query_one("#chatlog", SelectableLog)
        def w(line): self.app.call_from_thread(log.write, line)
        def set_meta(d):
            if "activity" in d: self.activity = d["activity"]
            if "tokens" in d: self.tok_in += d["tokens"].get("in", 0); self.tok_out += d["tokens"].get("out", 0)
            if "ctx" in d: self.ctx = d["ctx"]
            if "window" in d: self.window = d["window"]
            if d.get("compacted"): self.compacts += 1
            self.app.call_from_thread(self._refresh_bars)
        def emit(kind, body):
            if kind == "llm":
                self.app.call_from_thread(self._write_agent, body)   # render prosa + TABEL rapi
            elif kind == "tool":
                nm = body.split(" ", 1)[0]; arg = body.split(" ", 1)[1] if " " in body else ""
                from rich.markup import escape as _e
                w(f"  [yellow]*[/] [b]{nm}[/] [dim]{_e(arg[:120])}[/]")
            elif kind == "result":
                from rich.markup import escape as _e
                lines = [l for l in body.splitlines() if l.strip()]
                head = _e(lines[0].lstrip("#").strip()[:130]) if lines else "(kosong)"
                more = f" [dim]... +{len(lines)-1} baris (dipakai agent, tak ditampilkan penuh)[/]" if len(lines) > 1 else ""
                w(f"  [dim]>[/] {head}{more}")
            else:
                from rich.markup import escape as _e
                w(f"[red]! {_e(body)}[/]")
        try:
            la = _llm_mod()
            if self.messages is None: self.messages = la.new_messages(prov == "anthropic")
            self.messages.append({"role": "user", "content": text})
            la.agent_turn(self.messages, prov, model, key, base, emit, allow_gated=self.allow_gated, confirm=None, on_meta=set_meta)
        except (Exception, SystemExit) as e:
            # SystemExit dari _http_json bukan turunan Exception -> harus disebut eksplisit.
            # WAJIB escape: pesan error bisa memuat potongan markup (mis. '[/u cyan]') yg
            # kalau ditulis mentah bikin log gagal parse -> dulu ini mer-crash TUI saat hunting.
            from rich.markup import escape as _e
            w(f"[red]! error: {_e(str(e))}[/]")
        finally:
            # SIMPAN DI finally: kalau agent_turn gagal (mis. API 503/timeout), pesan
            # user + hasil sebagian tetap tersimpan. Dulu save di jalur sukses saja,
            # sehingga turn yang error hilang.
            self._autosave()
            self.busy = False; self.activity = "idle"; self._worker = None
            self.app.call_from_thread(self._refresh_bars)
            self.app.call_from_thread(lambda: self.query_one("#chatinput", ChatBox).focus())

class ContextMenuScreen(ModalScreen):
    """Menu klik-kanan pada baris program: pindahkan ke worklist (ditinjau/kerja/skip/belum)
    + aksi cepat. Muncul di posisi kursor. Status sekarang ditandai."""
    BINDINGS = [("escape", "app.pop_screen", "tutup")]
    ACTIONS = [
        ("reviewed", "\U0001f441 Tandai Ditinjau"),
        ("working",  "\U0001f3af Tandai Dikerjakan"),
        ("skip",     "\U0001f515 Skip (sembunyikan)"),
        ("belum",    "\u00b7 Kembalikan ke Belum"),
        ("_sep1", "\u2500 proses target \u2500"),
        ("recon",    "\U0001f50e Recon"),
        ("monitor",  "\U0001f4e1 Monitor"),
        ("dedup",    "\U0001f501 Dedup"),
        ("workspace","\U0001f4c1 Workspace"),
        ("notify",   "\U0001f514 Notify (TG/Discord)"),
        ("external", "\U0001f9f0 Ext-tools"),
        ("handoff",  "\U0001f4e6 Handoff Pack (Burp)"),
        ("_sep2", "\u2500 agent \u2500"),
        ("llm",      "\U0001f916 LLM Agent (hunting)"),
        ("strategist","\U0001f9ed Strategist (semua program)"),
    ]
    def __init__(self, prs, xy, on_action):
        super().__init__()
        self.prs = prs if isinstance(prs, list) else [prs]   # bisa 1 atau BANYAK (multi-seleksi)
        self.xy = xy; self.on_action = on_action
    def compose(self) -> ComposeResult:
        yield OptionList(id="ctxlist")
    def on_mouse_down(self, ev):
        # KLIK di LUAR kotak menu -> tutup (on_click tak sampai App -> pakai mouse_down)
        try:
            box = self.query_one("#ctxlist", OptionList)
            x = getattr(ev, "screen_x", None); y = getattr(ev, "screen_y", None)
            if x is None: x, y = getattr(ev, "x", 0), getattr(ev, "y", 0)
            if not box.region.contains(int(x), int(y)): self.app.pop_screen()
        except Exception: pass
    def on_mount(self):
        from rich.markup import escape
        from textual.widgets.option_list import Option
        box = self.query_one("#ctxlist", OptionList)
        if len(self.prs) == 1:
            box.border_title = "\u2192 " + escape((self.prs[0].get("name") or "program")[:28])
        else:
            box.border_title = "\u2192 " + str(len(self.prs)) + " program terpilih"
        curst = self._cur()
        for act, label in self.ACTIONS:
            if act.startswith("_sep"):
                box.add_option(Option("[dim]" + label + "[/]", id=act, disabled=True)); continue
            mark = "[green]\u2713[/] " if act == curst or (act == "belum" and not curst) else "  "
            box.add_option(Option(mark + label, id=act))
        box.highlighted = 0
        w, h = 40, len(self.ACTIONS) + 3
        try:
            if self.xy:                                  # dekat kursor (klik kanan)
                x, y = self.xy
                x = max(0, min(int(x), self.app.size.width - w))
                y = max(0, min(int(y), self.app.size.height - h))
            else:                                        # dipicu tombol -> tengah layar
                x = max(0, (self.app.size.width - w) // 2)
                y = max(1, (self.app.size.height - h) // 2)
            box.styles.offset = (x, y)
        except Exception:
            pass
        box.focus()
    def _cur(self):
        try: return self.app._st(self.prs[0]["key"]) if len(self.prs) == 1 else ""
        except Exception: return ""
    def on_option_list_option_selected(self, ev):
        act = ev.option.id
        self.app.pop_screen()
        if act and not act.startswith("_sep"):
            self.on_action(self.prs, act)

class ResumePickerScreen(ModalScreen):
    """Pop-up daftar riwayat chat tersimpan -> pilih mana yang mau dilanjutkan.

    Sebelumnya /resume hanya memuat sesi milik target yang sedang dibuka, jadi kalau
    kamu pindah target ia berkata "tak ada sesi tersimpan" walau riwayat lain ada.
    Di sini SEMUA sesi ditampilkan (terbaru dulu) lengkap dgn jumlah pesan, waktu,
    dan cuplikan pesan terakhir.
    """
    BINDINGS = [("escape", "app.pop_screen", "batal"), ("d", "hapus", "hapus"),
                ("r", "muat_ulang", "refresh")]
    def __init__(self, on_pick, current=None):
        super().__init__(); self.on_pick = on_pick; self.current = current; self.items = []
    def compose(self) -> ComposeResult:
        with Vertical(id="stat"):
            yield Label("[b cyan]RIWAYAT CHAT[/]  [dim]pilih sesi yang mau dilanjutkan[/]", classes="title")
            yield OptionList(id="reslist")
            yield Static("[dim]up/down pilih  ·  Enter lanjutkan  ·  d hapus  ·  esc batal[/]")
    def on_mount(self):
        self._reload()
        try: self.query_one("#reslist", OptionList).focus()
        except Exception: pass
    def _reload(self):
        from rich.markup import escape
        box = self.query_one("#reslist", OptionList)
        box.clear_options()
        self.items = _llm_mod().session_list()
        if not self.items:
            box.add_option(Option("[dim](belum ada riwayat tersimpan)[/]", id="none"))
            return
        for i, it in enumerate(self.items):
            # nama = target (dari metadata) -> rapi; fallback parse dari sid lama
            nama = (it.get("target") or "").replace("_", " ").strip()
            if not nama:
                nama = it["sid"]
                if nama.startswith("tui-"): nama = nama[4:]
                nama = re.sub(r"-\d{8}_\d{6}.*$", "", nama).replace("_", " ").strip() or "(tanpa nama)"
            waktu = (it.get("saved") or "")[:16].replace("T", " ")
            kini = "  [b green]<- sedang dibuka[/]" if self.current and it["sid"] == self.current else ""
            baris1 = f"[b]{i+1}. {escape(nama)}[/]{kini}   [dim]{it['n']} pesan · {waktu}[/]"
            baris2 = "     [dim]" + escape(it.get("preview") or "(kosong)") + "[/]"
            box.add_option(Option(baris1 + chr(10) + baris2, id=str(i)))
        box.highlighted = 0
    def action_muat_ulang(self): self._reload()
    def _pilih(self):
        box = self.query_one("#reslist", OptionList)
        if box.highlighted is None or not self.items: return None
        try: return self.items[box.highlighted]
        except Exception: return None
    def action_hapus(self):
        it = self._pilih()
        if not it: return
        if _llm_mod().session_delete(it["path"]):
            self.app.notify(f"riwayat dihapus: {it['sid']}")
        else:
            self.app.notify("gagal menghapus", severity="warning")
        self._reload()
    def on_option_list_option_selected(self, ev):
        it = self._pilih()
        self.app.pop_screen()
        if it: self.on_pick(it)

class SchedulerScreen(ModalScreen):
    """Scheduling: pasang/hapus cron pipeline harian dari dalam TUI (keyboard)."""
    BINDINGS = [("escape", "app.pop_screen", "tutup"), ("ctrl+s", "install", "install"), ("ctrl+d", "remove", "hapus")]
    def compose(self) -> ComposeResult:
        with Vertical(id="stat"):
            yield Label("[b cyan]SCHEDULING -- pipeline otomatis harian (cron)[/]", classes="title")
            yield Static(self._status(), id="cronstat")
            yield Static("Pipeline = finder -> program baru -> scope.md + dedup + recon pasif -> notif. (butuh cron/Linux)")
            yield Label("Jam (0-23), lalu tekan [b green]Ctrl+S[/] = pasang/update:")
            yield Input(value="8", id="cronhour")
            yield Label("\n[b green]> Ctrl+S[/] pasang jadwal - [b red]Ctrl+D[/] hapus jadwal - [dim]esc = tutup[/]")
    def _status(self):
        return "Status: [green]TERJADWAL AKTIF[/]" if cron_active() else "Status: [yellow]belum terjadwal[/]"
    def on_input_submitted(self, _): self.action_install()
    def action_install(self):
        hour = self.query_one("#cronhour", Input).value.strip() or "8"
        ok = cron_install(hour)
        self.query_one("#cronstat", Static).update(self._status())
        self.app.notify(f"✅ cron dipasang jam {hour}:00" if ok else "❌ gagal (cron tak tersedia? bukan Linux?)")
    def action_remove(self):
        cron_remove(); self.query_one("#cronstat", Static).update(self._status()); self.app.notify("jadwal dihapus")

def _diag_report(app):
    """Laporan lingkungan utk mendiagnosa glitch render (user kirim ke maintainer)."""
    import platform
    L = []
    L.append("== FAJAR-AGENT DIAG ==")
    L.append("waktu       : " + datetime.datetime.now().isoformat(timespec="seconds"))
    L.append("agent       : %s v%s" % (AGENT_NAME, AGENT_VERSION))
    L.append("python      : %s  (%s)" % (sys.version.split()[0], platform.platform()))
    for mod in ("textual", "rich"):
        try:
            import importlib.metadata as _md
            L.append("%-12s: %s" % (mod, _md.version(mod)))
        except Exception:
            try:
                L.append("%-12s: %s" % (mod, __import__(mod).__version__))
            except Exception as e:
                L.append("%-12s: ? (%s)" % (mod, e))
    L.append("-- terminal --")
    for k in ("TERM", "COLORTERM", "TERM_PROGRAM", "TERM_PROGRAM_VERSION", "LANG", "LC_ALL",
              "TMUX", "STY", "SSH_TTY", "SSH_CONNECTION", "DISPLAY", "WAYLAND_DISPLAY",
              "WT_SESSION", "KONSOLE_VERSION", "VTE_VERSION", "ALACRITTY_WINDOW_ID",
              "KITTY_WINDOW_ID", "GNOME_TERMINAL_SERVICE", "NO_COLOR", "TEXTUAL"):
        v = os.environ.get(k)
        if v:
            L.append("  %s=%s" % (k, v))
    try:
        drv = getattr(app, "_driver", None)
        L.append("driver      : %s" % (type(drv).__name__ if drv else None))
        L.append("is_inline   : %s" % getattr(app, "is_inline", "?"))
        L.append("ukuran app  : %sx%s" % (app.size.width, app.size.height))
        L.append("screen_stack: %s -> %s" % (len(app.screen_stack),
                                             [type(x).__name__ for x in app.screen_stack]))
    except Exception as e:
        L.append("app state   : err %s" % e)
    L.append("-- clipboard --")
    found = [c for c in ("wl-copy", "xclip", "xsel", "pbcopy") if shutil.which(c)]
    L.append("  tool tersedia: %s" % (found or "TIDAK ADA (copy besar ditolak)"))
    L.append("  trace aktif  : %s" % (getattr(app, "_trace_path", None) or "tidak (set FAJAR_TRACE=1)"))
    return chr(10).join(L)

def _clip_write(text):
    """Tulis ke clipboard OS lewat tool asli (TANPA escape terminal).

    Kembalikan nama tool bila sukses, None bila tak ada tool. Ini dipakai menggantikan
    OSC52 bawaan Textual: OSC52 menulis '\\x1b]52;c;<base64>' LANGSUNG ke terminal di luar
    pipeline render — blob besar bisa terjalin dgn frame & merusak sequence posisi kursor,
    sehingga baris tergambar di koordinat salah (sampah/glitch).
    """
    for cmd in (["wl-copy"], ["xclip", "-selection", "clipboard"],
                ["xsel", "--clipboard", "--input"], ["pbcopy"]):
        if not shutil.which(cmd[0]): continue
        try:
            p = subprocess.run(cmd, input=text.encode("utf-8"),
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5)
            if p.returncode == 0: return cmd[0]
        except Exception:
            pass
    return None

class BBTUI(App):
    CSS = CSS
    ALLOW_SELECT = True   # seleksi teks pakai mouse (drag) + Ctrl+C copy -- tanpa Shift/slash
    TITLE = "FAJAR-AGENT -- Bug Bounty Hunting Harness"   # command palette (ctrl+p / ikon header) AKTIF: ganti tema, dll
    BINDINGS = [Binding("ctrl+c", "copy_text", "salin", key_display="Ctrl+C", show=True), ("q", "quit", "keluar"), ("slash", "search", "cari"), ("r", "refresh", "refresh"),
                ("e", "recon", "recon"), ("m", "monitor", "monitor"), ("d", "dedup", "dedup"),
                ("n", "notify", "notif"), ("w", "workspace", "workspace"), ("x", "external", "ext-tools"),
                ("b", "only_new", "baru"), ("c", "cycle_sort", "urut"), ("l", "llm", "llm-agent"), ("t", "strategist", "strategist"), ("p", "pipeline", "pipeline"), ("g", "schedule", "jadwal"),
                ("f", "cycle_view", "filter"), ("v", "mark_reviewed", "ditinjau"), ("k", "mark_working", "kerja"), ("full_stop", "toggle_skip", "skip"),
                ("space", "toggle_select", "pilih"), ("a", "select_all", "pilih semua"),
                ("s", "settings", "settings"), ("i", "guide", "panduan"), ("question_mark", "help", "bantuan"),
                ("escape", "clear_search", "")]   # redraw & mode-salin tak lagi di footer: glitch-nya sudah beres, salin cukup Ctrl+C. Sisa lewat /redraw dan /mouse.
    VIEWS = ["all", "baru", "belum", "ditinjau", "kerja", "skip"]
    VIEW_LABEL = {"all": "semua (skip disembunyikan)", "baru": "\U0001f195 baru", "belum": "belum ditinjau",
                  "ditinjau": "\U0001f441 ditinjau", "kerja": "\U0001f3af dikerjakan", "skip": "\U0001f515 skip"}
    def __init__(self):
        super().__init__(); self.cfg = load_cfg(); self.progs = {}; self.rowmap = {}
        self.filter = ""; self.new_keys = set(); self.only_new = False; self.view = "all"
        self.selected_keys = set()   # multi-seleksi (Space menandai)
        self.status = self._load_status()
    def _load_status(self):
        try: return json.load(open(STATUS, encoding="utf-8"))
        except Exception: return {}
    def _save_status(self):
        try:
            os.makedirs(CFG_DIR, exist_ok=True)
            json.dump(self.status, open(STATUS, "w", encoding="utf-8"))
        except Exception: pass
    def _st(self, key): return self.status.get(key, "")
    def _set_st(self, key, val):
        if val: self.status[key] = val
        else: self.status.pop(key, None)
        self._save_status()
    def _icon(self, pr):
        st = self._st(pr["key"])
        if st == "skip": return "\U0001f515"
        if st == "working": return "\U0001f3af"
        if st == "reviewed": return "\U0001f441"
        if pr["key"] in self.new_keys: return "\U0001f195"
        return "\u00b7"
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True, icon="*")
        with Horizontal(id="body"):
            with Vertical(id="side"):
                yield Static("memuat...", id="stat")
                yield Static("[b]Filter platform[/b]\n[dim]ketik / untuk cari nama/scope[/]", classes="title")
            with Vertical(id="tablewrap"):
                yield Tabs(
                    Tab("semua", id="tab-all"), Tab("\U0001f195 baru", id="tab-baru"),
                    Tab("\u00b7 belum", id="tab-belum"), Tab("\U0001f441 ditinjau", id="tab-ditinjau"),
                    Tab("\U0001f3af kerja", id="tab-kerja"), Tab("\U0001f515 skip", id="tab-skip"),
                    id="cattabs")
                yield DataTable(id="tbl", cursor_type="row", zebra_stripes=True)
            yield VerticalScroll(Static("pilih program ->", id="detail"))
        yield Input(placeholder="cari nama/scope... (enter)", id="search")
        yield Footer()   # ^p palette (ganti tema, cari perintah) TETAP tampil
    def _trace_on(self):
        """FAJAR_TRACE=1 -> rekam SEMUA byte yg app tulis ke terminal (diagnosa glitch)."""
        if str(os.environ.get("FAJAR_TRACE", "")).lower() not in ("1", "true", "yes", "on"):
            return
        drv = getattr(self, "_driver", None)
        if drv is None:
            return
        path = os.path.expanduser("~/fajar-trace.bin")
        try:
            fh = open(path, "wb")
        except Exception:
            return
        orig = drv.write
        def w(x, *a, **k):
            try:
                fh.write(x.encode("utf-8", "replace") if isinstance(x, str) else bytes(x))
                fh.flush()
            except Exception:
                pass
            return orig(x, *a, **k)
        drv.write = w
        self._trace_path = path
    def on_mount(self):
        self._trace_on()
        self._start_freeze_watch()          # FAJAR_FREEZE=1 -> rekam siapa nge-blok thread utama
        self._start_profiler()              # FAJAR_PROFILE=1 -> profil fungsi paling makan waktu
        t = self.query_one("#tbl", DataTable)
        t.add_columns("S", "Program", "Plat", "Reward", "WC", "Aset", "Sev", "Q")
        self.query_one("#side").border_title = "DASHBOARD"
        self.query_one("#tablewrap").border_title = "PROGRAMS"
        self.query_one("#detail").border_title = "DETAIL"
        self._boot()
        self.set_focus(t)   # penting: fokus ke tabel, bukan ke kotak search
        self.push_screen(SplashScreen())   # banner pembuka (sekalian nutup loading)
    def _beat(self):
        import time as _t; self._hb = _t.monotonic()
    def _start_freeze_watch(self):
        # Detektor freeze OPSIONAL (aktif hanya bila env FAJAR_FREEZE di-set). Thread
        # penjaga mengambil STACK thread utama saat heartbeat telat -> tahu PERSIS fungsi
        # apa yg nge-blok UI. Tanpa env: nol overhead (tak ada interval/thread tambahan).
        if not os.environ.get("FAJAR_FREEZE"):
            return
        import time as _t, threading, sys as _s, traceback
        self._hb = _t.monotonic(); self._freeze_seen = 0.0
        main_id = threading.get_ident()
        self.set_interval(0.15, self._beat)          # heartbeat thread utama
        logp = os.path.expanduser("~/fajar-freeze.log")
        def watch():
            while not getattr(self, "_stop_watch", False):
                _t.sleep(0.15)
                gap = _t.monotonic() - getattr(self, "_hb", _t.monotonic())
                if gap > 0.4 and self._hb != self._freeze_seen:
                    self._freeze_seen = self._hb
                    try:
                        fr = _s._current_frames().get(main_id)
                        stk = "".join(traceback.format_stack(fr)) if fr else "(no frame)"
                        with open(logp, "a", encoding="utf-8") as f:
                            f.write(f"\n=== FREEZE ~{gap*1000:.0f}ms @ {datetime.datetime.now().isoformat()} ===\n{stk}\n")
                    except Exception:
                        pass
        threading.Thread(target=watch, daemon=True).start()
    def _start_profiler(self):
        # SAMPLING PROFILER opsional (env FAJAR_PROFILE=1): tiap 12ms ambil frame TERATAS
        # thread utama & tally -> saat keluar tulis fungsi paling 'makan waktu' ke
        # ~/fajar-profile.txt. Menemukan biang BERAT kronis (hitch kecil beruntun yg tak
        # sampai ambang freeze). Tanpa env: nol overhead.
        if not os.environ.get("FAJAR_PROFILE"):
            return
        import time as _t, threading, sys as _s, collections, atexit
        main_id = threading.get_ident()
        counts = collections.Counter(); state = {"n": 0}
        def sampler():
            while not getattr(self, "_stop_watch", False):
                _t.sleep(0.012)
                fr = _s._current_frames().get(main_id)
                if fr is None: continue
                state["n"] += 1
                # rangkai 3 frame teratas -> konteks cukup tanpa terlalu ramai
                sig = []
                f = fr
                for _ in range(3):
                    if f is None: break
                    co = f.f_code
                    sig.append(f"{os.path.basename(co.co_filename)}:{f.f_lineno}:{co.co_name}")
                    f = f.f_back
                counts[" <- ".join(sig)] += 1
        def dump():
            try:
                tot = max(1, state["n"])
                with open(os.path.expanduser("~/fajar-profile.txt"), "w", encoding="utf-8") as fh:
                    fh.write(f"# FAJAR sampling profiler — {tot} sampel thread utama (12ms/sampel)\n")
                    fh.write("# %%  sampel  frame_teratas <- pemanggil <- pemanggil\n")
                    for k, c in counts.most_common(40):
                        fh.write(f"{c*100.0/tot:5.1f}%  {c:6d}  {k}\n")
            except Exception:
                pass
        atexit.register(dump)
        threading.Thread(target=sampler, daemon=True).start()
    def on_unmount(self):
        self._stop_watch = True
    def _save_cache(self):
        try:
            os.makedirs(CFG_DIR, exist_ok=True)
            json.dump({"fetched_at": datetime.datetime.now().isoformat(),
                       "programs": self.progs, "new_keys": sorted(self.new_keys)},
                      open(CACHE, "w", encoding="utf-8"))
        except Exception: pass
    def _load_cache(self):
        try:
            d = json.load(open(CACHE, encoding="utf-8"))
            progs = d.get("programs") or {}
            if not progs: return None
            nk = set(d.get("new_keys") or [])
            at = None
            try: at = datetime.datetime.fromisoformat(d.get("fetched_at"))
            except Exception: pass
            return progs, nk, at
        except Exception:
            return None
    def _is_stale(self):
        at = getattr(self, "_fetched_at", None)
        if not at: return True
        return (datetime.datetime.now() - at).total_seconds() > STALE_HOURS * 3600
    def _fresh_label(self):
        at = getattr(self, "_fetched_at", None)
        if not at: return "belum ada tarikan"
        sec = int((datetime.datetime.now() - at).total_seconds())
        if sec < 90: return "baru saja"
        if sec < 3600: return f"{sec // 60} menit lalu"
        if sec < 86400: return f"{sec // 3600} jam lalu"
        return f"{sec // 86400} hari lalu"
    def _boot(self):
        cache = self._load_cache()
        if cache:
            # START INSTAN: tampilkan cache dulu, lalu segarkan di latar bila basi
            self.progs, self.new_keys, self._fetched_at = cache
            self._render()
            if self._is_stale(): self.load(announce=True)
        else:
            self.load(announce=True)
    def _load_start_ui(self, empty):
        # indikator loading yg JELAS: spinner bila tabel kosong (load pertama),
        # atau border '↻ menyegarkan…' + toast bila cache sudah tampil.
        try:
            if empty: self.query_one("#tbl", DataTable).loading = True
            else: self.query_one("#tablewrap").border_title = "PROGRAMS  [yellow]↻ menyegarkan…[/]"
        except Exception: pass
        self._render(getattr(self, "_last_errs", None))
        self.notify("↻ menyegarkan data dari platform…", timeout=4)
    def _load_done_ui(self):
        try: self.query_one("#tbl", DataTable).loading = False
        except Exception: pass
        try: self.query_one("#tablewrap").border_title = "PROGRAMS"
        except Exception: pass
    @work(thread=True)
    def load(self, announce=False):
        self._refreshing = True
        empty = not self.progs
        self.app.call_from_thread(self._load_start_ui, empty)
        progs, errs = load_programs(self.cfg)
        old = self.progs or {}
        # 🔒/⚠ = info (bukan gagal); sisanya (exception platform, ❌ private) = tarikan GAGAL
        hard = [e for e in (errs or []) if not str(e).startswith(("🔒", "⚠"))]
        if not progs:
            # TARIKAN TOTAL GAGAL (jaringan/semua platform) -> JANGAN timpa/hapus apa pun.
            # Dulu: self.progs=progs(kosong) + _save_cache() -> data hilang PERMANEN.
            self._refreshing = False
            keep = list(errs or [])
            keep.append("⚠ tarikan kosong — data sebelumnya DIPERTAHANKAN (cek jaringan lalu r)" if old
                        else "⚠ tarikan kosong — belum ada data (cek jaringan/API lalu r)")
            self._last_errs = keep
            self.app.call_from_thread(self._load_done_ui)
            self.app.call_from_thread(self._render, keep)
            if announce:
                self.app.call_from_thread(lambda: self.notify(
                    "⚠ gagal menyegarkan — data lama dipertahankan", severity="warning", timeout=6))
            return
        if hard and old:
            # TARIKAN SEBAGIAN GAGAL -> UNION: data baru diutamakan, entri lama yg hilang
            # dari tarikan ini TETAP ada (mis. 1 platform/token blip) -> tak 'hilang' sesaat.
            merged = dict(old); merged.update(progs); progs = merged
        prev_new = self.new_keys
        self.new_keys = self._diff_seen(progs)   # diff vs seen -> program yg BENAR-BENAR baru
        self.progs = progs
        self._fetched_at = datetime.datetime.now()
        self._refreshing = False
        self._last_errs = errs
        self._save_cache()                       # SAVE: cache tarikan -> start berikutnya instan
        self.app.call_from_thread(self._load_done_ui)
        self.app.call_from_thread(self._render, errs)
        if announce and self.new_keys and self.new_keys != prev_new:
            self.app.call_from_thread(self._announce_new)
        elif announce:
            extra = " (sebagian sumber gagal — data lama dipertahankan)" if hard else " (tak ada yg baru)"
            msg = f"✓ data terbaru — {len(progs)} program{extra}"
            self.app.call_from_thread(lambda: self.notify(msg, timeout=4))
    def _announce_new(self):
        n = len(self.new_keys)
        self.view = "baru"; self._render()          # FOKUS BARU: auto-pindah ke tab 🆕
        self.notify(f"🔔 {n} program BARU ditemukan — tab 🆕", timeout=8)
    def _diff_seen(self, progs):
        prev = set()
        try: prev = set(json.load(open(SEEN, encoding="utf-8")))
        except Exception: pass
        cur = set(progs.keys())
        new = set() if not prev else (cur - prev)   # run pertama: baseline, jangan banjir 'baru'
        try:
            os.makedirs(CFG_DIR, exist_ok=True)
            json.dump(sorted(prev | cur), open(SEEN, "w", encoding="utf-8"))
        except Exception: pass
        return new
    def _q(self, p): return quiet_score(p, p["key"] in self.new_keys)
    def _render(self, errs=None):
        t = self.query_one("#tbl", DataTable)
        try: _keep_row = t.cursor_coordinate.row   # ingat baris kursor -> tak lompat ke atas
        except Exception: _keep_row = 0
        t.clear(); self.rowmap = {}
        items = list(self.progs.values())
        mq = _num(self.cfg, "min_quiet")
        # private (diundang) tak ikut disaring skor quiet
        if mq: items = [p for p in items if self._q(p) >= mq or "PRIVATE" in str(p.get("signal", ""))]
        v = self.view
        if v != "skip":
            items = [p for p in items if self._st(p["key"]) != "skip"]   # skip disembunyikan di semua view lain
        if v == "baru":       items = [p for p in items if p["key"] in self.new_keys]
        elif v == "belum":    items = [p for p in items if not self._st(p["key"]) and p["key"] not in self.new_keys]
        elif v == "ditinjau": items = [p for p in items if self._st(p["key"]) == "reviewed"]
        elif v == "kerja":    items = [p for p in items if self._st(p["key"]) == "working"]
        elif v == "skip":     items = [p for p in items if self._st(p["key"]) == "skip"]
        if self.filter:
            f = self.filter.lower()
            items = [p for p in items if f in (p["name"] or "").lower() or any(f in s.lower() for s in p["scope"])]
        sort = str(self.cfg.get("sort", "platform"))
        if sort == "quiet": items.sort(key=lambda x: (-self._q(x), (x["name"] or "").lower()))
        elif sort == "reward": items.sort(key=lambda x: (-(x["bounty_max"] or 0), (x["name"] or "").lower()))
        elif sort == "assets": items.sort(key=lambda x: (-len(x["scope"]), (x["name"] or "").lower()))
        else: items.sort(key=lambda x: (x["key"] not in self.new_keys, x["platform"], (x["name"] or "").lower()))
        from rich.text import Text
        for p in items:
            nm = (p["name"] or "-")[:32]
            cell = Text.from_markup(f"[black on #ffd700]{nm}[/]") if p["key"] in self.selected_keys else nm
            rk = t.add_row(self._icon(p), cell, p["platform"][:3], reward(p), str(len(p["wild"])),
                           str(len(p["scope"])), p["maxsev"], str(self._q(p)))
            self.rowmap[rk] = p
        self._key2rk = {pr["key"]: rk for rk, pr in self.rowmap.items()}   # peta cepat utk update sel
        try:
            if self.rowmap: t.move_cursor(row=max(0, min(_keep_row, len(self.rowmap) - 1)))
        except Exception: pass
        self._side_panel(len(items), errs)
    def _side_panel(self, n_shown, errs=None):
        """Bangun HANYA panel samping (stat + label tab). Dipisah dari _render supaya
        perubahan status 1-baris bisa memperbarui ini TANPA membangun ulang tabel (mahal)."""
        per = {}
        for p in self.progs.values(): per[p["platform"]] = per.get(p["platform"], 0) + 1
        mq = _num(self.cfg, "min_quiet")
        refreshing = getattr(self, "_refreshing", False)
        fresh = ("[b yellow]menyegarkan data...[/]" if refreshing
                 else f"[green]tersimpan[/] [dim]{self._fresh_label()} - r=segar[/]")
        stat = f"{fresh}\n[b]Total:[/] {len(self.progs)}\n" + "\n".join(f"  {k}: {v}" for k, v in per.items())
        allp = list(self.progs.values())
        nb = nrev = nwork = nskip = nbelum = 0        # SATU lintasan (dulu 5 lintasan terpisah)
        for p in allp:
            st = self._st(p["key"])
            if st == "reviewed": nrev += 1
            elif st == "working": nwork += 1
            elif st == "skip": nskip += 1
            elif p["key"] in self.new_keys: nb += 1
            else: nbelum += 1
        stat += (f"\n\n[b]WORKLIST[/]\n"
                 f"  [{'green' if nb else 'dim'}]🆕 baru {nb}[/]   [cyan]👁 ditinjau {nrev}[/]   [yellow]🎯 kerja {nwork}[/]\n"
                 f"  [dim]· belum {nbelum}   🔕 skip {nskip}[/]")
        if self.selected_keys:
            stat += f"\n\n[b black on #ffd700] {len(self.selected_keys)} terpilih [/] [dim](Enter=menu utk semua · esc=batal)[/]"
        stat += f"\n[b]tampil:[/] {n_shown}  [dim](Space=pilih · Enter=menu · f=kategori)[/]"
        # perbarui label tab dgn jumlah + aktifkan tab sesuai view
        try:
            counts = {"all": len(allp) - nskip, "baru": nb, "belum": nbelum,
                      "ditinjau": nrev, "kerja": nwork, "skip": nskip}
            base = {"all": "semua", "baru": "\U0001f195 baru", "belum": "\u00b7 belum",
                    "ditinjau": "\U0001f441 ditinjau", "kerja": "\U0001f3af kerja", "skip": "\U0001f515 skip"}
            tabs = self.query_one("#cattabs", Tabs)
            for kk, lbl in base.items():
                tabs.query_one("#tab-" + kk, Tab).label = f"{lbl} {counts[kk]}"
            self._sync_tab()
        except Exception: pass
        if self.filter: stat += f"\n[yellow]filter: {self.filter}[/]"
        stat += f"\n[b]urut:[/] {self.cfg.get('sort','platform')} [dim](c=ubah)[/]"
        if mq: stat += f"\n[cyan]min-quiet: {int(mq)}[/]"
        stat += f"\n[dim]Q = skor anti-ramai (proxy)[/]"
        stat += f"\n[dim]enrich: {self.cfg.get('enrich_provider','jina')}[/]"
        if errs:
            # tampil PENUH per baris (dulu dipotong 60 char -> diagnosa token hilang).
            # baris diawali emoji status = info privat; sisanya = error platform publik.
            stat += "\n"
            for e in errs:
                col = "green" if e.startswith("🔒") else ("yellow" if e[0] in "⚠" else "red")
                stat += f"\n[{col}]{e}[/]"
        self.query_one("#stat", Static).update(stat)
    def _view_ok(self, pr):
        """Apakah pr TAMPIL di view sekarang (cermin rantai filter _render, tanpa urut)."""
        k = pr["key"]; st = self._st(k); v = self.view
        mq = _num(self.cfg, "min_quiet")
        if mq and self._q(pr) < mq and "PRIVATE" not in str(pr.get("signal", "")): return False
        if v != "skip" and st == "skip": return False
        if v == "baru" and k not in self.new_keys: return False
        if v == "belum" and (st or k in self.new_keys): return False
        if v == "ditinjau" and st != "reviewed": return False
        if v == "kerja" and st != "working": return False
        if v == "skip" and st != "skip": return False
        if self.filter:
            f = self.filter.lower()
            if not (f in (pr["name"] or "").lower() or any(f in s.lower() for s in pr["scope"])): return False
        return True
    def _fast_status(self, pr):
        """Update status 1-baris: kalau baris TETAP tampil -> cukup ubah ikon sel + panel
        samping (instan). Kalau masuk/keluar view -> _render penuh (perlu susun ulang)."""
        was = pr["key"] in getattr(self, "_key2rk", {})   # rowmap di-key ROW-key; peta prog-key = _key2rk
        now = self._view_ok(pr)
        if was and now:
            rk = self._key2rk.get(pr["key"])
            try:
                if rk is None: raise KeyError
                self.query_one("#tbl", DataTable).update_cell(rk, "S", self._icon(pr))
                self._side_panel(len(self.rowmap))
                return
            except Exception:
                pass
        self._render()
    def on_tabs_tab_activated(self, ev):
        if ev.tabs.id != "cattabs": return
        want = (ev.tab.id or "tab-all").replace("tab-", "")
        if want != self.view:
            self.view = want; self._render()
    def _sync_tab(self):
        try:
            tabs = self.query_one("#cattabs", Tabs)
            tid = "tab-" + self.view
            if tabs.active != tid: tabs.active = tid
        except Exception: pass
    def _tool_target(self, kind, pr):
        if kind == "dedup":
            return pr["key"].split("|", 1)[1] if (pr["platform"] == "hackerone" and "|" in pr["key"]) else (pr["url"] or apex(pr))
        return apex(pr)
    def _tool_cmd(self, kind, tgt):
        if kind == "recon": return [sys.executable, _tool("recon.py"), tgt, "--profile", "passive"]
        if kind == "monitor": return [sys.executable, _tool("asset-monitor.py"), tgt]
        out = os.path.expanduser("~/bb-dedup-" + re.sub(r"\W", "_", tgt)[:40] + ".md")
        return [sys.executable, _tool("dedup.py"), tgt, "--out", out]
    @work(thread=True)
    def _batch_tool(self, kind, prs):
        n = len(prs)
        for i, pr in enumerate(prs, 1):
            tgt = self._tool_target(kind, pr)
            if not tgt: continue
            try:
                subprocess.run(self._tool_cmd(kind, tgt), capture_output=True, timeout=1800)
                self.app.call_from_thread(lambda i=i, tgt=tgt: self.notify(f"\u2713 {kind} {i}/{n}: {tgt}", timeout=3))
            except Exception as e:
                self.app.call_from_thread(lambda tgt=tgt, e=e: self.notify(f"\u2717 {kind} {tgt}: {str(e)[:50]}", severity="warning"))
        self.app.call_from_thread(lambda: self.notify(f"\u2713 {kind} batch selesai ({n} target)", timeout=6))
    @work(thread=True)
    def _run_handoff(self, prs):
        la = _llm_mod(); n = len(prs); ok = 0
        for i, pr in enumerate(prs, 1):
            d = apex(pr)
            if not d: continue
            try:
                res = la.t_handoff(d)
                good = "belum ada" not in res and "[gagal]" not in res
                ok += 1 if good else 0
                msg = (f"✓ handoff {i}/{n}: {d}" if good
                       else f"⚠ {d}: recon dulu (e/Recon) lalu ulangi")
                self.app.call_from_thread(lambda m=msg: self.notify(m, timeout=5))
            except (Exception, SystemExit) as e:
                self.app.call_from_thread(lambda e=e: self.notify(f"✗ handoff {d}: {str(e)[:50]}", severity="warning"))
        self.app.call_from_thread(lambda: self.notify(
            f"\U0001f4e6 handoff selesai: {ok}/{n} pack dibuat (lihat ~/bb-recon/<domain>/handoff.md)", timeout=7))
    def _make_workspace(self, pr):
        if not pr: return False
        name = re.sub(r"\W", "_", (pr["name"] or "target"))[:40]
        cands = [os.path.join(SCRIPT_DIR, "..", "TARGET-WORKSPACE-TEMPLATE"), os.path.join(SCRIPT_DIR, "TARGET-WORKSPACE-TEMPLATE")]
        tpl = next((c for c in cands if os.path.isdir(c)), None)
        dest = os.path.expanduser(f"~/bb-workspaces/{name}")
        try:
            if not os.path.exists(dest):
                if tpl: shutil.copytree(tpl, dest)
                else: os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, "scope.md"), "a", encoding="utf-8") as fh:
                fh.write(f"\n\n## Auto-seed (bbtui) -- {pr['name']} [{pr['platform']}] {pr['url']}\n"
                         "### Wildcard\n" + "\n".join("- " + w for w in pr["wild"]) +
                         "\n### Scope\n" + "\n".join("- " + str(sx) for sx in pr["scope"][:80]))
            return True
        except Exception:
            return False
    def _ctx_action(self, prs, act):
        if not prs: return
        if act in ("reviewed", "working", "skip", "belum"):
            val = "" if act == "belum" else act
            for pr in prs: self._set_st(pr["key"], val)
            self.selected_keys.clear()
            lbl = {"reviewed": "\U0001f441 ditinjau", "working": "\U0001f3af dikerjakan",
                   "skip": "\U0001f515 di-skip", "belum": "\u00b7 belum"}[act]
            self.notify((f"{len(prs)} program -> " if len(prs) > 1 else (prs[0]["name"] or "") + " -> ") + lbl)
            self._render()
        elif act in ("recon", "monitor", "dedup"):
            for pr in prs: self._mark_working(pr)
            self.selected_keys.clear(); self._render()
            if len(prs) == 1:
                self.push_screen(ToolScreen(act, self._tool_target(act, prs[0])))   # 1 -> modal interaktif
            else:
                self.notify(f"\u21bb {act} batch: {len(prs)} target (latar, profil passive)...", timeout=5)
                self._batch_tool(act, list(prs))                                    # banyak -> batch latar
        elif act == "workspace":
            made = sum(1 for pr in prs if self._make_workspace(pr))
            self.selected_keys.clear(); self._render()
            self.notify(f"\U0001f4c1 workspace dibuat/di-seed: {made} program")
        elif act == "notify":
            self.selected_keys.clear(); self._render()
            for pr in prs: self._send_notify(pr)
            self.notify(f"\U0001f514 mengirim {len(prs)} program ke channel notif...", timeout=4)
        elif act == "external":
            tgt = apex(prs[0]) if prs else ""
            if len(prs) > 1:
                self.notify(f"ext-tools: pakai target pertama ({tgt}) — jalankan satu per satu", timeout=5)
            self.selected_keys.clear(); self._render()
            self.push_screen(ExternalToolsScreen(self.cfg, tgt))
        elif act == "handoff":
            for pr in prs: self._mark_working(pr)
            tgs = list(prs); self.selected_keys.clear(); self._render()
            self.notify(f"\U0001f4e6 Handoff Pack: {len(tgs)} target (butuh recon dulu; latar)...", timeout=5)
            self._run_handoff(tgs)
        elif act == "strategist":
            self.selected_keys.clear(); self._render()
            self.action_strategist()                 # portfolio-level (abaikan baris terpilih)
        elif act == "llm":
            for p in prs: self._mark_working(p)
            tgs = list(prs); self.selected_keys.clear()
            if len(tgs) > 1:
                self.notify(f"LLM: {len(tgs)} target dimuat ke 1 chat (konteks semua) \U0001f3af", timeout=5)
            self.push_screen(LlmChatScreen(self.cfg, targets=tgs))
    def on_data_table_row_selected(self, ev):
        # RowSelected muncul utk KLIK mouse DAN Enter. Klik ditangani drag-select ->
        # buka menu HANYA bila dipicu Enter keyboard (tak ada mouse-down barusan).
        last = getattr(self, "_last_mouse", None)
        if last and (datetime.datetime.now() - last).total_seconds() < 0.2:
            return
        pr = self.rowmap.get(ev.row_key)
        self._open_menu(self._menu_targets(pr))
    # ---------- SELEKSI MOUSE: klik = 1, drag = rentang ----------
    def _ev_row(self, ev, t=None):
        # baris dari META event (dibawa event walau tanpa hover) -> aman di mode 1002
        try:
            r = ev.style.meta.get("row")
            if r is not None and r >= 0: return r
        except Exception:
            pass
        return self._hover_row(t) if t is not None else None
    def _hover_row(self, t):
        try:
            c = t.hover_coordinate
            r = c.row if hasattr(c, "row") else c[0]
            return r if (r is not None and r >= 0) else None
        except Exception:
            return None
    def _apply_drag_range(self, t, a, b):
        from textual.coordinate import Coordinate
        from rich.text import Text
        lo, hi = (a, b) if a <= b else (b, a)
        newsel = set()
        for r in range(lo, hi + 1):
            try:
                rk = t.coordinate_to_cell_key(Coordinate(r, 0)).row_key
                pr = self.rowmap.get(rk)
                if pr: newsel.add(pr["key"])
            except Exception:
                pass
        if newsel == self.selected_keys:
            return
        changed = newsel ^ self.selected_keys           # hanya baris yg berubah status
        self.selected_keys = newsel
        k2rk = getattr(self, "_key2rk", {})
        for key in changed:
            rk = k2rk.get(key); pr = self.rowmap.get(rk) if rk is not None else None
            if not pr: continue
            nm = (pr["name"] or "-")[:32]
            cell = Text.from_markup(f"[black on #ffd700]{nm}[/]") if key in self.selected_keys else Text(nm)
            try: t.update_cell(rk, "Program", cell)
            except Exception: pass
    def _row_prog(self, t, row):
        from textual.coordinate import Coordinate
        try: return self.rowmap.get(t.coordinate_to_cell_key(Coordinate(row, 0)).row_key)
        except Exception: return None
    def on_mouse_down(self, ev):
        if isinstance(self.screen, ModalScreen): return   # modal terbuka -> jangan ganggu (cegah freeze)
        b = getattr(ev, "button", 0)
        try: t = self.query_one("#tbl", DataTable)
        except Exception: return
        self._last_mouse = datetime.datetime.now()
        if b == 3:                                     # KLIK KANAN -> menu (on_click tak sampai App!)
            row = self._ev_row(ev, t)
            pr = self._row_prog(t, row) if row is not None else None
            if pr:
                xy = (getattr(ev, "screen_x", None) or getattr(ev, "x", 40),
                      getattr(ev, "screen_y", None) or getattr(ev, "y", 10))
                self._open_menu(self._menu_targets(pr), xy)
            return
        if b != 1: return
        row = self._ev_row(ev, t)
        if row is None: return
        # TIDAK capture_mouse (bisa nyangkut -> "jalan sendiri"). TIDAK reset seleksi
        # & TIDAK apply range di sini: klik biasa = pindah KURSOR saja (biar tabel yg
        # urus). Seleksi kuning baru dimulai kalau mouse benar2 BERGERAK (drag).
        self._drag_anchor = row; self._dragging = True; self._drag_moved = False
    def on_mouse_move(self, ev):
        if not getattr(self, "_dragging", False): return   # kasus umum (tak drag) -> keluar cepat
        if getattr(ev, "button", 0) != 1:                  # tombol sudah dilepas (up terlewat) -> stop
            self._dragging = False; return
        if isinstance(self.screen, ModalScreen):
            self._dragging = False; return
        try: t = self.query_one("#tbl", DataTable)
        except Exception: return
        row = self._ev_row(ev, t)
        if row is None: return
        anchor = getattr(self, "_drag_anchor", row)
        if row == anchor and not getattr(self, "_drag_moved", False):
            return                                         # masih di baris awal -> belum drag
        if not getattr(self, "_drag_moved", False):
            self._drag_moved = True
            self.selected_keys = set()                     # gerakan pertama -> mulai seleksi baru
        self._apply_drag_range(t, anchor, row)
    def _release_mouse_safe(self):
        self._dragging = False; self._drag_moved = False
        try: self.query_one("#tbl", DataTable).release_mouse()
        except Exception: pass
        try: self.release_mouse()
        except Exception: pass
    def on_mouse_up(self, ev):
        if isinstance(self.screen, ModalScreen): return
        was_drag = getattr(self, "_dragging", False) and getattr(self, "_drag_moved", False)
        self._release_mouse_safe()
        self._last_mouse = datetime.datetime.now()
        if not was_drag: return                            # klik biasa -> tak ada seleksi, diam
        n = len(self.selected_keys)
        if n: self.notify(f"{n} program terpilih (Enter=menu · esc=batal)", timeout=3)
        self._render()
    def _menu_targets(self, pr):
        if self.selected_keys:
            prs = [self.progs[k] for k in self.selected_keys if k in self.progs]
            if prs: return prs
        return [pr] if pr else []
    def _open_menu(self, prs, xy=None):
        self._release_mouse_safe()                 # pastikan tak stuck sebelum menu
        if prs: self.push_screen(ContextMenuScreen(prs, xy, self._ctx_action))
    def action_ctx_menu(self):
        self._open_menu(self._menu_targets(self._selected()))
    def action_toggle_select(self):
        pr = self._selected()
        if not pr: return
        k = pr["key"]
        if k in self.selected_keys: self.selected_keys.discard(k); onoff = "dilepas"
        else: self.selected_keys.add(k); onoff = "DIPILIH"
        # perbarui 1 sel + panel (tanpa rebuild -> kursor tak lompat)
        try:
            from rich.text import Text
            t = self.query_one("#tbl", DataTable)
            nm = (pr["name"] or "-")[:32]
            cell = Text.from_markup(f"[black on #ffd700]{nm}[/]") if k in self.selected_keys else Text(nm)
            rk = t.coordinate_to_cell_key(t.cursor_coordinate).row_key
            t.update_cell(rk, "Program", cell)
        except Exception: pass
        self.notify(f"{onoff}: {pr['name']}  ·  total {len(self.selected_keys)} terpilih (Enter=menu)", timeout=3)
    def action_select_all(self):
        # pilih semua yg TAMPIL sekarang; kalau sudah ada terpilih -> batalkan semua
        if self.selected_keys:
            self.selected_keys.clear()
        else:
            self.selected_keys = set(self.rowmap[k]["key"] for k in self.rowmap)
        self._render()
    def _render_stat(self):
        try: self._render()
        except Exception: pass
    def on_data_table_row_highlighted(self, ev):
        # DEBOUNCE: panel detail (string besar + repaint) TIDAK dibangun tiap baris saat
        # scroll cepat -> hanya 60ms setelah kursor BERHENTI. Ini biang lag scroll.
        self._pending_detail = self.rowmap.get(ev.row_key)
        tm = getattr(self, "_detail_timer", None)
        if tm is not None:
            try: tm.stop()
            except Exception: pass
        self._detail_timer = self.set_timer(0.06, self._update_detail)
    def _update_detail(self):
        pr = getattr(self, "_pending_detail", None)
        if not pr:
            return
        try: detail = self.query_one("#detail", Static)   # timer bisa nembak saat screen ganti
        except Exception: return
        others = [s for s in pr["scope"] if not is_wild(s)]
        mgd = {True: "managed", False: "unmanaged", None: "-"}.get(pr.get("managed"))
        md = (f"[b cyan]{pr['name']}[/] [{pr['platform']}]"
              + ("  [green]🆕 BARU[/]" if pr["key"] in self.new_keys else "") + "\n"
              f"Reward: [b]{reward(pr)}[/]  MaxSev: {pr['maxsev']}  Q(anti-ramai): [b]{self._q(pr)}[/]/100\n"
              f"Program: {mgd}  -  Aset: {len(pr['scope'])}  -  Wildcard: {len(pr['wild'])}\n"
              f"Sinyal H1: [dim]{pr.get('signal','-')}[/]\n"
              f"URL (rules): {pr['url'] or '-'}\n\n"
              f"[b]Wildcard ({len(pr['wild'])}):[/]\n" + ("\n".join('  ' + w for w in pr['wild']) or '  -') +
              f"\n\n[b]Aset in-scope ({len(others)}):[/]\n" + ("\n".join('  ' + s for s in others[:40]) or '  -') +
              (f"\n  ... +{len(others)-40} lagi" if len(others) > 40 else "") +
              "\n\n[b]AKSI:[/] [yellow]e[/]=recon - [yellow]m[/]=monitor - [yellow]d[/]=dedup - [yellow]l[/]=llm-agent"
              "\n[b]WORKLIST:[/] [yellow]Enter[/]/[yellow]Space[/]=MENU pindah kategori - [yellow]v[/]=👁 [yellow]k[/]=🎯 [yellow].[/]=🔕 - [yellow]f[/]=view"
              "\n[dim]recon/monitor/llm otomatis 🎯 - klik-kanan juga (bila terminal mengizinkan) - ?=bantuan[/]")
        try: detail.update(md)
        except Exception: pass
    def _selected(self):
        t = self.query_one("#tbl", DataTable)
        try: return self.rowmap.get(t.coordinate_to_cell_key(t.cursor_coordinate).row_key)
        except Exception: return None
    def action_only_new(self):
        self.view = "all" if self.view == "baru" else "baru"; self._render()
    def action_cycle_view(self):
        i = self.VIEWS.index(self.view) if self.view in self.VIEWS else 0
        self.view = self.VIEWS[(i + 1) % len(self.VIEWS)]
        self.notify("view: " + self.VIEW_LABEL.get(self.view, self.view)); self._render()
    def action_mark_reviewed(self):
        pr = self._selected()
        if not pr: return
        cur = self._st(pr["key"])
        self._set_st(pr["key"], "" if cur == "reviewed" else "reviewed")
        self.notify(("\U0001f441 ditinjau: " if self._st(pr["key"]) else "\u00b7 kembali ke belum: ") + (pr["name"] or ""))
        self._fast_status(pr)
    def action_mark_working(self):
        pr = self._selected()
        if not pr: return
        cur = self._st(pr["key"])
        self._set_st(pr["key"], "" if cur == "working" else "working")
        self.notify(("\U0001f3af dikerjakan: " if self._st(pr["key"]) else "\u00b7 kembali ke belum: ") + (pr["name"] or ""))
        self._fast_status(pr)
    def action_toggle_skip(self):
        pr = self._selected()
        if not pr: return
        if self._st(pr["key"]) == "skip":
            self._set_st(pr["key"], "")
            self.notify("\u21a9 dikembalikan dari skip: " + (pr["name"] or ""))
        else:
            self._set_st(pr["key"], "skip")
            self.notify("\U0001f515 di-skip (disembunyikan; view Skip [f] utk kembalikan): " + (pr["name"] or ""))
        self._fast_status(pr)
    def _mark_working(self, pr):
        if pr and self._st(pr["key"]) != "skip": self._set_st(pr["key"], "working")
    def action_cycle_sort(self):
        order = ["platform", "quiet", "reward", "assets"]
        cur = str(self.cfg.get("sort", "platform"))
        self.cfg["sort"] = order[(order.index(cur) + 1) % len(order)] if cur in order else "quiet"
        save_cfg(self.cfg); self.notify(f"urut: {self.cfg['sort']}"); self._render()
    def action_mouse_toggle(self):
        """F2: lepas/ambil mouse dari terminal.

        MODE SALIN (mouse dilepas) = app TIDAK mengirim escape mouse, jadi terminal
        menyeleksi teks secara NATIVE seperti teks biasa dan Ctrl+Shift+C milik terminal
        yang menyalin. App sama sekali tak terlibat -> tak ada OSC52, tak ada render
        seleksi, tak ada yang bisa merusak layar.
        """
        drv = getattr(self, "_driver", None)
        if drv is None:
            self.notify("driver belum siap"); return
        self._mouse_app = not getattr(self, "_mouse_app", True)
        # mode 1000/1003/1015/1006: h = app ambil mouse, l = lepas ke terminal.
        # pakai method driver bila ada; kalau tidak, tulis escape-nya langsung.
        suffix = "h" if self._mouse_app else "l"
        meth = getattr(drv, "_enable_mouse_support" if self._mouse_app else "_disable_mouse_support", None)
        try:
            if callable(meth):
                meth()
            else:
                drv.write("".join("\x1b[?%d%s" % (m, suffix) for m in (1000, 1003, 1015, 1006)))
                try: drv.flush()
                except Exception: pass
        except Exception as e:
            self.notify("gagal ganti mode mouse: %s" % e, severity="warning")
            return
        if self._mouse_app:
            self.notify("MOUSE APP aktif - klik tombol/tabel jalan. Tekan F2 utk MODE SALIN.", timeout=6)
        else:
            self.notify("MODE SALIN aktif - sorot teks seperti terminal biasa, "
                        "salin Ctrl+Shift+C, tempel Ctrl+Shift+V. F2 utk kembali.", timeout=10)
        self.action_redraw()
    def action_redraw(self):
        # Gambar ulang SELURUH layar (bukan diff). Textual normalnya hanya menulis sel yang
        # BERUBAH; kalau terminal sempat ter-scroll/desync, sel basi tak pernah ditimpa ->
        # sampah permanen (status bar dobel, teks lama nyangkut). _set_dirty() tanpa argumen
        # menandai seluruh region layar sehingga compositor memakai render_full_update().
        try:
            scr = self.screen; comp = scr._compositor
            # render_update() memilih render_full_update() bila SELURUH region layar ada di
            # _dirty_regions milik COMPOSITOR (bukan milik widget Screen -> beda atribut).
            comp._dirty_regions.add(comp.size.region)
            scr._set_dirty()
            scr.refresh()
        except Exception:
            try: self.refresh(repaint=True, layout=True)
            except Exception: pass
    def copy_to_clipboard(self, text: str) -> None:
        """Override: pakai clipboard OS, JANGAN OSC52 raksasa.

        Bawaan Textual menulis '\\x1b]52;c;<base64>' langsung ke terminal. Untuk blok chat
        besar, blob itu terjalin dgn frame -> sequence posisi kursor rusak -> baris tergambar
        di koordinat salah (inilah glitch 'copy lalu paste'). Pakai wl-copy/xclip/xsel/pbcopy.
        """
        self._clipboard = text
        if not text: return
        if _clip_write(text):                      # jalur AMAN: nol escape ke terminal
            try: self.call_after_refresh(self.action_redraw)
            except Exception: pass
            return
        if len(text) > 1000:                       # blob OSC52 besar = perusak layar
            self.notify("teks terlalu panjang untuk clipboard terminal (butuh tool OS). "
                        "Pasang: sudo apt install xclip   # atau wl-clipboard di Wayland",
                        severity="warning", timeout=10)
            return
        def _osc():
            # ditunda: ditulis SETELAH frame selesai supaya tak terjalin dgn sequence
            # posisi kursor, lalu layar digambar ulang penuh utk memastikan bersih.
            try: App.copy_to_clipboard(self, text)
            except Exception: pass
            self.action_redraw()
        try: self.call_after_refresh(_osc)
        except Exception: pass
    def action_copy_text(self):
        # salin teks yg dipilih (drag mouse) -- Ctrl+C. Lewat copy_to_clipboard() di atas.
        try: text = self.screen.get_selected_text() or ""
        except Exception: text = ""
        if not text:
            self.notify("belum ada teks dipilih -- sorot dulu dengan mouse"); return
        self.copy_to_clipboard(text)
        self.notify(f"tersalin {len(text)} karakter")
    def action_help(self): self.push_screen(HelpScreen())
    def action_guide(self): self.push_screen(GuideScreen())
    def action_external(self):
        pr = self._selected(); self.push_screen(ExternalToolsScreen(self.cfg, apex(pr) if pr else ""))
    def action_pipeline(self):
        self.push_screen(RunScreen([sys.executable, _tool("pipeline.py")], "Pipeline (finder->dedup->recon)"))
    def action_schedule(self):
        self.push_screen(SchedulerScreen())
    def action_llm(self):
        prs = self._menu_targets(self._selected())
        if prs: self._ctx_action(prs, "llm")       # hormati multi-seleksi (bukan cuma 1)
    def _portfolio_brief(self, limit=45):
        """Ringkas SELURUH portfolio (dari dashboard) -> brief padat utk STRATEGIST.
        Urut by Q anti-ramai (tinggi=sepi), buang skip. Return (teks, pool_list)."""
        cand = [p for p in self.progs.values() if self._st(p["key"]) != "skip"]
        cand.sort(key=lambda p: self._q(p), reverse=True)
        pool = cand[:max(1, limit)]
        stflag = {"working": "🎯kerja", "reviewed": "👁ditinjau"}
        L = ["[PORTFOLIO CONTEXT] -- daftar program dari dashboard operator (sumber RESMI: TUI; sudah difilter & diberi skor).",
             "PERANMU = STRATEGIST: pilih & rekomendasikan target TERBAIK utk diburu. JANGAN list_programs/new_programs/program_detail (data sudah di sini).",
             "Q = skor anti-ramai (makin TINGGI makin sepi/menjanjikan utk hindari duplikat). status = worklist operator; 🆕 = program baru.",
             f"{len(pool)} teratas (dari {len(cand)} non-skip):",
             "rank | Q | program | plat | reward | aset | wild | flag"]
        for i, p in enumerate(pool, 1):
            fl = []
            if p["key"] in self.new_keys: fl.append("🆕baru")
            st = self._st(p["key"])
            if st: fl.append(stflag.get(st, st))
            L.append(f"{i:>2} | {self._q(p):>3} | {(p.get('name') or '-')[:34]} | {p.get('platform')} | "
                     f"{reward(p)} | {len(p.get('scope', []))} | {len(p.get('wild', []))} | {' '.join(fl) or '-'}")
        L += ["",
              "Tugas: analisa lalu rekomendasikan 2-3 target dgn ALASAN (permukaan scope, kenapa sepi/anti-dup, jenis aset).",
              "Tutup dgn CHECKPOINT: minta operator ketik  /pick <nama>  utk MULAI rangkaian hunting penuh target itu."]
        return "\n".join(L), pool
    def action_strategist(self):
        if not self.progs:
            self.notify("data program belum termuat — tunggu/refresh (r) dulu"); return
        brief, pool = self._portfolio_brief()
        self.push_screen(LlmChatScreen(self.cfg, mode="strategist", portfolio=brief, pool=pool))
    def action_recon(self):
        prs = self._menu_targets(self._selected())
        if prs: self._ctx_action(prs, "recon")
    def action_monitor(self):
        prs = self._menu_targets(self._selected())
        if prs: self._ctx_action(prs, "monitor")
    def action_dedup(self):
        prs = self._menu_targets(self._selected())
        if prs: self._ctx_action(prs, "dedup")
    def action_notify(self):
        pr = self._selected()
        if not pr: self.notify("pilih program dulu"); return
        self._send_notify(pr)
    @work(thread=True)
    def _send_notify(self, pr):
        txt = (f"🎯 {pr['name']} [{pr['platform']}]\nReward: {reward(pr)}  Sev: {pr['maxsev']}\n"
               f"Wildcard: {', '.join(pr['wild'][:8]) or '-'}\nURL: {pr['url'] or '-'}")
        res = notify_channels(txt, self.cfg)
        self.app.call_from_thread(self.notify, " - ".join(res))
    def action_workspace(self):
        pr = self._selected()
        if not pr: self.notify("pilih program dulu"); return
        name = re.sub(r"\W", "_", (pr["name"] or "target"))[:40]
        cands = [os.path.join(SCRIPT_DIR, "..", "TARGET-WORKSPACE-TEMPLATE"), os.path.join(SCRIPT_DIR, "TARGET-WORKSPACE-TEMPLATE")]
        tpl = next((c for c in cands if os.path.isdir(c)), None)
        dest = os.path.expanduser(f"~/bb-workspaces/{name}")
        try:
            if not os.path.exists(dest):
                if tpl: shutil.copytree(tpl, dest)
                else: os.makedirs(dest, exist_ok=True)
            with open(os.path.join(dest, "scope.md"), "a", encoding="utf-8") as fh:
                fh.write(f"\n\n## Auto-seed (bbtui) -- {pr['name']} [{pr['platform']}] {pr['url']}\n"
                         "### Wildcard\n" + "\n".join("- " + w for w in pr["wild"]) +
                         "\n### Scope\n" + "\n".join("- " + s for s in pr["scope"][:80]))
            self.notify(f"workspace dibuat: {dest}")
        except Exception as e:
            self.notify(f"gagal buat workspace: {e}")
    def action_search(self):
        s = self.query_one("#search", Input); s.add_class("on"); s.focus()
    def action_clear_search(self):
        if self.selected_keys:                 # esc pertama = batalkan multi-seleksi
            self.selected_keys.clear(); self._render(); return
        s = self.query_one("#search", Input); s.remove_class("on"); s.value = ""; self.filter = ""; self._render()
    def on_input_submitted(self, ev):
        if ev.input.id == "search":
            self.filter = ev.value.strip(); ev.input.remove_class("on"); self._render(); self.query_one("#tbl").focus()
    def action_refresh(self): self.load(announce=True)
    def action_settings(self): self.push_screen(SettingsScreen(self.cfg))

if __name__ == "__main__":
    # mouse=False -> app TIDAK mengirim escape mouse sama sekali: seleksi & Ctrl+Shift+C
    # sepenuhnya milik terminal (bebas glitch), tombol/tabel jadi keyboard-only.
    _mouse = True
    if "--no-mouse" in sys.argv:
        _mouse = False
    else:
        try: _mouse = bool(load_cfg().get("mouse", True))
        except Exception: _mouse = True
    try:
        BBTUI().run(mouse=_mouse)
    except KeyboardInterrupt:
        pass   # keluar bersih tanpa traceback (Ctrl+C)

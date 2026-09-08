#!/usr/bin/env python3
"""FAJAR-AGENT (bbtui) — TUI modern (Textual): harness bug bounty 5 platform + recon/monitor/dedup + LLM agent.

Full-screen: sidebar (stats+filter), DataTable program, panel detail scope, run-log streaming.
Keybindings: / cari · r refresh · e recon · m monitor · d dedup · s settings · q keluar.
Butuh: python3 + 'textual'  (pip install --user --break-system-packages textual  |  atau venv).
Data: arkadiyt/bounty-targets-data. Enrichment provider opsional (jina gratis/firecrawl/serper/h1api).
Companion headless: daily-target-finder.py
"""
import json, os, re, sys, base64, shlex, shutil, datetime, subprocess, urllib.request, urllib.parse

try:
    from textual.app import App, ComposeResult
    from textual.containers import Horizontal, Vertical, VerticalScroll, Center, Middle
    from textual.widgets import Header, Footer, DataTable, Static, Input, RichLog, Label, Button, OptionList
    from textual.widgets.option_list import Option
    from textual.screen import ModalScreen
    from textual import work
except ImportError:
    sys.exit("[!] butuh 'textual'. Pasang:  pip install --user --break-system-packages textual\n"
             "    (atau: python3 -m venv ~/.venv-bbtui && ~/.venv-bbtui/bin/pip install textual && ~/.venv-bbtui/bin/python bbtui.py)")

BASE = "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/{}_data.json"
DISCLOSE_URL = "https://raw.githubusercontent.com/disclose/diodb/master/program-list.json"  # 2400+ program independen/VDP/self-hosted
CFG_DIR = os.path.expanduser("~/.config/bbtui"); CFG = os.path.join(CFG_DIR, "config.json")
SEEN = os.path.join(CFG_DIR, "seen.json")  # baseline utk deteksi PROGRAM BARU antar sesi
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CFG = {"platforms": ["hackerone", "bugcrowd", "yeswehack", "intigriti", "federacy"],
               "require_wildcard": True, "min_bounty": 0, "asset_type": "",
               # kriteria lanjutan (0/""/any = abaikan)
               "min_assets": 0, "max_assets": 0, "min_wildcards": 0, "managed_filter": "any",
               "min_sev": "", "min_efficiency": 0, "max_ttfr": 0, "max_ttb": 0, "min_quiet": 0, "sort": "platform",
               "enrich_provider": "jina",
               "firecrawl_api_key": "", "scraperapi_key": "", "serper_api_key": "", "h1_api_user": "", "h1_api_token": "",
               "bugcrowd_api_token": "", "intigriti_api_token": "", "yeswehack_api_token": "",  # disimpan; authed-pull penuh baru H1
               "telegram_token": "", "telegram_chat": "", "discord_webhook": "",
               # Telegram bot FAJAR-AGENT (pakai token+chat di atas)
               "telegram_bot_enabled": False, "telegram_allow_active": False, "telegram_allowlist": "",
               "llm_provider": "anthropic", "llm_model": "", "llm_base_url": "", "llm_api_key": "",
               "mcp_servers": {},   # integrasi MCP: {"nama": {"command","args":[],"env":{},"trusted":false,"enabled":true}}
               "external_tools": {   # integrasi tool lain (jalan bila terpasang) — {target}=domain {url} {handle}. Edit bebas.
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
    c = pr.get("cur", "$"); lo, hi = pr["bounty_min"], pr["bounty_max"]
    if lo is not None and hi is not None: return f"{c}{lo}-{c}{hi}"
    if hi is not None: return f"<={c}{hi}"
    if lo is not None: return f">={c}{lo}"
    return "bounty" if pr["bounty"] else "-"

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
        cur = {"USD": "$", "EUR": "€", "GBP": "£"}.get((p.get("max_bounty") or {}).get("currency") or "USD", "$")
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
    if pf == "disclose":   # diodb — program independen/self-hosted/VDP (scope tak terstruktur → baca policy_url)
        pol = p.get("policy_url")
        if not pol or str(p.get("policy_url_status", "")).lower() == "dead": return None
        return dict(platform="disclose", key=f"dio|{p.get('program_name') or pol}", name=p.get("program_name") or pol,
                    url=pol, bounty=(str(p.get("offers_bounty", "")).lower() == "yes"), bounty_min=None, bounty_max=None,
                    cur="$", maxsev="-", signal=f"safe_harbor={p.get('safe_harbor','?')} swag={p.get('offers_swag')}",
                    managed=None, eff=None, ttfr=None, ttb=None, ttr=None, scope=[], wild=[])
    return None

def quiet_score(pr, is_new=False):
    """Skor 0-100 'anti-ramai' — PROXY dari data yg benar2 ada (BUKAN jumlah hacker asli).
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
    if not pr["bounty"]: return False
    # program private (token) & disclose (VDP/independen, tak punya wildcard) = selalu tampil walau wildcard wajib
    _relax = "PRIVATE" in str(pr.get("signal", "")) or pr.get("platform") == "disclose"
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

def _h1_auth_hdr(cfg):
    u = cfg.get("h1_api_user"); t = cfg.get("h1_api_token")
    if not u or not t: return None
    return {"Authorization": "Basic " + base64.b64encode(f"{u}:{t}".encode()).decode(), "Accept": "application/json"}

def _h1_detail(handle, hdr):
    """Ambil scope terstruktur 1 program H1 lewat API resmi (termasuk PRIVATE yg kamu diundang)."""
    try:
        d = json.loads(_get(f"https://api.hackerone.com/v1/hackers/programs/{handle}", headers=hdr, timeout=30))
        a = d.get("data", {}).get("attributes", {}) or {}
        ss = (((d.get("data", {}).get("relationships", {}) or {}).get("structured_scopes", {}) or {}).get("data", [])) or []
        assets = [s.get("attributes", {}) for s in ss]
        scope = [x.get("asset_identifier") for x in assets if x.get("asset_identifier") and x.get("eligible_for_submission", True)]
        wild = [x.get("asset_identifier") for x in assets if x.get("asset_identifier") and (x.get("asset_type") == "WILDCARD" or is_wild(x.get("asset_identifier")))]
        mx = max((SEV.get((x.get("max_severity") or "").lower(), 0) for x in assets), default=0)
        sev = {v: k for k, v in SEV.items()}.get(mx, "-")
        return dict(platform="hackerone", key=f"h1|{handle}", name="🔒 " + (a.get("name") or handle),
                    url=f"https://hackerone.com/{handle}", bounty=bool(a.get("offers_bounties")), bounty_min=None,
                    bounty_max=None, cur="$", maxsev=sev, managed=None, eff=None, ttfr=None, ttb=None, ttr=None,
                    signal="PRIVATE / accessible (login API)", scope=scope, wild=wild)
    except Exception:
        return None

def fetch_h1_private(cfg, have_keys, cap=60):
    """Tarik program yg BISA KAMU AKSES dari akun H1 (termasuk PRIVATE) via API resmi. Butuh h1_api_user+token."""
    hdr = _h1_auth_hdr(cfg)
    if not hdr: return {}, None
    out = {}; url = "https://api.hackerone.com/v1/hackers/programs?page%5Bsize%5D=100"
    try:
        for _pg in range(8):
            d = json.loads(_get(url, headers=hdr, timeout=45))
            for it in d.get("data", []):
                h = (it.get("attributes", {}) or {}).get("handle")
                if not h: continue
                key = f"h1|{h}"
                if key in have_keys or key in out: continue   # sudah ada dari data publik → yg tersisa = private/baru
                pr = _h1_detail(h, hdr)
                if pr: out[key] = pr
                if len(out) >= cap: return out, None
            nxt = (d.get("links") or {}).get("next")
            if not nxt: break
            url = nxt
        return out, None
    except Exception as e:
        return out, f"h1-api: {e}"

def _bearer(tok):
    return {"Authorization": "Bearer " + tok, "Accept": "application/json"} if tok else None

def _intigriti_detail(handle, hdr):
    try:
        d = json.loads(_get(f"https://api.intigriti.com/external/researcher/v1/programs/{handle}", headers=hdr, timeout=30))
        doms = d.get("domains") or d.get("inScope") or d.get("scope") or []
        ids = []
        for x in doms:
            v = x if isinstance(x, str) else (x.get("endpoint") or x.get("value") or x.get("url") or x.get("identifier") or "")
            if v: ids.append(v)
        return ids, [i for i in ids if is_wild(i)]
    except Exception:
        return [], []

def fetch_intigriti_private(cfg, have_keys, cap=50):
    """Program akun Intigriti (termasuk PRIVATE) + scope via Personal Access Token. EKSPERIMENTAL."""
    tok = cfg.get("intigriti_api_token")
    if not tok: return {}, None
    hdr = _bearer(tok); out = {}
    try:
        d = json.loads(_get("https://api.intigriti.com/external/researcher/v1/programs?limit=500", headers=hdr, timeout=45))
        items = d if isinstance(d, list) else (d.get("records") or d.get("data") or d.get("items") or [])
        for it in items:
            handle = it.get("handle") or it.get("id") or it.get("programId") or it.get("name")
            if not handle: continue
            key = f"it|{handle}"
            if key in have_keys or key in out: continue
            scope, wild = _intigriti_detail(handle, hdr)
            url = it.get("webLink") or it.get("url") or f"https://app.intigriti.com/researcher/programs/{handle}"
            out[key] = dict(platform="intigriti", key=key, name="🔒 " + str(it.get("name") or handle), url=url,
                            bounty=True, bounty_min=None, bounty_max=None, cur="$", maxsev="-", managed=None,
                            eff=None, ttfr=None, ttb=None, ttr=None, signal="PRIVATE/accessible (Intigriti token)",
                            scope=scope, wild=wild)
            if len(out) >= cap: break
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
    for pf in cfg["platforms"]:
        try:
            for p in fetch(pf):
                pr = norm(pf, p)
                if pr and passes(pr, cfg): cur[pr["key"]] = pr
        except Exception as e:
            errs.append(f"{pf}: {e}")
    # + program PRIVATE dari akun (bila token diisi) — cakupan lebih luas lewat API token
    if cfg.get("h1_api_user") and cfg.get("h1_api_token"):
        priv, perr = fetch_h1_private(cfg, set(cur.keys()))
        for k, pr in priv.items():
            if passes(pr, cfg): cur[k] = pr
        if perr: errs.append(perr)
    for fn, tokkey in ((fetch_intigriti_private, "intigriti_api_token"), (fetch_ywh_private, "yeswehack_api_token")):
        if cfg.get(tokkey):
            priv, perr = fn(cfg, set(cur.keys()))
            for k, pr in priv.items():
                if passes(pr, cfg): cur[k] = pr
            if perr: errs.append(perr)
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
        m = re.search(r"[\$€£]\s?\d[\d,\.]*\s*[km]?", text, re.I); paid = m.group(0) if m else "-"
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
#side { width: 32; padding: 1; border: round $primary; margin: 0 1 0 0; }
#stat { height: auto; }
#tablewrap { width: 2fr; border: round $primary; }
#detail { width: 1fr; border: round $accent; padding: 1; margin: 0 0 0 1; }
DataTable { height: 1fr; background: $surface; }
DataTable > .datatable--header { text-style: bold; background: $primary; }
DataTable > .datatable--cursor { background: $accent; color: $text; text-style: bold; }
#search { dock: bottom; display: none; border: tall $accent; }
#search.on { display: block; }
.title { text-style: bold; color: $accent; }
SplashScreen { align: center middle; }
#splash { width: auto; height: auto; text-align: center; padding: 2 6; border: round $accent; background: $panel; }
ModalScreen { align: center middle; }
ModalScreen #stat { width: 84; max-height: 90%; border: round $accent; padding: 1 2; background: $panel; }
ModalScreen #stat Label { width: 100%; }
ModalScreen #stat Static { width: 100%; }
#stat Horizontal { height: auto; align: left middle; margin: 1 0; }
Button { height: 3; width: auto; min-width: 16; margin: 0 2 0 0; }
#chatwrap { width: 100%; height: 100%; border: round $accent; background: $surface; }
#chathdr { height: 1; background: $accent; color: $text; text-style: bold; padding: 0 1; }
#chatlog { height: 1fr; padding: 0 1; background: $surface; }
#chatstatus { height: 1; color: $accent; padding: 0 1; }
#chatbar { dock: bottom; height: 3; }
#chatinput { width: 1fr; border: tall $accent; }
#chatbar Button { height: 3; min-width: 8; margin: 0; }
#slashbox { dock: bottom; height: auto; max-height: 12; margin: 0 0 3 0; border: round $accent; background: $panel; display: none; }
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
                     f"[b]FAJAR-AGENT[/] v{AGENT_VERSION} — [b]Bug-Bounty Hunting Harness[/]\n"
                     "[dim]5 platform · anti-dupe · recon · monitor · dedup · LLM agent[/]\n"
                     "[dim]owner: researcher[/]\n\n"
                     "[yellow]▶ tekan Enter untuk mulai[/]", id="splash")
    def on_key(self, event):
        event.stop(); self.app.pop_screen()

class HelpScreen(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "tutup"), ("question_mark", "app.pop_screen", "tutup")]
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="stat"):
            yield Static(
                "[b cyan]FAJAR-AGENT — Bantuan / Fitur[/]\n\n"
                "[b]Navigasi[/]\n"
                "  ↑/↓ pindah baris   /  cari nama/scope   r  refresh   q  keluar   ?  bantuan\n"
                "  [yellow]b[/] tampilkan HANYA program BARU (🆕)   [yellow]c[/] ganti urutan (platform→quiet→reward→assets)\n\n"
                "[b]Kolom Q = skor QUIET (anti-ramai, 0-100)[/] — PROXY dari data nyata: baru + scope besar +\n"
                "  aset niche (android/ios/api) + unmanaged + program kurang 'dioptimalkan'. Makin tinggi = makin\n"
                "  mungkin sepi/minim-duplikat. [dim]Bukan hitungan hacker asli — itu tak ada di data gratis.[/]\n\n"
                "[b]Aksi pada program tersorot[/] (target auto-terisi, bisa diedit/ketik manual):\n"
                "  [yellow]e[/] Recon      → extract web: subdomain+httpx+katana+JS+endpoint+gf → ~/bb-recon/\n"
                "                (pilih profil: passive / standard / deep)\n"
                "  [yellow]m[/] Monitor    → pantau subdomain BARU (multi-sumber) → ~/bb-monitor/ (cocok di-cron)\n"
                "  [yellow]d[/] Dedup      → kelas bug yang SUDAH dilaporkan di program → known-issues.md\n"
                "  [yellow]w[/] Workspace  → buat folder target ~/bb-workspaces/<nama>/ (scope ter-seed)\n"
                "  [yellow]n[/] Notify     → kirim program ini ke Telegram/Discord\n"
                "  [yellow]x[/] Ext-tools  → jalankan tool lain (hermes/neurosploit/nuclei/sqlmap) via command template\n"
                "  [yellow]p[/] Pipeline   → jalankan rangkaian OTOMATIS sekarang (finder→scope.md→dedup→recon)\n"
                "  [yellow]g[/] Jadwal     → SCHEDULING: pasang/hapus cron pipeline harian (dari TUI)\n"
                "  [yellow]l[/] LLM Agent  → CHAT harness bertahap (ala Hermes/OpenCode/Claude Code): goal → tahap → 'lanjut'.\n"
                "               status bar REAL (aktivitas·token·konteks%·auto-compact) · slash: /help /yolo /model /new\n"
                "               /clear /resume /memory /skills /tools /context /compact /status · ctrl+a yolo · ctrl+o model\n\n"
                "[b]Settings[/] ([yellow]s[/]):\n"
                "  KRITERIA: platform, min bounty, wajib-wildcard\n"
                "  ENRICHMENT: provider (jina gratis / firecrawl / serper / h1api) + API key\n"
                "  NOTIFIKASI: Telegram bot token+chat id, Discord webhook\n\n"
                "[b]External tools[/]: edit [b]~/.config/bbtui/config.json[/] → external_tools {nama: \"cmd {target}\"}.\n"
                "[b]Kolom[/]: Program · Plat · Reward · WC(wildcard) · Aset · Sev.  [dim]esc = tutup[/]"
            )
    def action_dummy(self): pass

class SettingsScreen(ModalScreen):
    BINDINGS = [("escape", "app.pop_screen", "tutup"), ("ctrl+s", "save", "simpan")]
    def __init__(self, cfg): super().__init__(); self.cfg = cfg
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="stat"):
            yield Label("[b cyan]SETTINGS[/]  ([b]Ctrl+S[/] atau tombol Simpan = simpan · Enter di field = simpan · esc = batal TANPA simpan)", classes="title")
            yield Label("\n[b yellow]— KRITERIA PENCARIAN —[/]")
            yield Label("Platform (6 sumber OTONOM, pisah koma): hackerone, bugcrowd, yeswehack, intigriti, federacy, disclose")
            yield Label("[dim]disclose = 2400+ program independen/VDP (matikan 'wajib wildcard' utk lihat). Program PRIVATE H1 otomatis ikut bila h1 token diisi (🔒).[/]")
            yield Input(value=",".join(self.cfg.get("platforms", [])), id="plat")
            yield Label("Min bounty (0 = semua)")
            yield Input(value=str(self.cfg.get("min_bounty", 0)), id="minb")
            yield Label("Wajib wildcard? (y/n)")
            yield Input(value="y" if self.cfg["require_wildcard"] else "n", id="wc")
            yield Label("Jenis/fokus aset (kosong=semua; pisah koma): web, android, ios, api, mobile")
            yield Input(value=self.cfg.get("asset_type", ""), id="atype")
            yield Label("\n[b yellow]— KRITERIA LANJUTAN (0/kosong/any = abaikan) —[/]")
            yield Label("[dim]Semua di bawah berlaku LINTAS-PLATFORM. Yg berbasis data khusus (sev/efficiency/waktu) hanya "
                        "menyaring di platform yg menyediakannya (kini: HackerOne) — platform lain tidak dibuang.[/]")
            yield Label("Min skor QUIET 0-100 — [b]semua platform[/] (anti-ramai: baru+scope besar+niche+unmanaged)")
            yield Input(value=str(self.cfg.get("min_quiet", 0)), id="mq")
            yield Label("Urutkan: platform | quiet | reward | assets  (atau tekan c di layar utama)")
            yield Input(value=self.cfg.get("sort", "platform"), id="sort")
            yield Label("Min jumlah aset in-scope / Max aset (0=abaikan)")
            yield Input(value=str(self.cfg.get("min_assets", 0)), id="mina")
            yield Input(value=str(self.cfg.get("max_assets", 0)), id="maxa")
            yield Label("Min jumlah wildcard (0=abaikan)")
            yield Input(value=str(self.cfg.get("min_wildcards", 0)), id="minw")
            yield Label("Program managed: any | only | exclude  (H1/Bugcrowd)")
            yield Input(value=self.cfg.get("managed_filter", "any"), id="mgd")
            yield Label("Min severity ceiling (H1 saja): kosong | low | medium | high | critical")
            yield Input(value=self.cfg.get("min_sev", ""), id="msev")
            yield Label("[dim]— khusus HackerOne (dari data program): —[/]")
            yield Label("Min response efficiency % (0=abaikan)")
            yield Input(value=str(self.cfg.get("min_efficiency", 0)), id="meff")
            yield Label("Max jam rata2 respon pertama / Max jam rata2 bayar (0=abaikan)")
            yield Input(value=str(self.cfg.get("max_ttfr", 0)), id="mttfr")
            yield Input(value=str(self.cfg.get("max_ttb", 0)), id="mttb")
            yield Label("[dim]CATATAN JUJUR: jumlah hacker terdaftar & total bounty dibayar TIDAK ada di data gratis "
                        "(hanya di halaman program). Q = proxy anti-ramai, bukan hitungan hacker asli.[/]")
            yield Label("\n[b yellow]— ENRICHMENT (opsional) —[/]")
            yield Label(f"Provider: {', '.join(PROVIDERS)}  (jina = gratis tanpa key)")
            yield Input(value=self.cfg.get("enrich_provider", "jina"), id="prov")
            yield Label("firecrawl_api_key"); yield Input(value=self.cfg.get("firecrawl_api_key", ""), id="fc", password=True)
            yield Label("serper_api_key"); yield Input(value=self.cfg.get("serper_api_key", ""), id="sp", password=True)
            yield Label("h1_api_user + token → tarik program yg BISA KAMU AKSES termasuk PRIVATE/invite (via API resmi H1). Buat token: hackerone.com/settings/api_token")
            yield Label("h1_api_user"); yield Input(value=self.cfg.get("h1_api_user", ""), id="h1u")
            yield Label("h1_api_token"); yield Input(value=self.cfg.get("h1_api_token", ""), id="h1t", password=True)
            yield Label("[dim]Token platform lain (disimpan; auto-pull program-private penuh baru H1. BC/Intigriti/YWH pakai OAuth → dipakai enrichment/manual):[/]")
            yield Label("bugcrowd_api_token"); yield Input(value=self.cfg.get("bugcrowd_api_token", ""), id="bct", password=True)
            yield Label("intigriti_api_token"); yield Input(value=self.cfg.get("intigriti_api_token", ""), id="itt", password=True)
            yield Label("yeswehack_api_token"); yield Input(value=self.cfg.get("yeswehack_api_token", ""), id="ywt", password=True)
            yield Label("\n[b yellow]— NOTIFIKASI —[/]")
            yield Label("Telegram bot token"); yield Input(value=self.cfg.get("telegram_token", ""), id="ntg", password=True)
            yield Label("Telegram chat id"); yield Input(value=self.cfg.get("telegram_chat", ""), id="ntc")
            yield Label("Discord webhook URL"); yield Input(value=self.cfg.get("discord_webhook", ""), id="ndc", password=True)
            yield Label("\n[b yellow]— TELEGRAM BOT (FAJAR-AGENT) —[/]")
            yield Label("[dim]Pakai token+chat di atas. Jalankan bot: [b]bb.py telegram[/]. Chat id? kirim /start ke bot.[/]")
            yield Label("Aktifkan bot? (y/n) — master switch, bot menolak start bila 'n'")
            yield Input(value="y" if self.cfg.get("telegram_bot_enabled") else "n", id="tgen")
            yield Label("Default aksi-aktif/traffic saat bot mulai? (y/n) — aman: n (harus /yolo di chat)")
            yield Input(value="y" if self.cfg.get("telegram_allow_active") else "n", id="tgact")
            yield Label("Allowlist chat id tambahan (pisah koma; kosong = hanya owner di 'Telegram chat id')")
            yield Input(value=self.cfg.get("telegram_allowlist", ""), id="tgallow")
            yield Label("\n[b yellow]— LLM AGENT (otak otonom, opsional) —[/]")
            yield Label("provider: anthropic | openai (openai = kompatibel Groq/OpenRouter/Ollama)")
            yield Input(value=self.cfg.get("llm_provider", "anthropic"), id="lprov")
            yield Label("model (mis. claude-sonnet-5 / gpt-4o-mini / llama3.1)")
            yield Input(value=self.cfg.get("llm_model", ""), id="lmodel")
            yield Label("base_url (openai-compatible saja, mis. http://localhost:11434/v1)")
            yield Input(value=self.cfg.get("llm_base_url", ""), id="lbase")
            yield Label("llm_api_key"); yield Input(value=self.cfg.get("llm_api_key", ""), id="lkey", password=True)
            mcps = self.cfg.get("mcp_servers") or {}
            yield Label(f"[dim]MCP: {len(mcps)} server terdaftar. Edit di ~/.config/bbtui/config.json → \"mcp_servers\": "
                        "{{\"nama\": {{\"command\":\"npx\",\"args\":[...],\"trusted\":false}}}}. Di chat: /mcp connect.[/]")
            yield Label("[dim]Tool eksternal (hermes/neurosploit/nuclei): tekan x di layar utama untuk kelola.[/]")
            yield Label("\n[b green]▶ SIMPAN: tekan Ctrl+S  (atau Enter di kotak isian mana pun)[/]  ·  [dim]esc = batal tanpa simpan[/]")
    def on_input_submitted(self, _): self.action_save()
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
            self.cfg["require_wildcard"] = g("wc").lower() != "n"
            self.cfg["asset_type"] = g("atype")
            digit = lambda i: int(re.sub(r"[^\d]", "", g(i)) or 0)
            self.cfg["min_quiet"] = digit("mq"); self.cfg["min_assets"] = digit("mina"); self.cfg["max_assets"] = digit("maxa")
            self.cfg["min_wildcards"] = digit("minw"); self.cfg["min_efficiency"] = digit("meff")
            self.cfg["max_ttfr"] = digit("mttfr"); self.cfg["max_ttb"] = digit("mttb")
            self.cfg["sort"] = (g("sort") or "platform").lower()
            self.cfg["managed_filter"] = (g("mgd") or "any").lower()
            self.cfg["min_sev"] = g("msev").lower()
            self.cfg["enrich_provider"] = g("prov") or "jina"
            self.cfg["firecrawl_api_key"] = g("fc"); self.cfg["serper_api_key"] = g("sp")
            self.cfg["h1_api_user"] = g("h1u"); self.cfg["h1_api_token"] = g("h1t")
            self.cfg["bugcrowd_api_token"] = g("bct"); self.cfg["intigriti_api_token"] = g("itt"); self.cfg["yeswehack_api_token"] = g("ywt")
            self.cfg["telegram_token"] = g("ntg"); self.cfg["telegram_chat"] = g("ntc"); self.cfg["discord_webhook"] = g("ndc")
            self.cfg["telegram_bot_enabled"] = g("tgen").lower() == "y"
            self.cfg["telegram_allow_active"] = g("tgact").lower() == "y"
            self.cfg["telegram_allowlist"] = g("tgallow")
            self.cfg["llm_provider"] = g("lprov") or "anthropic"; self.cfg["llm_model"] = g("lmodel")
            self.cfg["llm_base_url"] = g("lbase"); self.cfg["llm_api_key"] = g("lkey")
            save_cfg(self.cfg)
            self.app.pop_screen()
            if ignored:
                self.app.notify(f"⚠ platform diabaikan (hanya {', '.join(PLAT_ALL)}): {', '.join(ignored)}", severity="warning")
            self.app.notify(f"✅ tersimpan → {CFG} (tekan r untuk refresh)")
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
    """Jalankan recon/monitor/dedup — target dari pilihan ATAU ketik manual."""
    BINDINGS = [("escape", "app.pop_screen", "batal")]
    def __init__(self, kind, default=""): super().__init__(); self.kind = kind; self.default = default
    def compose(self) -> ComposeResult:
        with Vertical(id="stat"):
            yield Label(f"[b cyan]{self.kind.upper()}[/]  — target dari pilihan atau ketik manual, lalu [b]Enter[/]", classes="title")
            hint = {"recon": "domain, mis. wolt.com", "monitor": "domain, mis. wolt.com", "dedup": "handle/URL, mis. whatnot"}[self.kind]
            yield Input(value=self.default, id="tgt", placeholder=hint)
            if self.kind == "recon":
                yield Label("Profil: [b]passive[/] (tak kirim) · [b]standard[/] (extract web: httpx+katana+JS+endpoint) · [b]deep[/] (scan)")
                yield Input(value="standard", id="prof")
                yield Static("[yellow]standard/deep mengirim request ke target — pastikan in-scope.[/]")
            yield Static("[dim]Enter = jalankan · esc = batal[/]")
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
    """Integrasi tool bug hunting lain — LIST + TAMBAH + HAPUS + JALANKAN, semua dari TUI."""
    BINDINGS = [("escape", "app.pop_screen", "batal")]
    def __init__(self, cfg, default=""): super().__init__(); self.cfg = cfg; self.default = default
    def compose(self) -> ComposeResult:
        ext = self.cfg.get("external_tools", {})
        with VerticalScroll(id="stat"):
            yield Label("[b cyan]EXTERNAL TOOLS[/] — kelola & jalankan tool bug hunting lain", classes="title")
            yield Label("Target (dari pilihan / ketik manual):")
            yield Input(value=self.default, id="xtgt")
            if ext:
                yield Static("\n[b]Terdaftar:[/]")
                for i, (name, cmd) in enumerate(ext.items(), 1):
                    yield Static(f"  [yellow]{i}[/] [b]{name}[/]  [dim]{cmd}[/]")
            else:
                yield Static("\n[yellow]Belum ada tool. Tambahkan di bawah.[/]")
            yield Label("\n[b green]JALANKAN[/] — nomor tool → Enter:")
            yield Input(placeholder="mis. 1", id="xnum")
            yield Label("[b green]TAMBAH[/] — format  [b]nama = perintah[/]  (pakai {target}/{url}/{handle}) → Enter:")
            yield Input(placeholder="mis. sqlmap = sqlmap -u {url} --batch", id="xadd")
            yield Label("[b red]HAPUS[/] — nomor tool → Enter:")
            yield Input(placeholder="mis. 2", id="xdel")
            yield Static("\n[dim]Placeholder: {target}=domain · {url} · {handle}=nama program. Tersimpan ke ~/.config/bbtui/config.json. esc=tutup[/]")
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
            gone = items[idx][0]; del ext[gone]; save_cfg(self.cfg); self.app.notify(f"🗑 '{gone}' dihapus"); self._refresh(); return
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
        self.app.pop_screen(); self.app.push_screen(RunScreen(shlex.split(cmd), f"{name} · {tgt}"))

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
    """Ambil daftar model dari API provider (pakai kunci) lalu pilih — bebas ganti model kapan saja."""
    BINDINGS = [("escape", "app.pop_screen", "tutup")]
    def __init__(self, cfg, on_pick): super().__init__(); self.cfg = cfg; self.on_pick = on_pick; self.models = []
    def compose(self) -> ComposeResult:
        with VerticalScroll(id="stat"):
            yield Label("[b cyan]PILIH MODEL[/] — diambil live dari provider via API key", classes="title")
            yield Static("mengambil daftar model…", id="mlist")
            yield Label("Ketik nomor / nama model → Enter:")
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
# logo "FAJAR" gradasi sunrise (kuning → oranye), diakhiri wordmark AGENT
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
    ("/help", "tampilkan daftar perintah"), ("/yolo", "toggle auto-approve aksi aktif (kirim traffic)"),
    ("/model [nama]", "ganti model (kosong = pilih dari daftar provider)"), ("/provider <anthropic|openai>", "ganti provider"),
    ("/new", "sesi baru (reset percakapan; memori tetap)"), ("/clear", "bersihkan layar chat"),
    ("/resume", "lanjutkan sesi tersimpan terakhir"), ("/save", "simpan sesi sekarang"),
    ("/memory [cari]", "lihat/cari memori jangka panjang"), ("/skills", "daftar skill/playbook"),
    ("/skill install <nama> <url|path>", "pasang skill baru (playbook)"),
    ("/tools", "daftar tool yg dimiliki agent"), ("/stage", "ingatkan agent lanjut/lapor tahap"),
    ("/add <path>", "upload/ingest file atau folder projek ke konteks (drag path juga bisa)"),
    ("/mcp [connect]", "status / connect server MCP (integrasi eksternal)"),
    ("/context", "info pemakaian konteks (token/window)"), ("/compact", "ringkas konteks sekarang (hemat token)"),
    ("/status", "info kondisi agent"), ("/stop", "HENTIKAN proses agent yg sedang jalan (=⏹/esc)"),
    ("/quit", "KELUAR sesi chat (esc sengaja TIDAK menutup)"),
]

def classify_assets(scope):
    """Kelompokkan aset in-scope per jenis → menentukan skill & pendekatan."""
    web, api, android, ios, other = [], [], [], [], []
    for s in scope:
        sl = str(s).lower()
        if "play.google" in sl or sl.startswith("com.") or ".apk" in sl or "/android" in sl: android.append(s)
        elif "apps.apple" in sl or "testflight" in sl or "itunes.apple" in sl or (sl.isdigit() and len(sl) >= 6): ios.append(s)
        elif sl.startswith("api.") or "/api" in sl or ".api." in sl or "graphql" in sl: api.append(s)
        elif "." in sl and " " not in sl: web.append(s)
        else: other.append(s)
    return {"web": web, "api": api, "android": android, "ios": ios, "other": other}

def program_context(pr):
    """SKEMA EKSTRAKSI: ubah 1 program → brief terstruktur utk LLM (sumber scope resmi + rute skill)."""
    g = classify_assets(pr.get("scope", []))
    present = [k for k in ("web", "api", "android", "ios", "other") if g[k]]
    skill_map = {"web": "web-vuln-classes", "api": "api-pentest", "android": "mobile-pentest", "ios": "mobile-pentest"}
    skills = sorted({skill_map[k] for k in present if k in skill_map}) or ["web-vuln-classes"]
    L = ["[TARGET CONTEXT] — sumber scope RESMI dari TUI (jangan cari/riset ulang; jangan program_detail).",
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
        if len(g[k]) > 50: L.append(f"  … +{len(g[k])-50} lagi")
    return "\n".join(L)

def _md_line(raw):
    """Konversi 1 baris markdown → Rich markup rapi (buang '#', **tebal**, `kode`); escape '[..]' agar [FAKTA] tak hilang."""
    from rich.markup import escape
    import re as _re
    raw = raw.rstrip("\n")
    st = raw.lstrip()
    hashes = len(st) - len(st.lstrip("#"))
    def inline(s):
        s = _re.sub(r"\*\*(.+?)\*\*", r"[b]\1[/]", s)
        s = _re.sub(r"(?<!\*)\*(?!\s)([^*]+?)\*(?!\*)", r"[i]\1[/]", s)
        s = _re.sub(r"`([^`]+)`", r"[cyan]\1[/]", s)
        return s
    if hashes and st[hashes:hashes + 1] == " ":            # heading → tebal polos (tenang), tanpa '#'
        return "[b]" + inline(escape(st[hashes:].strip())) + "[/]"
    # bullet rapi
    body = escape(raw)
    body = _re.sub(r"^(\s*)[-*]\s+", r"\1• ", body)
    return inline(body)

class LlmChatScreen(ModalScreen):
    """Chat LLM ala Hermes/OpenCode/Claude Code — status bar, slash-commands, alur BERTAHAP rapi."""
    BINDINGS = [("escape", "soft_escape", "stop"), ("ctrl+q", "quit_chat", "keluar"), ("ctrl+a", "toggle_active", "yolo"),
                ("ctrl+o", "pick_model", "model"), ("ctrl+r", "resume", "resume"), ("ctrl+l", "clear", "clear")]
    def __init__(self, cfg, target=None):
        super().__init__(); self.cfg = cfg; self.target = target; self.messages = None
        self.allow_gated = False; self.busy = False; self.activity = "idle"
        self.tok_in = 0; self.tok_out = 0; self.turns = 0
        self.ctx = 0; self.window = 0; self.compacts = 0; self._worker = None; self.t0 = None; self._suggest = ""
        self.sess_start = datetime.datetime.now()
        self.sid = datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + base64.b16encode(os.urandom(3)).decode().lower()
        # sesi di-key PER TARGET → tiap program punya riwayat sendiri (tak saling timpa)
        base = (target.get("key") or target.get("name")) if target else "general"
        self.sess_key = "tui-" + re.sub(r"\W", "_", str(base))[:50]
    def compose(self) -> ComposeResult:
        _p, _m, _b, key = _llm_creds(self.cfg)
        with Vertical(id="chatwrap"):
            yield Static(self._headerline(), id="chathdr")
            yield RichLog(highlight=True, markup=True, wrap=True, id="chatlog")
            yield Static(self._statusline(), id="chatstatus")
            yield OptionList(id="slashbox")
            with Horizontal(id="chatbar"):
                yield Button("⏹", id="btnstop", variant="error")
                yield Input(placeholder=("ketik goal atau /  (daftar perintah)  ·  'lanjut' tiap checkpoint" if key else "set API key dulu (Settings s)"), id="chatinput")
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
        return (f"{dot} [b]{act}[/]  │  {self._ctxbar()}  │  {tok} tok{clock}  │  giliran {self.turns}{cmp}  │  "
                f"aktif {'[green]ON[/]' if self.allow_gated else '[red]OFF[/]'}  │  [dim]/ menu · esc stop · ^Q keluar[/]")
    def _refresh_bars(self):
        self.query_one("#chathdr", Static).update(self._headerline())
        self.query_one("#chatstatus", Static).update(self._statusline())
    def on_mount(self):
        log = self.query_one("#chatlog", RichLog)
        prov, model, _b, key = _llm_creds(self.cfg)
        la = _llm_mod()
        self.window = la.model_window(model)          # ctx bar langsung tampil (0/window) sejak awal
        self.set_interval(1.0, self._refresh_bars)    # jam sesi & elapsed hidup tiap detik
        # --- banner + identitas harness ---
        log.write(AGENT_BANNER)
        log.write(f"[b]{AGENT_NAME}[/] v{AGENT_VERSION}  ·  {AGENT_TAGLINE}")
        log.write(f"[dim]model:[/] [b]{model}[/] · [dim]provider:[/] {prov}   [dim]session:[/] {self.sid}")
        log.write("[dim]" + "─" * 70 + "[/]")
        # --- tools (real, dari registry) ---
        names = [t["name"] for t in la.TOOLS]
        log.write("[b yellow]Tools[/]")
        for grp, keys in TOOL_GROUPS:
            have = [k for k in keys if k in names]
            if have: log.write(f"  [dim]{grp}:[/] " + ", ".join(have))
        # --- skills (real, dari SKILLS) + ext-tools ---
        log.write("[b yellow]Skills[/] [dim](playbook framework — load_skill)[/]")
        log.write("  " + ", ".join(la.SKILLS.keys()))
        nx = len(self.cfg.get("external_tools", {}))
        log.write(f"[b yellow]Ext-tools[/] [dim](nuclei/burp/sqlmap/dll — run_ext_tool)[/]  {nx} terdaftar")
        # --- ringkasan hitungan real ---
        log.write("[dim]" + "─" * 70 + "[/]")
        log.write(f"[b]{len(names)} tools[/] · [b]{len(la.SKILLS)} skills[/] · [b]{nx} ext-tools[/] · ketik [yellow]/help[/] utk perintah")
        # --- status memori & sesi ---
        try:
            mi = la.mem_list()
            if mi and "kosong" not in mi: log.write(f"[dim]🧠 memori jangka panjang: {mi.count(chr(10))} entri (recall lintas sesi).[/]")
        except Exception: pass
        # --- alur & welcome ---
        log.write("\n[cyan]Alur bertahap:[/] pilih target → recon → analisa/hipotesis → rencana → verifikasi → draf laporan → [b]submit=kamu[/]")
        log.write("[cyan]✦ Tip:[/] tiap tahap berhenti di CHECKPOINT — ketik [b]'lanjut'[/]. Aksi aktif (traffic) perlu [b]/yolo[/] ON.")
        if not key: log.write("\n[red]⚠ belum ada API key.[/] Settings (s) → blok LLM AGENT, atau `bb.py llm --setup`.")
        # --- TARGET terpilih: suntik konteks scope resmi (skema ekstraksi) ---
        inp = self.query_one("#chatinput", Input)
        if self.target and key:
            ctx = program_context(self.target)
            self.messages = la.new_messages(prov == "anthropic")
            self.messages.append({"role": "user", "content": ctx})   # sumber scope resmi utk model
            g = classify_assets(self.target.get("scope", []))
            present = [k for k in ("web", "api", "android", "ios", "other") if g[k]]
            log.write(f"\n[b green]🎯 TARGET:[/] [b]{self.target.get('name')}[/] [{self.target.get('platform')}]  "
                      f"· aset: {', '.join(present) or '-'}  · wildcard: {len(self.target.get('wild',[]))}  · sev: {self.target.get('maxsev','-')}")
            log.write("[dim]💬 sesi chat BARU & bersih untuk target ini. Scope resmi sudah dimuat ke konteks.[/]")
            prev = la.session_load(self.sess_key)
            if prev: log.write(f"[green]💾 ada sesi tersimpan untuk target ini ({len(prev)} pesan) — ketik [b]/resume[/] untuk lanjutkan.[/]")
            log.write("\n[b yellow]⏸ AGENT BELUM JALAN — menunggu perintahmu.[/]")
            log.write("[dim]Tekan Enter/Kirim untuk pakai goal saran ini, atau ketik goal-mu sendiri:[/]")
            log.write(f"[dim]  saran: “mulai hunting {self.target.get('name')}: SCOPE-GATE lalu HUNTING BRIEF”[/]")
            self._suggest = f"mulai hunting {self.target.get('name')}: SCOPE-GATE pakai TARGET CONTEXT lalu susun HUNTING BRIEF sesuai jenis aset."
        log.write("\n[dim]➤ Kirim/Enter=mulai · ⏹ atau esc=stop proses · [b]Ctrl+Q atau /quit=keluar sesi[/] · q di layar utama=tutup aplikasi[/]")
        if self.cfg.get("mcp_servers"):
            log.write("[dim]🔌 menghubungkan server MCP…[/]"); self._mcp_connect()
        inp.focus()
    # ---- actions ----
    def on_button_pressed(self, ev):
        if ev.button.id == "btnsend":
            inp = self.query_one("#chatinput", Input); v = inp.value.strip(); inp.value = ""
            if not v and self._suggest: v = self._suggest
            if v: self._submit(v)
        elif ev.button.id == "btnstop":
            self.action_stop()
    def action_stop(self):
        log = self.query_one("#chatlog", RichLog)
        if not self.busy:
            log.write("[dim]tak ada proses berjalan.[/]"); return
        try:
            if self._worker is not None: self._worker.cancel()
        except Exception: pass
        self.busy = False; self.activity = "idle"; self._refresh_bars()
        log.write("[yellow]⏹ dihentikan. (request yg sudah terlanjur terkirim bisa selesai di belakang, hasilnya diabaikan)[/]")
    def action_soft_escape(self):
        # esc TIDAK langsung keluar: kalau sibuk -> stop; kalau tidak -> ingatkan cara keluar
        if self.busy: self.action_stop()
        else: self.query_one("#chatlog", RichLog).write("[dim]keluar sesi chat: [b]Ctrl+Q[/] atau ketik [b]/quit[/]. (esc sengaja tidak menutup agar tak salah pencet)[/]")
    def action_quit_chat(self):
        if self.busy: self.action_stop()
        self.app.pop_screen()
    # ---- actions ----
    def action_toggle_active(self):
        self.allow_gated = not self.allow_gated; self._refresh_bars()
        self.query_one("#chatlog", RichLog).write(f"[b]{'🟢 YOLO ON — aksi kirim-traffic diizinkan' if self.allow_gated else '🔴 YOLO OFF — aksi aktif ditolak'}[/]")
    def action_pick_model(self):
        self.app.push_screen(ModelPickerScreen(self.cfg, lambda mdl: self._refresh_bars()))
    def action_clear(self):
        self.query_one("#chatlog", RichLog).clear(); self.query_one("#chatlog", RichLog).write("[dim]layar dibersihkan (percakapan & memori tetap).[/]")
    def action_resume(self):
        msgs = _llm_mod().session_load(self.sess_key); log = self.query_one("#chatlog", RichLog)
        if not msgs: log.write("[yellow]tak ada sesi tersimpan.[/]"); return
        self.messages = msgs
        log.write("\n[dim]" + "─" * 60 + "[/]")
        log.write(f"[b green]💾 SESI DILANJUTKAN[/] ({len(msgs)} pesan) — riwayat di bawah, tinggal terus ketik:")
        self._render_history(msgs)
        log.write("[dim]" + "─" * 60 + "[/]")
    def _render_history(self, msgs):
        from rich.markup import escape
        log = self.query_one("#chatlog", RichLog)
        for msg in msgs:
            role = msg.get("role"); c = msg.get("content")
            if role == "user" and isinstance(c, str):
                if c.startswith("[TARGET CONTEXT]") or c.startswith("[ARTEFAK"):
                    log.write("[dim]  · (konteks target dimuat)[/]"); continue
                log.write(f"\n[b green]▶ kamu[/]\n  {escape(c[:1500])}")
            elif role == "assistant":
                text = ""
                if isinstance(c, list): text = "".join(b.get("text", "") for b in c if isinstance(b, dict) and b.get("type") == "text")
                elif isinstance(c, dict): text = c.get("content") or ""
                elif isinstance(c, str): text = c
                if text.strip(): self._write_agent(text)
            # pesan tool/tool_result (internal) dilewati agar transkrip bersih
    # ---- slash commands ----
    def _slash(self, raw):
        log = self.query_one("#chatlog", RichLog)
        parts = raw[1:].split(None, 1); cmd = parts[0].lower(); arg = parts[1].strip() if len(parts) > 1 else ""
        if cmd in ("help", "?", "h"):
            log.write("[b cyan]Perintah slash:[/]"); [log.write(f"  [yellow]{c}[/] — {d}") for c, d in SLASH_HELP]
        elif cmd in ("yolo", "active", "a"): self.action_toggle_active()
        elif cmd == "model":
            if arg: self.cfg["llm_model"] = arg; save_cfg(self.cfg); self._refresh_bars(); log.write(f"[green]model → {arg}[/]")
            else: self.action_pick_model()
        elif cmd == "provider":
            if arg in ("anthropic", "openai"):
                self.cfg["llm_provider"] = arg; save_cfg(self.cfg); self._refresh_bars(); log.write(f"[green]provider → {arg}[/]")
            else:
                log.write(f"[yellow]provider sekarang: {self.cfg.get('llm_provider','anthropic')}. Pakai: /provider anthropic | openai[/]")
        elif cmd in ("new", "reset"):
            self.messages = None; self.tok_in = self.tok_out = self.turns = 0; self.ctx = 0; self.t0 = None; self._refresh_bars()
            if self.target:   # sesi baru tetap bawa scope target
                self.messages = _llm_mod().new_messages(_llm_creds(self.cfg)[0] == "anthropic")
                self.messages.append({"role": "user", "content": program_context(self.target)})
                log.write(f"[b]— sesi baru untuk {self.target.get('name')} —[/] [dim](scope target dimuat ulang; memori tetap)[/]")
            else:
                log.write("[b]— sesi baru —[/] [dim](memori jangka panjang tetap)[/]")
        elif cmd == "clear": self.action_clear()
        elif cmd == "resume": self.action_resume()
        elif cmd == "save":
            if self.messages: _llm_mod().session_save(self.sess_key, self.messages); log.write("[green]sesi disimpan.[/]")
            else: log.write("[yellow]belum ada percakapan.[/]")
        elif cmd == "memory":
            out = _llm_mod().mem_search(arg) if arg else _llm_mod().mem_list()
            log.write("[b cyan]🧠 memori:[/]\n" + out[:1500])
        elif cmd in ("add", "read", "ingest", "upload"):
            if not arg: log.write("[yellow]pakai: /add <path-file-atau-folder>[/]"); return
            self._ingest_path(arg)
        elif cmd == "mcp":
            if arg.lower().startswith("connect"):
                log.write("[cyan]⟳ connect server MCP…[/]"); self._mcp_connect()
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
                      f"giliran={self.turns} token_in/out={self.tok_in}/{self.tok_out} ctx={self.ctx}/{self.window} compact×{self.compacts} sibuk={self.busy}")
        elif cmd == "context":
            win = self.window or _llm_mod().model_window(_llm_creds(self.cfg)[1])
            est = _llm_mod().estimate_ctx(self.messages) if self.messages else 0
            log.write(f"[b]konteks:[/] terpakai≈{self.ctx or est} tok / window {win} tok ({int((self.ctx or est)*100/win)}%). Auto-compact di ~75%.")
        elif cmd == "compact":
            if not self.messages or len(self.messages) < 3: log.write("[yellow]konteks masih pendek.[/]"); return
            p, mdl, base, k = _llm_creds(self.cfg)
            log.write("[magenta]⟳ meringkas konteks…[/]"); self._do_compact(p, mdl, base, k)
        elif cmd == "stage": self._submit("lanjut ke tahap berikutnya sesuai urutan; kalau tahap sekarang belum kelar, selesaikan lalu checkpoint.")
        elif cmd == "stop": self.action_stop()
        elif cmd in ("quit", "exit", "q", "keluar"):
            if self.busy: self.action_stop()
            log.write("[dim]keluar sesi chat…[/]"); self.app.pop_screen()
        else: log.write(f"[yellow]perintah '/{cmd}' tak dikenal. /help utk daftar.[/]")
    @work(thread=True)
    def _mcp_connect(self):
        log = self.query_one("#chatlog", RichLog)
        try:
            rep = _llm_mod().mcp_connect_all(self.cfg)
            for line in rep: self.app.call_from_thread(log.write, "  [dim]MCP • " + line + "[/]")
            if not rep: self.app.call_from_thread(log.write, "[dim]tak ada server MCP di config.[/]")
        except Exception as e:
            self.app.call_from_thread(log.write, f"[red]MCP gagal: {e}[/]")
    def _ingest_path(self, raw):
        la = _llm_mod(); log = self.query_one("#chatlog", RichLog)
        p = os.path.expanduser(raw.strip().strip('"').strip("'"))
        if os.path.isdir(p): content = la.t_ingest_folder(p); label = f"FOLDER {p}"
        elif os.path.isfile(p): content = la.t_read_file(p); label = f"FILE {p}"
        else: log.write(f"[yellow]path tak ditemukan: {raw}[/]"); return
        prov = _llm_creds(self.cfg)[0]
        if self.messages is None: self.messages = la.new_messages(prov == "anthropic")
        self.messages.append({"role": "user", "content": f"[ARTEFAK DI-UPLOAD: {label}]\n{content}"})
        try: la.session_save(self.sess_key, self.messages)
        except Exception: pass
        log.write(f"[green]📎 ditambahkan ke konteks:[/] {label} [dim]({len(content)} char)[/]. "
                  "Beri instruksi (mis. 'cari endpoint & secret di artefak ini').")
    # ---- palette slash (autocomplete) ----
    def _slash_box(self):
        try: return self.query_one("#slashbox", OptionList)
        except Exception: return None
    def on_input_changed(self, ev):
        if ev.input.id != "chatinput": return
        box = self._slash_box()
        if box is None: return
        v = ev.value
        if v.startswith("/"):
            q = v[1:].split()[0].lower() if len(v) > 1 else ""
            box.clear_options()
            name_hits, desc_hits = [], []
            for c, d in SLASH_HELP:
                cmd = c.split()[0]                      # token perintah, mis. /model
                if q in cmd[1:].lower(): name_hits.append((c, d, cmd))   # match NAMA command dulu
                elif q in d.lower(): desc_hits.append((c, d, cmd))       # baru deskripsi
            for c, d, cmd in name_hits + desc_hits:
                box.add_option(Option(f"{c}  —  {d}", id=cmd))
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
        inp = self.query_one("#chatinput", Input)
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
    def on_input_submitted(self, ev):
        box = self._slash_box()
        if box and box.has_class("on"):   # palette aktif
            val = ev.value.strip(); tok = val.split()[0].lower() if val else ""
            known = {c.split()[0] for c, _d in SLASH_HELP}
            if tok in known:                       # yg diketik PERSIS sebuah command → jalankan itu (+ argnya)
                ev.input.value = ""; box.remove_class("on"); self._slash(val); return
            self._fill_slash(run=True); return     # cuma prefix → jalankan yg ter-highlight (arrow utk pilih)
        text = ev.value.strip(); ev.input.value = ""
        if not text and self._suggest: text = self._suggest
        if text: self._submit(text)
    def _submit(self, text):
        log = self.query_one("#chatlog", RichLog)
        if text.startswith("/"): self._slash(text); return          # slash SELALU jalan (walau sibuk)
        if self.busy:
            log.write("[yellow]⏳ agent masih memproses — tunggu CHECKPOINT, atau tekan ⏹/esc untuk stop.[/]"); return
        cand = text.strip().strip('"').strip("'")                   # drag-drop path → ingest
        if (os.sep in cand or cand.startswith("~")) and os.path.exists(os.path.expanduser(cand)):
            log.write(f"\n[b green]📎 upload[/] {cand}"); self._ingest_path(cand); return
        log.write(f"\n[b green]▶ kamu[/]\n  {text}")
        self._send(text)
    # ---- render jawaban agent: prosa rapi + tabel markdown jadi Rich Table ----
    @staticmethod
    def _is_row(l): return l.strip().count("|") >= 2
    @staticmethod
    def _is_sep(l):
        s = l.strip().strip("|")
        return bool(s) and all(set(c.strip()) <= set("-:") and c.strip() for c in s.split("|"))
    def _build_table(self, rows):
        from rich.table import Table
        from rich.markup import escape
        cells = lambda r: [c.strip() for c in r.strip().strip("|").split("|")]
        hdr = cells(rows[0])
        t = Table(show_header=True, header_style="bold", border_style="grey50", pad_edge=False, expand=False)
        for h in hdr: t.add_column(escape(h) or " ")
        for r in rows[1:]:
            cs = (cells(r) + [""] * len(hdr))[:len(hdr)]
            t.add_row(*[escape(c) for c in cs])
        return t
    def _write_agent(self, body):
        # jawaban agent DALAM KOTAK (panel); proses tool tetap di luar (dim). Warna tenang.
        from rich.panel import Panel
        from rich.console import Group
        from rich.text import Text
        log = self.query_one("#chatlog", RichLog)
        parts = []; lines = body.splitlines(); n = len(lines); i = 0; para = []
        def flush():
            if not para: return
            t = Text()
            for k, ln in enumerate(para):
                if k: t.append("\n")
                if "CHECKPOINT" in ln:
                    t.append("➤ " + ln.strip().lstrip("#").strip(), style="bold cyan")
                else:
                    try: t.append_text(Text.from_markup(_md_line(ln)))
                    except Exception: t.append(ln)
            parts.append(t); para.clear()
        while i < n:
            if self._is_row(lines[i]) and i + 1 < n and self._is_sep(lines[i + 1]):
                flush(); j = i + 2
                while j < n and self._is_row(lines[j]) and not self._is_sep(lines[j]): j += 1
                parts.append(self._build_table([lines[i]] + lines[i + 2:j])); i = j
            else:
                para.append(lines[i]); i += 1
        flush()
        inner = Group(*parts) if parts else Text("")
        log.write("")
        log.write(Panel(inner, title="🤖 agent", title_align="left", border_style="cyan", padding=(0, 1)))
    def _send(self, text):
        prov, model, base, key = _llm_creds(self.cfg)
        if not key: self.app.notify("set API key dulu (Settings s)"); return
        self._suggest = ""   # saran goal terpakai sekali
        self.busy = True; self.activity = "berpikir"; self.turns += 1; self.t0 = datetime.datetime.now(); self._refresh_bars()
        self._worker = self._run_stage(text, prov, model, base, key)
    @work(thread=True)
    def _do_compact(self, prov, model, base, key):
        la = _llm_mod(); log = self.query_one("#chatlog", RichLog)
        before = la.estimate_ctx(self.messages)
        self.messages[:] = la.compact(self.messages, prov, model, key, base)
        self.ctx = la.estimate_ctx(self.messages); self.compacts += 1
        self.app.call_from_thread(log.write, f"[magenta]✔ konteks diringkas: ~{before} → ~{self.ctx} tok.[/]")
        self.app.call_from_thread(self._refresh_bars)
    @work(thread=True)
    def _run_stage(self, text, prov, model, base, key):
        log = self.query_one("#chatlog", RichLog)
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
                w(f"  [yellow]⚙[/] [b]{nm}[/] [dim]{_e(arg[:120])}[/]")
            elif kind == "result":
                from rich.markup import escape as _e
                lines = [l for l in body.splitlines() if l.strip()]
                head = _e(lines[0].lstrip("#").strip()[:130]) if lines else "(kosong)"
                more = f" [dim]… +{len(lines)-1} baris (dipakai agent, tak ditampilkan penuh)[/]" if len(lines) > 1 else ""
                w(f"  [dim]▸[/] {head}{more}")
            else:
                from rich.markup import escape as _e
                w(f"[red]⚠ {_e(body)}[/]")
        try:
            la = _llm_mod()
            if self.messages is None: self.messages = la.new_messages(prov == "anthropic")
            self.messages.append({"role": "user", "content": text})
            la.agent_turn(self.messages, prov, model, key, base, emit, allow_gated=self.allow_gated, confirm=None, on_meta=set_meta)
            la.session_save(self.sess_key, self.messages)
        except Exception as e:
            w(f"[red]⚠ error: {e}[/]")
        finally:
            self.busy = False; self.activity = "idle"; self._worker = None
            self.app.call_from_thread(self._refresh_bars)
            self.app.call_from_thread(lambda: self.query_one("#chatinput", Input).focus())

class SchedulerScreen(ModalScreen):
    """Scheduling: pasang/hapus cron pipeline harian dari dalam TUI (keyboard)."""
    BINDINGS = [("escape", "app.pop_screen", "tutup"), ("ctrl+s", "install", "install"), ("ctrl+d", "remove", "hapus")]
    def compose(self) -> ComposeResult:
        with Vertical(id="stat"):
            yield Label("[b cyan]SCHEDULING — pipeline otomatis harian (cron)[/]", classes="title")
            yield Static(self._status(), id="cronstat")
            yield Static("Pipeline = finder → program baru → scope.md + dedup + recon pasif → notif. (butuh cron/Linux)")
            yield Label("Jam (0-23), lalu tekan [b green]Ctrl+S[/] = pasang/update:")
            yield Input(value="8", id="cronhour")
            yield Label("\n[b green]▶ Ctrl+S[/] pasang jadwal · [b red]Ctrl+D[/] hapus jadwal · [dim]esc = tutup[/]")
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

class BBTUI(App):
    CSS = CSS
    ENABLE_COMMAND_PALETTE = False   # matikan palette bawaan Textual (ctrl+p) yg bikin bingung
    TITLE = "FAJAR-AGENT — Bug Bounty Hunting Harness"
    BINDINGS = [("q", "quit", "keluar"), ("slash", "search", "cari"), ("r", "refresh", "refresh"),
                ("e", "recon", "recon"), ("m", "monitor", "monitor"), ("d", "dedup", "dedup"),
                ("n", "notify", "notif"), ("w", "workspace", "workspace"), ("x", "external", "ext-tools"),
                ("b", "only_new", "baru"), ("c", "cycle_sort", "urut"), ("l", "llm", "llm-agent"), ("p", "pipeline", "pipeline"), ("g", "schedule", "jadwal"), ("ctrl+t", "theme", "tema"),
                ("s", "settings", "settings"), ("question_mark", "help", "bantuan"), ("escape", "clear_search", "")]
    def __init__(self): super().__init__(); self.cfg = load_cfg(); self.progs = {}; self.rowmap = {}; self.filter = ""; self.new_keys = set(); self.only_new = False
    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal(id="body"):
            with Vertical(id="side"):
                yield Static("memuat...", id="stat")
                yield Static(
                    "[b cyan]— MENU —[/]\n"
                    "[b]s[/] Settings (kriteria/API key)\n"
                    "[b]l[/] LLM Agent   [b]x[/] Ext-tools\n"
                    "[b]e[/] Recon  [b]m[/] Monitor  [b]d[/] Dedup\n"
                    "[b]w[/] Workspace  [b]n[/] Notify\n"
                    "[b]g[/] Jadwal  [b]p[/] Pipeline\n"
                    "[b]b[/] Baru  [b]c[/] Urut  [b]/[/] Cari  [b]r[/] Refresh\n"
                    "[b]^t[/] Tema  [b]?[/] Bantuan  [b]q[/] Keluar",
                    id="menu", classes="title")
            with Vertical(id="tablewrap"):
                yield DataTable(id="tbl", cursor_type="row", zebra_stripes=True)
            yield VerticalScroll(Static("pilih program →", id="detail"))
        yield Input(placeholder="cari nama/scope... (enter)", id="search")
        yield Footer()
    def on_mount(self):
        t = self.query_one("#tbl", DataTable)
        t.add_columns("Program", "Plat", "Reward", "WC", "Aset", "Sev", "Q")
        self.query_one("#side").border_title = "DASHBOARD"
        self.query_one("#tablewrap").border_title = "PROGRAMS"
        self.query_one("#detail").border_title = "DETAIL / SCOPE"
        self.load()
        self.set_focus(t)   # penting: fokus ke tabel, bukan ke kotak search
        self.push_screen(SplashScreen())   # banner pembuka (sekalian nutup loading)
    @work(thread=True)
    def load(self):
        self.app.call_from_thread(self.query_one("#stat", Static).update, "[cyan]menarik 5 platform...[/]")
        progs, errs = load_programs(self.cfg)
        self.progs = progs
        self.new_keys = self._diff_seen(progs)   # program yg belum pernah terlihat sebelumnya
        self.app.call_from_thread(self._render, errs)
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
        t = self.query_one("#tbl", DataTable); t.clear(); self.rowmap = {}
        items = list(self.progs.values())
        mq = _num(self.cfg, "min_quiet")
        if mq: items = [p for p in items if self._q(p) >= mq]
        if self.only_new:
            items = [p for p in items if p["key"] in self.new_keys]
        if self.filter:
            f = self.filter.lower()
            items = [p for p in items if f in (p["name"] or "").lower() or any(f in s.lower() for s in p["scope"])]
        sort = str(self.cfg.get("sort", "platform"))
        if sort == "quiet": items.sort(key=lambda x: (-self._q(x), (x["name"] or "").lower()))
        elif sort == "reward": items.sort(key=lambda x: (-(x["bounty_max"] or 0), (x["name"] or "").lower()))
        elif sort == "assets": items.sort(key=lambda x: (-len(x["scope"]), (x["name"] or "").lower()))
        else: items.sort(key=lambda x: (x["key"] not in self.new_keys, x["platform"], (x["name"] or "").lower()))
        per = {}
        for p in self.progs.values(): per[p["platform"]] = per.get(p["platform"], 0) + 1
        for p in items:
            new = p["key"] in self.new_keys
            nm = ("🆕 " + (p["name"] or "-"))[:32] if new else (p["name"] or "-")[:32]
            rk = t.add_row(nm, p["platform"][:3], reward(p), str(len(p["wild"])), str(len(p["scope"])), p["maxsev"], str(self._q(p)))
            self.rowmap[rk] = p
        stat = f"[b]Total:[/] {len(self.progs)}\n" + "\n".join(f"  {k}: {v}" for k, v in per.items())
        nb = len(self.new_keys)
        stat += f"\n\n[b {'green' if nb else 'dim'}]🆕 baru: {nb}[/]" + ("  [dim](b=hanya baru)[/]" if nb else "")
        if self.only_new: stat += "\n[green]MODE: hanya program baru[/]"
        stat += f"\n\n[b]tampil:[/] {len(items)}"
        if self.filter: stat += f"\n[yellow]filter: {self.filter}[/]"
        stat += f"\n[b]urut:[/] {self.cfg.get('sort','platform')} [dim](c=ubah)[/]"
        if mq: stat += f"\n[cyan]min-quiet: {int(mq)}[/]"
        stat += f"\n[dim]Q = skor anti-ramai (proxy)[/]"
        stat += f"\n[dim]enrich: {self.cfg.get('enrich_provider','jina')}[/]"
        if errs: stat += "\n[red]" + "; ".join(errs)[:60] + "[/]"
        self.query_one("#stat", Static).update(stat)
    def on_data_table_row_highlighted(self, ev):
        pr = self.rowmap.get(ev.row_key)
        if not pr: return
        others = [s for s in pr["scope"] if not is_wild(s)]
        mgd = {True: "managed", False: "unmanaged", None: "-"}.get(pr.get("managed"))
        md = (f"[b cyan]{pr['name']}[/] [{pr['platform']}]"
              + ("  [green]🆕 BARU[/]" if pr["key"] in self.new_keys else "") + "\n"
              f"Reward: [b]{reward(pr)}[/]  MaxSev: {pr['maxsev']}  Q(anti-ramai): [b]{self._q(pr)}[/]/100\n"
              f"Program: {mgd}  ·  Aset: {len(pr['scope'])}  ·  Wildcard: {len(pr['wild'])}\n"
              f"Sinyal H1: [dim]{pr.get('signal','-')}[/]\n"
              f"URL (rules): {pr['url'] or '-'}\n\n"
              f"[b]Wildcard ({len(pr['wild'])}):[/]\n" + ("\n".join('  ' + w for w in pr['wild']) or '  -') +
              f"\n\n[b]Aset in-scope ({len(others)}):[/]\n" + ("\n".join('  ' + s for s in others[:40]) or '  -') +
              (f"\n  … +{len(others)-40} lagi" if len(others) > 40 else "") +
              "\n\n[b]AKSI:[/] [yellow]e[/]=recon(extract web) · [yellow]m[/]=monitor subdomain · [yellow]d[/]=dedup"
              "\n[dim]target terisi dari sini, tapi bisa diedit/ketik manual · ?=bantuan[/]")
        self.query_one("#detail", Static).update(md)
    def _selected(self):
        t = self.query_one("#tbl", DataTable)
        try: return self.rowmap.get(t.coordinate_to_cell_key(t.cursor_coordinate).row_key)
        except Exception: return None
    def action_only_new(self):
        if not self.new_keys and not self.only_new:
            self.notify("belum ada program baru sejak sesi terakhir"); return
        self.only_new = not self.only_new; self._render()
    def action_cycle_sort(self):
        order = ["platform", "quiet", "reward", "assets"]
        cur = str(self.cfg.get("sort", "platform"))
        self.cfg["sort"] = order[(order.index(cur) + 1) % len(order)] if cur in order else "quiet"
        save_cfg(self.cfg); self.notify(f"urut: {self.cfg['sort']}"); self._render()
    def action_theme(self):
        try: self.theme = "textual-light" if self.theme == "textual-dark" else "textual-dark"
        except Exception:
            try: self.dark = not self.dark
            except Exception: pass
        self.notify(f"tema: {getattr(self, 'theme', 'dark' if getattr(self,'dark',True) else 'light')}")
    def action_help(self): self.push_screen(HelpScreen())
    def action_external(self):
        pr = self._selected(); self.push_screen(ExternalToolsScreen(self.cfg, apex(pr) if pr else ""))
    def action_pipeline(self):
        self.push_screen(RunScreen([sys.executable, _tool("pipeline.py")], "Pipeline (finder→dedup→recon)"))
    def action_schedule(self):
        self.push_screen(SchedulerScreen())
    def action_llm(self):
        self.push_screen(LlmChatScreen(self.cfg, target=self._selected()))
    def action_recon(self):
        pr = self._selected(); self.push_screen(ToolScreen("recon", apex(pr) if pr else ""))
    def action_monitor(self):
        pr = self._selected(); self.push_screen(ToolScreen("monitor", apex(pr) if pr else ""))
    def action_dedup(self):
        pr = self._selected()
        d = "" if not pr else (pr["key"].split("|", 1)[1] if (pr["platform"] == "hackerone" and "|" in pr["key"]) else (pr["url"] or apex(pr)))
        self.push_screen(ToolScreen("dedup", d))
    def action_notify(self):
        pr = self._selected()
        if not pr: self.notify("pilih program dulu"); return
        self._send_notify(pr)
    @work(thread=True)
    def _send_notify(self, pr):
        txt = (f"🎯 {pr['name']} [{pr['platform']}]\nReward: {reward(pr)}  Sev: {pr['maxsev']}\n"
               f"Wildcard: {', '.join(pr['wild'][:8]) or '-'}\nURL: {pr['url'] or '-'}")
        res = notify_channels(txt, self.cfg)
        self.app.call_from_thread(self.notify, " · ".join(res))
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
                fh.write(f"\n\n## Auto-seed (bbtui) — {pr['name']} [{pr['platform']}] {pr['url']}\n"
                         "### Wildcard\n" + "\n".join("- " + w for w in pr["wild"]) +
                         "\n### Scope\n" + "\n".join("- " + s for s in pr["scope"][:80]))
            self.notify(f"workspace dibuat: {dest}")
        except Exception as e:
            self.notify(f"gagal buat workspace: {e}")
    def action_search(self):
        s = self.query_one("#search", Input); s.add_class("on"); s.focus()
    def action_clear_search(self):
        s = self.query_one("#search", Input); s.remove_class("on"); s.value = ""; self.filter = ""; self._render()
    def on_input_submitted(self, ev):
        if ev.input.id == "search":
            self.filter = ev.value.strip(); ev.input.remove_class("on"); self._render(); self.query_one("#tbl").focus()
    def action_refresh(self): self.load()
    def action_settings(self): self.push_screen(SettingsScreen(self.cfg))

if __name__ == "__main__":
    try:
        BBTUI().run()
    except KeyboardInterrupt:
        pass   # keluar bersih tanpa traceback (Ctrl+C)

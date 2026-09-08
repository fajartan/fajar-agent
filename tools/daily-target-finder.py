#!/usr/bin/env python3
"""daily-target-finder — cari target program tiap hari (anti-dupe: baru + wildcard + dibayar).

Sumber: arkadiyt/bounty-targets-data (scope harian H1/Bugcrowd/YesWeHack).
Output (folder BBTF_OUT, default ~/bb-targets):
  - latest.md        : laporan terbaru (TABEL rapi: reward min/max, wildcard, aset, max-severity, sinyal, url)
  - latest.json      : data mesin lengkap + scope detail (untuk fase hunting / AI ranking)
  - history/DATE.md  : arsip md tiap hari (history finder)
Deteksi: PROGRAM BARU + ASET BARU (scope change) = edge "jadi pertama".

Env: BBTF_OUT, BBTF_PLATFORMS(=hackerone,bugcrowd,yeswehack), BBTF_WILDCARD(1), BBTF_MIN_BOUNTY(0)
Butuh: python3 (stdlib) + internet.  Cron:  0 8 * * * python3 daily-target-finder.py
"""
import json, os, datetime, urllib.request

BASE = "https://raw.githubusercontent.com/arkadiyt/bounty-targets-data/main/data/{}_data.json"
DISCLOSE_URL = "https://raw.githubusercontent.com/disclose/diodb/master/program-list.json"
PLATFORMS = os.environ.get("BBTF_PLATFORMS", "hackerone,bugcrowd,yeswehack,intigriti,federacy").split(",")
REQUIRE_WILDCARD = os.environ.get("BBTF_WILDCARD", "1") == "1"
MIN_BOUNTY = int(os.environ.get("BBTF_MIN_BOUNTY", "0"))
ASSET_FILTER = [x for x in os.environ.get("BBTF_ASSET_TYPE", "").lower().replace(" ", "").split(",") if x]  # web,android,ios,api,mobile
OUT = os.path.expanduser(os.environ.get("BBTF_OUT", "~/bb-targets"))
STATE = os.path.join(OUT, ".state", "snapshot.json")
SEV = {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0, None: 0}

def fetch(pf):
    url = DISCLOSE_URL if pf == "disclose" else BASE.format(pf)
    req = urllib.request.Request(url, headers={"User-Agent": "bbtf/2.0"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.loads(r.read().decode("utf-8", "replace"))

def is_wild(s):
    return isinstance(s, str) and "*" in s

def cell(v):
    return str(v if v is not None else "—").replace("|", "/").replace("\n", " ").strip() or "—"

def reward(pr):
    c = pr.get("cur", "$")
    lo = pr["bounty_min"]; hi = pr["bounty_max"]
    if lo is not None or hi is not None:
        if lo is not None and hi is not None: return f"{c}{lo}–{c}{hi}"
        if hi is not None: return f"≤{c}{hi}"
        return f"≥{c}{lo}"
    return "bounty" if pr["bounty"] else "—"

def types_of(pr):
    """Kategori fokus dari scope: web / android / ios / api (heuristik)."""
    t = set()
    for s in pr.get("scope", []):
        s = str(s).lower()
        if "play.google" in s or s.startswith("com.") or ".apk" in s or "android" in s: t.add("android")
        elif "apps.apple" in s or "itunes.apple" in s or "testflight" in s or (s.isdigit() and len(s) >= 6): t.add("ios")
        elif s.startswith("api.") or "/api" in s or ".api." in s: t.add("api")
        elif "." in s: t.add("web")
    return t or {"other"}

def norm(pf, p):
    if pf == "hackerone":
        if p.get("submission_state") != "open":
            return None
        ins = (p.get("targets") or {}).get("in_scope", [])
        scope = [t.get("asset_identifier") for t in ins if t.get("asset_identifier")]
        wild = [t.get("asset_identifier") for t in ins
                if t.get("asset_type") == "WILDCARD" or is_wild(t.get("asset_identifier"))]
        maxsev = max((SEV.get((t.get("max_severity") or "").lower(), 0) for t in ins), default=0)
        sevname = {v: k for k, v in SEV.items()}.get(maxsev, "—")
        detail = [{"asset": t.get("asset_identifier"), "type": t.get("asset_type"),
                   "severity": t.get("max_severity")} for t in ins]
        return dict(platform="hackerone", key=f"h1|{p.get('handle')}", name=p.get("name"), url=p.get("url"),
                    bounty=bool(p.get("offers_bounties")), bounty_min=None, bounty_max=None,
                    managed=bool(p.get("managed_program")), maxsev=sevname,
                    signal=(f"1st~{p.get('average_time_to_first_program_response')}h "
                            f"resolve~{p.get('average_time_to_report_resolved')}h "
                            f"ttbounty~{p.get('average_time_to_bounty_awarded')}h "
                            f"eff{p.get('response_efficiency_percentage')}%"),
                    n_assets=len(scope), scope=scope, wild=wild, detail=detail)
    if pf == "bugcrowd":
        ins = (p.get("targets") or {}).get("in_scope", [])
        ids = [(t.get("target") or t.get("uri") or t.get("name")) for t in ins]
        ids = [x for x in ids if x]
        detail = [{"asset": (t.get("target") or t.get("uri") or t.get("name")), "type": t.get("type")} for t in ins]
        mp = p.get("max_payout") or 0
        return dict(platform="bugcrowd", key=f"bc|{p.get('name')}", name=p.get("name"), url=p.get("url"),
                    bounty=mp > 0, bounty_min=None, bounty_max=(mp or None),
                    managed=bool(p.get("managed_by_bugcrowd")), maxsev="—", signal="—",
                    n_assets=len(ids), scope=ids, wild=[x for x in ids if is_wild(x)], detail=detail)
    if pf == "yeswehack":
        if not p.get("public") or p.get("disabled"):
            return None
        ins = (p.get("targets") or {}).get("in_scope", [])
        ids = [t.get("target") for t in ins if t.get("target")]
        detail = [{"asset": t.get("target"), "type": t.get("type")} for t in ins]
        mn = p.get("min_bounty"); mx = p.get("max_bounty")
        return dict(platform="yeswehack", key=f"ywh|{p.get('id') or p.get('name')}", name=p.get("name"),
                    url=p.get("url", ""), bounty=bool(mx), bounty_min=(mn or None), bounty_max=(mx or None),
                    managed=bool(p.get("managed")), maxsev="—", signal="—",
                    n_assets=len(ids), scope=ids, wild=[x for x in ids if is_wild(x)], detail=detail)
    if pf == "intigriti":
        if p.get("confidentiality_level") != "public":
            return None
        ins = (p.get("targets") or {}).get("in_scope", [])
        ids = [t.get("endpoint") for t in ins if t.get("endpoint")]
        detail = [{"asset": t.get("endpoint"), "type": t.get("type")} for t in ins]
        mn = (p.get("min_bounty") or {}).get("value"); mx = (p.get("max_bounty") or {}).get("value")
        cur = (p.get("max_bounty") or {}).get("currency") or (p.get("min_bounty") or {}).get("currency") or "$"
        cur = {"USD": "$", "EUR": "€", "GBP": "£"}.get(cur, cur + " ")
        return dict(platform="intigriti", key=f"it|{p.get('handle') or p.get('id')}", name=p.get("name"),
                    url=p.get("url", ""), bounty=bool(mx), bounty_min=(mn or None), bounty_max=(mx or None), cur=cur,
                    managed=False, maxsev="—", signal="—",
                    n_assets=len(ids), scope=ids, wild=[x for x in ids if is_wild(x)], detail=detail)
    if pf == "federacy":
        if not p.get("offers_awards"):
            return None
        ins = (p.get("targets") or {}).get("in_scope", [])
        ids = [t.get("target") for t in ins if t.get("target")]
        detail = [{"asset": t.get("target"), "type": t.get("type")} for t in ins]
        return dict(platform="federacy", key=f"fd|{p.get('id') or p.get('name')}", name=p.get("name"),
                    url=p.get("url", ""), bounty=True, bounty_min=None, bounty_max=None,
                    managed=False, maxsev="—", signal="—",
                    n_assets=len(ids), scope=ids, wild=[x for x in ids if is_wild(x)], detail=detail)
    if pf == "disclose":   # diodb — independen/self-hosted/VDP (scope tak terstruktur; baca policy_url)
        pol = p.get("policy_url")
        if not pol or str(p.get("policy_url_status", "")).lower() == "dead":
            return None
        return dict(platform="disclose", key=f"dio|{p.get('program_name') or pol}", name=p.get("program_name") or pol,
                    url=pol, bounty=(str(p.get("offers_bounty", "")).lower() == "yes"), bounty_min=None, bounty_max=None,
                    managed=None, maxsev="—", signal=f"safe_harbor={p.get('safe_harbor','?')}",
                    n_assets=0, scope=[], wild=[], detail=[])
    return None

def passes(pr):
    if not pr["bounty"]:
        return False
    if REQUIRE_WILDCARD and not pr["wild"]:
        return False
    # H1 tak punya angka bounty (None) -> selalu lolos ambang; hanya buang bila diketahui & di bawah ambang
    if MIN_BOUNTY and pr["bounty_max"] is not None and pr["bounty_max"] < MIN_BOUNTY:
        return False
    if ASSET_FILTER:
        want = set(ASSET_FILTER)
        if "mobile" in want: want |= {"android", "ios"}
        if not (types_of(pr) & want):
            return False
    return True

def table(items):
    if not items:
        return "_(tidak ada)_\n"
    h = "| # | Program | Reward | WC | Aset | MaxSev | Sinyal | URL |\n|--:|---|---|--:|--:|---|---|---|\n"
    rows = []
    for i, pr in enumerate(items, 1):
        rows.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            i, cell(pr["name"]), cell(reward(pr)), len(pr["wild"]), pr["n_assets"],
            cell(pr["maxsev"]), cell(pr["signal"]), cell(pr["url"])))
    return h + "\n".join(rows) + "\n"

def detail_block(items):
    L = []
    for pr in items:
        L.append(f"\n### {pr['name']} [{pr['platform']}] — {reward(pr)}")
        L.append(f"- Program/aturan (rules ada di URL ini): {pr['url'] or '—'}")
        L.append(f"- managed: {pr['managed']} | max-severity: {pr['maxsev']} | sinyal: {pr['signal']}")
        L.append(f"- Wildcard ({len(pr['wild'])}): {', '.join(pr['wild']) or '—'}")
        others = [d['asset'] for d in pr['detail'] if d['asset'] and not is_wild(d['asset'])]
        L.append(f"- Semua aset in-scope ({len(others)}): {', '.join(others) or '—'}")
        if pr.get("new_assets"):
            L.append(f"- 🆕 ASET BARU: {', '.join(pr['new_assets'])}")
    return "\n".join(L) + "\n"

def main():
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    current, errors = {}, []
    for pf in PLATFORMS:
        try:
            data = fetch(pf)
        except Exception as e:
            errors.append(f"{pf}: {e}"); continue
        for p in data:
            pr = norm(pf, p)
            if pr and passes(pr):
                current[pr["key"]] = pr

    first_run = not os.path.exists(STATE)
    prev = {}
    if not first_run:
        try: prev = json.load(open(STATE, encoding="utf-8"))
        except Exception: prev = {}

    new_programs, scope_changed = [], []
    for k, pr in current.items():
        if k not in prev:
            new_programs.append(pr)
        else:
            added = [s for s in pr["scope"] if s not in set(prev[k].get("scope", []))]
            if added:
                scope_changed.append(dict(pr, new_assets=added))
    if first_run:
        new_programs, scope_changed = [], []

    json.dump({k: {"scope": v["scope"], "name": v["name"], "platform": v["platform"]} for k, v in current.items()},
              open(STATE, "w", encoding="utf-8"))

    now = datetime.datetime.now()
    today = now.strftime("%Y-%m-%d")
    sortk = lambda x: (x["platform"], (x["name"] or "").lower())
    new_programs.sort(key=sortk); scope_changed.sort(key=sortk)
    by_plat = {pf: sorted([p for p in current.values() if p["platform"] == pf], key=sortk) for pf in PLATFORMS}

    L = []
    L.append(f"# Target Finder — {now.strftime('%Y-%m-%d %H:%M')}")
    counts = " · ".join(f"{pf}:{len(by_plat.get(pf, []))}" for pf in PLATFORMS)
    L.append(f"Kriteria: berbayar{' + wildcard' if REQUIRE_WILDCARD else ''} + min_bounty={MIN_BOUNTY}")
    L.append(f"**Total cocok: {len(current)}** ({counts})")
    if errors: L.append(f"> ⚠️ gagal ambil: {', '.join(errors)}")
    if first_run: L.append("\n> **RUN PERTAMA (baseline).** Program & aset baru muncul mulai run berikutnya.")
    L.append("\n## 🆕 PROGRAM BARU (prioritas #1)\n" + table(new_programs))
    L.append("## 🔄 SCOPE CHANGE — aset baru (prioritas #2)\n" + table(scope_changed))
    for pf in PLATFORMS:
        L.append(f"## Semua cocok — {pf} ({len(by_plat.get(pf, []))})\n" + table(by_plat.get(pf, [])))
    prio = new_programs + scope_changed
    if prio:
        L.append("## 🎯 Detail scope program prioritas (data untuk recon/hunting)\n" + detail_block(prio))
    L.append("\n---")
    L.append("Legenda: Reward → H1 tanpa angka ('bounty'); Bugcrowd '≤max'; YWH/Intigriti 'min–max' (+currency). "
             "MaxSev & Sinyal (1st-response/resolve/time-to-bounty/efficiency) hanya untuk HackerOne. WC = jumlah wildcard.")
    L.append("**Scope LENGKAP setiap program → `latest.json` (field `scope`).** Aturan/policy lengkap → buka URL program.")
    L.append("⚠️ TIDAK tersedia di dataset gratis ini (butuh scraping halaman / API ber-auth): "
             "tanggal launch program, total $ dibayar ke researcher, jumlah report diterima/dibayar. "
             "Untuk itu buka URL program, atau sambungkan H1 API (butuh token).")
    L.append("Langkah AI: ranking pakai EXPERT-TACTICS + ANTI-DUP (buang recon-findable & brand ramai; "
             "utamakan niche+wildcard+butuh-pemahaman) → top-3 → SCOPE-GATE.")
    report = "\n".join(L)

    os.makedirs(os.path.join(OUT, "history"), exist_ok=True)
    open(os.path.join(OUT, "history", f"{today}.md"), "w", encoding="utf-8").write(report)
    open(os.path.join(OUT, "latest.md"), "w", encoding="utf-8").write(report)
    json.dump({"date": today, "total": len(current), "new_programs": new_programs,
               "scope_changed": scope_changed,
               "all": [{k: p[k] for k in ("name", "platform", "url", "bounty_min", "bounty_max",
                                          "maxsev", "n_assets", "wild", "scope")} for p in current.values()]},
              open(os.path.join(OUT, "latest.json"), "w", encoding="utf-8"), indent=1)

    print(f"[+] {today} {now.strftime('%H:%M')}: cocok={len(current)} ({counts}) baru={len(new_programs)} scope_change={len(scope_changed)}")
    print(f"[+] -> {OUT}/latest.md  |  history/{today}.md  |  latest.json")
    if first_run: print("[i] run pertama = baseline; jalankan lagi besok untuk yang baru.")

if __name__ == "__main__":
    main()

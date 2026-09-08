#!/usr/bin/env python3
"""llm_agent — OTAK LLM otonom yang mengendalikan SEMUA fitur framework via tool-calling.

Konsep: kamu beri satu GOAL bahasa alami ("cari 3 program API sepi lalu recon pasif yg pertama"),
LLM memilih & memanggil tool (list/finder/recon/dedup/monitor/workspace/notify) sendiri, membaca
hasilnya, lalu lanjut sampai tujuan tercapai — SESUAI aturan AI-OPERATING-RULES:
  • Otonom penuh untuk yg AMAN: baca data, cari program, analisa, recon PASIF, dedup, monitor.
  • WAJIB konfirmasi manusia (GATE) untuk yg aktif/berisiko: recon standard/deep, exploit, submit.
  • Tidak pernah menyimpan/menembak kredensial. Tidak auto-submit. Scope-gate dihormati.

Pakai:
  python3 llm_agent.py -i                 mode chat BERTAHAP (rekomendasi): tiap tahap berhenti di CHECKPOINT, ketik 'lanjut'
  python3 llm_agent.py "goal kamu di sini"  satu tahap lalu berhenti (untuk lanjut, pakai -i)
  python3 llm_agent.py --models           tampilkan model tersedia dari provider (pakai kunci)
  python3 llm_agent.py --auto "goal"      tool GATE otomatis ditolak (mode aman non-interaktif)
  python3 llm_agent.py --setup            tulis kunci API & model ke ~/.config/bbtui/config.json
  (di TUI: tekan l = chat LLM bertahap, ctrl+o = ganti model live, ctrl+a = izinkan aksi aktif)

Provider (config ~/.config/bbtui/config.json atau env):
  llm_provider : "anthropic" (default) | "openai"   (openai = kompatibel: OpenAI/Groq/OpenRouter/Ollama)
  llm_api_key  : kunci API   (atau env ANTHROPIC_API_KEY / OPENAI_API_KEY)
  llm_model    : mis. "claude-sonnet-5" | "gpt-4o-mini" | "llama3.1" (edit sesuai punyamu)
  llm_base_url : hanya utk provider openai-compatible, mis. "http://localhost:11434/v1" (Ollama)
Butuh: python3 saja (urllib). Tidak ada dependensi eksternal.
"""
import os, sys, re, json, shlex, argparse, datetime, subprocess, urllib.request, urllib.error
import concurrent.futures as _cf

_CTX = {}   # konteks LLM aktif (provider/model/key/base_url/allow_gated) — dipakai delegasi sub-agen

CFG_DIR = os.path.expanduser("~/.config/bbtui"); CFG = os.path.join(CFG_DIR, "config.json")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.expanduser(os.environ.get("BBTF_OUT", "~/bb-targets"))
LATEST = os.path.join(OUT, "latest.json")
WS = os.path.expanduser("~/bb-workspaces")
MEM_DIR = os.path.join(CFG_DIR, "agent-memory")          # memori jangka panjang (lintas sesi)
SESS_DIR = os.path.join(CFG_DIR, "agent-sessions")       # riwayat percakapan (resume)

def load_cfg():
    c = {}
    try: c = json.load(open(CFG, encoding="utf-8"))
    except Exception: pass
    return c

def cfg_get(c, key, env, default=""):
    return os.environ.get(env) or c.get(key) or default

def tool_path(n): return os.path.join(SCRIPT_DIR, n)

def run_script(script, args, timeout=1800):
    """Jalankan tool framework, kembalikan (rc, output-teks-terpotong)."""
    try:
        p = subprocess.run([sys.executable, tool_path(script)] + args,
                           capture_output=True, text=True, timeout=timeout,
                           encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")
        return p.returncode, out[-6000:]
    except subprocess.TimeoutExpired:
        return 1, f"[timeout {timeout}s] {script}"
    except Exception as e:
        return 1, f"[error jalanin {script}: {e}]"

# ---------------- data helpers ----------------
def ensure_latest(refresh=False):
    if refresh or not os.path.exists(LATEST):
        run_script("daily-target-finder.py", [])
    try: return json.load(open(LATEST, encoding="utf-8"))
    except Exception: return {"programs": [], "new_programs": [], "scope_changed": []}

def _match(pr, platform, asset_type, min_bounty, wildcard_only, query):
    if platform and pr.get("platform") != platform: return False
    if wildcard_only and not pr.get("wild"): return False
    if min_bounty:
        bmax = pr.get("bounty_max")
        if isinstance(bmax, (int, float)) and bmax < min_bounty: return False
    if asset_type:
        blob = " ".join(str(s).lower() for s in pr.get("scope", []))
        at = asset_type.lower()
        keys = {"android": ["play.google", "com.", ".apk", "android"], "ios": ["apps.apple", "testflight", "itunes"],
                "api": ["api.", "/api", ".api."], "web": ["http", "."], "mobile": ["play.google", "apps.apple", "com.", ".apk"]}
        if not any(k in blob for k in keys.get(at, [at])): return False
    if query:
        q = query.lower()
        if q not in (pr.get("name") or "").lower() and not any(q in str(s).lower() for s in pr.get("scope", [])):
            return False
    return True

# ---------------- TOOLS (yg bisa dipanggil LLM) ----------------
def t_list_programs(platform="", asset_type="", min_bounty=0, wildcard_only=False, query="", limit=25):
    data = ensure_latest()
    progs = data.get("programs", [])
    hit = [p for p in progs if _match(p, platform, asset_type, min_bounty, wildcard_only, query)]
    hit = hit[:max(1, min(int(limit or 25), 60))]
    lines = [f"total_cocok={len(hit)} (dari {len(progs)})"]
    for p in hit:
        rw = f"{p.get('bounty_min')}-{p.get('bounty_max')}" if p.get("bounty_max") else "n/a"
        lines.append(f"- [{p.get('platform')}] {p.get('name')} | reward={rw} | wild={len(p.get('wild',[]))} | assets={p.get('n_assets')} | sev={p.get('maxsev')} | {p.get('url','')}")
    return "\n".join(lines)

def t_new_programs():
    data = ensure_latest(refresh=True)
    new = data.get("new_programs", []); ch = data.get("scope_changed", [])
    if not new and not ch: return "Tidak ada program baru / scope-change sejak run finder terakhir."
    L = [f"PROGRAM BARU: {len(new)}"]
    for p in new[:20]: L.append(f"- [{p.get('platform')}] {p.get('name')} | {p.get('url','')} | wild={len(p.get('wild',[]))}")
    L.append(f"SCOPE-CHANGE (aset baru): {len(ch)}")
    for p in ch[:20]: L.append(f"- [{p.get('platform')}] {p.get('name')} | aset baru: {', '.join(p.get('new_assets',[])[:5])}")
    return "\n".join(L)

def t_program_detail(name=""):
    data = ensure_latest(); q = (name or "").lower()
    for p in data.get("programs", []):
        if q and q in (p.get("name") or "").lower():
            others = [s for s in p.get("scope", []) if "*" not in str(s)]
            return (f"{p.get('name')} [{p.get('platform')}] {p.get('url','')}\n"
                    f"reward min={p.get('bounty_min')} max={p.get('bounty_max')} sev={p.get('maxsev')}\n"
                    f"WILDCARD:\n" + "\n".join("  " + w for w in p.get("wild", [])) +
                    f"\nASET in-scope ({len(others)}):\n" + "\n".join("  " + str(s) for s in others[:60]))
    return f"program '{name}' tak ketemu di latest.json (coba list_programs dulu)."

def t_recon(domain="", profile="passive"):
    if not domain: return "[gagal] domain kosong."
    rc, out = run_script("recon.py", [domain, "--profile", profile])
    return f"recon({domain},{profile}) rc={rc}\n{out}"

def t_dedup(handle=""):
    if not handle: return "[gagal] handle/url kosong."
    rc, out = run_script("dedup.py", [handle])
    return f"dedup({handle}) rc={rc}\n{out}"

def t_monitor(domain=""):
    if not domain: return "[gagal] domain kosong."
    rc, out = run_script("asset-monitor.py", [domain])
    return f"monitor({domain}) rc={rc}\n{out}"

def t_workspace(name=""):
    if not name: return "[gagal] nama kosong."
    data = ensure_latest(); pr = None
    for p in data.get("programs", []):
        if name.lower() in (p.get("name") or "").lower(): pr = p; break
    import re as _re
    dest = os.path.join(WS, _re.sub(r"\W", "_", name)[:40]); os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "scope.md"), "w", encoding="utf-8") as fh:
        if pr:
            fh.write(f"# Scope — {pr.get('name')} [{pr.get('platform')}]\n- URL: {pr.get('url','')}\n"
                     f"- Reward: {pr.get('bounty_min')}-{pr.get('bounty_max')}\n\n## Wildcard\n"
                     + "\n".join("- " + w for w in pr.get("wild", [])) + "\n\n## Scope\n"
                     + "\n".join("- " + str(s) for s in pr.get("scope", [])))
        else:
            fh.write(f"# Scope — {name}\n(program tak ada di latest.json; isi manual)\n")
    return f"workspace disiapkan: {dest}/scope.md"

def t_notify(text=""):
    c = load_cfg(); import urllib.parse
    tok = c.get("telegram_token"); chat = c.get("telegram_chat"); hook = c.get("discord_webhook")
    res = []
    try:
        if hook:
            urllib.request.urlopen(urllib.request.Request(hook, data=json.dumps({"content": text[:1900]}).encode(),
                                   headers={"Content-Type": "application/json"}), timeout=15); res.append("discord ok")
    except Exception as e: res.append(f"discord gagal:{e}")
    try:
        if tok and chat:
            urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage?%s" % (tok, urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]})), timeout=15); res.append("tg ok")
    except Exception as e: res.append(f"tg gagal:{e}")
    return " · ".join(res) or "tidak ada channel notif dikonfigurasi (isi telegram_*/discord_webhook)."

# ---------------- MEMORI JANGKA PANJANG (ala Hermes: ingat lintas sesi, update diri) ----------------
def _slug(s): return re.sub(r"[^a-z0-9]+", "-", str(s).lower()).strip("-")[:50] or "note"

def mem_save(key="", text="", kind="note", target=""):
    """Simpan/append satu memori durable. kind: finding|target|dedup|learning|note. Otonom (aman)."""
    if not text: return "[gagal] text kosong."
    os.makedirs(MEM_DIR, exist_ok=True)
    slug = f"{_slug(kind)}--{_slug(target or key or text[:20])}"
    fp = os.path.join(MEM_DIR, slug + ".md")
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    head = "" if os.path.exists(fp) else f"---\nkind: {kind}\ntarget: {target}\nkey: {key}\ncreated: {ts}\n---\n"
    with open(fp, "a", encoding="utf-8") as fh: fh.write(head + f"\n[{ts}] {text}\n")
    _mem_reindex()
    return f"memori tersimpan: {slug} (kind={kind})"

def _mem_reindex():
    try:
        rows = []
        for f in sorted(os.listdir(MEM_DIR)):
            if not f.endswith(".md") or f == "INDEX.md": continue
            fm = _read_fm(os.path.join(MEM_DIR, f))
            rows.append(f"- [{fm.get('kind','note')}] {f[:-3]} — target={fm.get('target','')} ({fm.get('created','')})")
        open(os.path.join(MEM_DIR, "INDEX.md"), "w", encoding="utf-8").write("# MEMORI AGENT\n" + "\n".join(rows))
    except Exception: pass

def _read_fm(fp):
    fm = {}
    try:
        t = open(fp, encoding="utf-8", errors="replace").read()
        if t.startswith("---"):
            for line in t.split("---", 2)[1].strip().splitlines():
                if ":" in line: k, v = line.split(":", 1); fm[k.strip()] = v.strip()
    except Exception: pass
    return fm

def mem_search(query="", limit=8):
    """Cari memori relevan (substring, case-insensitive). Dipakai agent di tahap awal utk recall + anti-dup lintas sesi."""
    if not os.path.isdir(MEM_DIR): return "[memori kosong]"
    q = (query or "").lower(); hits = []
    for f in sorted(os.listdir(MEM_DIR)):
        if not f.endswith(".md") or f == "INDEX.md": continue
        body = open(os.path.join(MEM_DIR, f), encoding="utf-8", errors="replace").read()
        if not q or q in body.lower() or q in f.lower():
            snip = body.strip().replace("\n", " ")[:300]
            hits.append(f"### {f[:-3]}\n{snip}")
        if len(hits) >= int(limit or 8): break
    return "\n\n".join(hits) if hits else f"[tak ada memori cocok untuk '{query}']"

def mem_list():
    fp = os.path.join(MEM_DIR, "INDEX.md")
    return open(fp, encoding="utf-8", errors="replace").read() if os.path.exists(fp) else "[memori kosong]"

def mem_digest(max_chars=2500):
    """Ringkas memori utk di-inject ke konteks tiap panggilan (long-context recall)."""
    if not os.path.isdir(MEM_DIR): return ""
    idx = mem_list()
    return idx[:max_chars] + (" …" if len(idx) > max_chars else "")

# ---------------- persistensi sesi (resume percakapan panjang) ----------------
def session_save(sid, messages):
    try:
        os.makedirs(SESS_DIR, exist_ok=True)
        json.dump({"saved": datetime.datetime.now().isoformat(), "messages": messages},
                  open(os.path.join(SESS_DIR, _slug(sid) + ".json"), "w", encoding="utf-8"))
    except Exception: pass

def session_load(sid):
    try: return json.load(open(os.path.join(SESS_DIR, _slug(sid) + ".json"), encoding="utf-8")).get("messages")
    except Exception: return None

SKILLS = {
    "operating-rules": "AI-OPERATING-RULES.md", "anti-dup": "ANTI-DUP-PLAYBOOK.md",
    "novel-hunting": "NOVEL-HUNTING.md", "expert-tactics": "EXPERT-TACTICS.md",
    "recon-runbook": "RECON-RUNBOOK.md", "payloads": "PAYLOAD-CHEATSHEET.md",
    "verify": "VERIFY-BEFORE-SUBMIT.md", "report-kit": "REPORT-KIT.md",
    "program-selection": "PROGRAM-SELECTION.md", "monitor-workflow": "MONITOR-WORKFLOW.md",
    "autonomous": "AUTONOMOUS-OPERATOR.md", "framework": "FRAMEWORK-BUGBOUNTY-AI.md",
    "web-vuln-classes": "WEB-VULN-CLASSES.md", "api-pentest": "API-PENTEST.md", "mobile-pentest": "MOBILE-PENTEST.md",
}
USER_SKILLS = os.path.join(CFG_DIR, "skills")   # skill yg diinstall user (playbook tambahan)

def _skill_path(fname):
    for base in (os.path.join(SCRIPT_DIR, ".."), SCRIPT_DIR, os.path.join(SCRIPT_DIR, "..", ".."), os.getcwd()):
        p = os.path.join(base, fname)
        if os.path.exists(p): return p
    return None

def all_skills():
    """Gabungan skill BAWAAN (playbook framework) + skill TERPASANG user (~/.config/bbtui/skills)."""
    d = {}
    for slug, fn in SKILLS.items():
        p = _skill_path(fn)
        if p: d[slug] = p
    if os.path.isdir(USER_SKILLS):
        for f in sorted(os.listdir(USER_SKILLS)):
            if f.endswith(".md"): d.setdefault(f[:-3], os.path.join(USER_SKILLS, f))
    return d

def t_list_skills():
    d = all_skills(); builtin = set(SKILLS)
    out = ["SKILLS (load_skill <nama> utk baca; install_skill utk pasang baru):"]
    for slug in d: out.append(f"- {slug}" + ("" if slug in builtin else " [terpasang]"))
    return "\n".join(out)

def t_load_skill(name=""):
    p = all_skills().get((name or "").strip().lower())
    if not p: return f"[skill '{name}' tak ada] pilihan: {', '.join(all_skills())}"
    body = open(p, encoding="utf-8", errors="replace").read()
    return f"=== SKILL {name} ===\n{body[:9000]}" + (" …[terpotong]" if len(body) > 9000 else "")

def t_install_skill(name="", source="", text=""):
    """Pasang skill/playbook baru. source: URL (unduh) atau path lokal; atau text langsung.
    CATATAN KEAMANAN: isi skill jadi INSTRUKSI yg diikuti agent → hanya install dari sumber tepercaya."""
    if not name: return "[gagal] nama skill kosong."
    os.makedirs(USER_SKILLS, exist_ok=True)
    slug = _slug(name); fp = os.path.join(USER_SKILLS, slug + ".md")
    try:
        if text: body = text
        elif source.startswith("http://") or source.startswith("https://"):
            body = urllib.request.urlopen(urllib.request.Request(source, headers={"User-Agent": "fajar-agent"}), timeout=30).read().decode("utf-8", "replace")
        elif source and os.path.exists(os.path.expanduser(source)):
            body = open(os.path.expanduser(source), encoding="utf-8", errors="replace").read()
        else: return "[gagal] beri 'text', atau 'source' berupa URL/path file yg valid."
        open(fp, "w", encoding="utf-8").write(body)
        return f"skill '{slug}' terpasang → {fp} ({len(body)} char). Muat via load_skill {slug}."
    except Exception as e:
        return f"[gagal install skill: {e}]"

def t_list_ext_tools():
    ext = load_cfg().get("external_tools", {})
    if not ext: return "Belum ada external_tools. Tambah di TUI (x) atau ~/.config/bbtui/config.json."
    return "External tools terdaftar (placeholder {target}/{url}/{handle}):\n" + "\n".join(f"- {k}: {v}" for k, v in ext.items())

def t_run_ext_tool(name="", target=""):
    ext = load_cfg().get("external_tools", {})
    if name not in ext: return f"[gagal] '{name}' tak terdaftar. Ada: {', '.join(ext) or '-'}"
    if not target: return "[gagal] target kosong."
    tmpl = ext[name]
    cmd = tmpl.replace("{target}", target).replace("{url}", target if target.startswith("http") else "https://" + target).replace("{handle}", target)
    try:
        p = subprocess.run(shlex.split(cmd), capture_output=True, text=True, timeout=3600, encoding="utf-8", errors="replace")
        out = (p.stdout or "") + (("\n[stderr]\n" + p.stderr) if p.stderr else "")
        return f"$ {cmd}\nrc={p.returncode}\n{out[-6000:]}"
    except FileNotFoundError:
        return f"[gagal] tool '{name}' belum terpasang di sistem (cek: bb.py doctor)."
    except subprocess.TimeoutExpired:
        return f"[timeout] {cmd}"
    except Exception as e:
        return f"[error] {e}"

def t_read_recon(domain=""):
    if not domain: return "[gagal] domain kosong."
    for base in (os.path.expanduser("~/bb-recon"), os.path.expanduser("~/bb-workspaces")):
        rec = os.path.join(base, domain, "recon")
        sm = os.path.join(rec, "summary.md")
        if os.path.exists(sm):
            files = [f for f in os.listdir(rec) if os.path.isfile(os.path.join(rec, f))]
            body = open(sm, encoding="utf-8", errors="replace").read()
            return f"[recon {domain}] dir={rec}\nfile: {', '.join(sorted(files))}\n\n--- summary.md ---\n{body[:6000]}"
    return f"[belum ada hasil recon utk {domain}] jalankan recon dulu (profile passive/standard)."

def t_save_note(program="", text="", kind="hypotheses"):
    if not program or not text: return "[gagal] program/text kosong."
    import re as _re
    dest = os.path.join(WS, _re.sub(r"\W", "_", program)[:40]); os.makedirs(dest, exist_ok=True)
    fname = {"report": "reports/draft.md", "hypotheses": "hypotheses.md", "note": "notes.md"}.get(kind, "notes.md")
    fp = os.path.join(dest, fname); os.makedirs(os.path.dirname(fp), exist_ok=True)
    with open(fp, "a", encoding="utf-8") as fh: fh.write("\n\n" + text)
    return f"tersimpan (append) -> {fp}"

# ---------------- INGEST dokumen/folder projek (read-only, analisa artefak) ----------------
_INGEST_EXT = {".js", ".ts", ".jsx", ".tsx", ".json", ".txt", ".md", ".py", ".java", ".kt", ".xml", ".yml",
               ".yaml", ".env", ".html", ".htm", ".php", ".rb", ".go", ".conf", ".ini", ".smali", ".sql", ".sh", ".har"}
_SKIP_DIR = {"node_modules", ".git", "__pycache__", "build", "dist", ".gradle", ".idea", "vendor"}

def t_read_file(path="", max_chars=9000):
    """Baca satu file teks (JS/JSON/source/Burp export/dll) utk dianalisa. Read-only."""
    p = os.path.expanduser(path or "")
    if not os.path.isfile(p): return f"[tak ada file: {path}]"
    try:
        if os.path.getsize(p) > 3_000_000: return f"[file >3MB, lewati: {path}]"
        b = open(p, "rb").read()
        if b"\x00" in b[:2048]: return f"[file biner, lewati: {path}] ukuran={len(b)} byte"
        txt = b.decode("utf-8", "replace")
        return f"=== {path} ({len(txt)} char) ===\n" + txt[:max_chars] + (" …[terpotong]" if len(txt) > max_chars else "")
    except Exception as e:
        return f"[gagal baca {path}: {e}]"

def t_ingest_folder(path="", max_files=40, per_file=500):
    """Masukkan folder projek: pohon file + cuplikan isi file teks. Utk analisa codebase/APK-decompile/dll. Read-only."""
    p = os.path.expanduser(path or "")
    if not os.path.isdir(p): return f"[bukan folder: {path}]"
    tree, snippets, n = [], [], 0
    for dp, dn, files in os.walk(p):
        dn[:] = [d for d in dn if d not in _SKIP_DIR]
        for f in sorted(files):
            rel = os.path.relpath(os.path.join(dp, f), p)
            tree.append(rel)
            if os.path.splitext(f)[1].lower() in _INGEST_EXT and n < max_files:
                try:
                    t = open(os.path.join(dp, f), encoding="utf-8", errors="replace").read()
                    snippets.append(f"--- {rel} ---\n{t[:per_file]}"); n += 1
                except Exception: pass
    head = f"POHON PROJEK '{path}' ({len(tree)} file):\n" + "\n".join("  " + t for t in tree[:200])
    return head + f"\n\nCUPLIKAN ISI ({n} file teks):\n" + "\n\n".join(snippets)

def t_search_files(path="", pattern="", max_hits=80):
    """Grep regex di file/folder (cari secret/endpoint/kredensial di JS/source). Read-only.
    Contoh pattern: api[_-]?key|secret|token|authorization|BEGIN [A-Z]+ PRIVATE KEY|https?://[^\\s\"']+"""
    import re as _re
    p = os.path.expanduser(path or "")
    if not os.path.exists(p): return f"[tak ada: {path}]"
    try: rx = _re.compile(pattern, _re.I)
    except Exception as e: return f"[regex salah: {e}]"
    base = p if os.path.isdir(p) else os.path.dirname(p)
    paths = []
    if os.path.isfile(p): paths = [p]
    else:
        for dp, dn, files in os.walk(p):
            dn[:] = [d for d in dn if d not in _SKIP_DIR]
            paths += [os.path.join(dp, f) for f in files]
    hits = []
    for fp in paths:
        try:
            if os.path.getsize(fp) > 3_000_000: continue
            for i, line in enumerate(open(fp, encoding="utf-8", errors="replace"), 1):
                if rx.search(line):
                    hits.append(f"{os.path.relpath(fp, base)}:{i}: {line.strip()[:200]}")
                    if len(hits) >= max_hits: return "\n".join(hits) + "\n…(batas hit)"
        except Exception: continue
    return "\n".join(hits) if hits else f"[tak ada cocok '{pattern}' di {path}]"

# ---------------- MULTI-AGENT: delegasi ke sub-agen (paralel) ----------------
ROLE_TOOLS = {
    "recon": ["program_detail", "recon", "read_recon", "monitor", "list_ext_tools", "run_ext_tool", "memory_search", "memory_save"],
    "dedup": ["program_detail", "dedup", "memory_search", "memory_save"],
    "analysis": ["read_recon", "read_file", "ingest_folder", "search_files", "list_skills", "load_skill", "dedup", "memory_search", "memory_save"],
    "discovery": ["list_programs", "new_programs", "program_detail", "memory_search"],
    "report": ["read_recon", "read_file", "load_skill", "save_note", "memory_search"],
    "general": ["list_programs", "new_programs", "program_detail", "recon", "read_recon", "read_file", "ingest_folder",
                "search_files", "monitor", "dedup", "memory_search", "memory_save", "list_skills", "load_skill", "list_ext_tools", "run_ext_tool"],
}
def _tools_for(role):
    names = ROLE_TOOLS.get(role, ROLE_TOOLS["general"])
    return [BYNAME[n] for n in names if n in BYNAME]   # tanpa delegate → cegah rekursi

def run_subagent(role, goal, provider, model, key, base_url, allow_gated, max_iters=8):
    """Sub-agen OTONOM (tanpa checkpoint) dgn subset tool sesuai peran. Return ringkasan teks."""
    is_anth = provider == "anthropic"
    sysp = (f"Kamu SUB-AGEN [{role}] dari FAJAR-AGENT. Kerjakan sub-tugas ini OTONOM sampai tuntas "
            f"(tanpa checkpoint/tanya). Pakai hanya tool yg tersedia untuk peranmu. Patuhi scope & aturan: "
            f"tidak exploit, tidak submit, tidak olah kredensial. Akhiri dengan RINGKASAN padat berlabel "
            f"[FAKTA]/[HIPOTESIS] + rekomendasi langkah berikutnya. Ringkas dan konkret.")
    tools = _tools_for(role)
    messages = ([] if is_anth else [{"role": "system", "content": sysp}])
    messages.append({"role": "user", "content": goal})
    buf = []
    for _ in range(max_iters):
        try:
            resp = (chat_anthropic(messages, model, key, system=sysp, tools=tools) if is_anth
                    else chat_openai(messages, model, key, base_url, system=sysp, tools=tools))
        except SystemExit as e:
            return f"[sub-agen {role} gagal] {e}"
        if resp["text"].strip(): buf.append(resp["text"].strip())
        messages.append({"role": "assistant", "content": resp["raw"]} if is_anth else resp["raw"])
        if not resp["calls"]: break
        results = [(c["id"], execute_tool(c["name"], c["input"], allow_gated, None)) for c in resp["calls"]]
        _append_results(messages, results, is_anth)
    return (buf[-1] if buf else "(sub-agen tak menghasilkan output)")

def t_spawn_agents(tasks=None):
    """Delegasi PARALEL ke beberapa sub-agen. tasks: [{role, goal}]. role: recon|dedup|analysis|discovery|report|general."""
    if not tasks or not isinstance(tasks, list): return "[gagal] 'tasks' harus list [{role, goal}]."
    if not _CTX.get("key"): return "[gagal] konteks LLM tak tersedia (jalankan via agent utama)."
    tasks = tasks[:4]   # batasi paralelisme
    def worker(t):
        role = (t.get("role") or "general").lower(); goal = t.get("goal") or ""
        res = run_subagent(role, goal, _CTX["provider"], _CTX["model"], _CTX["key"], _CTX["base_url"], _CTX.get("allow_gated", False))
        return role, goal, res
    out = []
    with _cf.ThreadPoolExecutor(max_workers=min(len(tasks), 4)) as ex:
        for role, goal, res in ex.map(worker, tasks):
            out.append(f"### 🤖 sub-agen [{role}] — {goal[:60]}\n{res}")
    return "\n\n".join(out)

# registry: gated=True -> butuh konfirmasi manusia (aktif/berdampak)
TOOLS = [
    {"name": "list_programs", "gated": False, "fn": t_list_programs,
     "desc": "Cari/filter program bug bounty dari data live (5 platform). Filter: platform, asset_type(web/android/ios/api/mobile), min_bounty, wildcard_only, query, limit.",
     "schema": {"type": "object", "properties": {"platform": {"type": "string"}, "asset_type": {"type": "string"}, "min_bounty": {"type": "integer"}, "wildcard_only": {"type": "boolean"}, "query": {"type": "string"}, "limit": {"type": "integer"}}}},
    {"name": "new_programs", "gated": False, "fn": t_new_programs,
     "desc": "Jalankan finder & tampilkan PROGRAM BARU + SCOPE-CHANGE sejak run terakhir (prioritas anti-duplikat).",
     "schema": {"type": "object", "properties": {}}},
    {"name": "program_detail", "gated": False, "fn": t_program_detail,
     "desc": "Detail scope satu program dari latest.json berdasarkan nama. JANGAN dipakai bila sudah ada blok [TARGET CONTEXT] (scope sudah tersedia di situ).",
     "schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "recon", "gated": False, "fn": t_recon,
     "desc": "Recon sebuah domain. profile=passive AMAN (default, tanpa nembak target). profile standard/deep AKTIF -> butuh izin.",
     "schema": {"type": "object", "properties": {"domain": {"type": "string"}, "profile": {"type": "string", "enum": ["passive", "standard", "deep"]}}, "required": ["domain"]}},
    {"name": "dedup", "gated": False, "fn": t_dedup,
     "desc": "Cek isu yg sudah pernah dilaporkan (DEDUP-GATE) utk handle/url program, agar tak submit duplikat.",
     "schema": {"type": "object", "properties": {"handle": {"type": "string"}}, "required": ["handle"]}},
    {"name": "monitor", "gated": False, "fn": t_monitor,
     "desc": "Pantau subdomain (pasif) sebuah domain, deteksi aset baru.",
     "schema": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}},
    {"name": "read_recon", "gated": False, "fn": t_read_recon,
     "desc": "Baca hasil recon (summary.md + daftar file) sebuah domain untuk dianalisa jadi hipotesis.",
     "schema": {"type": "object", "properties": {"domain": {"type": "string"}}, "required": ["domain"]}},
    {"name": "read_file", "gated": False, "fn": t_read_file,
     "desc": "Baca 1 file teks lokal (JS/JSON/source/Burp/HAR export) yg di-upload/drag user untuk dianalisa.",
     "schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "ingest_folder", "gated": False, "fn": t_ingest_folder,
     "desc": "Masukkan FOLDER PROJEK (pohon file + cuplikan) untuk analisa codebase/APK-decompile/JS bundle.",
     "schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "search_files", "gated": False, "fn": t_search_files,
     "desc": "Grep regex di file/folder cari secret/endpoint/kredensial (mis. api[_-]?key|token|https?://...).",
     "schema": {"type": "object", "properties": {"path": {"type": "string"}, "pattern": {"type": "string"}}, "required": ["path", "pattern"]}},
    {"name": "memory_search", "gated": False, "fn": mem_search,
     "desc": "Cari MEMORI jangka panjang (lintas sesi): catatan target, temuan lalu, dedup, pelajaran. Panggil di tahap awal utk recall & anti-dup lintas waktu.",
     "schema": {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer"}}}},
    {"name": "memory_save", "gated": False, "fn": mem_save,
     "desc": "Simpan memori durable (UPDATE DIRI). kind: finding|target|dedup|learning|note. Panggil tiap dapat fakta penting (quirk target, endpoint, apa yg berhasil/gagal, isu yg sudah ada).",
     "schema": {"type": "object", "properties": {"key": {"type": "string"}, "text": {"type": "string"}, "kind": {"type": "string", "enum": ["finding", "target", "dedup", "learning", "note"]}, "target": {"type": "string"}}, "required": ["text"]}},
    {"name": "memory_list", "gated": False, "fn": mem_list,
     "desc": "Lihat indeks seluruh memori jangka panjang agent.",
     "schema": {"type": "object", "properties": {}}},
    {"name": "delegate", "gated": False, "fn": t_spawn_agents,
     "desc": "Delegasi PARALEL ke beberapa SUB-AGEN yg bekerja BERSAMAAN (mis. 1 recon, 1 dedup, 1 analisa). "
             "tasks=[{role,goal}] · role: recon|dedup|analysis|discovery|report|general. Pakai utk kerja paralel/lintas-domain.",
     "schema": {"type": "object", "properties": {"tasks": {"type": "array", "items": {"type": "object",
                "properties": {"role": {"type": "string"}, "goal": {"type": "string"}}, "required": ["goal"]}}}, "required": ["tasks"]}},
    {"name": "list_skills", "gated": False, "fn": t_list_skills,
     "desc": "Lihat daftar SKILL (playbook framework: anti-dup, expert-tactics, payloads, verify, report-kit, dll).",
     "schema": {"type": "object", "properties": {}}},
    {"name": "load_skill", "gated": False, "fn": t_load_skill,
     "desc": "Muat isi satu SKILL/playbook untuk memandu tahap ini (mis. anti-dup sebelum dedup, payloads sebelum rencana, verify sebelum laporan).",
     "schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "install_skill", "gated": True, "fn": t_install_skill,
     "desc": "Pasang SKILL/playbook baru (dari URL, path file, atau text). Isi jadi instruksi agent — hanya sumber tepercaya.",
     "schema": {"type": "object", "properties": {"name": {"type": "string"}, "source": {"type": "string"}, "text": {"type": "string"}}, "required": ["name"]}},
    {"name": "list_ext_tools", "gated": False, "fn": t_list_ext_tools,
     "desc": "Lihat daftar external tools yg terdaftar (nuclei/dalfox/reconftw/dll) beserta template perintahnya.",
     "schema": {"type": "object", "properties": {}}},
    {"name": "run_ext_tool", "gated": True, "fn": t_run_ext_tool,
     "desc": "Jalankan external tool AKTIF (mis. nuclei/dalfox) pada target — mengirim traffic, butuh izin manusia & in-scope.",
     "schema": {"type": "object", "properties": {"name": {"type": "string"}, "target": {"type": "string"}}, "required": ["name", "target"]}},
    {"name": "save_note", "gated": True, "fn": t_save_note,
     "desc": "Tulis catatan/hipotesis/draf laporan ke workspace program (kind: hypotheses|report|note).",
     "schema": {"type": "object", "properties": {"program": {"type": "string"}, "text": {"type": "string"}, "kind": {"type": "string", "enum": ["hypotheses", "report", "note"]}}, "required": ["program", "text"]}},
    {"name": "workspace", "gated": True, "fn": t_workspace,
     "desc": "Buat folder workspace + scope.md utk sebuah program (menulis file ke disk).",
     "schema": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}},
    {"name": "notify", "gated": True, "fn": t_notify,
     "desc": "Kirim pesan ke Telegram/Discord kamu (aksi keluar/eksternal).",
     "schema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
]
BYNAME = {t["name"]: t for t in TOOLS}

# ---------------- MCP CLIENT (integrasi server MCP via stdio JSON-RPC) ----------------
import itertools as _it, threading as _th, queue as _q, time as _time
_mcp_id = _it.count(1)
_mcp_procs = {}   # name -> Popen

def _readline_timeout(proc, timeout=25):
    out = _q.Queue()
    def rd():
        try: out.put(proc.stdout.readline())
        except Exception: out.put("")
    t = _th.Thread(target=rd, daemon=True); t.start()
    try: return out.get(timeout=timeout)
    except Exception: return ""

def _mcp_rpc(proc, method, params, timeout=30):
    mid = next(_mcp_id)
    try:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "id": mid, "method": method, "params": params}) + "\n"); proc.stdin.flush()
    except Exception as e:
        return {"error": str(e)}
    start = _time.time()
    while _time.time() - start < timeout:
        line = _readline_timeout(proc, timeout)
        if not line: break
        line = line.strip()
        if not line: continue
        try: obj = json.loads(line)
        except Exception: continue
        if obj.get("id") == mid: return obj.get("result") if obj.get("result") is not None else {"error": obj.get("error")}
        # notifikasi/log server → abaikan
    return {"error": "timeout"}

def _mcp_notify(proc, method, params=None):
    try:
        proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method, "params": params or {}}) + "\n"); proc.stdin.flush()
    except Exception: pass

def mcp_start(name, spec):
    """Spawn server MCP, handshake initialize, kembalikan daftar tools."""
    cmd = [spec["command"]] + list(spec.get("args") or [])
    env = dict(os.environ); env.update(spec.get("env") or {})
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, encoding="utf-8", env=env)
    _mcp_procs[name] = proc
    _mcp_rpc(proc, "initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                  "clientInfo": {"name": "fajar-agent", "version": "1.0"}})
    _mcp_notify(proc, "notifications/initialized")
    res = _mcp_rpc(proc, "tools/list", {})
    return (res or {}).get("tools", []) or []

def mcp_call(server, tool, args):
    proc = _mcp_procs.get(server)
    if not proc or proc.poll() is not None: return f"[MCP {server} tak terhubung]"
    res = _mcp_rpc(proc, "tools/call", {"name": tool, "arguments": args or {}})
    if res.get("error"): return f"[MCP {server}/{tool} error: {res['error']}]"
    parts = []
    for c in (res.get("content") or []):
        parts.append(c.get("text", "") if c.get("type") == "text" else json.dumps(c)[:500])
    return ("\n".join(p for p in parts if p) or json.dumps(res)[:1200])[:6000]

def _mcp_fn(server, tool):
    def fn(**kwargs): return mcp_call(server, tool, kwargs)
    return fn

def mcp_connect_all(cfg=None):
    """Connect semua server MCP di config; tambahkan tool-nya ke TOOLS/BYNAME (mcp__server__tool)."""
    cfg = cfg or load_cfg(); servers = cfg.get("mcp_servers") or {}
    report = []
    for name, spec in servers.items():
        if not spec.get("enabled", True): continue
        if any(k.startswith("mcp__%s__" % name) for k in BYNAME):  # sudah terhubung
            report.append(f"{name}: sudah terhubung"); continue
        try:
            tools = mcp_start(name, spec)
        except Exception as e:
            report.append(f"{name}: GAGAL ({e})"); continue
        gated = not spec.get("trusted", False)
        for t in tools:
            tn = "mcp__%s__%s" % (name, t.get("name"))
            entry = {"name": tn, "gated": gated, "fn": _mcp_fn(name, t.get("name")),
                     "desc": ("[MCP:%s] " % name) + (t.get("description") or t.get("name") or "")[:200],
                     "schema": t.get("inputSchema") or {"type": "object", "properties": {}}}
            TOOLS.append(entry); BYNAME[tn] = entry
        report.append(f"{name}: {len(tools)} tool" + (" (trusted)" if not gated else " (gated)"))
    return report

def mcp_status():
    if not _mcp_procs: return "Tidak ada server MCP terhubung. Tambah di config.json → mcp_servers, lalu /mcp connect."
    out = []
    for name, proc in _mcp_procs.items():
        alive = proc.poll() is None
        tools = [k for k in BYNAME if k.startswith("mcp__%s__" % name)]
        out.append(f"- {name}: {'hidup' if alive else 'mati'} · {len(tools)} tool")
    return "Server MCP:\n" + "\n".join(out)

SYSTEM = """Kamu OTAK FAJAR-AGENT, harness bug-bounty milik operator (username HackerOne: researcher).
Kamu SERBA-BISA lintas domain: web app, API/GraphQL, Android/iOS/mobile, thick-client, cloud/S3, network/infra, secret-leak —
pilih skill & pendekatan sesuai jenis aset target (asset_type). Jangan batasi diri ke web saja.
Kamu menjalankan SELURUH rangkaian hunting, TAPI di bawah KONTROL PENUH manusia lewat CHECKPOINT bertahap.
Untuk kerja PARALEL/besar, pakai `delegate` → beberapa SUB-AGEN (recon/dedup/analysis/discovery/report) bekerja bersamaan.

== MODEL KERJA: TIAP TAHAP OTONOM, CHECKPOINT DI ANTARA TAHAP ==
DI DALAM satu tahap: bekerja OTONOM penuh — panggil semua tool yg perlu berturut-turut untuk menuntaskan tahap itu tanpa nanya (untuk tool AMAN). Jangan berhenti di tengah tahap.
Setelah SATU tahap tuntas:
  1) lapor hasil ringkas berlabel [FAKTA]/[HIPOTESIS],
  2) tulis baris: "CHECKPOINT <tahap sekarang> selesai → lanjut ke <tahap berikut>? balas 'lanjut' / 'stop' / arahan lain",
  3) BERHENTI (jangan panggil tool lagi giliran itu).
Lanjut ke tahap berikutnya HANYA setelah manusia menjawab 'lanjut' (atau arahan spesifik). Jangan pernah loncati tahap.

== KAPAN MULAI (WAJIB — jangan langsung nembak tool) ==
JANGAN panggil tool apa pun untuk sapaan/obrolan/pertanyaan ringan ("halo", "hai", "kamu bisa apa", "ini program apa"). Untuk itu: balas SINGKAT & ramah, sebutkan target yg sedang dipegang, lalu TANYA apakah mau mulai — TANPA tool, lalu berhenti.
Mulai TAHAP 1 (HUNTING BRIEF) & pemanggilan tool HANYA bila user jelas menyuruh mulai: "mulai", "mulai hunting", "gas", "cari", "recon", "scope-gate", atau mengirim goal-saran; atau "lanjut" untuk tahap berikutnya. Kalau ragu, TANYA dulu, jangan asal jalan.

== GAYA TULIS (WAJIB — rapi seperti asisten pro) ==
Tulis ringkas & jelas: prosa pendek + bullet "-" seperlunya. JANGAN pakai heading markdown bertingkat (#, ##, ###) atau tanda pagar berlebihan. Tebalkan hanya istilah kunci. Tandai klaim [FAKTA]/[HIPOTESIS]. Akhiri tiap tahap dengan SATU baris: "CHECKPOINT <tahap> selesai → <opsi>? balas 'lanjut'/'stop'/pilihan".
JANGAN pernah menyalin/echo isi tool atau skill ke dalam jawaban — olah jadi analisis singkat milikmu. Hasil tool untuk dipakai bernalar, bukan ditampilkan mentah. Panggil tiap tool seperlunya saja; jangan memanggil tool yg sama berulang.

== MEKANISME TARGET (bila ada blok [TARGET CONTEXT] dari TUI) ==
[TARGET CONTEXT] = sumber scope RESMI. JANGAN program_detail/list_programs untuk cari ulang target itu. Alur khusus, terarah pada HASIL nyata:

TAHAP 1 — HUNTING BRIEF (otonom penuh; jalankan tool aman berturut-turut TANPA nanya, lalu SINTESIS):
  Panggil (SENYAP — jangan salin/echo hasil mentahnya ke jawaban): memory_search(nama+aset) · load_skill sesuai skill_rute · dedup(handle/url) · (opsional) recon(profile=passive) apex.
  Tiap tool dipanggil SEKALI seperlunya — JANGAN ulang tool yg sama, JANGAN panggil program_detail/list_programs (scope sudah ada).
  Setelah tool selesai, tulis HANYA "HUNTING BRIEF" hasil olahanmu (bukan salinan skill/tool), format bersih:
    Target & permukaan: 1-2 kalimat per jenis aset yg relevan.
    Sudah dilaporkan (dari dedup): kelas/endpoint yg DIBUANG (biar anti-dup).
    Hipotesis prioritas (3-5, NOVEL & impact tinggi, hindari yg recon-findable/sudah-dilaporkan). Tiap baris:
       [#] aset/endpoint — kelas-bug — uji 1-variabel — sinyal sukses — dampak — kenapa mungkin belum-dup
  Tutup: "CHECKPOINT tahap 1 selesai → dalami hipotesis #? / recon aktif (butuh izin)? / lanjut?"

TAHAP 2 — EKSEKUSI TERPANDU (per hipotesis terpilih): beri langkah uji 1-variabel PERSIS + baseline. Traffic aktif/exploit-PoC = DIKERJAKAN MANUSIA (kamu beri perintah persisnya). recon standard/deep & run_ext_tool = butuh izin (/yolo). Minta manusia tempel hasil.
TAHAP 3 — VERIFY & LAPORAN: analisa hasil yg ditempel → VERIFY-BEFORE-SUBMIT (impact, reproduksi 2×, anti-dup) → draf laporan via save_note kind=report.
TAHAP 4 — SUBMIT = HANYA MANUSIA (serahkan draf + instruksi).

== URUTAN TAHAP (bila TANPA target context) ==
0.SCOPE-GATE 1.PILIH TARGET (list/new_programs, utamakan sepi) 2.RECON PASIF 3.RECON AKTIF/EXT (izin) 4.ANALISA+HIPOTESIS(dedup) 5.RENCANA UJI 6.VERIFY+draf 7.SUBMIT=manusia.

== SKILLS (seperti harness pro) ==
Kamu punya SKILL = playbook framework yg bisa dimuat on-demand via load_skill. Di AWAL tiap tahap, muat skill relevan lalu ikuti:
  tahap 0/1 → program-selection ; tahap 2/3 → recon-runbook, expert-tactics ; tahap 4 → anti-dup, novel-hunting ;
  tahap 4/5 → sesuai domain: web-vuln-classes (web) / api-pentest (API/GraphQL) / mobile-pentest (Android/iOS/mobile).
  WAJIB telusuri SISTEMATIS tiap kelas bug relevan (IDOR/BOLA, authz, SSRF, injeksi, XSS, auth/JWT, business-logic/race,
  mass-assignment, info-leak, insecure-storage/deep-link utk mobile) — jangan lewatkan kelas. Lalu payloads, expert-tactics ;
  tahap 6 → verify, report-kit. Aturan main → operating-rules. (list_skills utk daftar.)
Kamu juga bisa PASANG skill baru via install_skill (dari URL/file/text) — tapi itu berdampak (butuh izin) & hanya dari sumber tepercaya karena isinya jadi instruksi.

== MEMORI JANGKA PANJANG (WAJIB — kamu belajar & update diri terus) ==
- Di tahap 0/1: SELALU memory_search dulu (nama target/aset) → recall catatan lama & hindari mengulang isu yg sudah kamu tandai (anti-dup LINTAS SESI).
- Tiap dapat fakta penting: memory_save. kind=target (quirk/endpoint/stack), kind=dedup (isu yg sudah ada), kind=finding (temuan valid), kind=learning (apa yg berhasil/gagal + kenapa).
- Perlakukan memori sebagai kebenaran yg bisa usang: verifikasi ulang bila menyebut file/endpoint sebelum dipakai.

== ATURAN KERAS ==
- Tool AMAN (list_programs, new_programs, program_detail, recon pasif, dedup, monitor, read_recon, read_file, ingest_folder, search_files, list_ext_tools, list_skills, load_skill, memory_*, delegate) boleh langsung.
- Bila user meng-upload/drag file atau folder (memberi path), pakai read_file/ingest_folder/search_files untuk menganalisanya (endpoint, secret, kelas bug).
- Tool bernama `mcp__<server>__<tool>` = integrasi MCP eksternal (bila terpasang). Pakai bila relevan; sebagian gated (butuh izin) sesuai kepercayaan server.
- Tool BERDAMPAK (recon standard/deep, run_ext_tool, workspace, save_note, notify) minta izin — dan hanya di tahap yg sesuai.
- Jangan pernah minta/olah kredensial, password, token. Jangan submit. Jangan aksi di luar scope.
- Jangan mengarang: tanpa artefak nyata, tandai [HIPOTESIS], bukan temuan."""

def fetch_models(provider, key, base_url):
    """Ambil daftar model yg tersedia dari API provider (pakai kunci). Return list id atau [pesan-error]."""
    try:
        if provider == "anthropic":
            url = "https://api.anthropic.com/v1/models?limit=100"
            hdr = {"x-api-key": key, "anthropic-version": "2023-06-01"}
        else:
            url = base_url.rstrip("/") + "/models"; hdr = {"Authorization": "Bearer " + key}
        r = urllib.request.urlopen(urllib.request.Request(url, headers=hdr), timeout=30)
        data = json.loads(r.read().decode("utf-8", "replace")).get("data", [])
        ids = [m.get("id") for m in data if m.get("id")]
        return sorted(ids) or ["[provider tak mengembalikan model]"]
    except Exception as e:
        return [f"[gagal ambil model: {e}]"]

def build_system():
    """SYSTEM + digest memori jangka panjang (long-context recall tiap panggilan)."""
    dg = mem_digest()
    return SYSTEM + (("\n\n== MEMORI TERSIMPAN (indeks; pakai memory_search utk isi) ==\n" + dg) if dg else "")

# ---------------- provider adapters ----------------
def _http_json(url, headers, payload, timeout=180, retries=3):
    """POST JSON dgn retry pada error transient (429/5xx/timeout/koneksi) + backoff."""
    body = json.dumps(payload).encode()
    last = ""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, data=body, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode("utf-8", "replace"))
        except urllib.error.HTTPError as e:
            msg = e.read().decode("utf-8", "replace")[:400]; last = f"[LLM API {e.code}] {msg}"
            if e.code in (429, 500, 502, 503, 504, 529) and attempt < retries - 1:
                import time; time.sleep(2 ** attempt + 1); continue
            raise SystemExit(last)
        except Exception as e:
            last = f"[LLM koneksi gagal] {e}"
            if attempt < retries - 1:
                import time; time.sleep(2 ** attempt + 1); continue
            raise SystemExit(last)
    raise SystemExit(last or "[LLM gagal]")

def _toolschema(tools, provider):
    tl = tools or TOOLS
    if provider == "anthropic":
        return [{"name": t["name"], "description": t["desc"], "input_schema": t["schema"]} for t in tl]
    return [{"type": "function", "function": {"name": t["name"], "description": t["desc"], "parameters": t["schema"]}} for t in tl]

def chat_anthropic(messages, model, key, system=None, tools=None):
    r = _http_json("https://api.anthropic.com/v1/messages",
                   {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                   {"model": model, "max_tokens": 3072, "system": system if system is not None else build_system(),
                    "messages": messages, "tools": _toolschema(tools, "anthropic")})
    text, calls = "", []
    for b in r.get("content", []):
        if b.get("type") == "text": text += b.get("text", "")
        elif b.get("type") == "tool_use": calls.append({"id": b["id"], "name": b["name"], "input": b.get("input", {})})
    u = r.get("usage", {}) or {}
    return {"text": text, "calls": calls, "raw": r.get("content", []), "stop": r.get("stop_reason"),
            "usage": {"in": u.get("input_tokens", 0), "out": u.get("output_tokens", 0)}}

def chat_openai(messages, model, key, base_url, system=None, tools=None):
    msgs = list(messages); sysp = system if system is not None else build_system()
    if msgs and msgs[0].get("role") == "system": msgs = [{"role": "system", "content": sysp}] + msgs[1:]
    else: msgs = [{"role": "system", "content": sysp}] + msgs
    r = _http_json(base_url.rstrip("/") + "/chat/completions",
                   {"Authorization": "Bearer " + key, "content-type": "application/json"},
                   {"model": model, "messages": msgs, "tools": _toolschema(tools, "openai"), "max_tokens": 3072})
    msg = r["choices"][0]["message"]
    calls = []
    for c in (msg.get("tool_calls") or []):
        try: args = json.loads(c["function"].get("arguments") or "{}")
        except Exception: args = {}
        calls.append({"id": c["id"], "name": c["function"]["name"], "input": args})
    u = r.get("usage", {}) or {}
    return {"text": msg.get("content") or "", "calls": calls, "raw": msg, "stop": r["choices"][0].get("finish_reason"),
            "usage": {"in": u.get("prompt_tokens", 0), "out": u.get("completion_tokens", 0)}}


# ---------------- agent core (dipakai CLI & TUI) ----------------
def is_gated(name, args):
    """True bila aksi berdampak/aktif (kirim traffic atau tulis/keluar)."""
    if BYNAME[name]["gated"]: return True
    if name == "recon" and args.get("profile") in ("standard", "deep"): return True
    return False

def execute_tool(name, args, allow_gated=False, confirm=None):
    """Jalankan satu tool. Untuk aksi gated: pakai confirm(name,args)->bool bila ada, else allow_gated."""
    if name not in BYNAME: return f"[tool '{name}' tak dikenal]"
    if is_gated(name, args):
        ok = confirm(name, args) if confirm is not None else allow_gated
        if not ok:
            return f"[GATE] aksi berdampak '{name}' butuh izin manusia — tidak dijalankan. (izinkan lalu balas 'lanjut')"
    try: return BYNAME[name]["fn"](**args)
    except TypeError as e: return f"[arg salah: {e}]"
    except Exception as e: return f"[error: {e}]"

def new_messages(is_anth):
    return [] if is_anth else [{"role": "system", "content": SYSTEM}]

def _append_assistant(messages, resp, is_anth):
    messages.append({"role": "assistant", "content": resp["raw"]} if is_anth else resp["raw"])

def _append_results(messages, results, is_anth):
    if is_anth:
        messages.append({"role": "user", "content": [{"type": "tool_result", "tool_use_id": cid, "content": out} for cid, out in results]})
    else:
        for cid, out in results:
            messages.append({"role": "tool", "tool_call_id": cid, "content": out})

def model_window(model):
    m = (model or "").lower()
    if "claude" in m: return 200000
    if "gpt-4o" in m or "gpt-4.1" in m or "o1" in m or "o3" in m: return 128000
    if "glm" in m: return 128000
    if "gemini" in m: return 1000000
    if "llama" in m or "mistral" in m or "qwen" in m: return 32000
    return 128000

def estimate_ctx(messages):
    """Perkiraan kasar token konteks (≈ 4 char/token). Fallback bila API tak kirim usage."""
    total = 0
    for msg in messages:
        c = msg.get("content")
        total += len(c) if isinstance(c, str) else len(json.dumps(c, ensure_ascii=False, default=str))
    return total // 4

def summarize(messages, provider, model, key, base_url):
    """Panggilan ringkas TANPA tools → state percakapan yg padat (untuk auto-compact)."""
    ask = ("Ringkas SELURUH percakapan ini jadi STATUS padat yg cukup untuk melanjutkan pekerjaan tanpa kehilangan konteks: "
           "target & scope, tahap sekarang, temuan/[FAKTA], hipotesis aktif, hasil dedup, dan langkah berikutnya. Maks 350 kata.")
    try:
        if provider == "anthropic":
            r = _http_json("https://api.anthropic.com/v1/messages",
                           {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                           {"model": model, "max_tokens": 1024, "system": "Kamu peringkas konteks yg presisi.",
                            "messages": messages + [{"role": "user", "content": ask}]})
            return "".join(b.get("text", "") for b in r.get("content", []) if b.get("type") == "text")
        else:
            msgs = [x for x in messages if x.get("role") != "system"] + [{"role": "user", "content": ask}]
            r = _http_json(base_url.rstrip("/") + "/chat/completions",
                           {"Authorization": "Bearer " + key, "content-type": "application/json"},
                           {"model": model, "messages": [{"role": "system", "content": "Kamu peringkas konteks yg presisi."}] + msgs, "max_tokens": 1024})
            return r["choices"][0]["message"].get("content") or ""
    except Exception as e:
        return f"[auto-compact gagal meringkas: {e}]"

def compact(messages, provider, model, key, base_url):
    """Ganti percakapan lama dgn 1 ringkasan + pesan terakhir → hemat konteks (auto-compacting)."""
    is_anth = provider == "anthropic"
    summary = summarize(messages, provider, model, key, base_url)
    tail = messages[-1:] if messages and messages[-1].get("role") == "user" else []
    out = new_messages(is_anth)
    out.append({"role": "user", "content": "[RINGKASAN KONTEKS SEBELUMNYA — lanjutkan dari sini]\n" + summary})
    out.extend(tail)
    return out

ACTIVITY = {"list_programs": "mencari program", "new_programs": "cek program baru", "program_detail": "membaca scope",
            "recon": "recon", "dedup": "cek duplikat", "monitor": "memantau subdomain", "read_recon": "membaca hasil recon",
            "list_ext_tools": "lihat ext-tools", "run_ext_tool": "menjalankan ext-tool", "save_note": "menulis catatan",
            "workspace": "menyiapkan workspace", "notify": "mengirim notif", "memory_search": "mengingat (memori)",
            "memory_save": "menyimpan memori", "memory_list": "lihat memori", "list_skills": "lihat skills", "load_skill": "memuat skill"}

def agent_turn(messages, provider, model, key, base_url, emit, allow_gated=False, confirm=None, on_meta=None,
               ctx_window=0, auto_compact=True, compact_at=0.75, max_iters=10):
    """Jalankan SATU tahap: model kerja otonom (banyak tool) sampai berhenti di checkpoint (end_turn).
    emit(kind, text) kind in {llm, tool, result, err}. on_meta(dict) opsional utk status bar (activity/tokens/ctx).
    Auto-compact: bila estimasi konteks > compact_at*window, ringkas otomatis (real, via summarize())."""
    is_anth = provider == "anthropic"
    window = ctx_window or model_window(model)
    _CTX.clear(); _CTX.update({"provider": provider, "model": model, "key": key, "base_url": base_url, "allow_gated": allow_gated})
    def meta(d):
        if on_meta:
            try: on_meta(d)
            except Exception: pass
    for _ in range(max_iters):
        # --- auto-compacting REAL saat konteks mendekati penuh ---
        if auto_compact and window and estimate_ctx(messages) > compact_at * window and len(messages) > 4:
            emit("llm", f"[auto-compact] konteks ~{estimate_ctx(messages)} tok > {int(compact_at*100)}% dari {window} — meringkas…")
            meta({"activity": "auto-compact"})
            messages[:] = compact(messages, provider, model, key, base_url)
            meta({"compacted": True, "ctx": estimate_ctx(messages), "window": window})
        meta({"activity": "berpikir"})
        try:
            resp = chat_anthropic(messages, model, key) if is_anth else chat_openai(messages, model, key, base_url)
        except SystemExit as e:
            emit("err", str(e)); meta({"activity": "idle"}); return messages
        if resp.get("usage"):
            meta({"tokens": resp["usage"], "ctx": resp["usage"].get("in", 0) or estimate_ctx(messages), "window": window})
        if resp["text"].strip(): emit("llm", resp["text"].strip())
        _append_assistant(messages, resp, is_anth)
        if not resp["calls"]:
            meta({"activity": "checkpoint"}); return messages  # tahap selesai — tunggu manusia
        results = []
        for c in resp["calls"]:
            meta({"activity": ACTIVITY.get(c["name"], c["name"])})
            emit("tool", f"{c['name']} {json.dumps(c['input'], ensure_ascii=False)}")
            out = execute_tool(c["name"], c["input"], allow_gated, confirm)
            emit("result", out)
            results.append((c["id"], out))
        _append_results(messages, results, is_anth)
    emit("err", "[batas iterasi tahap tercapai]"); meta({"activity": "idle"})
    return messages

def run_agent(goal, provider, model, key, base_url, auto, max_stages=20):
    """CLI: satu goal, jalan bertahap. Antar tahap, model berhenti; kita otomatis 'lanjut' sampai model diam."""
    def emit(kind, text):
        pre = {"llm": "\n\033[36m[LLM]\033[0m ", "tool": "  \033[33m→\033[0m ", "result": "     ", "err": "\033[31m"}[kind]
        body = text if kind == "llm" else (text[:500].replace("\n", "\n     ") + (" …" if len(text) > 500 else ""))
        print(pre + body + ("\033[0m" if kind == "err" else ""))
    def confirm(name, args):
        if auto:
            print(f"  [--auto] GATE '{name}' DITOLAK (pakai -i tanpa --auto untuk izin)."); return False
        return input(f"  [GATE] izinkan aksi berdampak '{name}' {args}? (y/N) ").strip().lower() == "y"
    is_anth = provider == "anthropic"
    messages = new_messages(is_anth); messages.append({"role": "user", "content": goal})
    # CLI one-shot: jalan sampai model berhenti tanpa tool (satu tahap). Tahap berikut lewat -i.
    agent_turn(messages, provider, model, key, base_url, emit, allow_gated=False, confirm=confirm)

def do_setup():
    c = load_cfg(); os.makedirs(CFG_DIR, exist_ok=True)
    print("Setup LLM (kosongkan = biarkan). JANGAN tempel kunci di chat publik.")
    for k, prompt in [("llm_provider", "provider [anthropic/openai]"), ("llm_model", "model (mis. claude-sonnet-5 / gpt-4o-mini)"),
                      ("llm_base_url", "base_url (openai-compatible saja, mis. http://localhost:11434/v1)"), ("llm_api_key", "api_key")]:
        v = input(f"  {prompt} [{c.get(k,'')}]: ").strip()
        if v: c[k] = v
    json.dump(c, open(CFG, "w", encoding="utf-8"), indent=1)
    try: os.chmod(CFG, 0o600)
    except Exception: pass
    print(f"[+] tersimpan -> {CFG} (chmod 600)")

def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("goal", nargs="*")
    ap.add_argument("-i", "--interactive", action="store_true")
    ap.add_argument("--auto", action="store_true", help="jalankan tool AMAN tanpa nanya (tool GATE tetap ditolak)")
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--models", action="store_true", help="tampilkan model yg tersedia dari provider (pakai kunci)")
    a = ap.parse_args()
    if a.setup: do_setup(); return
    c = load_cfg()
    provider = cfg_get(c, "llm_provider", "LLM_PROVIDER", "anthropic").lower()
    model = cfg_get(c, "llm_model", "LLM_MODEL", "claude-sonnet-5" if provider == "anthropic" else "gpt-4o-mini")
    base_url = cfg_get(c, "llm_base_url", "LLM_BASE_URL", "https://api.openai.com/v1")
    key = cfg_get(c, "llm_api_key", "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY")
    if not key:
        sys.exit("[!] belum ada kunci API. Jalankan:  python3 llm_agent.py --setup   (atau set env ANTHROPIC_API_KEY/OPENAI_API_KEY)")
    if a.models:
        print(f"[model tersedia @ {provider}]"); [print("  " + m) for m in fetch_models(provider, key, base_url)]; return
    print(f"[llm_agent] provider={provider} model={model}  (tool AMAN otonom; aksi berdampak butuh izin)")
    if a.interactive:
        print("mode chat BERTAHAP — beri goal; tiap tahap berhenti di CHECKPOINT, ketik 'lanjut' utk tahap berikut. 'exit' keluar.")
        def emit(kind, text):
            pre = {"llm": "\n\033[36m[LLM]\033[0m ", "tool": "  \033[33m→\033[0m ", "result": "     ", "err": "\033[31m"}[kind]
            body = text if kind == "llm" else (text[:500].replace("\n", "\n     ") + (" …" if len(text) > 500 else ""))
            print(pre + body + ("\033[0m" if kind == "err" else ""))
        def confirm(name, args):
            if a.auto: print(f"  [--auto] GATE '{name}' DITOLAK."); return False
            return input(f"  [GATE] izinkan aksi berdampak '{name}' {args}? (y/N) ").strip().lower() == "y"
        is_anth = provider == "anthropic"; messages = new_messages(is_anth)
        while True:
            try: g = input("\n\033[32mkamu>\033[0m ").strip()
            except (EOFError, KeyboardInterrupt): break
            if g.lower() in ("exit", "quit", "q", ""): break
            messages.append({"role": "user", "content": g})
            agent_turn(messages, provider, model, key, base_url, emit, allow_gated=False, confirm=confirm)
        return
    goal = " ".join(a.goal).strip()
    if not goal:
        sys.exit('pakai:  python3 llm_agent.py "cari 3 program api sepi lalu recon pasif yg pertama"   |   -i utk chat')
    run_agent(goal, provider, model, key, base_url, a.auto)

if __name__ == "__main__":
    main()

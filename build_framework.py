#!/usr/bin/env python3
"""build_framework.py — rakit ulang bugbounty-framework/ + setup-bugbounty.sh + zip dari sumber kanonik.

Sumber kanonik:
  - bb.py                (root)
  - tools/*.py           (root/tools) -> termasuk llm_agent.py yg baru
  - 13 dokumen framework (root *.md, daftar di DOCS)
  - README.md + TARGET-WORKSPACE-TEMPLATE/  (hanya ada di folder -> dipertahankan)

Installer di-generate dengan MEMPERTAHANKAN head (7 baris) & TAIL toolchain apa adanya,
lalu meregenerasi semua blok embed file di tengah dari isi folder (satu sumber kebenaran).
"""
import os, shutil, zipfile

ROOT = os.path.dirname(os.path.abspath(__file__))
FW = os.path.join(ROOT, "bugbounty-framework")
SETUP = os.path.join(ROOT, "setup-bugbounty.sh")
MARK = "___BBEOF___"
TAIL_ANCHOR = "chmod +x tools/*.py bb.py"

TOOLS = ["daily-target-finder.py", "recon.py", "asset-monitor.py", "dedup.py", "doctor.py",
         "pipeline.py", "naabutonmap.py", "bbtui.py", "llm_agent.py", "telegram_bot.py"]  # whitelist
DOCS = ["FRAMEWORK-BUGBOUNTY-AI.md", "AI-OPERATING-RULES.md", "ANTI-DUP-PLAYBOOK.md", "NOVEL-HUNTING.md",
        "EXPERT-TACTICS.md", "AUTONOMOUS-OPERATOR.md", "MONITOR-WORKFLOW.md", "RECON-RUNBOOK.md",
        "PAYLOAD-CHEATSHEET.md", "REPORT-KIT.md", "VERIFY-BEFORE-SUBMIT.md", "PROGRAM-SELECTION.md", "LEARNING-LOG.md",
        "WEB-VULN-CLASSES.md", "API-PENTEST.md", "MOBILE-PENTEST.md"]

def sync_canonical():
    os.makedirs(os.path.join(FW, "tools"), exist_ok=True)
    shutil.copy2(os.path.join(ROOT, "bb.py"), os.path.join(FW, "bb.py"))
    # buang tool non-framework yg mungkin nyangkut di folder
    for f in list(os.listdir(os.path.join(FW, "tools"))):
        if f.endswith(".py") and f not in TOOLS:
            os.remove(os.path.join(FW, "tools", f))
    for f in TOOLS:
        src = os.path.join(ROOT, "tools", f)
        if os.path.exists(src): shutil.copy2(src, os.path.join(FW, "tools", f))
        else: print("  [!] tool hilang:", f)
    for d in DOCS:
        src = os.path.join(ROOT, d)
        if os.path.exists(src): shutil.copy2(src, os.path.join(FW, d))
        else: print("  [!] dok hilang:", d)
    # installer lintas-OS (PowerShell) + bootstrap web-install
    for extra in ("setup-bugbounty.ps1", "install.sh", "install.ps1"):
        sp = os.path.join(ROOT, extra)
        if os.path.exists(sp): shutil.copy2(sp, os.path.join(FW, extra))

def block(relpath, content):
    if MARK in content:
        raise SystemExit(f"[!] {relpath} mengandung {MARK} — installer akan rusak.")
    return f"cat > {relpath} <<'{MARK}'\n{content}\n{MARK}\n"

def gen_installer():
    txt = open(SETUP, encoding="utf-8").read()
    head = txt[:txt.index("cat > ")]                       # shebang + setup args + cd + mkdir -p .
    tail = txt[txt.index(TAIL_ANCHOR):]                    # chmod + toolchain install .. EOF
    mid = []
    # 1) dokumen framework (urutan DOCS) + README
    for d in DOCS + ["README.md"]:
        p = os.path.join(FW, d)
        if os.path.exists(p): mid.append(block(d, open(p, encoding="utf-8").read()))
    # 2) entry bb.py
    mid.append(block("bb.py", open(os.path.join(FW, "bb.py"), encoding="utf-8").read()))
    # 3) tools/*.py
    mid.append("mkdir -p tools\n")
    for f in sorted(os.listdir(os.path.join(FW, "tools"))):
        if f.endswith(".py"):
            mid.append(block(f"tools/{f}", open(os.path.join(FW, "tools", f), encoding="utf-8").read()))
    # 4) TARGET-WORKSPACE-TEMPLATE
    tpl = os.path.join(FW, "TARGET-WORKSPACE-TEMPLATE")
    if os.path.isdir(tpl):
        for dirpath, _dn, files in os.walk(tpl):
            rel = os.path.relpath(dirpath, FW).replace("\\", "/")
            mid.append(f"mkdir -p {rel}\n")
            for f in sorted(files):
                r = f"{rel}/{f}"
                if f == ".gitkeep": mid.append(f"touch {r}\n")
                else: mid.append(block(r, open(os.path.join(dirpath, f), encoding="utf-8").read()))
    out = head + "".join(mid) + tail
    open(SETUP, "w", encoding="utf-8", newline="\n").write(out)
    # mirror ke dalam folder juga
    shutil.copy2(SETUP, os.path.join(FW, "setup-bugbounty.sh"))
    return len(mid)

def make_zip():
    # bersihkan __pycache__
    for dp, dn, _f in os.walk(FW):
        for d in list(dn):
            if d == "__pycache__": shutil.rmtree(os.path.join(dp, d), ignore_errors=True)
    zp = os.path.join(ROOT, "bugbounty-framework.zip")
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for dp, _dn, files in os.walk(FW):
            for f in files:
                fp = os.path.join(dp, f)
                z.write(fp, os.path.relpath(fp, ROOT))
    return zp, os.path.getsize(zp)

if __name__ == "__main__":
    sync_canonical()
    n = gen_installer()
    zp, sz = make_zip()
    total = sum(len(files) for _dp, _dn, files in os.walk(FW))
    print(f"[+] folder: {FW}  ({total} file)")
    print(f"[+] installer: {SETUP}  ({os.path.getsize(SETUP)} bytes, {n} blok)")
    print(f"[+] zip: {zp}  ({sz} bytes)")

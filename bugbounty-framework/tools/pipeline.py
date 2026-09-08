#!/usr/bin/env python3
"""pipeline — rangkaian OTOMATIS (buat cron): finder -> program BARU -> simpan scope.md + dedup + recon pasif -> notif.

Alur:
  1) daily-target-finder  (update ~/bb-targets/latest.json, deteksi program & aset baru)
  2) untuk tiap PROGRAM BARU: buat workspace + scope.md (tersimpan), jalankan dedup, recon --profile passive
  3) notif ringkasan (env BBPIPE_WEBHOOK / BBPIPE_TG_TOKEN+BBPIPE_TG_CHAT)

Pakai:  python3 pipeline.py [--max N] [--profile passive|standard]
Cron :  0 8 * * *  python3 ~/bugbounty-framework/tools/pipeline.py >> ~/bb-pipeline.log 2>&1
Butuh: python3 + tool (recon/dedup/finder di folder yg sama).
"""
import os, re, sys, json, argparse, subprocess, urllib.request, urllib.parse

D = os.path.dirname(os.path.abspath(__file__))
def tool(s): return os.path.join(D, s)
def run(script, args): return subprocess.run([sys.executable, tool(script)] + args)

def notify(text):
    hook = os.environ.get("BBPIPE_WEBHOOK"); tok = os.environ.get("BBPIPE_TG_TOKEN"); chat = os.environ.get("BBPIPE_TG_CHAT")
    try:
        if hook: urllib.request.urlopen(urllib.request.Request(hook, data=json.dumps({"content": text[:1900]}).encode(), headers={"Content-Type": "application/json"}), timeout=15)
        if tok and chat: urllib.request.urlopen("https://api.telegram.org/bot%s/sendMessage?%s" % (tok, urllib.parse.urlencode({"chat_id": chat, "text": text[:4000]})), timeout=15)
    except Exception as e: print("  [!] notif gagal:", e)

def seed_scope(name, pr, wsdir):
    dest = os.path.join(wsdir, re.sub(r"\W", "_", name)[:40])
    os.makedirs(dest, exist_ok=True)
    with open(os.path.join(dest, "scope.md"), "w", encoding="utf-8") as fh:
        fh.write(f"# Scope — {name} [{pr.get('platform')}]\n- URL: {pr.get('url','')}\n"
                 f"- Reward: min={pr.get('bounty_min')} max={pr.get('bounty_max')}\n\n## Wildcard\n"
                 + "\n".join("- " + w for w in pr.get("wild", [])) + "\n\n## Scope\n"
                 + "\n".join("- " + s for s in pr.get("scope", [])))
    return dest

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=5); ap.add_argument("--profile", default="passive")
    a = ap.parse_args()
    out = os.path.expanduser(os.environ.get("BBTF_OUT", "~/bb-targets"))
    ws = os.path.expanduser("~/bb-workspaces")
    print("==> [1] finder"); run("daily-target-finder.py", [])
    try:
        data = json.load(open(os.path.join(out, "latest.json"), encoding="utf-8"))
    except Exception as e:
        sys.exit(f"[!] tak bisa baca latest.json: {e}")
    new = data.get("new_programs", []); changed = data.get("scope_changed", [])
    print(f"==> [2] program baru: {len(new)} | scope-change: {len(changed)}")
    done = []
    for pr in new[:a.max]:
        name = pr.get("name") or "target"
        dest = seed_scope(name, pr, ws)
        wild = pr.get("wild", []); dom = next((w.lstrip("*.") for w in wild if "." in w.lstrip("*.")), "")
        url = pr.get("url", "")
        print(f"    - {name}: scope.md -> {dest}")
        if url: run("dedup.py", [url, "--out", os.path.join(dest, "known-issues.md")])
        if dom: run("recon.py", [dom, "--profile", a.profile, "--out", ws])
        done.append(name)
    msg = f"[pipeline] {len(new)} program baru, {len(changed)} scope-change. Diproses: {', '.join(done) or '-'}"
    print("==> [3] " + msg); notify(msg)

if __name__ == "__main__":
    main()

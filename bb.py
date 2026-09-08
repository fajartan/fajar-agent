#!/usr/bin/env python3
"""bb — SATU pintu untuk semua fitur bug bounty (TUI + finder + recon + monitor + dedup + doctor).

Pakai:
  python3 bb.py                      buka TUI (browse 5 platform + recon/monitor/dedup/workspace/notif/ext-tools)
  python3 bb.py tui
  python3 bb.py find                 cari target harian  -> ~/bb-targets/latest.md
  python3 bb.py recon <domain> [--profile passive|standard|deep] [--cookie ..] [--header ..]
  python3 bb.py monitor <domain>     pantau subdomain baru
  python3 bb.py dedup <handle|url> [--file hacktivity.txt]
  python3 bb.py pipeline [--max N]   OTOMATIS (cron): finder -> program baru -> scope.md + dedup + recon
  python3 bb.py llm "goal"           OTAK LLM otonom: pilih & jalankan fitur sendiri (butuh apikey; --setup dulu)
  python3 bb.py llm -i               chat interaktif dgn agent LLM
  python3 bb.py llm --setup          simpan apikey/model LLM ke config
  python3 bb.py telegram             FAJAR-AGENT via Telegram (bot; butuh telegram_token+telegram_chat)
  python3 bb.py doctor               cek kesiapan tool
  python3 bb.py update               perbarui FAJAR-AGENT ke versi terbaru (git pull / unduh arsip)
  python3 bb.py --version            tampilkan versi
  python3 bb.py help

Filter pencarian (env, dipakai find/pipeline; atau Settings di TUI):
  BBTF_MIN_BOUNTY=500     min reward (hanya nyaring Bugcrowd/YWH/Intigriti; H1 tak berangka)
  BBTF_WILDCARD=1         wajib punya wildcard
  BBTF_ASSET_TYPE=android fokus jenis: web / android / ios / api / mobile (pisah koma)
  BBTF_PLATFORMS=hackerone,bugcrowd,yeswehack,intigriti,federacy
Program 'sepi/minim-dupe' = utamakan bagian [BARU] (program/aset baru) + jenis niche (android/ios/api).
Semua perintah meneruskan argumen ke tool di tools/.
"""
import os, sys, subprocess

VERSION = "1.1"
D = os.path.dirname(os.path.abspath(__file__))

def _version():
    sha = ""
    try:  # tampilkan commit pendek bila ini git clone
        if os.path.isdir(os.path.join(D, ".git")):
            sha = " (" + subprocess.run(["git", "-C", D, "rev-parse", "--short", "HEAD"],
                                        capture_output=True, text=True).stdout.strip() + ")"
    except Exception:
        pass
    print(f"FAJAR-AGENT v{VERSION}{sha}  |  {D}")
    print("update:  fajar update   |   repo: https://github.com/fajartan/fajar-agent")
TOOLS = os.path.join(D, "tools") if os.path.isdir(os.path.join(D, "tools")) else D
MAP = {"tui": "bbtui.py", "find": "daily-target-finder.py", "finder": "daily-target-finder.py",
       "recon": "recon.py", "monitor": "asset-monitor.py", "dedup": "dedup.py", "doctor": "doctor.py",
       "pipeline": "pipeline.py", "auto": "pipeline.py", "llm": "llm_agent.py", "ai": "llm_agent.py", "agent": "llm_agent.py",
       "telegram": "telegram_bot.py", "tg": "telegram_bot.py", "bot": "telegram_bot.py",
       "update": "update.py", "upgrade": "update.py"}
HELP = __doc__

def main():
    args = sys.argv[1:]
    cmd = (args[0] if args else "tui").lower()
    if cmd in ("--version", "-v", "version"):
        _version(); return
    if cmd in ("help", "-h", "--help"):
        print(HELP); return
    script = MAP.get(cmd)
    if not script:
        print(f"[!] perintah '{cmd}' tidak dikenal.\n"); print(HELP); sys.exit(1)
    path = os.path.join(TOOLS, script)
    if not os.path.exists(path):
        sys.exit(f"[!] tidak ketemu: {path}")
    try:
        sys.exit(subprocess.call([sys.executable, path] + args[1:]))
    except KeyboardInterrupt:
        sys.exit(130)   # anak menangani Ctrl+C sendiri; induk keluar diam-diam

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(130)

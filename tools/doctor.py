#!/usr/bin/env python3
"""doctor — cek kesiapan semua tool bug hunting (mana terpasang / hilang) + saran perbaikan.
Pakai: python3 doctor.py
"""
import shutil, importlib.util, os

GO = ["subfinder", "httpx", "httpx-toolkit", "naabu", "dnsx", "nuclei", "katana", "chaos", "gau", "anew",
      "gf", "assetfinder", "waybackurls", "unfurl", "ffuf", "getJS", "mantra", "jsleak", "gowitness"]
PYC = ["uro", "wafw00f", "dirsearch", "arjun"]
SYS = ["nmap", "whatweb", "feroxbuster", "git", "jq"]
LIB = ["textual", "rich"]
WL = ["/usr/share/seclists", os.path.expanduser("~/seclists")]

def ok(x): return shutil.which(x) is not None
def libok(m):
    try: return importlib.util.find_spec(m) is not None
    except Exception: return False
def line(name, good): print(f"  [{'OK ' if good else ' X '}] {name}")

def main():
    print("== Go / recon tools ==");  [line(t, ok(t)) for t in GO]
    print("== Python CLI ==");        [line(t, ok(t)) for t in PYC]
    print("== Sistem ==");            [line(t, ok(t)) for t in SYS]
    print("== Library python ==");    [line(t, libok(t)) for t in LIB]
    print("== Wordlist ==");          line("SecLists", any(os.path.isdir(w) for w in WL))
    print("== API keys (opsional) =="); [line(k, bool(os.environ.get(k))) for k in ("CHAOS_KEY", "PDCP_API_KEY")]
    miss = [t for t in GO + PYC + SYS if not ok(t)] + [t for t in LIB if not libok(t)]
    print(f"\nRingkas: {len(miss)} komponen hilang" + (": " + ", ".join(miss) if miss else " — SEMUA SIAP"))
    if miss:
        print("Perbaiki: jalankan  bash setup-bugbounty.sh  (atau pasang manual komponen di atas).")
        print("  textual: pip install --user --break-system-packages textual")

if __name__ == "__main__":
    main()

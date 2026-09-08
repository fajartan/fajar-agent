#!/usr/bin/env python3
"""naabutonmap — ambil output naabu (host:port) lalu jalankan nmap -sVC per host.
Dipakai di RECON-RUNBOOK.md. Butuh nmap terpasang.
Contoh:  python3 naabutonmap.py -i naabu.txt -o nmap_out
"""
import argparse, os, subprocess, sys
from collections import defaultdict

def main():
    ap = argparse.ArgumentParser(description="naabu host:port -> nmap -sVC per host")
    ap.add_argument("-i", "--input", required=True, help="file output naabu (host:port per baris)")
    ap.add_argument("-o", "--outdir", default="nmap_out", help="folder hasil nmap")
    args = ap.parse_args()

    if not os.path.isfile(args.input):
        sys.exit(f"[!] input tidak ditemukan: {args.input}")

    hosts = defaultdict(set)
    with open(args.input) as f:
        for line in f:
            line = line.strip()
            if not line or ":" not in line:
                continue
            host, port = line.rsplit(":", 1)
            if port.isdigit():
                hosts[host].add(port)

    if not hosts:
        sys.exit("[!] tidak ada host:port valid di input")

    os.makedirs(args.outdir, exist_ok=True)
    for host, ports in hosts.items():
        plist = ",".join(sorted(ports, key=int))
        out = os.path.join(args.outdir, host.replace("/", "_"))
        print(f"[*] nmap {host} -> ports {plist}")
        try:
            subprocess.run(["nmap", "-sVC", "-Pn", "-p", plist, "-oA", out, host], check=False)
        except FileNotFoundError:
            sys.exit("[!] nmap belum terpasang")
    print(f"[+] selesai -> {args.outdir}")

if __name__ == "__main__":
    main()

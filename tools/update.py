#!/usr/bin/env python3
"""update - perbarui FAJAR-AGENT ke versi terbaru.

Logika: kalau folder instal adalah git clone (.git ada) -> `git pull`.
        selain itu -> unduh arsip repo & timpa file di tempat.
        Repo PUBLIC: pakai codeload. Repo PRIVATE: fallback ke `gh` (harus login).
Env: FAJAR_REPO (default fajartan/fajar-agent), FAJAR_BRANCH (default main).
Pakai:  fajar update   |   python3 bb.py update
"""
import os, sys, io, shutil, tarfile, tempfile, subprocess, urllib.request

REPO = os.environ.get("FAJAR_REPO", "fajartan/fajar-agent")
BRANCH = os.environ.get("FAJAR_BRANCH", "main")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # induk dari tools/ = folder instal

def _download():
    # 1) arsip publik (codeload) - jalan bila repo PUBLIC
    url = "https://codeload.github.com/%s/tar.gz/refs/heads/%s" % (REPO, BRANCH)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "fajar-agent-update"})
        return urllib.request.urlopen(req, timeout=90).read()
    except Exception as e:
        print("    arsip publik gagal (%s) -> coba gh (untuk repo private)" % e)
    # 2) fallback: gh api tarball (repo PRIVATE, butuh gh login)
    if shutil.which("gh"):
        try:
            p = subprocess.run(["gh", "api", "repos/%s/tarball/%s" % (REPO, BRANCH)], capture_output=True, timeout=120)
            if p.returncode == 0 and p.stdout:
                return p.stdout
            print("    gh gagal:", (p.stderr or b"").decode("utf-8", "replace")[:200])
        except Exception as e:
            print("    gh error:", e)
    return None

def main():
    print("==> FAJAR-AGENT update  (%s@%s)  di: %s" % (REPO, BRANCH, ROOT))
    if os.path.isdir(os.path.join(ROOT, ".git")):
        print("==> git clone terdeteksi -> git pull")
        sys.exit(subprocess.call(["git", "-C", ROOT, "pull", "--ff-only"]))
    data = _download()
    if not data:
        sys.exit("[!] gagal unduh arsip. Kalau repo private: pasang & login `gh` (gh auth login), atau jadikan repo public.")
    tmp = tempfile.mkdtemp()
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as t:
            t.extractall(tmp)
        src = next(os.path.join(tmp, d) for d in os.listdir(tmp) if os.path.isdir(os.path.join(tmp, d)))
        n = 0
        for r, _dn, files in os.walk(src):
            rel = os.path.relpath(r, src)
            dst = ROOT if rel == "." else os.path.join(ROOT, rel)
            os.makedirs(dst, exist_ok=True)
            for f in files:
                shutil.copy2(os.path.join(r, f), os.path.join(dst, f)); n += 1
        print("==> selesai. %d file diperbarui di %s" % (n, ROOT))
        print("    jalankan lagi:  fajar")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

if __name__ == "__main__":
    main()

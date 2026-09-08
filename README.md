# FAJAR-AGENT — Bug-Bounty Hunting Harness

Harness bug bounty bertenaga LLM: cari program (5 platform) → recon → analisa → hipotesis (anti-dup) → verifikasi → draf laporan, **bertahap dengan kontrol penuh manusia**. Dilengkapi TUI modern, memori jangka panjang, skills, dan integrasi ~40 tool eksternal.

> ⚠️ Untuk pengujian keamanan **yang diizinkan** saja (program bug bounty dalam scope). Agent tidak pernah submit laporan atau mengeksekusi exploit sendiri — itu tetap keputusan & tanggung jawab manusia.

## Instalasi (satu perintah → cukup ketik `fajar`)

**macOS / Linux**
```bash
curl -fsSL https://raw.githubusercontent.com/fajartan/fajar-agent/main/install.sh | sh
```
**Windows (PowerShell)**
```powershell
irm https://raw.githubusercontent.com/fajartan/fajar-agent/main/install.ps1 | iex
```
Installer mengunduh payload sendiri ke `~/.fajar-agent` (Windows: `%LOCALAPPDATA%\fajar-agent`), memasang `textual`, dan membuat perintah global **`fajar`**. Buka terminal baru lalu:
```
fajar            # TUI FAJAR-AGENT
fajar llm -i     # agent chat bertahap    ·    fajar find    ·    fajar telegram
```
> Ganti `fajartan/fajar-agent` dengan repo GitHub-mu (atau host `install.sh`/`install.ps1` di domain sendiri). `curl|sh` & `irm|iex` mengeksekusi skrip dari internet — sama seperti installer harness lain; pastikan sumber tepercaya.

### Alternatif — git clone (jalan langsung, tanpa build)
```bash
git clone https://github.com/fajartan/fajar-agent.git
cd fajar-agent
pip install --user textual rich
python3 bb.py          # Windows: python bb.py
```
Repo ini **flat** — `bb.py` + `tools/` + dokumen langsung di root; tak ada langkah build/extract. Inti FAJAR-AGENT = Python murni, jalan di **terminal apa pun** (PowerShell/CMD Windows, bash/zsh Linux/macOS). TUI, finder, LLM agent, Telegram, MCP native lintas-OS. Toolchain recon aktif (subfinder/nuclei/dll) berbasis Linux — di Windows pakai WSL.

### Kebutuhan
- Python 3.8+ (inti pakai stdlib). TUI butuh `textual` (`pip install --user textual`; Linux: tambah `--break-system-packages` bila perlu).
- Toolchain recon (subfinder/httpx/nuclei/dll): pasang manual (lihat `RECON-RUNBOOK.md`) — opsional; agent tetap jalan tanpanya.
- LLM agent butuh API key provider (Anthropic / OpenAI-compatible: Groq/OpenRouter/Ollama).

## Pakai
```bash
python3 bb.py                 # TUI (browse program + recon/monitor/dedup/ext-tools/LLM)
python3 bb.py find            # cari target harian -> ~/bb-targets/latest.md
python3 bb.py recon <domain>  # recon (passive|standard|deep)
python3 bb.py llm --setup     # simpan API key & model LLM
python3 bb.py llm -i          # FAJAR-AGENT chat bertahap (terminal)
python3 bb.py doctor          # cek kesiapan tool
```

Di TUI: `l` = FAJAR-AGENT chat (slash `/help`, `/yolo`, `/model`, `/resume`, `/skill install`, `/compact`, …), `x` = ext-tools, `s` = settings, `g` = jadwal cron, `?` = bantuan.

## Fitur utama
- **FAJAR-AGENT** — otak LLM bertahap (checkpoint "lanjut"), status bar real (token/konteks%/auto-compact), pilih model live dari provider, memori jangka panjang lintas sesi, skills (playbook) yang bisa **di-install**.
- **Finder 5 platform** (HackerOne/Bugcrowd/YesWeHack/Intigriti/Federacy) + skor QUIET anti-ramai + deteksi program baru.
- **Recon/monitor/dedup**, pipeline cron harian, integrasi ~40 ext-tool (nuclei/burp/sqlmap/ffuf/…).

Struktur repo flat: `bb.py`, `tools/`, dokumen `.md`, `TARGET-WORKSPACE-TEMPLATE/`, `install.sh`, `install.ps1`.

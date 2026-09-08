<#  FAJAR-AGENT web installer (Windows PowerShell).
    Pakai:  irm https://<HOST>/install.ps1 | iex
    Setelah itu cukup ketik:  fajar
    Ganti fajartan/fajar-agent (atau host sendiri) sebelum publikasi. #>
$ErrorActionPreference = "Stop"
$RepoRaw = if ($env:FAJAR_REPO) { $env:FAJAR_REPO } else { "https://raw.githubusercontent.com/fajartan/fajar-agent/main" }
$Dest    = if ($env:FAJAR_HOME) { $env:FAJAR_HOME } else { "$env:LOCALAPPDATA\fajar-agent" }
$Bin     = "$Dest\bin"

function Say($m){ Write-Host "==> $m" -ForegroundColor Yellow }

# 1) Python
$py = $null
foreach ($c in @("python","py","python3")) { if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break } }
if (-not $py) { Write-Host "[!] Python 3 tidak ada. Install dari https://python.org" -ForegroundColor Red; return }
Say "Python: $py"

# 2) unduh + ekstrak payload (zip) ke $Dest
Say "mengunduh FAJAR-AGENT -> $Dest"
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
$zip = "$Dest\payload.zip"
Invoke-WebRequest -UseBasicParsing "$RepoRaw/bugbounty-framework.zip" -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $Dest -Force
Remove-Item $zip -Force
$bb = "$Dest\bugbounty-framework\bb.py"
if (-not (Test-Path $bb)) { $bb = "$Dest\bb.py" }
if (-not (Test-Path $bb)) { Write-Host "[!] bb.py tak ketemu setelah ekstrak" -ForegroundColor Red; return }

# 3) dependensi TUI (best-effort)
try { & $py -m pip install --user --upgrade textual rich 2>$null } catch {}

# 4) launcher global 'fajar' (fajar.cmd) + tambah ke PATH user
New-Item -ItemType Directory -Force -Path $Bin | Out-Null
Set-Content -Path "$Bin\fajar.cmd" -Value "@echo off`r`n`"$py`" `"$bb`" %*" -Encoding ASCII
$u = [Environment]::GetEnvironmentVariable("Path","User")
if ($u -notlike "*$Bin*") { [Environment]::SetEnvironmentVariable("Path", "$u;$Bin", "User") }

Write-Host ""
Say "SELESAI. Buka terminal baru, lalu ketik:  fajar"
Write-Host "    fajar             # TUI FAJAR-AGENT"
Write-Host "    fajar llm -i      # agent chat bertahap   |   fajar find   |   fajar telegram"
Write-Host "[i] Recon aktif (subfinder/nuclei) = Linux; di Windows pakai WSL." -ForegroundColor DarkGray

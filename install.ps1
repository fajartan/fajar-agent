<#  FAJAR-AGENT web installer (Windows PowerShell).
    Pakai:  irm https://raw.githubusercontent.com/fajartan/fajar-agent/main/install.ps1 | iex
    Setelah itu cukup ketik:  fajar #>
$ErrorActionPreference = "Stop"
$UserRepo = if ($env:FAJAR_REPO) { $env:FAJAR_REPO } else { "fajartan/fajar-agent" }
$Branch   = if ($env:FAJAR_BRANCH) { $env:FAJAR_BRANCH } else { "main" }
$Dest     = if ($env:FAJAR_HOME) { $env:FAJAR_HOME } else { "$env:LOCALAPPDATA\fajar-agent" }
$Bin      = "$Dest\bin"
function Say($m){ Write-Host "==> $m" -ForegroundColor Yellow }

# 1) Python
$py = $null
foreach ($c in @("python","py","python3")) { if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break } }
if (-not $py) { Write-Host "[!] Python 3 tidak ada. Install dari https://python.org" -ForegroundColor Red; return }
Say "Python: $py"

# 2) unduh arsip repo (flat) -> $Dest
Say "mengunduh FAJAR-AGENT ($UserRepo@$Branch) -> $Dest"
$tmp = Join-Path $env:TEMP ("fajar_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $tmp | Out-Null
$zip = "$tmp\src.zip"
Invoke-WebRequest -UseBasicParsing "https://codeload.github.com/$UserRepo/zip/refs/heads/$Branch" -OutFile $zip
Expand-Archive -Path $zip -DestinationPath $tmp -Force
$src = Get-ChildItem -Path $tmp -Directory | Select-Object -First 1
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item -Path (Join-Path $src.FullName '*') -Destination $Dest -Recurse -Force
Remove-Item $tmp -Recurse -Force
if (-not (Test-Path "$Dest\bb.py")) { Write-Host "[!] bb.py tak ketemu setelah unduh" -ForegroundColor Red; return }

# 3) dependensi TUI (best-effort)
try { & $py -m pip install --user --upgrade textual rich 2>$null } catch {}

# 4) launcher global 'fajar' + PATH user
New-Item -ItemType Directory -Force -Path $Bin | Out-Null
Set-Content -Path "$Bin\fajar.cmd" -Value "@echo off`r`n`"$py`" `"$Dest\bb.py`" %*" -Encoding ASCII
$u = [Environment]::GetEnvironmentVariable("Path","User")
if ($u -notlike "*$Bin*") { [Environment]::SetEnvironmentVariable("Path", "$u;$Bin", "User") }

Write-Host ""
Say "SELESAI. Buka terminal baru, lalu ketik:  fajar"
Write-Host "    fajar             # TUI FAJAR-AGENT"
Write-Host "    fajar llm -i      # agent chat bertahap   |   fajar find   |   fajar telegram"
Write-Host "[i] Recon aktif (subfinder/nuclei) = Linux; di Windows pakai WSL." -ForegroundColor DarkGray

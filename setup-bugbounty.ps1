<#  setup-bugbounty.ps1 — installer FAJAR-AGENT untuk Windows PowerShell.
    Inti = Python murni (cross-OS). Script ini: cek Python, pasang 'textual', siapkan folder, cetak cara pakai.
    Pakai:
      powershell -ExecutionPolicy Bypass -File setup-bugbounty.ps1            # dari folder yg berisi bb.py / bugbounty-framework
      powershell -ExecutionPolicy Bypass -File setup-bugbounty.ps1 -Zip x.zip # extract dari zip dulu
    Catatan: toolchain recon (subfinder/nuclei/dll) berbasis Linux — di Windows pakai WSL untuk itu.
    TUI, finder, LLM agent (FAJAR-AGENT), Telegram, MCP jalan native di Windows. #>
param([string]$Zip = "", [switch]$NoDeps)

$ErrorActionPreference = "Stop"
Write-Host "==> FAJAR-AGENT setup (PowerShell)" -ForegroundColor Yellow

# 1) temukan Python
$py = $null
foreach ($c in @("python","py","python3")) {
  if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) { Write-Host "[!] Python 3 tidak ditemukan. Install dari https://python.org lalu ulangi." -ForegroundColor Red; exit 1 }
Write-Host "    Python: $py"

# 2) extract zip bila diberikan
if ($Zip -and (Test-Path $Zip)) {
  Write-Host "    extract $Zip ..."
  Expand-Archive -Path $Zip -DestinationPath . -Force
}

# 3) temukan entry bb.py
$base = "."
if (Test-Path ".\bugbounty-framework\bb.py") { $base = ".\bugbounty-framework" }
elseif (Test-Path ".\bb.py") { $base = "." }
else { Write-Host "[!] bb.py tidak ditemukan. Jalankan dari folder hasil clone/extract (atau pakai -Zip)." -ForegroundColor Red; exit 1 }
Write-Host "    entry: $base\bb.py"

# 4) dependensi Python (textual utk TUI)
if (-not $NoDeps) {
  Write-Host "    memasang 'textual' (TUI)..."
  try { & $py -m pip install --user --upgrade textual rich 2>$null; Write-Host "    textual ok" -ForegroundColor Green }
  catch { Write-Host "    [!] gagal pasang textual; TUI perlu: $py -m pip install --user textual" -ForegroundColor DarkYellow }
}

# 5) cek kesiapan
Write-Host "==> cek tool (doctor):"
& $py "$base\bb.py" doctor

Write-Host ""
Write-Host "==> SELESAI. Cara pakai (PowerShell):" -ForegroundColor Green
Write-Host "    $py $base\bb.py            # TUI FAJAR-AGENT"
Write-Host "    $py $base\bb.py find       # cari target"
Write-Host "    $py $base\bb.py llm --setup ; $py $base\bb.py llm -i   # agent chat bertahap"
Write-Host "    $py $base\bb.py telegram   # bot Telegram"
Write-Host "[i] Toolchain recon (subfinder/nuclei/dll) = Linux; di Windows pakai WSL untuk recon aktif." -ForegroundColor DarkGray

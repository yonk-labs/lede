# One-command installer for lede (Windows).
#   irm https://raw.githubusercontent.com/yonk-labs/lede/main/install.ps1 | iex
$ErrorActionPreference = "Stop"

$py = Get-Command python -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python3 -ErrorAction SilentlyContinue }
if (-not $py) {
    Write-Error "python not found — install Python 3.10+ from https://python.org (check 'Add python.exe to PATH' during setup)"
    exit 1
}

& $py.Source -m pip install --user --upgrade lede

Write-Host "lede installed. Run 'lede --help' to get started."
Write-Host "If the 'lede' command isn't found, ensure your Python Scripts directory is on PATH."

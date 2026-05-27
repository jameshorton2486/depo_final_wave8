<#
================================================================================
 DEPO-PRO  -  Frontend Packaging Script
================================================================================
 PURPOSE
   Collects the DEPO-PRO front-end code (the `frontend/` web UI, the PyWebView
   desktop launcher, and any front-end build config) into a single clean .zip
   file that you can upload into the chat for review.

   The zip MIRRORS your original project folder layout, so paths like
   `frontend/index.html` and the root launcher script stay intact.

 INCLUDES
   - The entire `frontend/` directory tree (HTML / JS / CSS / Tailwind / assets)
   - Any root-level Python file that launches the PyWebView desktop window
   - Front-end tooling config at the project root (tailwind / postcss / package.json ...)
   - A few small reference files (pyproject.toml, README) for context

 EXCLUDES (kept out to keep the zip small and safe)
   - node_modules, dist, build, .cache, .git, __pycache__, virtual environments
   - compiled / log / OS junk (*.pyc, *.log, Thumbs.db, .DS_Store)
   - .env and any secret / database files

 HOW TO RUN  (in PowerShell)
   1. Save this file as  depo_pack_frontend.ps1
   2. If your project is NOT at the default path, edit the $ProjectRoot value
      a few lines below (or pass -ProjectRoot "C:\path\to\project" when running).
   3. Run:
        powershell -NoProfile -ExecutionPolicy Bypass -File .\depo_pack_frontend.ps1
   4. The finished zip is written to your Desktop as  depo_frontend_only.zip
      Upload that zip into the chat.
================================================================================
#>

[CmdletBinding()]
param(
    # >>> EDIT THIS if your project lives somewhere else <<<
    [string]$ProjectRoot = "C:\Users\james\PycharmProjects\PythonProject\depo_final_wave8",

    # Where the finished zip is written (Desktop by default - easy to find).
    [string]$OutputDir   = [Environment]::GetFolderPath('Desktop'),

    # Name of the finished zip.
    [string]$ZipName     = "depo_frontend_only.zip",

    # Any single file larger than this many MB is skipped (prevents giant assets
    # from bloating the upload). Skipped files are listed in the final report.
    [int]$MaxFileMB      = 25
)

$ErrorActionPreference = 'Stop'

function Write-Section($text) {
    Write-Host ""
    Write-Host ('=' * 70)
    Write-Host "  $text"
    Write-Host ('=' * 70)
}

# ------------------------------------------------------------------------------
# 1. Resolve and validate the project root
# ------------------------------------------------------------------------------
Write-Section "DEPO-PRO  -  Frontend Packaging"

# If the default path is missing but this script is sitting inside the project
# folder, fall back to the script's own location.
if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    if ($PSScriptRoot -and (
            (Test-Path (Join-Path $PSScriptRoot 'backend')) -or
            (Test-Path (Join-Path $PSScriptRoot 'frontend')))) {
        $ProjectRoot = $PSScriptRoot
        Write-Host "[INFO] Default path not found - using this script's folder as the project root."
    }
}

if (-not (Test-Path -LiteralPath $ProjectRoot)) {
    Write-Host "[ERROR] Project folder not found:" -ForegroundColor Red
    Write-Host "        $ProjectRoot"
    Write-Host ""
    Write-Host "Fix: open this script, edit the `$ProjectRoot value near the top,"
    Write-Host "     then run it again. Or run with:"
    Write-Host "       .\depo_pack_frontend.ps1 -ProjectRoot 'C:\path\to\project'"
    exit 1
}

$ProjectRoot = (Resolve-Path -LiteralPath $ProjectRoot).Path.TrimEnd('\', '/')
Write-Host "Project root : $ProjectRoot"

# ------------------------------------------------------------------------------
# 2. Define what to include / exclude
# ------------------------------------------------------------------------------

# Directory names skipped wherever they appear in the tree.
$excludeDirs = @(
    'node_modules', '.git', '__pycache__', '.venv', 'venv', 'env',
    'dist', 'build', '.cache', '.pytest_cache', '.pytest_tmp',
    '.idea', '.vscode', '.next', '.parcel-cache', 'coverage'
)

# File-name patterns that are always skipped.
$excludeFiles = @(
    '*.pyc', '*.pyo', '*.log', '*.tmp', '.DS_Store', 'Thumbs.db',
    '.env', '.env.*', '*.sqlite', '*.sqlite3', '*.db'
)

# Root-level front-end config files to include if present.
$rootConfigCandidates = @(
    'tailwind.config.js', 'tailwind.config.cjs', 'tailwind.config.ts',
    'postcss.config.js', 'postcss.config.cjs',
    'package.json', 'package-lock.json', 'pnpm-lock.yaml', 'yarn.lock',
    'vite.config.js', 'vite.config.ts', '.nvmrc', 'index.html'
)

# Small reference files included for context.
$referenceCandidates = @('pyproject.toml', 'README.md', 'requirements.txt')

function Test-Excluded([string]$fullPath) {
    $rel   = $fullPath.Substring($ProjectRoot.Length).TrimStart('\', '/')
    $parts = $rel -split '[\\/]'
    foreach ($p in $parts) {
        if ($excludeDirs -contains $p) { return $true }
    }
    $leaf = Split-Path -Path $fullPath -Leaf
    foreach ($pat in $excludeFiles) {
        if ($leaf -like $pat) { return $true }
    }
    return $false
}

# ------------------------------------------------------------------------------
# 3. Collect the file list
# ------------------------------------------------------------------------------
Write-Section "Collecting files"

$collected  = New-Object System.Collections.Generic.List[object]
$skippedBig = New-Object System.Collections.Generic.List[object]

function Add-FileToList([string]$fullPath) {
    if (-not (Test-Path -LiteralPath $fullPath -PathType Leaf)) { return }
    if (Test-Excluded $fullPath) { return }

    $fi     = Get-Item -LiteralPath $fullPath
    $sizeMB = [math]::Round($fi.Length / 1MB, 2)
    $rel    = $fi.FullName.Substring($ProjectRoot.Length).TrimStart('\', '/').Replace('\', '/')

    if ($fi.Length -gt ($MaxFileMB * 1MB)) {
        $skippedBig.Add([pscustomobject]@{ Rel = $rel; SizeMB = $sizeMB })
        return
    }
    if ($collected.Rel -contains $rel) { return }   # de-duplicate
    $collected.Add([pscustomobject]@{ Full = $fi.FullName; Rel = $rel; SizeMB = $sizeMB })
}

# --- 3a. The frontend/ directory --------------------------------------------
$frontendDir = Join-Path $ProjectRoot 'frontend'
if (Test-Path -LiteralPath $frontendDir -PathType Container) {
    Write-Host "[OK]   Found frontend/ - scanning..."
    Get-ChildItem -LiteralPath $frontendDir -Recurse -File -Force |
        ForEach-Object { Add-FileToList $_.FullName }
    Write-Host ("       {0} file(s) collected from frontend/" -f $collected.Count)
} else {
    Write-Host "[WARN] No 'frontend/' folder found at the project root." -ForegroundColor Yellow
    Write-Host "       The launcher and configs will still be packaged, but the"
    Write-Host "       web UI itself may live in a different folder."
}

# --- 3b. PyWebView desktop launcher (root-level .py files using 'webview') ---
$launcherFound = @()
Get-ChildItem -LiteralPath $ProjectRoot -Filter '*.py' -File -Force |
    ForEach-Object {
        if (Select-String -LiteralPath $_.FullName -Pattern 'webview' -SimpleMatch -Quiet) {
            Add-FileToList $_.FullName
            $launcherFound += $_.Name
        }
    }

# --- 3c. Root-level front-end config + small reference files ----------------
foreach ($name in $rootConfigCandidates) {
    $p = Join-Path $ProjectRoot $name
    if (Test-Path -LiteralPath $p -PathType Leaf) { Add-FileToList $p }
}
foreach ($name in $referenceCandidates) {
    $p = Join-Path $ProjectRoot $name
    if (Test-Path -LiteralPath $p -PathType Leaf) { Add-FileToList $p }
}

if ($collected.Count -eq 0) {
    Write-Host ""
    Write-Host "[ERROR] Nothing was found to package." -ForegroundColor Red
    Write-Host "        Check that `$ProjectRoot points at the real project folder."
    exit 1
}

# ------------------------------------------------------------------------------
# 4. Build the zip
#    Files are first copied into a temporary staging folder (preserving their
#    relative paths), then Compress-Archive zips that folder. Compress-Archive
#    is built into Windows PowerShell 5.1 and PowerShell 7+, so no .NET
#    assembly loading is required - it works the same everywhere.
# ------------------------------------------------------------------------------
Write-Section "Building zip"

if (-not (Test-Path -LiteralPath $OutputDir -PathType Container)) {
    New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
}
$zipPath = Join-Path $OutputDir $ZipName
if (Test-Path -LiteralPath $zipPath) {
    Remove-Item -LiteralPath $zipPath -Force
    Write-Host "[INFO] Removed previous $ZipName"
}

# Temporary staging folder - auto-removed when the script finishes.
$staging = Join-Path ([System.IO.Path]::GetTempPath()) `
    ("depo_pack_" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $staging -Force | Out-Null

try {
    # Copy each collected file into staging, recreating its folder structure.
    foreach ($item in $collected) {
        $dest    = Join-Path $staging ($item.Rel -replace '/', '\')
        $destDir = Split-Path -Path $dest -Parent
        if (-not (Test-Path -LiteralPath $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force | Out-Null
        }
        Copy-Item -LiteralPath $item.Full -Destination $dest -Force
    }

    # Zip the staging folder's contents (structure is preserved).
    Compress-Archive -Path (Join-Path $staging '*') `
        -DestinationPath $zipPath -CompressionLevel Optimal -Force

    Write-Host "[OK]   Archive created."
}
finally {
    if (Test-Path -LiteralPath $staging) {
        Remove-Item -LiteralPath $staging -Recurse -Force -ErrorAction SilentlyContinue
    }
}

# ------------------------------------------------------------------------------
# 5. Report
# ------------------------------------------------------------------------------
$totalMB   = [math]::Round((($collected | Measure-Object -Property SizeMB -Sum).Sum), 2)
$zipSizeMB = [math]::Round((Get-Item -LiteralPath $zipPath).Length / 1MB, 2)

Write-Section "Done"
Write-Host ("Files packaged : {0}" -f $collected.Count)
Write-Host ("Uncompressed   : {0} MB (approx)" -f $totalMB)
Write-Host ("Zip size       : {0} MB" -f $zipSizeMB)
Write-Host ("Saved to       : {0}" -f $zipPath)

Write-Host ""
Write-Host "Contents:"
$show = 120
$collected | Sort-Object Rel | Select-Object -First $show |
    ForEach-Object { Write-Host ("  {0}" -f $_.Rel) }
if ($collected.Count -gt $show) {
    Write-Host ("  ... and {0} more" -f ($collected.Count - $show))
}

if ($skippedBig.Count -gt 0) {
    Write-Host ""
    Write-Host ("[NOTE] {0} file(s) skipped for exceeding {1} MB:" -f `
        $skippedBig.Count, $MaxFileMB) -ForegroundColor Yellow
    $skippedBig | ForEach-Object { Write-Host ("  {0}  ({1} MB)" -f $_.Rel, $_.SizeMB) }
    Write-Host "       Re-run with  -MaxFileMB <bigger number>  to include them."
}

Write-Host ""
if ($launcherFound.Count -gt 0) {
    Write-Host ("PyWebView launcher detected: {0}" -f ($launcherFound -join ', '))
} else {
    Write-Host "[WARN] No PyWebView launcher script was found at the project root." `
        -ForegroundColor Yellow
    Write-Host "       If your desktop entry-point lives in a subfolder, tell me its"
    Write-Host "       path and I will adjust the script."
}

if ($zipSizeMB -gt 50) {
    Write-Host ""
    Write-Host ("[NOTE] The zip is {0} MB - that is large for a chat upload." -f $zipSizeMB) `
        -ForegroundColor Yellow
    Write-Host "       If the upload is rejected, lower -MaxFileMB or tell me which"
    Write-Host "       asset folders can be left out."
}

Write-Host ""
Write-Host ("Next step: upload  {0}  (on your Desktop) into the chat." -f $ZipName)
Write-Host ""

# ============================================================
#  DEPO-PRO - package the front-end for upload
#  Run from the project root:
#    powershell -NoProfile -ExecutionPolicy Bypass -File .\depo_pack_frontend.ps1
#  Produces depo_frontend_only.zip on your Desktop.
# ============================================================

$ProjectRoot = (Get-Location).Path
$ExcludeDirs = @('node_modules', '.git', '__pycache__', '.venv', 'venv',
                 'dist', 'build', '.cache', '.idea', '.vscode')

$desktop = [Environment]::GetFolderPath('Desktop')
if (-not $desktop) { $desktop = $ProjectRoot }
$OutputZip = Join-Path $desktop 'depo_frontend_only.zip'

Write-Host "Project root: $ProjectRoot"

$files = New-Object System.Collections.Generic.List[string]

# 1. Everything under frontend/, minus excluded sub-folders.
$frontend = Join-Path $ProjectRoot 'frontend'
if (Test-Path -LiteralPath $frontend) {
    Get-ChildItem -LiteralPath $frontend -Recurse -File | Where-Object {
        $segs = $_.FullName.Substring($ProjectRoot.Length) -split '[\\/]'
        -not ($segs | Where-Object { $ExcludeDirs -contains $_ })
    } | ForEach-Object { $files.Add($_.FullName) }
    Write-Host "Found frontend/ - $($files.Count) file(s)"
} else {
    Write-Host "[WARN] no frontend/ folder found at the project root"
}

# 2. Root-level launcher (.py using 'webview') and front-end config files.
Get-ChildItem -LiteralPath $ProjectRoot -File | Where-Object {
    (($_.Name -match 'tailwind|postcss|package|vite') -and ($_.Name -match '\.(js|cjs|ts|json)$')) -or
    ($_.Name -eq 'index.html') -or
    (($_.Extension -eq '.py') -and
     (Select-String -LiteralPath $_.FullName -Pattern 'webview' -SimpleMatch -Quiet))
} | ForEach-Object { $files.Add($_.FullName) }

if ($files.Count -eq 0) {
    Write-Host "[ERROR] nothing found to package - are you in the project root?"
    exit 1
}

# 3. Stage into a temp folder (keeps structure), then zip with Compress-Archive.
$staging = Join-Path ([System.IO.Path]::GetTempPath()) ('depo_pack_' + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $staging -Force | Out-Null
foreach ($f in $files) {
    $rel  = $f.Substring($ProjectRoot.Length).TrimStart('\', '/')
    $dest = Join-Path $staging $rel
    New-Item -ItemType Directory -Path (Split-Path $dest -Parent) -Force | Out-Null
    Copy-Item -LiteralPath $f -Destination $dest -Force
}
if (Test-Path -LiteralPath $OutputZip) { Remove-Item -LiteralPath $OutputZip -Force }
Compress-Archive -Path (Join-Path $staging '*') -DestinationPath $OutputZip -Force
Remove-Item -LiteralPath $staging -Recurse -Force

Write-Host ""
Write-Host "Packaged $($files.Count) file(s):"
$files | ForEach-Object { Write-Host ('  ' + $_.Substring($ProjectRoot.Length).TrimStart('\', '/')) }
Write-Host ""
Write-Host "Saved to: $OutputZip"
Write-Host "Upload that zip into the chat."
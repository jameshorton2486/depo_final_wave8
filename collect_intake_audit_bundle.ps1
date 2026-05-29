<#
=====================================================================
 DEPO-PRO  -  Intake / NOD / Keyterm / UFM audit bundle collector
---------------------------------------------------------------------
 Copies the files needed for the intake-extraction audit into
 prompt_files\intake_audit_bundle\ (folder structure preserved),
 writes a MANIFEST.txt, and zips the bundle to
 prompt_files\intake_audit_bundle.zip

 Scope: Texas civil freelance deposition intake. No federal jurisdiction.

 HOW TO RUN (from anywhere):
   powershell -ExecutionPolicy Bypass -File .\collect_intake_audit_bundle.ps1
 or, if you have it in the repo and are sitting at the repo root:
   .\collect_intake_audit_bundle.ps1
=====================================================================
#>

# --- Edit this if your repo lives elsewhere ---------------------------------
$RepoRoot = "C:\Users\james\PycharmProjects\PythonProject\depo_final_wave8"
# ----------------------------------------------------------------------------

$BundleName = "intake_audit_bundle"
$PromptDir  = Join-Path $RepoRoot "prompt_files"
$Dest       = Join-Path $PromptDir $BundleName
$ZipPath    = Join-Path $PromptDir "$BundleName.zip"

# Files to collect, relative to repo root.
$Files = @(
    # --- Parser core ---
    "backend/services/nod_parser/__init__.py",
    "backend/services/nod_parser/orchestrator.py",
    "backend/services/nod_parser/intelligence.py",
    "backend/services/nod_parser/pdf_text.py",
    "backend/services/nod_parser/type_a_form.py",
    "backend/services/nod_parser/type_b_pleading.py",
    "backend/services/intake_text_parser.py",
    # --- Keyterms ---
    "backend/services/keyterms.py",
    # --- Persistence + live schema ---
    "backend/services/intake_store.py",
    "backend/db/schema_v12.sql",
    "backend/db/migrations.py",
    # --- API ---
    "backend/api/intake.py",
    "backend/api/nod.py",
    # --- Deepgram params ---
    "backend/deepgram/client.py",
    # --- Frontend intake ---
    "frontend/screens/stage_1_intake.html",
    "frontend/assets/js/screens/stage_1.js",
    "frontend/assets/js/state.js",
    "frontend/assets/js/api.js",
    # --- Tests ---
    "tests/test_nod_parser.py",
    "tests/test_nod_intelligence.py",
    "tests/test_nod_api.py",
    "tests/test_intake_text_parser.py",
    "tests/test_intake_previews.py",
    # --- Authority docs ---
    "docs/nod_parser_spec.md",
    "docs/ufm_schema_v1.md",
    "docs/SYSTEM_OWNERSHIP.md",
    "docs/BLOCKERS.md",
    "CLAUDE.md"
)

# Optional extras: include the data dictionary if it has been saved into prompt_files.
$OptionalFiles = @(
    # Authoritative reference docs (agent filed these into docs/)
    "docs/DEPO-PRO_UFM_Data_Dictionary_v2.md",
    "docs/DEPO-PRO_Field_Template_Matrix.md",
    # Build prompts
    "prompt_files/PROMPT_intake_extraction_audit_and_fix.md",
    "prompt_files/PROMPT_intake_reparse_remediation_phase1_5.md"
)

Write-Host ""
Write-Host "DEPO-PRO intake audit bundle" -ForegroundColor Cyan
Write-Host "Repo root : $RepoRoot"
Write-Host "Bundle    : $Dest"
Write-Host ""

if (-not (Test-Path $RepoRoot)) {
    Write-Host "ERROR: Repo root not found: $RepoRoot" -ForegroundColor Red
    Write-Host "Edit the `$RepoRoot variable at the top of this script." -ForegroundColor Red
    exit 1
}

# Fresh staging folder (remove any prior run so the zip is clean).
if (Test-Path $Dest) { Remove-Item -Recurse -Force $Dest }
New-Item -ItemType Directory -Force -Path $Dest | Out-Null

$copied  = New-Object System.Collections.Generic.List[string]
$missing = New-Object System.Collections.Generic.List[string]

function Copy-One {
    param([string]$Rel)
    $src = Join-Path $RepoRoot $Rel
    if (Test-Path $src) {
        # Preserve folder structure under the bundle.
        $target = Join-Path $Dest $Rel
        $targetDir = Split-Path $target -Parent
        New-Item -ItemType Directory -Force -Path $targetDir | Out-Null
        Copy-Item -LiteralPath $src -Destination $target -Force
        $script:copied.Add($Rel)
        Write-Host "  [ok]   $Rel" -ForegroundColor Green
    } else {
        $script:missing.Add($Rel)
        Write-Host "  [MISS] $Rel" -ForegroundColor Yellow
    }
}

Write-Host "Copying required files..." -ForegroundColor Cyan
foreach ($f in $Files) { Copy-One $f }

Write-Host ""
Write-Host "Checking optional files..." -ForegroundColor Cyan
foreach ($f in $OptionalFiles) { Copy-One $f }

# Write a manifest describing the bundle.
$manifest = @()
$manifest += "DEPO-PRO  -  Intake / NOD / Keyterm / UFM audit bundle"
$manifest += "Generated: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
$manifest += "Repo root: $RepoRoot"
$manifest += "Scope: Texas civil freelance deposition intake. NO federal jurisdiction."
$manifest += ""
$manifest += "Purpose: audit how the NOD/notes parser populates the UFM metadata"
$manifest += "and the Deepgram keyterm list, against the locked v2 data dictionary."
$manifest += ""
$manifest += "FILES INCLUDED ($($copied.Count)):"
foreach ($c in $copied) { $manifest += "  $c" }
if ($missing.Count -gt 0) {
    $manifest += ""
    $manifest += "FILES NOT FOUND ($($missing.Count)) - verify path or rename:"
    foreach ($m in $missing) { $manifest += "  $m" }
}
$manifestPath = Join-Path $Dest "MANIFEST.txt"
$manifest | Set-Content -Path $manifestPath -Encoding UTF8

# Zip it.
if (Test-Path $ZipPath) { Remove-Item -Force $ZipPath }
Compress-Archive -Path (Join-Path $Dest "*") -DestinationPath $ZipPath -Force

Write-Host ""
Write-Host "----------------------------------------------------------" -ForegroundColor Cyan
Write-Host "Copied : $($copied.Count) file(s)"
if ($missing.Count -gt 0) {
    Write-Host "Missing: $($missing.Count) file(s)  (listed above and in MANIFEST.txt)" -ForegroundColor Yellow
} else {
    Write-Host "Missing: 0" -ForegroundColor Green
}
Write-Host "Bundle folder : $Dest"
Write-Host "Zip created   : $ZipPath"
Write-Host "----------------------------------------------------------" -ForegroundColor Cyan

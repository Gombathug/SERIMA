# One-time install of the demo on a new Windows machine, right after `git clone`.
#   powershell -ExecutionPolicy Bypass -File demo\install_demo.ps1 [-PythonExe <path to python.exe 3.14>]
# Needs git, Python 3.14 and Node.js on the PATH. Downloads PostgreSQL and MSYS2 into the
# parent folder of the repo (see env.ps1), then builds the demo database.
# Safe to re-run: every step already done is skipped.
param([string]$PythonExe = "")
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\env.ps1"
Set-Location $Repo

$PgZipUrl    = "https://get.enterprisedb.com/postgresql/postgresql-18.6-1-windows-x64-binaries.zip"
$MsysSfxUrl  = "https://github.com/msys2/msys2-installer/releases/download/nightly-x86_64/msys2-base-x86_64-latest.sfx.exe"
$ThemeCommit = "7672c556830ed2b22dddd62ccdd08772b9783e89"  # serimabe-theme v0.6.0
$Downloads   = Join-Path $Base "_downloads"

function Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function Check($what) { if ($LASTEXITCODE -ne 0) { throw "$what failed (exit code $LASTEXITCODE)" } }
function Get-File($url, $dest) {
    if (Test-Path $dest) { return }
    New-Item -ItemType Directory -Force $Downloads | Out-Null
    # Download to .part first so an interrupted download is never mistaken for a complete one.
    & curl.exe -L -f --retry 3 -o "$dest.part" $url; Check "Download of $url"
    Move-Item "$dest.part" $dest
}

foreach ($cmd in "git", "npm.cmd", "curl.exe", "tar.exe") {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) { throw "$cmd not found on the PATH: install it first (see demo/README.md)" }
}

# 1. Config (gitignored): the demo one is versioned as demo/config_demo.py
$Config = Join-Path $Repo "governanceplatform\config.py"
if (-not (Test-Path $Config)) {
    Step "governanceplatform\config.py"
    Copy-Item (Join-Path $PSScriptRoot "config_demo.py") $Config
}

# 2. Theme (gitignored): IBPT serimabe-theme v0.6.0 + the two local edits of demo/theme_overrides
$Theme = Join-Path $Repo "theme"
if (-not (Test-Path $Theme)) {
    Step "Theme (serimabe-theme v0.6.0)"
    git clone -q https://github.com/informed-governance-project/default-theme.git $Theme; Check "git clone default-theme"
    git -C $Theme remote add serimabe-theme https://github.com/informed-governance-project/serimabe-theme.git; Check "git remote add"
    git -C $Theme fetch -q serimabe-theme; Check "git fetch serimabe-theme"
    git -C $Theme -c advice.detachedHead=false checkout -q $ThemeCommit; Check "git checkout theme"
    Copy-Item -Recurse -Force (Join-Path $PSScriptRoot "theme_overrides\*") $Theme
}

# 3. Python venv
if (-not (Test-Path $Python)) {
    Step "Python venv (.venv)"
    if (-not $PythonExe) {
        # The py launcher finds 3.14 even when another version comes first on the PATH.
        $ErrorActionPreference = "Continue"
        if (Get-Command py -ErrorAction SilentlyContinue) { $PythonExe = (& py -3.14 -c "import sys; print(sys.executable)" 2>$null) }
        if (-not $PythonExe) { $PythonExe = "python" }
        $ErrorActionPreference = "Stop"
    }
    & $PythonExe -c "import sys; sys.exit(sys.version_info[:2] < (3, 14))"
    if ($LASTEXITCODE -ne 0) { throw "Python 3.14 is required ('$PythonExe' is older or missing): pass -PythonExe <path to python.exe>" }
    & $PythonExe -m venv .venv; Check "python -m venv"
}
Step "Python packages"
& $Python -m pip install -q --disable-pip-version-check -r requirements.txt pytest pytest-django pytest-cov ruff; Check "pip install"

# 4. Front-end packages, served as static/npm_components (a junction: no admin rights needed)
if (-not (Test-Path (Join-Path $Repo "node_modules"))) {
    Step "npm ci"
    npm.cmd ci; Check "npm ci"
}
$NpmLink = Join-Path $Repo "static\npm_components"
if (-not (Test-Path $NpmLink)) {
    cmd /c mklink /J "$NpmLink" "$Repo\node_modules" | Out-Null; Check "mklink static\npm_components"
}

# 5. PostgreSQL 18, portable (..\pgsql)
if (-not (Test-Path "$PgBin\pg_ctl.exe")) {
    Step "PostgreSQL 18 (download ~350 MB)"
    $zip = Join-Path $Downloads "pgsql.zip"
    Get-File $PgZipUrl $zip
    & tar.exe -xf $zip -C $Base; Check "Extraction of pgsql.zip"  # the zip holds a top-level pgsql\ folder
}

# 6. MSYS2 (..\msys64) with Pango (WeasyPrint PDFs) and gettext (compilemessages)
$Bash = Join-Path $Base "msys64\usr\bin\bash.exe"
if (-not (Test-Path $Bash)) {
    Step "MSYS2 (download ~45 MB)"
    $sfx = Join-Path $Downloads "msys2.sfx.exe"
    Get-File $MsysSfxUrl $sfx
    & $sfx -y "-o$Base"; Check "Extraction of MSYS2"  # creates msys64\ in $Base
}
if (-not ((Test-Path "$Msys\libpango-1.0-0.dll") -and (Test-Path "$Msys\msgfmt.exe"))) {
    Step "MSYS2 packages: pango, gettext"
    & $Bash -lc "true"  # first start initialises MSYS2 (keyring, home folder)
    & $Bash -lc "pacman -Sy --noconfirm --needed mingw-w64-x86_64-pango mingw-w64-x86_64-gettext-tools"; Check "pacman"
}

# 7. Demo database
if (Test-Path "$PgData\PG_VERSION") {
    Write-Host "Database folder $PgData already exists: left as is (demo\reset_demo.ps1 rebuilds it)."
} else {
    Step "Demo database"
    & powershell -ExecutionPolicy Bypass -File (Join-Path $PSScriptRoot "reset_demo.ps1"); Check "reset_demo.ps1"
}

Write-Host ""
Write-Host "Install done. Start the demo with:  powershell -ExecutionPolicy Bypass -File demo\start_demo.ps1" -ForegroundColor Green

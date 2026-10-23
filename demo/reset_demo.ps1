# (Re)build the demo database from scratch: ALL data in the demo database is replaced.
#   powershell -ExecutionPolicy Bypass -File demo\reset_demo.ps1 [-Password <pwd>]
param([string]$Password = "SerimaDemo2026!")
$ErrorActionPreference = "Stop"
. "$PSScriptRoot\env.ps1"
Set-Location $Repo

if (-not (Test-Path "$PgData\PG_VERSION")) {
    $pwFile = New-TemporaryFile
    Set-Content -Path $pwFile -Value "serima" -NoNewline
    & "$PgBin\initdb.exe" -D $PgData -U serima --pwfile=$pwFile -A scram-sha-256 -E UTF8 --locale=C | Out-Null
    Remove-Item $pwFile
}
Start-DemoDb

& "$PgBin\dropdb.exe" -h localhost --if-exists serima-governance
& "$PgBin\createdb.exe" -h localhost serima-governance

function Invoke-Manage { & $Python manage.py @args; if ($LASTEXITCODE -ne 0) { throw "manage.py $args failed" } }
Invoke-Manage migrate --no-input -v 0
Invoke-Manage update_group_permissions
Invoke-Manage loaddata docs/screenshots/fixture.json
Invoke-Manage compilemessages -v 0
& $Python demo\setup_demo.py --password $Password
if ($LASTEXITCODE -ne 0) { throw "setup_demo.py failed" }
Write-Host "Demo database ready. Start it with demo\start_demo.ps1"

# Shared paths for the demo scripts. Dot-sourced by start/stop/reset.
# Everything except the repo lives in its parent folder (D:\SERIMA_test by default).
$Repo    = Split-Path $PSScriptRoot -Parent
$Base    = Split-Path $Repo -Parent
$PgBin   = Join-Path $Base "pgsql\bin"
$PgData  = Join-Path $Base "pgdata"
$PgLog   = Join-Path $Base "pgdata.log"
$Msys    = Join-Path $Base "msys64\mingw64\bin"
$Python  = Join-Path $Repo ".venv\Scripts\python.exe"

# WeasyPrint (incident PDF reports) loads Pango from MSYS2; gettext (compilemessages) lives there too.
$env:WEASYPRINT_DLL_DIRECTORIES = $Msys
$env:PATH = "$PgBin;$Msys;$env:PATH"
$env:PGUSER = "serima"
$env:PGPASSWORD = "serima"

function Start-DemoDb {
    & "$PgBin\pg_ctl.exe" status -D $PgData *> $null
    if ($LASTEXITCODE -ne 0) {
        # Not `& pg_ctl ... | Out-Null`: the server inherits the pipe and the call never returns.
        $p = Start-Process "$PgBin\pg_ctl.exe" -ArgumentList "start", "-D", "`"$PgData`"", "-l", "`"$PgLog`"", "-w" -WindowStyle Hidden -PassThru
        $p.WaitForExit()
        if ($p.ExitCode -ne 0) { throw "PostgreSQL did not start, see $PgLog" }
    }
}

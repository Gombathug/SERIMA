# Stop the demo PostgreSQL server.
. "$PSScriptRoot\env.ps1"
& "$PgBin\pg_ctl.exe" stop -D $PgData -m fast

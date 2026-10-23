# Start PostgreSQL (if needed) and the SERIMA dev server on http://127.0.0.1:8000
. "$PSScriptRoot\env.ps1"
Start-DemoDb
Set-Location $Repo
Write-Host "SERIMA demo on http://127.0.0.1:8000  (Ctrl+C to stop the web server; demo\stop_demo.ps1 stops the database)"
& $Python manage.py runserver 127.0.0.1:8000

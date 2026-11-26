# Starts FaceID's own MySQL server, the one setup.ps1 installs, if it is not running yet.
# Does nothing when MySQL was installed separately as a Windows service (MySQL80).
$ErrorActionPreference = "Stop"
$faceidDir = Join-Path $env:LOCALAPPDATA "FaceID"
$mysqld = Join-Path $faceidDir "mysql\bin\mysqld.exe"
$ini = Join-Path $faceidDir "my.ini"
$port = 3307

function Test-Port {
    try { $client = New-Object Net.Sockets.TcpClient; $client.Connect("127.0.0.1", $port); $client.Close(); return $true }
    catch { return $false }
}

if (-not (Test-Path $ini)) { exit 0 }
if (Test-Port) { exit 0 }
Write-Host "Starting the database..."
# Hidden window: the server keeps running in the background until Windows shuts down.
Start-Process -FilePath $mysqld -ArgumentList "--defaults-file=`"$ini`"" -WindowStyle Hidden
for ($i = 0; $i -lt 60; $i++) {
    if (Test-Port) { exit 0 }
    Start-Sleep -Milliseconds 500
}
Write-Host "The database did not start within 30 seconds. Send a screenshot of the newest .err file in $faceidDir\mysql-data." -ForegroundColor Red
exit 1

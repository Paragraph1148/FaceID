# FaceID setup for Windows. Run by double-clicking setup.bat.
# Installs whatever is missing: the Visual C++ runtime, Python 3.10.11, the Python packages and MySQL 8.0.46.
# A MySQL already installed as a Windows service (MySQL80) is used instead of installing a second one.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$faceidDir = Join-Path $env:LOCALAPPDATA "FaceID"   # shared by every FaceID version folder
$mysqlDir = Join-Path $faceidDir "mysql"
$dataDir = Join-Path $faceidDir "mysql-data"
$ini = Join-Path $faceidDir "my.ini"
$passwordFile = Join-Path $faceidDir "mysql-root-password.txt"
$ownMysqlPort = 3307   # not 3306, so it never clashes with another MySQL

$pythonUrl = "https://www.python.org/ftp/python/3.10.11/python-3.10.11-amd64.exe"
$pythonSha256 = "D8DEDE5005564B408BA50317108B765ED9C3C510342A598F9FD42681CBE0648B"
$mysqlUrl = "https://cdn.mysql.com/Downloads/MySQL-8.0/mysql-8.0.46-winx64.zip"
$mysqlSha256 = "28E9EDA019D88EFF4478D811EA2110B83F02A3966BE157FE91CC55DEF3AB0D4D"
$vcRedistUrl = "https://aka.ms/vs/17/release/vc_redist.x64.exe"

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nSETUP FAILED: $text" -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

# Downloads $url into a temporary folder and checks its SHA-256, so a damaged download is never run.
function Get-Download($url, $file, $sha256) {
    $dir = Join-Path $env:TEMP "FaceID-setup"
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
    $path = Join-Path $dir $file
    if ((Test-Path $path) -and $sha256 -and (Get-FileHash $path -Algorithm SHA256).Hash -eq $sha256) { return $path }
    Write-Host "Downloading $file ..."
    & curl.exe -L --fail -o $path $url
    if ($LASTEXITCODE -ne 0) { Fail "Could not download $url. Check the internet connection and run setup again." }
    if ($sha256 -and (Get-FileHash $path -Algorithm SHA256).Hash -ne $sha256) {
        Remove-Item $path
        Fail "The download of $file was damaged. Run setup again."
    }
    return $path
}

function Find-Python310 {
    try {
        $exe = & py -3.10 -c "import sys; print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $exe) { return "$exe".Trim() }
    } catch { }
    foreach ($path in @("$env:LOCALAPPDATA\Programs\Python\Python310\python.exe", "$env:ProgramFiles\Python310\python.exe")) {
        if (Test-Path $path) { return $path }
    }
    return $null
}

function Test-VCRuntime {
    foreach ($key in @("HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64", "HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64")) {
        $runtime = Get-ItemProperty $key -ErrorAction SilentlyContinue
        # MySQL 8.0 and dlib need the 2019 runtime (14.2x) or newer.
        if ($runtime -and $runtime.Installed -eq 1 -and $runtime.Minor -ge 29) { return $true }
    }
    return $false
}

function Write-Config($port, $password) {
    New-Item -ItemType Directory -Force -Path instance | Out-Null
    $secret = & $python -c "import secrets; print(secrets.token_hex(32))"
    $escaped = $password.Replace('\', '\\').Replace('"', '\"')
    @"
# Local settings. Not committed.
SECRET_KEY = "$secret"
DB_HOST = "127.0.0.1"
DB_PORT = $port
DB_USER = "root"
DB_PASSWORD = "$escaped"
DB_NAME = "faceid"
"@ | Set-Content -Encoding UTF8 instance\config.py
}

function Start-OwnMysql {
    & powershell -NoProfile -ExecutionPolicy Bypass -File "$PSScriptRoot\start-mysql.ps1"
    if ($LASTEXITCODE -ne 0) { Fail "The database did not start." }
}

# Unpacks MySQL into %LOCALAPPDATA%\FaceID, creates an empty database server and gives root a random password.
function Install-OwnMysql {
    # A folder left by an install that stopped half-way holds no FaceID data yet, so start again cleanly.
    Remove-Item -Recurse -Force $mysqlDir, $dataDir, $ini -ErrorAction SilentlyContinue
    $zip = Get-Download $mysqlUrl "mysql-8.0.46-winx64.zip" $mysqlSha256
    Write-Host "Unpacking MySQL (a minute or two)..."
    $unpack = Join-Path $faceidDir "unpack"
    Remove-Item -Recurse -Force $unpack -ErrorAction SilentlyContinue
    New-Item -ItemType Directory -Force -Path $unpack | Out-Null
    & tar.exe -xf $zip -C $unpack
    if ($LASTEXITCODE -ne 0) { Fail "Could not unpack MySQL." }
    Move-Item (Join-Path $unpack "mysql-8.0.46-winx64") $mysqlDir
    Remove-Item -Recurse -Force $unpack

    # Listens on this laptop only, and turns off the X Protocol port so Windows Firewall has nothing to ask about.
    $options = "[mysqld]`r`nbasedir=`"$($mysqlDir.Replace('\', '/'))`"`r`ndatadir=`"$($dataDir.Replace('\', '/'))`"`r`nport=$ownMysqlPort`r`nbind-address=127.0.0.1`r`nmysqlx=OFF`r`n"
    [IO.File]::WriteAllText($ini, $options)

    Write-Host "Creating the database server..."
    & "$mysqlDir\bin\mysqld.exe" "--defaults-file=$ini" --initialize-insecure --console
    if ($LASTEXITCODE -ne 0) { Fail "MySQL could not create its data folder. Send a screenshot of the text above." }
    Start-OwnMysql

    $password = & $python -c "import secrets; print(secrets.token_urlsafe(18))"
    & "$mysqlDir\bin\mysql.exe" -uroot -h127.0.0.1 "-P$ownMysqlPort" --skip-password -e "ALTER USER 'root'@'localhost' IDENTIFIED BY '$password';"
    if ($LASTEXITCODE -ne 0) { Fail "Could not set the MySQL password. Send a screenshot of the text above." }
    # Kept outside the FaceID folder so a new FaceID version can find it.
    Set-Content -Path $passwordFile -Value $password
}

Step "Checking for the Microsoft Visual C++ runtime"
if (Test-VCRuntime) {
    Write-Host "Installed."
} else {
    $vcRedist = Get-Download $vcRedistUrl "vc_redist.x64.exe" $null
    $signature = Get-AuthenticodeSignature $vcRedist
    if ($signature.Status -ne "Valid" -or $signature.SignerCertificate.Subject -notlike "*Microsoft Corporation*") { Fail "The Visual C++ download is not signed by Microsoft." }
    Write-Host "Installing it. Windows will ask for permission: click Yes." -ForegroundColor Yellow
    try { $process = Start-Process $vcRedist -ArgumentList "/install", "/quiet", "/norestart" -Verb RunAs -Wait -PassThru }
    catch { Fail "The Visual C++ runtime was not installed (permission refused). Run setup again and click Yes." }
    # 1638: a newer version is already installed. 3010: installed, restart later.
    if (@(0, 1638, 3010) -notcontains $process.ExitCode) { Fail "Installing the Visual C++ runtime failed (code $($process.ExitCode))." }
}

Step "Checking for Python 3.10"
$python310 = Find-Python310
if (-not $python310) {
    $installer = Get-Download $pythonUrl "python-3.10.11-amd64.exe" $pythonSha256
    Write-Host "Installing Python 3.10.11 for this Windows user (about a minute)..."
    $process = Start-Process $installer -ArgumentList "/quiet", "InstallAllUsers=0", "InstallLauncherAllUsers=0", "Include_launcher=1", "PrependPath=1", "Include_test=0" -Wait -PassThru
    if ($process.ExitCode -ne 0) { Fail "Installing Python failed (code $($process.ExitCode))." }
    $python310 = Find-Python310
    if (-not $python310) { Fail "Python 3.10 was installed but cannot be found. Restart Windows and run setup again." }
}
Write-Host $python310

Step "Creating the virtual environment (.venv)"
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $python310 -m venv .venv }
$python = ".venv\Scripts\python.exe"

Step "Installing packages (takes a few minutes the first time)"
& $python -m pip install --upgrade pip
& $python -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Fail "Installing requirements.txt failed. Send a screenshot of the red text above." }
# face_recognition must skip its 'dlib' requirement: dlib comes prebuilt from dlib-bin (see docs/research).
& $python -m pip install --no-deps face_recognition==1.3.0
if ($LASTEXITCODE -ne 0) { Fail "Installing face_recognition failed." }
& $python -c "import dlib, face_recognition, cv2; print('dlib', dlib.__version__, '| OpenCV', cv2.__version__)"
if ($LASTEXITCODE -ne 0) { Fail "dlib or face_recognition does not import. Send a screenshot." }

Step "Setting up MySQL and the local settings (instance\config.py)"
if (Test-Path "instance\config.py") {
    Write-Host "Settings already exist, keeping them."
    Start-OwnMysql
} elseif (Test-Path $passwordFile) {
    Write-Host "Using the MySQL that an earlier FaceID setup installed."
    Start-OwnMysql
    $password = (Get-Content $passwordFile -Raw).Trim()
    Write-Config $ownMysqlPort $password
} elseif (Get-Service -Name "MySQL*" -ErrorAction SilentlyContinue) {
    Write-Host "Found MySQL installed as a Windows service."
    $secure = Read-Host "MySQL root password (the one chosen in MySQL Installer)" -AsSecureString
    $password = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    Write-Config 3306 $password
} else {
    Write-Host "MySQL is not installed. Installing MySQL 8.0.46 for FaceID (download about 250 MB)."
    Install-OwnMysql
    $password = (Get-Content $passwordFile -Raw).Trim()
    Write-Config $ownMysqlPort $password
}

Step "Creating or upgrading the database"
& $python -m flask --app faceid db-upgrade
if ($LASTEXITCODE -ne 0) { Remove-Item instance\config.py; Fail "Could not reach MySQL. Run setup again; if MySQL80 is installed, make sure it is Running in Services and retype the password." }

Step "Admin account"
$answer = Read-Host "Create an Admin account now? (y/n)"
if ($answer -eq "y") { & $python -m flask --app faceid create-admin }

Write-Host "`nSetup finished. Start FaceID with run.bat." -ForegroundColor Green
Read-Host "Press Enter to close"

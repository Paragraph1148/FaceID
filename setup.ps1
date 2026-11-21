# FaceID setup for Windows. Run by double-clicking setup.bat.
# Needs: Python 3.10 (python.org, 3.10.11) and MySQL Server 8.0.46 already installed.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nSETUP FAILED: $text" -ForegroundColor Red; Read-Host "Press Enter to close"; exit 1 }

Step "Checking for Python 3.10"
try { $version = & py -3.10 --version 2>&1 } catch { $version = "" }
if ("$version" -notmatch "Python 3\.10") {
    Fail "Python 3.10 not found. Install Python 3.10.11 from https://www.python.org/downloads/release/python-31011/ (Windows installer 64-bit), then run setup again."
}
Write-Host $version

Step "Creating the virtual environment (.venv)"
if (-not (Test-Path ".venv\Scripts\python.exe")) { & py -3.10 -m venv .venv }
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

Step "Writing local settings (instance\config.py)"
if (Test-Path "instance\config.py") {
    Write-Host "Already exists, keeping it."
} else {
    New-Item -ItemType Directory -Force -Path instance | Out-Null
    $secure = Read-Host "MySQL root password (the one chosen in MySQL Installer)" -AsSecureString
    $password = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    $secret = & $python -c "import secrets; print(secrets.token_hex(32))"
    $escaped = $password.Replace('\', '\\').Replace('"', '\"')
    @"
# Local settings. Not committed.
SECRET_KEY = "$secret"
DB_HOST = "127.0.0.1"
DB_PORT = 3306
DB_USER = "root"
DB_PASSWORD = "$escaped"
DB_NAME = "faceid"
"@ | Set-Content -Encoding UTF8 instance\config.py
}

Step "Creating or upgrading the database"
& $python -m flask --app faceid db-upgrade
if ($LASTEXITCODE -ne 0) { Remove-Item instance\config.py; Fail "Could not reach MySQL. Is MySQL80 running, and was the password right? Run setup again to retype it." }

Step "Admin account"
$answer = Read-Host "Create an Admin account now? (y/n)"
if ($answer -eq "y") { & $python -m flask --app faceid create-admin }

Write-Host "`nSetup finished. Start FaceID with run.bat." -ForegroundColor Green
Read-Host "Press Enter to close"

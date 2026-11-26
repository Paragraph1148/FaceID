@echo off
cd /d "%~dp0"
rem Replaces everything in the database with a backup (SPEC F7.2). Drag the backup file onto this file, or type its path.
echo Close the FaceID window (run.bat) before restoring.
set "FILE=%~1"
if "%FILE%"=="" set /p FILE=Backup file to restore: 
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-mysql.ps1" || (pause & exit /b 1)
.venv\Scripts\python.exe -m flask --app faceid restore "%FILE%"
pause

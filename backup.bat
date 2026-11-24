@echo off
cd /d "%~dp0"
rem Saves every row of the database, Face Encodings included, to one file (SPEC F7.2).
set /p FILE=Save the backup as (for example D:\faceid-backup.json): 
.venv\Scripts\python.exe -m flask --app faceid backup "%FILE%"
pause

@echo off
cd /d "%~dp0"
echo FaceID is starting. Keep this window open; close it to stop FaceID.
start "" http://127.0.0.1:5000
.venv\Scripts\python.exe -m flask --app faceid run --host 0.0.0.0 --port 5000 --with-threads
pause

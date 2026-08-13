@echo off
echo [start] killing old processes on port 5000...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000.*LISTENING"') do (
    echo [start] killing PID %%a
    taskkill /F /PID %%a >nul 2>&1
)
echo [start] building React frontend...
cd /d "%~dp0frontend"
call npm run build
cd /d "%~dp0"
echo [start] starting FastAPI server on :5000...
python -m uvicorn main:app --port 5000 --reload
pause

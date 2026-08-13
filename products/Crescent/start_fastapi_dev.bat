@echo off
echo [dev] killing old processes on ports 5000 and 5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5000.*LISTENING"') do (
    echo [dev] killing PID %%a on :5000
    taskkill /F /PID %%a >nul 2>&1
)
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":5173.*LISTENING"') do (
    echo [dev] killing PID %%a on :5173
    taskkill /F /PID %%a >nul 2>&1
)

echo [dev] starting FastAPI backend on :5000 (DEBUG mode)...
start "FastAPI Backend" cmd /c "set FLASK_DEBUG=true && cd /d %~dp0 && python -m uvicorn main:app --port 5000 --reload"

echo [dev] starting Vite frontend on :5173...
cd /d "%~dp0frontend"
start "Vite Frontend" cmd /c "cd /d %~dp0frontend && npm run dev"

echo.
echo [dev] Both servers launching in separate windows.
echo [dev] Open http://localhost:5000/workbench in your browser.
echo [dev] (FastAPI redirects to Vite :5173 automatically in DEBUG mode)
echo.
pause

@echo off
setlocal enabledelayedexpansion
title OMEGA Platform Launcher
color 0A

echo.
echo  ==========================================
echo   OMEGA Platform Launcher
echo   AI Agent + Financial Tracker
echo  ==========================================
echo.

:: ── Check Python ────────────────────────────────────────────────────────────
echo [1/5] Checking Python...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python not found. Download from https://python.org
    echo         Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Python %PYVER% detected.

:: ── Check Node.js ────────────────────────────────────────────────────────────
echo.
echo [2/5] Checking Node.js...
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js not found. Download from https://nodejs.org
    pause
    exit /b 1
)
for /f "tokens=1" %%v in ('node --version') do set NODEVER=%%v
echo [OK] Node.js %NODEVER% detected.

:: ── Install Python dependencies ───────────────────────────────────────────
echo.
echo [3/5] Installing Python dependencies...
python -m pip install --upgrade pip -q
python -m pip install google-generativeai requests SpeechRecognition pyaudio -q
if %errorlevel% neq 0 (
    echo [WARN] pyaudio may have failed. Voice input may be limited.
    echo        All other features will work normally.
)
echo [OK] Python packages ready.

:: ── Install Node dependencies ─────────────────────────────────────────────
echo.
echo [4/5] Installing Node dependencies...
if not exist "node_modules\" (
    call npm install --silent
    if %errorlevel% neq 0 (
        echo [ERROR] npm install failed. Check your internet connection.
        pause
        exit /b 1
    )
    echo [OK] Node modules installed.
) else (
    echo [OK] node_modules already present, skipping.
)

:: ── Launch Vite Dev Server in background ──────────────────────────────────
echo.
echo [5/5] Starting services...
echo       Launching Vite dev server on http://localhost:3000 ...
start "OMEGA-Vite" /min cmd /c "npm run dev"

:: Short wait for Vite to bind its port
timeout /t 3 /nobreak >nul

:: Open browser automatically
start "" "http://localhost:3000"

echo.
echo  ==========================================
echo   Vite server started in background.
echo   Dashboard: http://localhost:3000
echo  ==========================================
echo.

:: ── Launch Omega Agent in foreground ──────────────────────────────────────
echo  Starting OMEGA AI Agent...
echo  (This window is the OMEGA console — keep it open)
echo.
python omega.py

:: If omega exits, keep window open
echo.
echo [OMEGA] Agent session ended.
pause

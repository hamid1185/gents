@echo off
echo ========================================
echo   NexusForge Local Development
echo ========================================

echo This script helps set up local development without Docker.
echo Make sure you have:
echo - Python 3.11+ installed
echo - Node.js 18+ installed  
echo - PostgreSQL running
echo - Redis running
echo.

REM Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is not installed or not in PATH
    goto :end
)

REM Check Node.js
node --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Node.js is not installed or not in PATH
    goto :end
)

REM Setup backend
echo Setting up backend...
cd backend
if not exist "venv" (
    echo Creating Python virtual environment...
    python -m venv venv
)
echo Activating virtual environment...
call venv\Scripts\activate.bat
echo Installing Python dependencies...
pip install -r requirements.txt
echo Backend setup complete!
cd ..

REM Setup frontend  
echo.
echo Setting up frontend...
cd frontend
echo Installing Node.js dependencies...
npm install
echo Frontend setup complete!
cd ..

echo.
echo ========================================
echo   Development Setup Complete!
echo ========================================
echo To start backend:
echo   cd backend
echo   venv\Scripts\activate.bat
echo   python main.py
echo.
echo To start frontend:
echo   cd frontend  
echo   npm start
echo.
:end
pause
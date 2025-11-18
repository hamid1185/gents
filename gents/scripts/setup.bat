@echo off
echo ========================================
echo    NexusForge Setup for Windows
echo ========================================

REM Check if Docker is running
docker version >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Docker is not running!
    echo Please start Docker Desktop and try again.
    pause
    exit /b 1
)

REM Copy environment file if it doesn't exist
if not exist ".env" (
    echo Creating .env file from template...
    copy "config\.env.example" ".env"
    echo Please edit .env and add your GEMINI_API_KEY
    echo Press any key to continue after editing...
    pause
)

REM Build and start services
echo Building and starting NexusForge services...
docker-compose up -d --build

echo.
echo ========================================
echo    Setup Complete!
echo ========================================
echo Frontend: http://localhost:3000
echo Backend:  http://localhost:8000
echo.
echo Check status: docker-compose ps
echo View logs:    docker-compose logs -f
echo Stop:         docker-compose down
echo.
pause
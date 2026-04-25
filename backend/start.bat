@echo off
setlocal
chcp 65001 >nul

echo ============================================
echo Backend startup script
echo ============================================

REM Move to script directory first
cd /d "%~dp0"

REM Defaults
if "%DB_BACKEND%"=="" set DB_BACKEND=mysql
if "%MIGRATE_SQLITE_TO_MYSQL%"=="" set MIGRATE_SQLITE_TO_MYSQL=0

echo [config] DB_BACKEND=%DB_BACKEND%
echo [config] MIGRATE_SQLITE_TO_MYSQL=%MIGRATE_SQLITE_TO_MYSQL%

REM Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo [error] Python not found. Install Python 3.9+
    exit /b 1
)

REM Install requirements
echo [1/3] Installing dependencies...
python -m pip install -r requirements.txt -q
if errorlevel 1 (
    echo [error] Failed to install requirements
    exit /b 1
)

if not exist "data" mkdir data

if "%MIGRATE_SQLITE_TO_MYSQL%"=="1" (
    echo [2/4] Initializing MySQL schema...
    python scripts\init_mysql_schema.py
    if errorlevel 1 (
        echo [error] Failed to initialize MySQL schema
        exit /b 1
    )

    echo [3/4] Migrating SQLite to MySQL...
    python scripts\migrate_sqlite_to_mysql.py --skip-missing-table
    if errorlevel 1 (
        echo [error] Data migration failed
        exit /b 1
    )
)

echo [3/3] Starting FastAPI on http://0.0.0.0:8000
echo Docs: http://127.0.0.1:8000/docs
echo Health: http://127.0.0.1:8000/health
echo ============================================

python -m uvicorn app_main:app --host 0.0.0.0 --port 8000 --reload

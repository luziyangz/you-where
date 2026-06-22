# MySQL 集成回归（Windows）
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host "[mysql-test] 检查 Docker..."
docker info 2>$null | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Host "错误: Docker 守护进程未运行。请先启动 Docker Desktop。" -ForegroundColor Red
    Write-Host "诊断: python scripts/check_mysql_test_env.py"
    exit 1
}

Write-Host "[mysql-test] 启动 docker compose..."
docker compose -f docker-compose.test.yml up -d

Write-Host "[mysql-test] 等待 MySQL..."
$ready = $false
for ($i = 1; $i -le 60; $i++) {
    docker compose -f docker-compose.test.yml exec -T mysql_test `
        mysqladmin ping -h 127.0.0.1 -uroot -ptest_root_pw --silent 2>$null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { throw "MySQL 未就绪" }

if (-not $env:MYSQL_TEST_HOST) { $env:MYSQL_TEST_HOST = "127.0.0.1" }
if (-not $env:MYSQL_TEST_PORT) { $env:MYSQL_TEST_PORT = "3307" }
if (-not $env:MYSQL_TEST_USER) { $env:MYSQL_TEST_USER = "you_where_test" }
if (-not $env:MYSQL_TEST_PASSWORD) { $env:MYSQL_TEST_PASSWORD = "test_app_pw" }
if (-not $env:MYSQL_TEST_DB) { $env:MYSQL_TEST_DB = "you_where_test" }

Write-Host "[mysql-test] pytest tests_mysql/ ..."
python -m pytest tests_mysql/ -v --tb=short @args

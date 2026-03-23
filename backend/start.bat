@echo off
chcp 65001 >nul
echo ============================================
echo  你在哪页 后端服务启动脚本
echo ============================================

:: 检查 Python 是否存在
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [错误] 未找到 Python，请先安装 Python 3.9+
    pause
    exit /b 1
)

:: 切换到脚本所在目录
cd /d "%~dp0"

:: 安装依赖（如果尚未安装）
echo [1/3] 检查并安装依赖...
pip install -r requirements.txt -q
if %errorlevel% neq 0 (
    echo [错误] 依赖安装失败，请检查 requirements.txt
    pause
    exit /b 1
)

:: 创建数据目录
if not exist "data" mkdir data

echo [2/3] 依赖安装完成
echo [3/3] 启动 FastAPI 服务（http://127.0.0.1:8000）...
echo.
echo  API 文档：http://127.0.0.1:8000/docs
echo  健康检查：http://127.0.0.1:8000/health
echo.
echo  按 Ctrl+C 停止服务
echo ============================================

python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload

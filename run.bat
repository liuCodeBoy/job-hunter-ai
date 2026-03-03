@echo off
chcp 65001 >nul
echo.
echo  ========================================
echo   🤖 job-hunter-ai 求职助手
echo  ========================================
echo.

:: 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未找到 Python，请先安装 Python 3.10+
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: 检查配置文件
if not exist "config.yaml" (
    echo [提示] 未找到 config.yaml，正在从示例文件复制...
    copy config.example.yaml config.yaml
    echo [提示] 请编辑 config.yaml 填写你的配置后重新运行
    notepad config.yaml
    pause
    exit /b 0
)

:: 安装依赖
echo [1/4] 检查并安装依赖...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo [错误] 依赖安装失败
    pause
    exit /b 1
)

:: 安装 Playwright Chromium
echo [2/4] 检查 Playwright 浏览器...
python -m playwright install chromium --quiet 2>nul
if errorlevel 1 (
    echo [提示] Playwright 浏览器安装中，请稍候...
    python -m playwright install chromium
)

:: 创建数据目录
if not exist "data" mkdir data

:: 运行主程序
echo [3/4] 启动求职助手...
echo.
python skills/job-hunter/scripts/main.py --config config.yaml

echo.
echo [4/4] 运行完成！
echo 数据库位置: data\jobs.db
echo 日志位置:   data\job-hunter.log
echo.
pause

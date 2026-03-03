#!/bin/bash
# Linux / macOS 一键运行脚本

set -e

echo ""
echo "========================================"
echo "  🤖 job-hunter-ai 求职助手"
echo "========================================"
echo ""

# 检查 Python
if ! command -v python3 &> /dev/null; then
    echo "[错误] 未找到 python3，请先安装 Python 3.10+"
    exit 1
fi

# 检查配置文件
if [ ! -f "config.yaml" ]; then
    echo "[提示] 未找到 config.yaml，从示例文件复制..."
    cp config.example.yaml config.yaml
    echo "[提示] 请编辑 config.yaml 填写配置后重新运行"
    echo "  nano config.yaml  或  vim config.yaml"
    exit 0
fi

# 安装依赖
echo "[1/4] 安装依赖..."
pip3 install -r requirements.txt -q

# 安装 Playwright 浏览器（Linux 需要系统依赖）
echo "[2/4] 检查 Playwright 浏览器..."
if ! python3 -m playwright install chromium --quiet 2>/dev/null; then
    echo "[提示] 正在安装浏览器依赖（需要 sudo）..."
    sudo python3 -m playwright install-deps chromium
    python3 -m playwright install chromium
fi

# 创建数据目录
mkdir -p data

# 运行
echo "[3/4] 启动求职助手..."
echo ""
python3 skills/job-hunter/scripts/main.py --config config.yaml

echo ""
echo "[4/4] 运行完成！"
echo "数据库: data/jobs.db"
echo "日志:   data/job-hunter.log"

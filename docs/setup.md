# 详细部署指南

## Windows (WSL2) 部署

```bash
# 1. 安装 Python 依赖
pip install -r requirements.txt

# 2. 安装 Chrome（WSL2 内）
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb

# 3. 配置
cp config.example.yaml config.yaml
# 编辑 config.yaml

# 4. 运行
python skills/job-hunter/scripts/main.py
```

## Linux 服务器部署

```bash
# 无图形界面服务器需要安装虚拟显示
sudo apt install xvfb

# 运行时加上虚拟显示
xvfb-run python skills/job-hunter/scripts/main.py
```

## macOS 部署

```bash
# 安装 Chrome
brew install --cask google-chrome

# 安装依赖
pip install -r requirements.txt

# 运行
python skills/job-hunter/scripts/main.py
```

## 定时任务配置

### Linux/macOS (crontab)

```bash
crontab -e

# 每天早上 9:00
0 9 * * * cd /path/to/job-hunter-ai && python skills/job-hunter/scripts/main.py >> data/cron.log 2>&1
```

### Windows (任务计划程序)

1. 打开"任务计划程序"
2. 创建基本任务
3. 触发器：每天 09:00
4. 操作：启动程序 → `python` → 参数 `skills/job-hunter/scripts/main.py`

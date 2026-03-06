# OpenQuant Makefile
# Windows 用户可配合 Git Bash 或 WSL 使用，或直接使用下方等效命令

PYTHON ?= python
PROJECT_ROOT := $(shell pwd)

.PHONY: setup config scan run status logs report backtest optimize test clean

# 环境配置
setup:
	$(PYTHON) -m pip install -r requirements.txt
	@echo "创建目录结构..."
	@mkdir -p data/db logs notebooks
	@if [ ! -f config/.env ]; then cp config/.env.example config/.env; echo "已复制 config/.env.example -> config/.env"; fi
	@echo "执行 make config 配置 API 密钥"

config:
	@echo "请手动编辑 config/.env 填入 MINIMAX_API_KEY 和 DINGTALK_WEBHOOK"
	@echo "文件路径: $(PROJECT_ROOT)/config/.env"

# 日常操作
scan:
	$(PYTHON) -m src.main scan

scan-symbols:
	$(PYTHON) -m src.main scan --symbols $(SYMBOLS)

run:
	$(PYTHON) -m src.main run --interval $(or $(INTERVAL),30)

# 监控
status:
	$(PYTHON) -m src.main status

logs:
	@ls -la logs/
	@echo "--- 今日日志 ---"
	@cat logs/$$(date +%Y%m%d)/trading.log 2>/dev/null || echo "暂无日志"

report:
	$(PYTHON) -m src.main report --period $(or $(PERIOD),day)

# 维护
backtest:
	$(PYTHON) -m jupyter nbconvert --execute notebooks/backtest.ipynb --to html 2>/dev/null || \
		echo "请手动运行 notebooks/backtest.ipynb"

optimize:
	@echo "参数优化功能待实现"

test:
	$(PYTHON) -m pytest tests/ -v

test-cov:
	$(PYTHON) -m pytest tests/ -v --cov=src --cov-report=html

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -type f -name "*.pyc" -delete 2>/dev/null; true
	rm -rf .pytest_cache .coverage htmlcov/

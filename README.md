# OpenQuant

AI 半自动量化交易系统：AI 生成信号 → 人工确认 → 自动执行。

## 架构概览

```
用户交互(CLI/Web/钉钉) → 决策引擎(MiniMax+风控) → 执行层(模拟/实盘) → 数据层(AKShare/SQLite)
```

## 快速开始

### 1. 环境配置

```bash
# 安装依赖
pip install -r requirements.txt

# 配置大模型 API Key
cp config/model.yaml.example config/model.yaml
# 编辑 config/model.yaml 填入 minimax.api_key
```

### 2. 配置说明

详见 [docs/CONFIG.md](docs/CONFIG.md)

| 文件 | 说明 |
|------|------|
| `config/model.yaml` | 大模型配置（含 api_key，复制 model.yaml.example） |
| `config/trading.yaml` | 风控、运行参数、通知 |
| `config/watchlist.txt` | 自选股代码，每行一个 |

### 3. 运行命令

详见 [docs/COMMANDS.md](docs/COMMANDS.md)

| 命令 | 说明 |
|------|------|
| `python -m src.main scan` | 单次扫描自选股 |
| `python -m src.main scan --symbols 000001,600519 --mode short` | 扫描指定股票+投资模式 |
| `python -m src.main run` | 定时模式（默认 30 分钟） |
| `python -m src.main pick` | AI 选股 |
| `python -m src.main watch` | 实时监控股价 |
| `python -m src.main status` | 查看持仓与盈亏 |
| `python -m src.main report` | 生成复盘报告 |
| `python -m src.main watchlist list` | 自选股管理 |
| `python -m src.main test` | 运行测试 |

## 项目结构

```
openquant/
├── config/           # 配置
├── src/
│   ├── analyzer/     # MiniMax AI 分析
│   ├── data/         # AKShare 数据
│   ├── risk/         # 风控引擎
│   ├── execution/    # 交易执行
│   ├── notification/ # 钉钉/飞书
│   └── ui/           # CLI/Web
├── data/             # 数据与数据库
├── logs/             # 日志
├── notebooks/        # 回测与分析
└── tests/            # 测试
```

## 风控规则（硬规则）

- 单票最大仓位 30%
- 止损 5% 强制平仓
- 单日最大亏损 2% 触发全天停止

## 渐进式实盘路径

1. **纯回测** (1-2 月) - 验证策略
2. **模拟盘** (2-3 月) - 验证执行
3. **小资金实盘** (3-6 月) - 1-3 万起步
4. **逐步放大** - 策略容量验证
5. **全自动** - 连续稳定后考虑

## 许可证

MIT

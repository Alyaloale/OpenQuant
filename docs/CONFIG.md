# OpenQuant 配置说明

## 目录结构

```
OpenQuant/
├── config/                 # 配置文件
│   ├── model.yaml          # 大模型配置（含 api_key，不提交）
│   ├── model.yaml.example  # 大模型配置模板
│   ├── trading.yaml        # 策略、风控、运行参数（可提交）
│   ├── watchlist.txt       # 自选股列表
│   └── watchlist.example.txt
├── data/                   # 数据目录
│   └── db/                 # 数据库
│       └── trades.sqlite   # 模拟交易记录（不提交）
├── logs/                   # 日志
│   └── YYYYMMDD/           # 按日期
│       └── trading.log
└── ...
```

## 配置文件

| 文件 | 说明 | 是否提交 |
|------|------|----------|
| `config/model.yaml` | 大模型配置（含 api_key，勿提交） | ❌ |
| `config/model.yaml.example` | 大模型配置模板 | ✅ |
| `config/trading.yaml` | 风控、仓位、运行参数、通知 | ✅ |
| `config/watchlist.txt` | 自选股代码列表 | ✅ |
| `data/db/trades.sqlite` | 模拟交易记录 | ❌ |
| `logs/` | 运行日志 | ❌ |

## 路径覆盖

通过环境变量自定义路径：

| 变量 | 默认 | 说明 |
|------|------|------|
| `TRADE_DATA_DIR` | `data` | 数据根目录，含 db/ |
| `TRADE_LOG_DIR` | `logs` | 日志根目录 |

支持相对路径（相对项目根）或绝对路径。

## 配置说明

**config/model.yaml**（大模型，含 api_key，不提交）：
- `minimax`: api_key、base_url、model、timeout_ms、temperature
- `deepseek`: 同上，供扩展使用

**config/trading.yaml**（策略与运行，可提交）：
- `runtime`: trade_mode、initial_capital
- `notification`: dingtalk_webhook、feishu_webhook
- `risk`、`trading` 等

## 快速开始

```bash
# 1. 复制大模型配置并填入 api_key
cp config/model.yaml.example config/model.yaml
# 编辑 config/model.yaml 中的 minimax.api_key

# 2. （可选）编辑 config/trading.yaml 风控与通知

# 3. （可选）编辑 config/watchlist.txt 自选股
```

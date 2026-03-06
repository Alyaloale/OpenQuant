# OpenQuant 命令参考

所有命令以 `python -m src.main <command> [options]` 形式调用。

---

## 1. scan — 单次扫描自选股

对自选股进行 AI 分析，产生交易信号并进入人工确认流程。

```bash
# 扫描自选股（使用 config/watchlist.txt）
python -m src.main scan

# 扫描指定股票
python -m src.main scan --symbols 000001,600519,000858

# 指定投资模式
python -m src.main scan --mode short
python -m src.main scan --mode medium
python -m src.main scan --mode long

# 组合使用
python -m src.main scan --symbols 000001,600519 --mode long
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--symbols` | 股票代码，逗号分隔 | 使用自选股 |
| `--mode` | 投资模式：short/medium/long | config/trading.yaml |

---

## 2. run — 定时扫描模式

按固定间隔重复执行扫描，直到手动中断。

```bash
# 每 30 分钟扫描一次（默认）
python -m src.main run

# 每 15 分钟扫描一次
python -m src.main run --interval 15

# 指定投资模式
python -m src.main run --mode short --interval 60
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--interval` | 扫描间隔（分钟） | 30 |
| `--mode` | 投资模式 | config |

---

## 3. pick — AI 选股

从股池中筛选并生成 AI 交易信号。

```bash
# 从人气榜取 20 只分析（默认）
python -m src.main pick

# 分析 30 只
python -m src.main pick --limit 30

# 从自选股池选股
python -m src.main pick --pool watchlist

# 选股后询问是否加入自选
python -m src.main pick --add

# 指定投资模式
python -m src.main pick --mode long --limit 15 --add
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--pool` | 股池：hot（人气榜）/ watchlist（自选股） | hot |
| `--limit` | 分析数量 | 20 |
| `--add` | 选股后询问是否加入自选 | 否 |
| `--mode` | 投资模式 | config |

---

## 4. watch — 实时监控股价

按设定间隔轮询显示股价（免费接口有延迟）。

```bash
# 监控自选股，每 10 秒刷新
python -m src.main watch

# 监控指定股票
python -m src.main watch --symbols 000001,600519

# 每 15 秒刷新
python -m src.main watch --interval 15
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--symbols` | 股票代码，逗号分隔 | 自选股 |
| `--interval` | 刷新间隔（秒） | 10 |

**说明**：Ctrl+C 退出监控。

---

## 5. status — 查看持仓与盈亏

```bash
python -m src.main status
```

---

## 6. report — 生成复盘报告

```bash
# 日复盘（默认）
python -m src.main report

# 周复盘
python -m src.main report --period week

# 月复盘
python -m src.main report --period month
```

| 参数 | 说明 | 默认 |
|------|------|------|
| `--period` | 报告周期：day/week/month | day |

---

## 7. watchlist — 自选股管理

```bash
# 显示当前自选股
python -m src.main watchlist list
python -m src.main watchlist

# 添加股票
python -m src.main watchlist add 000001

# 移除股票
python -m src.main watchlist remove 600519
```

---

## 8. test — 运行测试

```bash
python -m src.main test
```

---

## AI 调用方式

每只股票为**一次独立 API 调用**，结构为：`[system 消息, user 消息]`。无多轮对话，无上下文共享。

- 同一批次扫描多只股票时，各次调用互不影响
- 投资模式（short/medium/long）通过 system 消息注入，确保大模型严格遵循对应分析侧重点

---

## 投资模式 (--mode)

| 值 | 含义 | 持仓周期 |
|----|------|----------|
| `short` | 短线 | 数日~2 周 |
| `medium` | 中线 | 数周~3 月 |
| `long` | 长线 | 数月~年 |

默认从 `config/trading.yaml` 的 `investment_mode` 读取，命令行 `--mode` 可临时覆盖。

---

## 帮助

```bash
python -m src.main --help
python -m src.main scan --help
python -m src.main pick --help
# 各子命令均支持 --help
```

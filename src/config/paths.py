"""
统一路径解析
优先级: 环境变量 > 项目默认路径
"""

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def get_config_dir() -> Path:
    """配置文件目录"""
    return PROJECT_ROOT / "config"


def get_data_dir() -> Path:
    """数据根目录。环境变量 TRADE_DATA_DIR 可覆盖（支持相对/绝对路径）"""
    env = os.getenv("TRADE_DATA_DIR")
    if env:
        p = Path(env)
        return p if p.is_absolute() else PROJECT_ROOT / p
    return PROJECT_ROOT / "data"


def get_log_dir() -> Path:
    """日志根目录。环境变量 TRADE_LOG_DIR 可覆盖"""
    env = os.getenv("TRADE_LOG_DIR")
    if env:
        p = Path(env)
        return p if p.is_absolute() else PROJECT_ROOT / p
    return PROJECT_ROOT / "logs"


def get_db_path() -> Path:
    """交易数据库路径"""
    return get_data_dir() / "db" / "trades.sqlite"


def get_watchlist_path() -> Path:
    """自选股列表文件路径"""
    return get_config_dir() / "watchlist.txt"


def get_trading_config_path() -> Path:
    """trading.yaml 路径"""
    return get_config_dir() / "trading.yaml"


def ensure_dirs():
    """确保数据、日志、数据库目录存在"""
    get_data_dir().mkdir(parents=True, exist_ok=True)
    (get_data_dir() / "db").mkdir(parents=True, exist_ok=True)
    get_log_dir().mkdir(parents=True, exist_ok=True)

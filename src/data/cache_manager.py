"""
本地缓存管理
SQLite 存储，减少 API 调用
"""

# TODO: 实现缓存
# - 日线数据按 symbol+date 缓存
# - TTL 策略 (收盘后数据长期有效)
# - 增量更新


class CacheManager:
    """本地缓存管理器"""

    def __init__(self, db_path: str = None):
        self.db_path = db_path

    def get(self, key: str) -> object:
        raise NotImplementedError("缓存获取待实现")

    def set(self, key: str, value: object, ttl: int = None):
        raise NotImplementedError("缓存写入待实现")

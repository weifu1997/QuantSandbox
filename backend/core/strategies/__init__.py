"""策略实现目录。

避免在包导入时自动加载 registry，防止旧 strategy.py -> backend.core.strategies.*
路径上的循环导入。需要 registry 时请直接导入 `backend.core.strategies.registry`。
"""

__all__: list[str] = []

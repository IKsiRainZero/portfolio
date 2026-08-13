"""DataSourceManager — 注册表、健康监控、降级编排、Agent tool 自动生成"""
from __future__ import annotations
import time
from services.data_sources.base import DataSource


class DataSourceManager:
    """管理所有数据源的注册、健康监控和 Agent 工具生成。"""

    def __init__(self):
        self._sources: dict[str, DataSource] = {}
        self._health: dict[str, bool] = {}
        self._last_check: float = 0
        self._check_interval: float = 300  # 5 min

    def register(self, source: DataSource) -> None:
        self._sources[source.name] = source
        self._health[source.name] = True  # 初始假设可达

    def get(self, name: str) -> DataSource | None:
        return self._sources.get(name)

    def list_sources(self) -> list[str]:
        return list(self._sources.keys())

    def health_check_all(self) -> dict[str, bool]:
        """检查所有源健康状态（带节流：5分钟内复用上次结果）"""
        now = time.time()
        if now - self._last_check < self._check_interval:
            return dict(self._health)
        for name, source in self._sources.items():
            self._health[name] = source.health_check()
        self._last_check = now
        return dict(self._health)

    def get_briefs(self, name: str, **params) -> tuple:
        """获取指定源的简报数据。返回 (data, stale, message)"""
        source = self.get(name)
        if source is None:
            return ([], False, f"数据源 '{name}' 未注册")
        if hasattr(source, "get_briefs"):
            return source.get_briefs(**params)
        return ([], False, "")

    def make_tool(self, source: DataSource):
        """为数据源生成 LangChain @tool。"""
        from langchain_core.tools import tool

        @tool
        def source_search(query: str = "") -> str:
            """查询{name}数据。参数query: 筛选关键词或留空获取最新。""".replace(
                "{name}", source.name
            )
            try:
                result = source.fetch(categories=[
                    _get_user_setting("news_categories", ["technology", "science"])
                ])
                validated = source.validate(result)
                return source.format_for_agent(validated)
            except Exception as e:
                return f"{source.name} 查询失败: {str(e)}"

        # 设置动态名称和描述
        source_search.name = f"{source.name}_search"
        source_search.__doc__ = (
            f"查询{source.name}数据获取最新信息。"
            f"参数query: 筛选关键词或留空获取最新。"
        )
        return source_search

    def get_all_tools(self) -> list:
        """返回所有已注册源的 Agent tool 列表。"""
        tools = []
        for name, source in self._sources.items():
            tools.append(self.make_tool(source))
        return tools


def _get_user_setting(key, default=None):
    """安全读取用户设置，不依赖 Flask 上下文。"""
    try:
        from services.user_settings import get_setting
        return get_setting(key, default)
    except Exception:
        return default


# 全局单例
manager = DataSourceManager()


def get_manager() -> DataSourceManager:
    return manager

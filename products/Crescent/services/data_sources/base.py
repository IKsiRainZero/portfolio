"""DataSource 抽象基类 — 所有数据源实现此接口"""
from abc import ABC, abstractmethod


class DataSource(ABC):
    """数据源适配器基类。

    每个方法明确标注是硬编码还是允许LLM参与：
    - 硬编码: 行为确定性，不依赖 LLM
    - LLM可辅助: 可引入 LLM 做语义理解，但有规则回退
    """
    name: str = "base"

    @abstractmethod
    def fetch(self, **params) -> list[dict]:
        """从外部源获取原始数据。 [硬编码: 超时/重试/UA]"""

    @abstractmethod
    def validate(self, raw: list[dict]) -> list[dict]:
        """校验数据质量。 [硬编码: schema/敏感词/去重]"""

    @abstractmethod
    def transform(self, raw: list[dict]) -> list[dict]:
        """标准化为内部格式。 [硬编码: 字段映射]"""

    @abstractmethod
    def format_for_agent(self, data: list[dict]) -> str:
        """转换为 LLM 可读文本。 [硬编码: 拼接; 后续可 LLM 辅助摘要]"""

    @abstractmethod
    def format_for_ui(self, data: list[dict]) -> list[dict]:
        """转换为前端渲染结构。 [硬编码: 字段裁剪]"""

    @abstractmethod
    def health_check(self) -> bool:
        """检查外部源是否可达。 [硬编码: HEAD/快速请求]"""

    def get_schema_hash(self, data: list[dict]) -> str:
        """计算数据 schema hash，用于 drift detection。"""
        import hashlib, json
        if not data:
            return ""
        keys = sorted(data[0].keys())
        return hashlib.sha256(json.dumps(keys).encode()).hexdigest()[:16]

"""新闻聚合 API 数据源 — 基于 NewsAPI.org 格式"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import time, requests
from services.data_sources.base import DataSource
from services.data_sources.filters import (
    filter_sensitive, deduplicate, validate_schema, detect_drift
)
from services.data_sources.cache import save_cache, load_cache, get_stale_data
from config import NEWS_API_KEY, NEWS_API_URL, NEWS_CACHE_TTL
from services.user_settings import get_setting

_REQUIRED_FIELDS = ("title", "url")

# 类别映射: 用户偏好 → API 参数
_CATEGORY_MAP = {
    "technology": "technology",
    "science": "science",
    "business": "business",
    "general": "general",
    "entertainment": "entertainment",
    "health": "health",
    "sports": "sports",
    "ai": "technology",
    "education": "general",
    "finance": "business",
    "politics": "general",
}

# 种子数据：API 未配置/不可达时的降级占位，配好 API Key 后自动替换
# 种子数据：2026-06-23 通过 WebSearch 搜集的真实 AI 新闻
# API Key 未配置时兜底展示，API 连通后自动替换为实时新闻
_SEED_BRIEFS = [
    {
        "source": "豆包2.1 Pro",
        "title": "字节发布豆包2.1 Pro：日均Token 180万亿，编程/Agent/视觉三项超Claude Opus 4.6，成本低近80%",
        "url": "https://www.cnstock.com/commonDetail/732838",
    },
    {
        "source": "Anthropic",
        "title": "Anthropic呼吁全球协调暂停前沿AI发展，称Claude正加速走向递归自我改进(RSI)，引发巨大争议",
        "url": "https://f.aa.com.tr/en/science-technology/anthropic-calls-for-global-coordination-to-pause-frontier-ai-development/3957328",
    },
    {
        "source": "OpenAI",
        "title": "OpenAI砸1.5亿美元联合麦肯锡/BCG培训30万AI顾问，AI竞争从模型参数转向企业落地最后一公里",
        "url": "https://36kr.com/p/3857988458681608",
    },
    {
        "source": "WAIC 2026",
        "title": "2026世界人工智能大会(上海)将首发超300款AI产品，设140+论坛，图灵奖得主姚期智主持首届WAIC学术会议",
        "url": "https://news.cctv.com/2026/06/17/ARTIsLfWMTkZMEIcS4SkjdmV260617.shtml",
    },
    {
        "source": "微软",
        "title": "纳德拉炮轰AI巨头：不能一边恐吓大众渲染AI风险，一边索要海量资源独吞价值；微软德州新增2吉瓦数据中心",
        "url": "https://www.163.com/dy/article/L02DTC2R051481US.html",
    },
    {
        "source": "AI算力",
        "title": "AI算力格局生变：CPU需求暴增，摩根大通预测2027年ASIC出货量将首超英伟达GPU，博通AI订单超300亿美元",
        "url": "https://cqcb.com/shuzijingji/2026-06-23/6166373_pc.html",
    },
]


def _resolve_api_key() -> str:
    """env NEWS_API_KEY 优先，user_settings news_api_key 兜底"""
    key = NEWS_API_KEY
    if not key:
        key = get_setting("news_api_key", "")
    return key


class NewsSource(DataSource):
    name = "news"

    def fetch(self, **params) -> list[dict]:
        """从 NewsAPI 获取新闻。参数: categories(list), count(int)"""
        categories = params.get("categories", ["technology", "science"])
        count = params.get("count", 5)

        all_articles = []
        ua = "PortfolioApp/1.0 (Learning Assistant)"

        for cat in categories[:3]:  # 最多 3 个分类
            api_cat = _CATEGORY_MAP.get(cat, "general")
            try:
                r = requests.get(
                    NEWS_API_URL,
                    params={
                        "apiKey": _resolve_api_key(),
                        "category": api_cat,
                        "pageSize": max(count, 10),
                        "country": "cn",
                    },
                    headers={"User-Agent": ua},
                    timeout=10,
                )
                r.encoding = "utf-8"
                body = r.json()
                if body.get("status") == "ok":
                    for art in body.get("articles", []):
                        all_articles.append({
                            "title": str(art.get("title", "")).strip(),
                            "source": str(art.get("source", {}).get("name", "")).strip(),
                            "url": str(art.get("url", "")).strip(),
                            "summary": str(art.get("description", "")).strip(),
                            "published_at": str(art.get("publishedAt", "")).strip(),
                            "category": cat,
                        })
            except Exception:
                continue  # 单个分类失败不影响其他

        return all_articles

    def validate(self, raw: list[dict]) -> list[dict]:
        """校验: schema + 敏感词 + 去重"""
        passed, errors = validate_schema(raw, _REQUIRED_FIELDS)
        if errors:
            # 日志记录但不阻塞 — 错误条目直接丢弃
            print(f"[NewsSource] schema errors: {errors[:3]}")
        clean = filter_sensitive(passed)
        clean = deduplicate(clean, "title")
        return clean

    def transform(self, raw: list[dict]) -> list[dict]:
        """标准化 — 当前与原始格式一致，预留字段映射"""
        return raw

    def format_for_agent(self, data: list[dict]) -> str:
        """拼接为 LLM 可读文本"""
        if not data:
            return "当前无可用新闻数据。"
        lines = ["[实时新闻] 以下来自聚合新闻 API:\n"]
        for i, art in enumerate(data, 1):
            src = art.get("source", "未知")
            title = art.get("title", "")
            summary = art.get("summary", "")
            lines.append(f"{i}. [{src}] {title}")
            if summary:
                lines.append(f"   {summary[:120]}")
        return "\n".join(lines)

    def format_for_ui(self, data: list[dict]) -> list[dict]:
        """前端卡片: source + title + url"""
        return [
            {
                "source": art.get("source", ""),
                "title": art.get("title", ""),
                "url": art.get("url", ""),
            }
            for art in data
        ]

    def health_check(self) -> bool:
        """HEAD 请求 API 根路径验证可达性"""
        try:
            r = requests.head(NEWS_API_URL, timeout=5)
            return r.status_code < 500
        except Exception:
            return False

    def get_briefs(self, categories: list = None, count: int = 5) -> tuple:
        """完整获取流程: fetch → validate → transform → cache。
        返回 (briefs: list[dict], stale: bool, message: str)
        """
        categories = categories or ["technology", "science"]

        # 无 API Key (env + user_settings) 时跳过 fetch，直接走降级链
        if not _resolve_api_key():
            return self._fallback_to_cache_or_seed()

        # 尝试新鲜数据
        try:
            raw = self.fetch(categories=categories, count=count)
            validated = self.validate(raw)
            if validated:
                transformed = self.transform(validated)
                schema_hash = self.get_schema_hash(transformed)

                cached = load_cache(self.name)
                if cached and cached.get("schema_hash"):
                    if detect_drift(transformed, cached["schema_hash"]):
                        print(f"[NewsSource] schema drift detected, logging")

                save_cache(self.name, transformed, schema_hash, NEWS_CACHE_TTL)
                ui_data = self.format_for_ui(transformed)
                return (ui_data, False, "")
        except Exception as e:
            print(f"[NewsSource] fetch failed: {e}")

        return self._fallback_to_cache_or_seed()

    def _fallback_to_cache_or_seed(self) -> tuple:
        """降级: 缓存 → 种子数据"""
        # 读缓存（无视 TTL）
        stale = get_stale_data(self.name)
        if stale and stale.get("data"):
            ui_data = self.format_for_ui(stale["data"])
            age_min = int((time.time() - stale.get("fetched_at", 0)) / 60)
            return (ui_data, True, f"{age_min}分钟前")

        # 彻底失败 → 种子占位数据
        return (_SEED_BRIEFS, True, "预置数据 · 配置 API 后自动更新")

from __future__ import annotations
import requests
from config import BRAVE_API_KEY, SERPAPI_KEY
from services.pipeline.protocols import Step
from services.pipeline.types import StepInput, StepOutput

BRAVE_URL = "https://api.search.brave.com/res/v1/web/search"
SERPAPI_URL = "https://serpapi.com/search"
DEFAULT_TIMEOUT = 10  # seconds


def is_search_available() -> bool:
    """Check if any search API is configured."""
    return bool(SERPAPI_KEY) or bool(BRAVE_API_KEY)


def _search_serpapi(query: str, max_results: int) -> list[dict]:
    try:
        resp = requests.get(
            SERPAPI_URL,
            params={
                "q": query,
                "api_key": SERPAPI_KEY,
                "num": min(max_results, 20),
                "engine": "google",
            },
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("organic_results", [])
        return [
            {
                "url": r.get("link", ""),
                "title": r.get("title", ""),
                "snippet": r.get("snippet", ""),
            }
            for r in results
        ]
    except Exception:
        return []


def _search_brave(query: str, max_results: int) -> list[dict]:
    try:
        resp = requests.get(
            BRAVE_URL,
            params={"q": query, "count": min(max_results, 20)},
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": BRAVE_API_KEY,
            },
            timeout=DEFAULT_TIMEOUT,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("web", {}).get("results", [])
        return [
            {
                "url": r.get("url", ""),
                "title": r.get("title", ""),
                "snippet": r.get("description", ""),
            }
            for r in results
        ]
    except Exception:
        return []


def search_web(query: str, max_results: int = 10) -> list[dict]:
    """搜索公网，返回 [{url, title, snippet}]。SerpAPI 优先，Brave 兜底。"""
    if SERPAPI_KEY:
        return _search_serpapi(query, max_results)
    if BRAVE_API_KEY:
        return _search_brave(query, max_results)
    return []


class SearchStep:
    """S3 子步骤：搜索公网获取 URL 列表。实现 Step 协议。"""

    def __init__(self, name: str = "S3_search") -> None:
        self.name = name

    def can_skip(self, input: StepInput) -> bool:
        return bool(input.config.get("skip_search"))

    def run(self, input: StepInput) -> StepOutput:
        max_results = input.config.get("max_results", 10)
        results = search_web(input.query, max_results)
        available = is_search_available()
        if not results:
            if not available:
                return StepOutput(
                    step_name=self.name,
                    status="ok",
                    data={"results": [], "count": 0, "warning": "No search API key configured (SerpAPI/Brave)"},
                    confidence=1.0,
                )
            return StepOutput(
                step_name=self.name,
                status="ok",
                data={"results": [], "count": 0, "warning": "Search returned 0 results"},
                confidence=0.5,
            )
        return StepOutput(
            step_name=self.name,
            status="ok",
            data={"results": results, "count": len(results)},
            confidence=0.7,
        )

from __future__ import annotations
import requests
from services.pipeline.dedup import deduplicate
from services.pipeline.protocols import Step
from services.pipeline.types import StepInput, StepOutput

DEFAULT_TIMEOUT = 8  # 轻量抓取，8s 超时


def fetch_url(url: str, timeout: int = DEFAULT_TIMEOUT) -> str | None:
    """抓取单个 URL，返回 HTML 文本。失败返回 None。"""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Crescent/0.4 (Research Agent)"},
        )
        resp.raise_for_status()
        return resp.text
    except Exception:
        return None


class FetchStep:
    """S3 子步骤：批量抓取搜索结果 URL。"""

    def __init__(self, name: str = "S3_fetch") -> None:
        self.name = name

    def can_skip(self, input: StepInput) -> bool:
        return not input.previous_outputs.get("S3_search", {}).get("results")

    def run(self, input: StepInput) -> StepOutput:
        from services.pipeline.normalizer import normalize
        from services.pipeline.types import IngestedDocument

        search_results = input.previous_outputs.get("S3_search", {}).get("results", [])
        urls = [r["url"] for r in search_results]
        docs: list[IngestedDocument] = []
        errors: list[str] = []

        for i, url in enumerate(urls):
            html = fetch_url(url)
            if html is None:
                errors.append(url)
                continue
            try:
                doc = normalize(html, url, source_type="webpage")
            except Exception as e:
                errors.append(f"{url}: {e}")
                continue
            docs.append(doc)

        docs = deduplicate(docs)

        return StepOutput(
            step_name=self.name,
            status="ok" if docs else "error",
            data={"documents": docs, "errors": errors, "fetched": len(docs), "total": len(urls)},
            confidence=0.8 if docs else 0.0,
        )

from __future__ import annotations
import re
from datetime import datetime, timezone
from services.pipeline.types import IngestedDocument, new_event_id


def _title_from_html(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip()[:200] if m else "Untitled"


def _clean_body(html: str) -> str:
    """去标签 + 去多余空白，保留正文。"""
    # 去 script/style
    text = re.sub(r"<(script|style|nav|footer|header)[^>]*>.*?</\1>", "", html, flags=re.DOTALL | re.IGNORECASE)
    # 去 HTML 标签
    text = re.sub(r"<[^>]+>", " ", text)
    # 去 HTML 实体
    text = re.sub(r"&[a-z]+;", " ", text)
    # 合并空白
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_tags(text: str) -> list[str]:
    """简单关键词抽取，不做语义分析。后续可接入 LLM 标注。"""
    keywords = [
        "transformer", "attention", "neural network", "deep learning",
        "machine learning", "LLM", "RAG", "agent", "reinforcement learning",
        "computer vision", "NLP", "embedding", "fine-tuning",
        "diffusion", "GAN", "CLIP", "BERT", "GPT",
    ]
    found = [kw for kw in keywords if kw.lower() in text.lower()]
    return found[:5]


def normalize(raw_html: str, url: str, source_type: str) -> IngestedDocument:
    """HTML → IngestedDocument。核心平坦字段必填，structured 暂不填充。"""
    title = _title_from_html(raw_html)
    body = _clean_body(raw_html)
    text = f"{title}\n\n{body}"
    tags = _extract_tags(text)

    return IngestedDocument(
        id=new_event_id(),
        text=text[:10000],  # 截断到 10k 字符，后续可按需扩展
        source_url=url,
        source_type=source_type,
        tags=tags,
        fetched_at=datetime.now(timezone.utc).isoformat(),
        structured={
            "title": title,
            "original_length": len(body),
            "truncated": len(body) > 10000,
        },
    )

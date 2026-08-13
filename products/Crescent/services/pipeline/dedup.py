from __future__ import annotations
from services.pipeline.types import IngestedDocument


def _jaccard_sim(a: str, b: str) -> float:
    """字符级 3-gram Jaccard，快且无需外部依赖。"""
    def ngrams(s, n=3):
        return {s[i:i+n] for i in range(max(0, len(s) - n + 1))}
    sa, sb = ngrams(a), ngrams(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def deduplicate(docs: list[IngestedDocument], threshold: float = 0.85) -> list[IngestedDocument]:
    """去重：文本相似度 > threshold 的文档保留第一个，后续丢弃。"""
    if len(docs) <= 1:
        return docs
    kept: list[IngestedDocument] = []
    for doc in docs:
        is_dup = False
        for k in kept:
            if _jaccard_sim(doc.text[:2000], k.text[:2000]) > threshold:
                is_dup = True
                break
        if not is_dup:
            kept.append(doc)
    return kept

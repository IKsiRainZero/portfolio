"""Credibility gate — filter papers before knowledge base import."""
import json
import re
from services.deepseek_client import chat

RELEVANT_CATEGORIES = {
    "cs.AI", "cs.CL", "cs.LG", "cs.MA", "cs.IR", "cs.SE",
    "stat.ML", "cs.HC",
}

DEFAULT_THRESHOLD = 0.5


def check_relevance(paper, project_cats=None):
    """Score 0-1 based on arXiv category overlap with our project interests."""
    if project_cats is None:
        project_cats = RELEVANT_CATEGORIES
    cats = set(paper.get("categories", []))
    if not cats:
        return 0.3
    overlap = cats & project_cats
    if overlap:
        return min(1.0, len(overlap) / max(len(cats), 1) + 0.3)
    return 0.1


def check_abstract_quality(paper):
    abstract = paper.get("abstract", "")
    if not abstract or len(abstract) < 50:
        return 0.0
    if len(abstract) < 150:
        return 0.5
    return 0.8


def _llm_credibility(paper):
    prompt = f"""评估以下论文的可信度（不需要访问外部链接）：
标题: {paper.get('title', '')}
作者: {', '.join(paper.get('authors', [])[:5])}
领域: {', '.join(paper.get('categories', []))}
摘要: {paper.get('abstract', '')[:800]}
核心方法: {paper.get('method', '')[:500]}

请回复JSON：
{{"score": 0.85, "flags": ["标记1", "标记2"], "rationale": "一句理由"}}
评分标准：0.9+可放心导入，0.7-0.9基本可信，0.4-0.7需人工复核，<0.4跳过。"""
    try:
        reply, _ = chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是学术论文质量评估助手。只输出JSON。",
            temperature=0.1, max_tokens=300, timeout=30,
        )
        js = reply.strip()
        if js.startswith("```"):
            js = re.sub(r"^```\w*\n?", "", js)
            js = re.sub(r"\n?```$", "", js)
        return json.loads(js)
    except Exception:
        return {
            "score": 0.6,
            "flags": ["LLM评估失败，默认可信度0.6"],
            "rationale": "评估异常",
        }


def evaluate(paper, threshold=None):
    """Full credibility evaluation. Returns {score, passed, flags, details}."""
    if threshold is None:
        threshold = DEFAULT_THRESHOLD

    rel = check_relevance(paper)
    abs_q = check_abstract_quality(paper)
    llm_result = _llm_credibility(paper)

    combined = 0.3 * rel + 0.2 * abs_q + 0.5 * llm_result.get("score", 0.5)
    flags = llm_result.get("flags", [])

    if rel < 0.3:
        flags.append("领域不相关")
    if abs_q < 0.3:
        flags.append("摘要过短或缺失")

    return {
        "score": round(combined, 3),
        "passed": combined >= threshold,
        "threshold": threshold,
        "details": {
            "relevance": round(rel, 3),
            "abstract_quality": round(abs_q, 3),
            "llm_score": round(llm_result.get("score", 0.5), 3),
            "rationale": llm_result.get("rationale", ""),
        },
        "flags": flags,
    }

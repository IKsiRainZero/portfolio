"""Structured paper summarizer — extract key fields, not full text."""
import json
import re
from services.deepseek_client import chat, load_prompt


def summarize_paper(md_text, arxiv_meta=None):
    """Extract structured summary from paper Markdown text.

    Returns dict with: abstract, core_problem, method, experiment_design,
    key_data_metrics, confidence. All strings except confidence (float).
    """
    system_prompt = load_prompt("paper_summarizer")
    if not system_prompt:
        system_prompt = _default_prompt()

    context = md_text[:12000]

    meta_context = ""
    if arxiv_meta:
        meta_context = (
            f"arXiv ID: {arxiv_meta.get('arxiv_id', '?')}\n"
            f"Title: {arxiv_meta.get('title', '?')}\n"
            f"Authors: {', '.join(arxiv_meta.get('authors', []))}\n"
        )

    user_msg = f"{meta_context}\n论文正文（截取前12000字）:\n{context}"

    try:
        reply, usage = chat(
            messages=[{"role": "user", "content": user_msg}],
            system_prompt=system_prompt,
            temperature=0.2,
            max_tokens=2000,
            timeout=90,
        )
    except Exception as e:
        return {
            "error": str(e), "title": "", "abstract": "", "core_problem": "",
            "method": "", "experiment_design": "", "key_data_metrics": "",
            "confidence": 0.0, "usage": {},
        }

    json_str = reply.strip()
    if json_str.startswith("```"):
        json_str = re.sub(r"^```\w*\n?", "", json_str)
        json_str = re.sub(r"\n?```$", "", json_str)

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        return {
            "error": "JSON parse failed", "raw": reply[:500],
            "title": "", "abstract": "", "core_problem": "", "method": "",
            "experiment_design": "", "key_data_metrics": "",
            "confidence": 0.0, "usage": usage,
        }

    result["usage"] = usage
    result.setdefault("title", "")
    result.setdefault("abstract", "")
    result.setdefault("core_problem", "")
    result.setdefault("method", "")
    result.setdefault("experiment_design", "")
    result.setdefault("key_data_metrics", "")
    result.setdefault("confidence", 0.7)
    return result


def _default_prompt():
    return """你是学术论文结构化提取器。从论文中提取以下字段，用JSON回复：
{
  "title": "论文标题（直接提取原文标题）",
  "abstract": "论文摘要（2-3句，直接引用或改写原摘要）",
  "core_problem": "论文要解决的核心问题是什么（1-2句）",
  "method": "采用的方法/框架/算法（2-4句，点出关键技术点）",
  "experiment_design": "实验设计概要：用了什么数据集、基准、对比方法、评估指标",
  "key_data_metrics": "关键数据/指标：最重要的1-3个数字结果",
  "confidence": 0.85
}
规则：每个字段都要填写，如果没有对应信息写"未提及"。confidence: 0.9+为信息充分，0.7-0.9为基本完整，<0.7为信息不足。只输出JSON。"""

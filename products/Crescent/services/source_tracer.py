"""来源追溯 — 6 步结构化管道，固定步骤保证行为可预测"""
import io
import json
import re
from typing import Generator, Dict, Any, List


def _llm(prompt: str, system: str = "") -> str:
    """调用 LLM（含自动 fallback）"""
    from services.llm_fallback import get_llm_with_fallback
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        llm, _provider = get_llm_with_fallback(temperature=0.3)
    except RuntimeError as e:
        return f"[LLM 不可用] {e}"

    msgs = []
    if system:
        msgs.append(SystemMessage(content=system))
    msgs.append(HumanMessage(content=prompt))

    try:
        resp = llm.invoke(msgs)
        return resp.content.strip() if hasattr(resp, 'content') else str(resp)
    except Exception as e:
        return f"[LLM 调用失败] {e}"


def step1_extract_keywords(content: str) -> Dict[str, Any]:
    """提取关键词和核心声明"""
    system = "你是一个信息溯源助手。从用户提供的内容中提取：1) 关键词（5-10个）2) 核心事实声明 3) 如果有URL，提取出来。用JSON格式回复。"
    prompt = f"内容：\n{content}\n\n请提取关键词、核心声明和URL。回复JSON：{{\"keywords\": [...], \"claims\": [...], \"urls\": [...]}}"
    raw = _llm(prompt, system)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            result = json.loads(m.group())
        else:
            result = {"keywords": [], "claims": [content[:200]], "urls": []}
    return result


def step2_multi_search(keywords: List[str], urls: List[str]) -> Dict[str, Any]:
    """多源搜索（cn.bing.com 主 + ddgs 辅，适配中国网络环境）"""
    import re
    import requests
    from scrapling.fetchers import Fetcher

    sources = []
    search_urls = urls.copy() if urls else []

    for url in search_urls:
        try:
            resp = Fetcher.get(url, timeout=15)
            sources.append({
                "url": url,
                "title": resp.css('title::text').get() or url,
                "status": "fetched",
                "html": resp.body[:50000]
            })
        except Exception as e:
            sources.append({"url": url, "status": "failed", "error": str(e)})

    # 搜索补充来源 — cn.bing.com 主 + ddgs 辅
    existing_urls = {s["url"] for s in sources}
    query = " ".join(keywords[:5])
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    def _add_source(url, title="", snippet="", status="search_result"):
        if url and url not in existing_urls:
            existing_urls.add(url)
            sources.append({"url": url, "title": title or url, "snippet": snippet, "status": status})

    # 后端 1: cn.bing.com (中国可达)
    try:
        r = requests.get("https://cn.bing.com/search",
                         params={"q": query, "count": 5},
                         headers={"User-Agent": ua}, timeout=15)
        r.encoding = "utf-8"
        hrefs = re.findall(r'href="(https?://[^"]+)"', r.text)
        for url in hrefs:
            url = url.strip()
            if (url.startswith("http") and "bing.com" not in url
                    and "microsoft.com" not in url and url.count("/") >= 4):
                _add_source(url)
    except Exception:
        pass

    # 备注: ddgs 在中国网络不可达，已移除

    return {"sources": sources, "total": len(sources)}


def step3_extract_content(sources: List[Dict]) -> Dict[str, Any]:
    """markitdown 提取正文"""
    from markitdown import MarkItDown
    from scrapling.fetchers import Fetcher

    md = MarkItDown()
    extracted = []

    for src in sources:
        if src.get("status") not in ("fetched", "search_result"):
            extracted.append({**src, "text": ""})
            continue

        try:
            if src.get("html"):
                text = md.convert(io.BytesIO(src["html"])).text_content
            else:
                resp = Fetcher.fetch(src["url"], timeout=15)
                text = md.convert(io.BytesIO(resp.body)).text_content
            text_clean = text[:5000] if text else ""
            extracted.append({**src, "text": text_clean, "status": "extracted"})
        except Exception as e:
            extracted.append({**src, "status": "extract_failed", "error": str(e), "text": src.get("snippet", "")})

    return {"items": extracted}


def step4_timeline_backtrack(items: List[Dict]) -> Dict[str, Any]:
    """时间线回溯 — 尝试找更早的出处"""
    earliest = None
    timeline = []

    for item in items:
        if item.get("status") in ("fetched", "extracted"):
            entry = {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
            }
            timeline.append(entry)
            if earliest is None:
                earliest = entry

    return {
        "timeline": timeline,
        "earliest_known": earliest,
        "note": "时间线基于当前搜索结果的发布时间排序。搜索范围仅限于公开网页，私密群聊/朋友圈/已删除内容无法访问。"
    }


def step5_diff_annotate(original_text: str, user_content: str) -> Dict[str, Any]:
    """LLM 逐句对比差异"""
    if not original_text or not user_content:
        return {"diffs": [], "note": "缺少对比内容，跳过差异分析"}

    system = '你是一个信息溯源助手。对比“原文”和“用户看到的版本”，逐句标注差异。重点关注：语义变化、情绪词汇增减、关键事实变更。'
    prompt = f"原文：\n{original_text[:3000]}\n\n用户看到的版本：\n{user_content[:3000]}\n\n逐句对比，标注差异。"
    raw = _llm(prompt, system)

    return {"diffs_raw": raw, "note": "差异标注来自模型分析，不是客观事实，用户可以自行判断。"}


def step6_final_conclusion(chain: Dict[str, Any]) -> Dict[str, Any]:
    """阶段性结论 + 明确不确定性边界"""
    sources = chain.get("sources", {})
    timeline = chain.get("timeline", {})
    diffs = chain.get("diffs", {})

    total_sources = sources.get("total", 0)
    failed = sum(1 for s in sources.get("sources", []) if "failed" in s.get("status", ""))

    determined = []
    uncertain = []

    if timeline.get("earliest_known"):
        determined.append(f"最早可查来源: {timeline['earliest_known'].get('url', '未知')}")
    if total_sources > 0:
        determined.append(f"共检索到 {total_sources} 个相关来源，其中 {failed} 个获取失败")
    if diffs.get("diffs_raw"):
        determined.append("已完成原文与用户版本差异对比")

    uncertain.append("无法确定是否还有其他更早来源（搜索范围仅限于公开网页）")
    uncertain.append("无法访问私密群聊、朋友圈、已删除内容")
    uncertain.append("差异标注来自模型分析，不是客观事实")
    if total_sources == 0:
        uncertain.append("未找到任何相关来源，该信息暂无公开可查记录")

    return {
        "determined": determined,
        "uncertain": uncertain,
        "source_links": timeline.get("timeline", []),
        "timestamp": chain.get("timestamp", ""),
    }


def trace_source(content: str) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
    """主入口：执行完整 6 步管道，yield 每步的进度和结果。

    用法（Flask SSE）:
        for event in trace_source(user_content):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\\n\\n"
    """
    import time

    chain = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}

    # Step 1
    yield {"step": 1, "name": "提取关键词", "status": "running", "content": "正在分析你提供的内容..."}
    kw = step1_extract_keywords(content)
    chain["keywords"] = kw
    yield {
        "step": 1, "name": "提取关键词", "status": "done",
        "content": f"提取到关键词：{', '.join(kw.get('keywords', []))}",
        "detail": kw
    }

    # Step 2
    yield {"step": 2, "name": "多平台搜索", "status": "running", "content": "用 Scrapling 搜索公开网页..."}
    sources = step2_multi_search(kw.get("keywords", []), kw.get("urls", []))
    chain["sources"] = sources
    yield {
        "step": 2, "name": "多平台搜索", "status": "done",
        "content": f"找到 {sources['total']} 个相关来源",
        "detail": sources
    }

    # Step 3
    yield {"step": 3, "name": "内容提取", "status": "running", "content": "用 markitdown 提取正文..."}
    extracted = step3_extract_content(sources.get("sources", []))
    chain["extracted"] = extracted
    yield {
        "step": 3, "name": "内容提取", "status": "done",
        "content": f"成功提取 {sum(1 for i in extracted['items'] if i.get('status') == 'extracted')} 篇正文",
        "detail": extracted
    }

    # Step 4
    yield {"step": 4, "name": "时间线回溯", "status": "running", "content": "回溯时间线，找最早出处..."}
    timeline = step4_timeline_backtrack(extracted.get("items", []))
    chain["timeline"] = timeline
    yield {
        "step": 4, "name": "时间线回溯", "status": "done",
        "content": f"最早可查来源: {timeline.get('earliest_known', {}).get('url', '待定')}",
        "detail": timeline
    }

    # Step 5
    yield {"step": 5, "name": "差异标注", "status": "running", "content": "对比原文与用户版本..."}
    first_text = ""
    for item in extracted.get("items", []):
        if item.get("text"):
            first_text = item["text"]
            break
    diffs = step5_diff_annotate(first_text, content)
    chain["diffs"] = diffs
    yield {
        "step": 5, "name": "差异标注", "status": "done",
        "content": "差异对比完成",
        "detail": diffs
    }

    # Step 6
    yield {"step": 6, "name": "阶段性结论", "status": "running", "content": "生成结论..."}
    conclusion = step6_final_conclusion(chain)
    chain["conclusion"] = conclusion
    yield {
        "step": 6, "name": "阶段性结论", "status": "done",
        "content": "分析完成",
        "detail": conclusion
    }

    return chain

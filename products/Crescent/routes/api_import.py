"""知识导入 + 内化 API"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from services.deepseek_client import chat, load_prompt
import config
import json
import re

router = APIRouter(prefix="/api")


@router.post("/ai/import-knowledge")
async def import_knowledge(request: Request):
    """接收用户文本 → LLM 提取知识点 + 生成题目 → 存入临时训练区"""
    if not config.API_KEY:
        return JSONResponse(content={"error": "请先配置 API Key"}, status_code=401)

    data = await request.json()
    raw_text = (data.get("text") or "").strip()
    if not raw_text or len(raw_text) < 20:
        return JSONResponse(content={"error": "文本太短，请至少输入20个字符"}, status_code=400)

    system_prompt = load_prompt("knowledge_importer")
    if not system_prompt:
        return JSONResponse(content={"error": "提示词文件 knowledge_importer.txt 不存在"}, status_code=500)

    try:
        reply, usage = chat(
            messages=[{"role": "user", "content": f"请处理以下文本：\n\n{raw_text[:4000]}"}],
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=4000,
            timeout=120,
        )
    except Exception as e:
        return JSONResponse(content={"error": f"AI 请求失败: {str(e)}"}, status_code=502)

    # 解析 JSON
    json_str = reply.strip()
    if json_str.startswith("```"):
        json_str = re.sub(r"^```\w*\n?", "", json_str)
        json_str = re.sub(r"\n?```$", "", json_str)

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        temp_path = config.DATA_DIR / "temp_import_debug.txt"
        temp_path.write_text(reply, encoding="utf-8")
        return JSONResponse(content={"error": "AI 返回格式异常，原始回复已保存", "raw": reply[:300]}, status_code=500)

    exercises = result.get("exercises", {})
    knowledge = result.get("knowledge", [])

    from services.exercise_store import merge as store_merge
    temp_counts = {}
    for ex_type in ["mcq", "coding", "flashcards"]:
        items = exercises.get(ex_type, [])
        temp_counts[ex_type] = len(items)
    total_temp = store_merge(exercises)

    return {
        "ok": True,
        "knowledge_count": len(knowledge),
        "knowledge_items": knowledge,
        "exercises_count": temp_counts,
        "total_temp": total_temp,
        "usage": usage,
    }


@router.post("/ai/internalize")
async def internalize(request: Request):
    """接收论文文本 → LLM 提取方法论卡片 → 写入 insights.json"""
    if not config.API_KEY:
        return JSONResponse(content={"error": "请先配置 API Key"}, status_code=401)

    data = await request.json()
    raw_text = (data.get("text") or "").strip()
    source_info = data.get("source", {})

    if not raw_text or len(raw_text) < 50:
        return JSONResponse(content={"error": "文本太短，请至少输入50个字符"}, status_code=400)

    system_prompt = load_prompt("knowledge_internalizer")
    if not system_prompt:
        return JSONResponse(content={"error": "提示词文件 knowledge_internalizer.txt 不存在"}, status_code=500)

    try:
        reply, usage = chat(
            messages=[{"role": "user", "content": f"请从以下论文内容提取方法论卡片：\n\n{raw_text[:6000]}"}],
            system_prompt=system_prompt,
            temperature=0.3,
            max_tokens=4000,
            timeout=120,
        )
    except Exception as e:
        return JSONResponse(content={"error": f"AI 请求失败: {str(e)}"}, status_code=502)

    json_str = reply.strip()
    if json_str.startswith("```"):
        json_str = re.sub(r"^```\w*\n?", "", json_str)
        json_str = re.sub(r"\n?```$", "", json_str)

    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        return JSONResponse(content={"error": "AI 返回格式异常", "raw": reply[:500]}, status_code=500)

    cards = result.get("methodology_cards", [])
    if not cards:
        return {"ok": True, "cards_added": 0, "message": "未提取到方法论卡片", "usage": usage}

    from services.insight_store import add_cards
    added, total = add_cards(cards, source_info)

    return {
        "ok": True,
        "cards_added": added,
        "total_cards": total,
        "cards": cards,
        "usage": usage,
    }


@router.post("/import/fetch-url")
async def fetch_url(request: Request):
    """抓取 URL 内容，提取文本（用于 JD 链接导入）"""
    import urllib.request
    import urllib.error
    from html.parser import HTMLParser

    url = (await request.json() or {}).get("url", "").strip()
    if not url:
        return JSONResponse(content={"error": "URL 为空"}, status_code=400)

    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (compatible; Portfolio/1.0)"
        })
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8", errors="replace")[:50000]
    except urllib.error.URLError as e:
        return JSONResponse(content={"error": f"无法访问该链接: {str(e.reason)}"}, status_code=502)
    except Exception as e:
        return JSONResponse(content={"error": f"抓取失败: {str(e)}"}, status_code=500)

    class TextExtractor(HTMLParser):
        def __init__(self):
            super().__init__()
            self.text = []
            self.skip = False
        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style", "noscript"):
                self.skip = True
        def handle_endtag(self, tag):
            if tag in ("script", "style", "noscript"):
                self.skip = False
        def handle_data(self, data):
            if not self.skip:
                t = data.strip()
                if t:
                    self.text.append(t)

    parser = TextExtractor()
    parser.feed(raw)
    text = "\n".join(parser.text)

    # 截断到合理长度
    if len(text) > 3000:
        text = text[:3000] + "\n…(内容过长，已截断)"

    return {"ok": True, "text": text, "url": url}

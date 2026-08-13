import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.templating import Jinja2Templates

from services.data_sources import get_manager
from services.user_settings import get_setting

router = APIRouter()
templates = Jinja2Templates(directory="templates")
templates.env.cache_size = 0
templates.env.cache = None  # Python 3.14 + Jinja2 LRUCache 兼容

# 新闻 API 可能不可达（国内网络环境），fetch 必须在超时内完成，不能阻塞首页渲染
_NEWS_FETCH_TIMEOUT = 5  # 秒


def _get_daily_briefs(limit=5):
    """从 NewsSource 获取真实新闻简报（降级到缓存或空列表）。
    返回 (briefs, stale, meta_msg) 供模板使用。
    在线程中执行以避免阻塞单线程 worker。
    """
    if not get_setting("news_enabled", True):
        return ([], False, "")

    categories = get_setting("news_categories", ["technology", "science"])
    count = get_setting("news_count", 5)

    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(_fetch_briefs, categories, count)
            briefs, stale, msg = future.result(timeout=_NEWS_FETCH_TIMEOUT)
    except FutureTimeout:
        return ([], True, "新闻数据源响应超时，稍后自动重试")
    except Exception:
        return ([], False, "")

    return (briefs, stale, msg)


def _fetch_briefs(categories, count):
    """在独立线程中执行实际的数据源调用。"""
    mgr = get_manager()
    briefs, stale, msg = mgr.get_briefs("news", count=count, categories=categories)
    for b in briefs:
        b["mtime"] = 0
    return (briefs, stale, msg)


@router.get("/")
async def home(request: Request):
    return templates.TemplateResponse(request, "pages/home.html", {"has_brief_card": True})


@router.get("/api/briefs")
async def api_briefs(request: Request):
    briefs, stale, msg = _get_daily_briefs()
    return {"briefs": briefs, "stale": stale, "meta": msg}


@router.get("/trainer")
async def trainer(request: Request):
    return templates.TemplateResponse(request, "pages/trainer.html")


@router.get("/study-plan")
async def study_plan(request: Request):
    return templates.TemplateResponse(request, "pages/study_plan.html")


@router.get("/textbook")
async def textbook(request: Request):
    return templates.TemplateResponse(request, "pages/textbook.html")


@router.get("/knowledge")
async def knowledge(request: Request):
    return RedirectResponse("/textbook", status_code=302)


@router.get("/classroom")
async def classroom(request: Request):
    return templates.TemplateResponse(request, "pages/classroom.html")


@router.get("/classroom/office")
async def classroom_office(request: Request):
    return templates.TemplateResponse(request, "pages/office.html")


@router.get("/impressions")
async def impressions(request: Request):
    return templates.TemplateResponse(request, "pages/impressions.html")


@router.get("/resume")
async def resume(request: Request):
    return RedirectResponse("/interview#resume", status_code=301)


@router.get("/interview")
async def interview(request: Request):
    return templates.TemplateResponse(request, "pages/mock_interview.html")


@router.get("/feynman")
async def feynman(request: Request):
    return RedirectResponse("/trainer#feynman", status_code=301)


@router.get("/settings")
async def settings(request: Request):
    return templates.TemplateResponse(request, "pages/settings.html")


@router.get("/changelog")
async def changelog(request: Request):
    return templates.TemplateResponse(request, "pages/changelog.html")


@router.get("/data/changelog.json")
async def changelog_data(request: Request):
    path = Path(__file__).parent.parent / "data" / "changelog.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data


@router.get("/agent-build")
async def agent_build(request: Request):
    return templates.TemplateResponse(request, "pages/agent_build.html")


@router.get("/source-trace")
async def source_trace(request: Request):
    return templates.TemplateResponse(request, "pages/source_trace.html")


@router.get("/architecture")
async def architecture(request: Request):
    return templates.TemplateResponse(request, "pages/architecture.html")


@router.get("/eval")
async def eval_page(request: Request):
    import config
    return templates.TemplateResponse(request, "pages/eval.html", {"admin_token": config.EVAL_ADMIN_SECRET})


@router.get("/knowledge-pipeline")
async def knowledge_pipeline(request: Request):
    return templates.TemplateResponse(request, "pages/knowledge_pipeline.html")


@router.get("/construction")
async def construction(request: Request):
    import json as _json
    data_dir = Path(__file__).parent.parent / "data" / "eval"
    ctx = {"has_data": False}
    try:
        if (data_dir / "heartbeat.json").exists():
            hb = _json.loads((data_dir / "heartbeat.json").read_text(encoding="utf-8"))
            ctx["heartbeat"] = hb.get("last_heartbeat", "")[:19]
            ctx["cycle_stats"] = hb.get("cycle_stats", {})
            ctx["has_data"] = True
        if (data_dir / "configs.json").exists():
            cf = _json.loads((data_dir / "configs.json").read_text(encoding="utf-8"))
            configs = cf.get("configs", [])
            ctx["config_count"] = len(configs)
            ctx["active_configs"] = [c for c in configs if not c.get("paused")][:5]
            ctx["has_data"] = True
        if (data_dir / "offline_suggestions.json").exists():
            osg = _json.loads((data_dir / "offline_suggestions.json").read_text(encoding="utf-8"))
            ctx["suggestion_count"] = len(osg.get("suggestions", []))
            rag = osg.get("rag_regression", {})
            ctx["rag_status"] = rag.get("status", "unknown")
            ctx["rag_hit_rate"] = rag.get("baseline_summary", {}).get("hit_rate@5")
            ctx["has_data"] = True
        if (data_dir / "meta_results.json").exists():
            mr = _json.loads((data_dir / "meta_results.json").read_text(encoding="utf-8"))
            results = mr.get("results", [])
            ctx["meta_result_count"] = len(results)
            latest = results[-1] if results else {}
            ctx["meta_freshness"] = latest.get("eval_freshness_score")
            ctx["has_data"] = True
    except Exception:
        pass
    return templates.TemplateResponse(request, "pages/construction.html", {"eval_data": ctx})


@router.get("/data/agent_architecture.json")
async def agent_architecture(request: Request):
    return {
        "title": "Portfolio App Agent 架构",
        "layers": [
            {
                "level": 1, "name": "原子能力单元 (Node/Step)",
                "desc": "最基础的功能单元，完成一件具体的事。",
                "ours": [
                    "Python 函数: search_knowledge, generate_question, analyze_progress 等 9 个 Tool",
                    "Ollama API 调用: 本地 LLM 推理",
                    "jieba 分词器: 中文关键词提取",
                    "bge-m3 嵌入模型: 文本→向量(1024维)",
                    "BGE Reranker: Cross-Encoder 精排"
                ]
            },
            {
                "level": 2, "name": "自动化流程 (Workflow)",
                "desc": "把多个原子单元按顺序串联，自动完成相对复杂的任务。",
                "ours": [
                    "RAG 检索管道: 分词→BM25→向量召回→RRF融合→Reranker→Top-5",
                    "知识同步管道: JSON文件→内容哈希检测→分块→嵌入→ChromaDB存储",
                    "SRS 间隔重复调度: 评分→间隔计算→到期提醒"
                ]
            },
            {
                "level": 3, "name": "对话机器人 (Chatbot)",
                "desc": "在 Workflow 基础上加入对话界面和记忆能力，实现多轮互动。",
                "ours": [
                    "Flask + Jinja2: 服务端渲染 + API",
                    "Session 管理: _SESSION_META(2h TTL) + _SESSION_HISTORY(压缩历史)",
                    "SSE 流式输出: threading+queue 桥接 → 实时推送"
                ]
            },
            {
                "level": 4, "name": "智能体 (Agent)",
                "desc": "在 Chatbot 基础上加入规划、工具使用和反馈学习能力，能自主思考和行动。",
                "ours": [
                    "手写 ReAct 循环: Thought→Action→Observation→Final (max_steps=6)",
                    "9 个工具: search_knowledge, generate_question, analyze_progress, diagnose_weakness, save_question_to_trainer, evaluate_answer, deep_question, feynman_check, create_study_plan",
                    "历史压缩: qwen2.5:0.5b 本地压缩 + 规则回退",
                    "本地 LLM: llama3.1:8b via Ollama native function calling"
                ]
            },
            {
                "level": 5, "name": "安全约束 (Harness)",
                "desc": "Agent 的\"安全带\"，确保自主运行时稳定、可控。",
                "ours": [
                    "max_steps=6: 防止无限循环",
                    "Session TTL 2h: 自动清理闲置会话",
                    "错误回退: LLM 调用失败时返回友好提示而非崩溃",
                    "模型切换白名单: 只能切换到已配置的模型",
                    "API Key 热更新: 敏感信息不在代码中硬编码"
                ]
            }
        ],
        "pipeline": [
            {"step": 1, "name": "用户输入", "desc": "用户在聊天框输入问题", "icon": "\U0001f4ac"},
            {"step": 2, "name": "jieba 分词", "desc": "中文分词 + 关键词提取", "icon": "✂️"},
            {"step": 3, "name": "BM25 检索", "desc": "基于词频的稀疏检索", "icon": "\U0001f4ca"},
            {"step": 4, "name": "bge-m3 向量化", "desc": "查询文本 → 1024维向量", "icon": "\U0001f9ee"},
            {"step": 5, "name": "ChromaDB 搜索", "desc": "向量相似度检索 (cosine)", "icon": "\U0001f50d"},
            {"step": 6, "name": "RRF 融合", "desc": "BM25(0.4) + Vector(0.6) 加权融合", "icon": "⚖️"},
            {"step": 7, "name": "BGE Reranker", "desc": "Cross-Encoder 精排 → top-5", "icon": "\U0001f3af"},
            {"step": 8, "name": "ReAct 循环", "desc": "LLM 思考→调用工具→观察→决定是否继续", "icon": "\U0001f504"},
            {"step": 9, "name": "LLM 生成回复", "desc": "基于检索结果 + 对话历史生成答案", "icon": "\U0001f916"},
            {"step": 10, "name": "SSE 流式输出", "desc": "Thought→Action→Observation→Final 实时推送", "icon": "\U0001f4e1"}
        ]
    }


@router.get("/research")
async def research(request: Request):
    return templates.TemplateResponse(request, "pages/research.html")


@router.get("/workbench")
async def workbench(request: Request):
    """工作台 — Phase 1 产业-能力匹配引擎 (React)"""
    import config
    if config.DEBUG:
        return RedirectResponse("http://localhost:5173", status_code=302)
    else:
        dist_index = Path(__file__).parent.parent / "static" / "dist" / "index.html"
        return FileResponse(str(dist_index))

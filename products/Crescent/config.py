"""
Crescent 配置
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
PROMPTS_DIR = BASE_DIR / "prompts"
USER_DATA_DIR = DATA_DIR / "user_data"
DOCS_DIR = BASE_DIR / "docs"
SCRIPTS_DIR = BASE_DIR / "scripts"

# ── DeepSeek API ──
# 安全策略 (参照 《个人信息保护法》第 51 条):
#   优先级: 环境变量 DEEPSEEK_API_KEY > 持久化文件 .api_key
#   部署到他人机器时推荐使用环境变量，避免凭证明文落盘
#   .api_key 文件仅用于本地开发便利，生产环境应删除
API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
if not API_KEY:
    # 优先读取项目根目录的 .api_key（部署环境），其次读取用户数据目录（UI 设置保存的）
    for _key_path in [BASE_DIR / ".api_key", USER_DATA_DIR / ".api_key"]:
        if _key_path.exists():
            API_KEY = _key_path.read_text(encoding="utf-8").strip()
            if API_KEY:
                break
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
MODEL = os.environ.get("DEEPSEEK_MODEL", "deepseek-v4-flash")

# ── LangChain / LangSmith (可选调试) ──
LANGSMITH_TRACING = os.environ.get("LANGSMITH_TRACING", "false").lower() == "true"
LANGSMITH_API_KEY = os.environ.get("LANGSMITH_API_KEY", "")

# ── Chroma 向量库 ──
CHROMA_PATH = BASE_DIR / "data" / "chroma_db"
CHROMA_COLLECTION = "knowledge_base"

# ── Embedding 模型 ──
# 默认使用 HuggingFace 模型名（自动缓存到 ~/.cache/huggingface/）
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL", "BAAI/bge-m3")

# ── 知识库原始文档路径 ──
KNOWLEDGE_SOURCES = [
    Path(__file__).parent.parent / "知识库" / "导出",       # 25领域 200+ 闪卡
    Path(__file__).parent.parent / "知识库" / "论文原文",   # 12篇 AI 论文 PDF
    Path(__file__).parent.parent / "知识库" / "精炼笔记",   # 论文精炼笔记
]

# ── 文档切分配置 ──
CHUNK_SIZE = 500
CHUNK_OVERLAP = 150

# ── LLM 提供商 ──
# "local" = Ollama 本地模型 | "deepseek" = DeepSeek API
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "deepseek")
LOCAL_MODEL_NAME = os.environ.get("LOCAL_MODEL_NAME", "qwen3:8b")
LOCAL_COMPRESS_MODEL = os.environ.get("LOCAL_COMPRESS_MODEL", "qwen2.5:0.5b")

# ── Agent 配置 ──
AGENT_MAX_ITERATIONS = 5
AGENT_MEMORY_WINDOW = 10
SESSION_TTL_SECONDS = 7200   # 2 小时 idle 自动回收
SESSION_MAX_COUNT = 100

# ── Flask ──
HOST = os.environ.get("FLASK_HOST", "127.0.0.1")
PORT = int(os.environ.get("FLASK_PORT", "5000"))
DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
SECRET_KEY = os.environ.get("FLASK_SECRET_KEY", os.urandom(24).hex())

# ── Reranker ──
USE_RERANKER = os.environ.get("USE_RERANKER", "false").lower() == "true"
RERANKER_MODEL = os.environ.get("RERANKER_MODEL", "BAAI/bge-reranker-large")
RERANKER_COARSE_K = 20
RERANKER_TOP_K = 5

# ── arXiv API ──
ARXIV_API_BASE = "http://export.arxiv.org/api/query"
ARXIV_RATE_LIMIT = 3.0

# ── Paper Pipeline ──
CREDIBILITY_THRESHOLD = 0.5
PAPER_SUMMARIZE_MAX_CHARS = 12000
ARXIV_SEARCH_MAX_RESULTS = 20

# ── 新闻数据源 ──
NEWS_API_KEY = os.environ.get("NEWS_API_KEY", "")
NEWS_API_URL = os.environ.get("NEWS_API_URL", "https://newsapi.org/v2/top-headlines")
NEWS_CACHE_TTL = int(os.environ.get("NEWS_CACHE_TTL", "1800"))  # 30 min

# ── 评估系统 (eval) ──
EVAL_ENABLED = os.environ.get("EVAL_ENABLED", "true").lower() == "true"
EVAL_SHADOW_MODE = os.environ.get("EVAL_SHADOW_MODE", "true").lower() == "true"
# 独立安全域: EVAL_ADMIN_SECRET 不复用 SECRET_KEY。
# 优先级: 环境变量 > 持久化文件 > 自动生成并持久化
# 若使用自动生成，secret 写入 eval_admin.secret 文件以保证重启后不变。
if "EVAL_ADMIN_SECRET" in os.environ:
    EVAL_ADMIN_SECRET = os.environ["EVAL_ADMIN_SECRET"]
else:
    _secret_file = BASE_DIR / "data" / "eval_admin.secret"
    try:
        if _secret_file.exists():
            EVAL_ADMIN_SECRET = _secret_file.read_text(encoding="utf-8").strip()
        else:
            _secret_file.parent.mkdir(parents=True, exist_ok=True)
            EVAL_ADMIN_SECRET = os.urandom(24).hex()
            _secret_file.write_text(EVAL_ADMIN_SECRET, encoding="utf-8")
    except Exception:
        EVAL_ADMIN_SECRET = os.urandom(24).hex()

# 指标优先级金字塔 (红线2: 硬编码，不可由LLM判断)
METRIC_PRIORITY = {
    "security_score": 1,
    "agent_success_rate": 2,
    "agent_efficiency": 3,
    "agent_tool_accuracy": 3,
    "code_health": 4,
    "doc_coverage": 4,
    "module_interop": 4,
    "kb_freshness": 4,
    "paper_quality": 5,
    "rag_relevance": 5,
    "test_coverage": 5,
    "data_completeness": 0,   # 宪法Metric: 最高优先级
    "eval_system_freshness": 0,  # 宪法Metric: 最高优先级
}

# 红线告警阈值 (战术指令T2)
RED_LINE_ALERTS = {
    "security_score": {"threshold": 0.7, "direction": "below"},
    "data_completeness": {"threshold": 0.9, "direction": "below", "consecutive_days": 2},
    "agent_success_rate": {"threshold": 0.5, "direction": "below"},
}

# ── 前瞻性扫描资源限制 (M1安全约束) ──
SCAN_MAX_FILE_BYTES = int(os.environ.get("SCAN_MAX_FILE_BYTES", "1048576"))  # 1MB
SCAN_MAX_FILES = int(os.environ.get("SCAN_MAX_FILES", "1000"))
SCAN_TIMEOUT_SECONDS = int(os.environ.get("SCAN_TIMEOUT_SECONDS", "30"))

# ── Brave Search API ──
# 优先级: 环境变量 BRAVE_API_KEY > 持久化文件 .brave_api_key
BRAVE_API_KEY = os.environ.get("BRAVE_API_KEY", "")
if not BRAVE_API_KEY:
    _brave_key_path = USER_DATA_DIR / ".brave_api_key"
    if _brave_key_path.exists():
        BRAVE_API_KEY = _brave_key_path.read_text(encoding="utf-8").strip()

# ── SerpAPI (Google Search) ──
# 优先级: 环境变量 SERPAPI_KEY > 持久化文件 .serpapi_key
# Brave 在中国不可用时的首选搜索引擎
SERPAPI_KEY = os.environ.get("SERPAPI_KEY", "")
if not SERPAPI_KEY:
    _serp_key_path = USER_DATA_DIR / ".serpapi_key"
    if _serp_key_path.exists():
        SERPAPI_KEY = _serp_key_path.read_text(encoding="utf-8").strip()

"""Agent 核心 — 自定义 ReAct 循环 + 工具 + 历史压缩 + Memory"""
import sys
import json
import re
import asyncio
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage

from config import (
    AGENT_MEMORY_WINDOW, DATA_DIR, USER_DATA_DIR,
)
from services.llm_fallback import get_llm_with_fallback
from services.rag_service import search as rag_search, rag_query, search_iterative
from services.deepseek_client import chat, load_prompt
from services.progress_tracker import load_progress, get_weak_areas
from services.agent_logger import log_agent_call, log_event, fingerprint_error
from services.harness import run_harness
from services.eval.trace_logger import emit_event


def _extract_topic_and_insight(message: str, reply: str):
    """从一条有意义的问答中提取话题气泡，无需额外 LLM 调用。

    返回 (topic, question, insight, key_terms) 或 None（不够有意义时）。
    """
    if not message or not reply or len(message) < 15:
        return None
    # 跳过简单问候/闲聊
    msg_lower = message.strip().lower()
    skip_patterns = ('你好', 'hi', 'hello', '嗨', '谢谢', 'thanks', '再见', 'bye',
                     '嗯', '哦', '好的', 'ok', '行', '在吗', '晚安', '早上好')
    if any(msg_lower.startswith(p) for p in skip_patterns):
        return None
    # topic: 截取到第一个问号或60字
    topic = message[:80].split('？')[0].split('?')[0].split('！')[0].strip()
    if len(topic) > 60:
        topic = topic[:60] + '…'
    # question: 用户消息（≤120字）
    question = message[:120] if len(message) > 120 else message
    # insight: agent 回复第一句（≤200字）
    # 跳过 harness 拦截前缀
    clean_reply = reply
    if clean_reply.startswith('⚠️'):
        clean_reply = clean_reply.split('──', 1)[-1].strip()
    insight_end = 200
    for sep in ('。\n', '。', '\n\n', '\n'):
        pos = clean_reply[:insight_end].find(sep)
        if pos > 20:
            insight_end = pos + 1
            break
    insight = clean_reply[:insight_end].strip()
    # key_terms: 用 jieba 分词提取关键词（过滤停用词，取前5个）
    stop = {'什么', '怎么', '如何', '为什么', '可以', '这个', '一下', '一个', '哪些', '还是',
            '多少', '有没有', '是不是', '能否', '帮我', '我想', '我要', '什么是', '是什么',
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
            '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
            '自己', '这', '他', '她', '它', '们', '那', '些', '所', '为', '所以', '因为',
            '分别', '代表', '什么', '怎么', '如何', '为什么', '哪些', '哪个', '还是',
            '每个', '各个', '各种', '其中', '之间', '中的', '里面',
            'the', 'is', 'of', 'in', 'to', 'and', 'for', 'what', 'how', 'why', 'a', 'an'}
    try:
        import jieba
        words = jieba.lcut(message)
    except Exception:
        import re
        words = re.findall(r'[\w一-鿿]{2,}', message)
    key_terms = []
    seen = set()
    for w in words:
        w = w.strip().lower()
        if len(w) >= 2 and w not in stop and w not in seen:
            key_terms.append(w)
            seen.add(w)
        if len(key_terms) >= 5:
            break
    return (topic, question, insight, key_terms if key_terms else [])


def _maybe_save_bubble(session_id: str, persona: str, message: str, reply: str):
    """如果一次交换足够有意义，提取上下文气泡并持久化。"""
    if not persona or persona not in ('deskmate', 'teacher', 'interviewer'):
        return
    extracted = _extract_topic_and_insight(message, reply)
    if extracted is None:
        return
    topic, question, insight, key_terms = extracted
    try:
        from services.session_store import save_bubble
        save_bubble(session_id, persona, topic, question, insight, key_terms)
    except Exception as e:
        # 气泡保存失败不影响主流程，但记录错误便于排查
        try:
            from services.agent_logger import log_event
            log_event("warning", {"phase": "save_bubble", "error": str(e)}, session_id)
        except Exception:
            pass


def _auto_inject_sources(reply: str, steps: list) -> str:
    """从 search_knowledge 的 observation 中提取来源，自动附到回复末尾。
    避免因漏标来源而被 harness 阻断整个回复。
    """
    if not reply or not steps:
        return reply
    # 检查回复是否已含来源标注
    if any(pat in reply for pat in ("[来源:", "[来源：", "来源:", "来源：")):
        return reply
    sources = set()
    for s in steps:
        if s.get("phase") == "observation" and s.get("tool") == "search_knowledge":
            output = s.get("output", "")
            # 从观察结果中提取 source/来源/文件名
            import re
            for pat in (r'\[来源[：:]\s*(.+?)\]', r'来源[：:]\s*(\S+)', r'"source"\s*:\s*"([^"]+)"', r'"filename"\s*:\s*"([^"]+)"'):
                sources.update(re.findall(pat, output, re.IGNORECASE))
    if sources:
        reply += "\n\n[来源: " + ", ".join(sorted(sources)[:5]) + "]"
    return reply
from services.eval.trace_logger import _safe_record_tool_span, emit_event

# ── Cancel mechanism ──
_cancel_flags: dict[str, asyncio.Event] = {}
_agent_queues: dict[str, asyncio.Queue] = {}
_agent_tasks: dict[str, asyncio.Task] = {}


def cancel_session(session_id: str) -> bool:
    """取消正在执行的 Agent 流。"""
    ok = False
    # 1. 直接取消 asyncio Task — _run() 会在下一个 await 抛 CancelledError
    task = _agent_tasks.pop(session_id, None)
    if task and not task.done():
        task.cancel()
        ok = True
    # 2. 向队列注入 cancelled 事件 — 让 SSE while 循环立即读取
    q = _agent_queues.pop(session_id, None)
    if q:
        try:
            q.put_nowait({"type": "cancelled", "session_id": session_id})
        except asyncio.QueueFull:
            pass
        ok = True
    # 3. 设置 flag 作为兜底
    flag = _cancel_flags.get(session_id)
    if flag:
        flag.set()
    else:
        _cancel_flags[session_id] = asyncio.Event()
        _cancel_flags[session_id].set()
    return ok


# ── 步数限制 ──
def _get_max_steps():
    try:
        from services.user_settings import get_setting
        unlimited = get_setting("agent_max_iterations_unlimited", False)
        if unlimited:
            return 999
        return get_setting("agent_max_iterations", 6)
    except Exception:
        return 6
# 超过此消息数触发历史压缩（system + 最近几轮完整保留，更早的压缩）
COMPRESS_THRESHOLD = 10


# ── 快速路径分类器 ──

_SIMPLE_GREETINGS = frozenset({
    "你好", "hi", "hello", "嗨", "hey", "在吗", "在不在",
    "谢谢", "thanks", "thank you", "3q",
    "再见", "bye", "拜拜", "晚安", "goodbye",
    "早上好", "下午好", "晚上好", "good morning",
    "嗯", "哦", "好的", "ok", "okay", "行",
    "你是谁", "你能做什么", "介绍一下你自己",
})

_TECHNICAL_KEYWORDS = [
    "论文", "代码", "算法", "模型", "训练", "神经网络", "深度学习",
    "题目", "练习", "做题", "出题", "考试", "测试",
    "进度", "薄弱", "诊断", "学习计划", "复习",
    "费曼", "解释", "教我", "知识库", "搜索",
    "code", "algorithm", "model", "train", "exercise", "test",
    "progress", "weakness", "diagnose", "explain",
    "什么是", "怎么", "如何", "为什么", "区别",
    "what is", "how to", "why", "difference",
    "?", "？", "吗", "呢",
]

# 非学习意图信号 — 用户想闲聊、讲故事、角色扮演等
# 命中这些信号的查询走快速路径，不触发 ReAct 循环和知识库检索
# 注意: "新闻"/"热搜" 已移除此列表 — 有 DataSource news_search 工具处理
_NON_LEARNING_SIGNALS = [
    # 天气/时间（天气 DataSource 完成后移除此行）
    "天气", "几点", "几号", "日期",
    # 闲聊/角色扮演
    "笑话", "故事", "聊天", "无聊", "陪我", "角色扮演",
    "你是谁造的", "你有感情吗", "你有意识",
    # 编程/工具请求（非学习用途）
    "帮我写", "翻译", "做ppt", "写邮件", "写周报",
    # 娱乐
    "推荐电影", "推荐音乐", "推荐游戏", "玩游戏",
    "唱", "画", "照片",
    # 个人问题
    "你喜欢", "你觉得", "你的名字", "你叫什么",
]

# ── 工具分组：意图驱动的动态工具路由 ──
# 工具按功能分为 4 组，根据用户消息的意图信号选择性绑定
_TOOL_GROUPS = {
    "retrieval":  ("search_knowledge", "web_search"),       # 查资料/搜索
    "assessment": ("generate_question", "evaluate_answer",   # 出题/批改/深入
                   "deep_question", "feynman_check",
                   "save_question_to_trainer"),
    "progress":   ("analyze_progress", "diagnose_weakness"), # 进度/诊断
    "planning":   ("create_study_plan",),                    # 学习计划
}

# 意图子信号 → 工具组映射（按需绑定，而非全量加载）
# 注意：中文关键词用单字/双字匹配，避免"出几道题"拆开导致漏匹配
_PRACTICE_SIGNALS = [
    "出题", "做题", "练习", "考试", "测试", "刷题", "训练",
    "批改", "改一下", "对不对", "答案是什么", "出几道", "来几道",
    "出一道", "做一道", "练一下", "练练",
    "exercise", "practice", "test", "quiz",
]
_PROGRESS_SIGNALS = [
    "进度", "薄弱", "诊断", "正确率", "学了多久", "统计",
    "学了多少", "学得怎么样", "学得如何",
    "progress", "diagnose", "weakness", "stats",
]
_PLANNING_SIGNALS = [
    "计划", "规划", "从哪里开始", "学习路线", "怎么学",
    "学什么", "接下来", "下一步", "怎么开始",
    "study plan", "plan", "roadmap",
]
_SEARCH_SIGNALS = [
    "查一下", "搜索", "搜一下", "找一下", "有没有", "知识库",
    "论文", "资料", "文档", "定义", "什么是", "是什么",
]

def _get_tool_profile(message: str) -> set:
    """根据用户消息返回建议的工具组集合。

    默认返回所有组（兜底）。命中特定信号则缩小到对应组。
    retrieval 总是保留（基础能力）。
    """
    msg = message.strip().lower()
    groups = set()

    if any(s in msg for s in _PRACTICE_SIGNALS):
        groups.add("assessment")
    if any(s in msg for s in _PROGRESS_SIGNALS):
        groups.add("progress")
    if any(s in msg for s in _PLANNING_SIGNALS):
        groups.add("planning")
    if any(s in msg for s in _SEARCH_SIGNALS):
        groups.add("retrieval")

    # 没有命中任何子信号 → 返回所有工具组（当前默认行为）
    if not groups:
        return {"retrieval", "assessment", "progress", "planning"}

    # retrieval 总是包含（兜底搜索能力）
    groups.add("retrieval")
    return groups


def _classify_intent(message: str) -> str:
    """将用户消息分类为: greeting / learning / casual
    greeting + casual → 快速路径（不触发 ReAct 循环和知识库检索）
    learning → 完整 ReAct 循环
    """
    msg = message.strip().lower()

    # 1. 精确问候
    if message.strip() in _SIMPLE_GREETINGS:
        return "greeting"

    # 2. 短消息无技术关键词 → casual
    if len(message.strip()) < 10:
        has_keyword = any(kw.lower() in msg for kw in _TECHNICAL_KEYWORDS)
        if not has_keyword:
            return "casual"

    # 3. 非学习意图信号 → casual
    for signal in _NON_LEARNING_SIGNALS:
        if signal in msg:
            return "casual"

    # 4. 其余 → learning（进入 ReAct 循环）
    return "learning"


def _is_simple_query(message: str) -> bool:
    """快速路径判定：greeting/casual 且无相关 DataSource 工具时才走快速路径。"""
    intent = _classify_intent(message)
    if intent not in ("greeting", "casual"):
        return False
    # 如果消息关键词可能匹配已注册的 DataSource 工具，不走快速路径
    return not _matches_datasource_tool(message)


def _matches_datasource_tool(message: str) -> bool:
    """检查消息是否可能被已注册的 DataSource 工具处理。"""
    try:
        from services.data_sources import get_manager
        sources = get_manager().list_sources()
    except Exception:
        return False
    msg = message.lower()
    # DataSource name keyword mapping — 当用户消息包含这些词且对应源已注册时，走 ReAct
    _DS_KEYWORDS = {
        "news": ["新闻", "news", "头条", "热搜", "热点"],
        "weather": ["天气", "weather", "气温", "下雨", "刮风", "晴天", "阴天"],
        "local_file": ["文件", "文档", "file", "我上传的", "本地"],
    }
    for source_name in sources:
        keywords = _DS_KEYWORDS.get(source_name, [])
        if any(kw in msg for kw in keywords):
            return True
    return False


# ══════════════════════════════════════════════
# Tool 定义
# ══════════════════════════════════════════════

@tool
def search_knowledge(query: str) -> str:
    """搜索知识库获取相关内容。当用户问技术概念、论文、知识点时使用。
    参数 query: 搜索关键词或问题（支持中英文）。
    内部使用迭代检索：先给 top-2 chunk，LLM 判断充足性，不足则扩展到 top-5。"""
    chunks = search_iterative(query, k=5, topn=2)
    if not chunks:
        emit_event("rag.empty", {
            "query": query[:200],
            "total_results": 0,
        })
        return (
            "知识库中未找到相关内容。\n\n"
            "💡 你可以去 **知识管道** 页面，使用联网搜索引入这方面的知识。引入后我就能回答你的问题了。\n"
            "[前往知识管道 →](/knowledge-pipeline)"
        )
    top_sim = chunks[0].get("similarity", 0)
    if len(chunks) >= 5:
        if top_sim < 0.35:
            emit_event("rag.coverage_gap", {
                "query": query[:200],
                "top_similarity": top_sim,
                "chunk_count": len(chunks),
            })
        else:
            emit_event("rag.intent_mismatch", {
                "query": query[:200],
                "top_similarity": top_sim,
                "chunk_count": len(chunks),
            })
    lines = []
    for i, c in enumerate(chunks, 1):
        lines.append(f"[{i}] {c['title']} (相似度: {c['similarity']})")
        lines.append(f"    {c['text'][:300]}")
    return "\n".join(lines)


@tool
def generate_question(topic: str, question_type: str = "mcq", difficulty: str = "中等") -> str:
    """生成练习题。用户要求做题、练习、测试时使用。
    参数 topic: 知识点名称, question_type: mcq/coding/flashcards, difficulty: 简单/中等/困难。"""
    system_prompt = load_prompt("knowledge_importer") or (
        f"你是一位专业的出题老师。请根据以下知识点，生成一道{difficulty}难度的{question_type}题目。"
        "如果是选择题(mcq)，给出4个选项(A/B/C/D)，标注正确答案和解析。"
        "如果是编程题(coding)，给出题目描述、输入输出示例和至少2个测试用例。"
        "如果是闪卡(flashcards)，给出问题和详细答案(200字以内)。"
        "用中文回答。"
    )
    try:
        reply, usage = chat(
            messages=[{"role": "user", "content": f"知识点: {topic}\n题型: {question_type}\n难度: {difficulty}\n\n请在题目末尾附加一个JSON块（用```json```包裹），包含字段: type, topic, question, options(仅mcq), answer, explanation, difficulty。例如:\n```json\n{{\"type\": \"mcq\", \"topic\": \"{topic}\", \"question\": \"...\", \"options\": [\"A. ...\", \"B. ...\", \"C. ...\", \"D. ...\"], \"answer\": \"A\", \"explanation\": \"...\", \"difficulty\": \"{difficulty}\"}}\n```"}],
            system_prompt=system_prompt,
            temperature=0.8,
            max_tokens=800,
        )
        return reply
    except Exception as e:
        return f"出题失败: {str(e)}"


@tool
def analyze_progress() -> str:
    """查询用户的学习进度统计，包括总答题数、正确率、连续学习天数等。"""
    try:
        progress = load_progress()
    except Exception as e:
        return f"读取学习进度失败: {str(e)}"

    if not progress:
        return "暂无学习记录。开始做题吧！"

    total = sum(
        len(items) for items in progress.get("exercises", {}).values()
        if isinstance(items, list)
    )
    correct = progress.get("stats", {}).get("correct", 0)

    # 按领域统计
    by_topic = {}
    for ex_type, items in progress.get("exercises", {}).items():
        if not isinstance(items, list):
            continue
        for item in items:
            topic = item.get("topic", item.get("domain", "其他"))
            if topic not in by_topic:
                by_topic[topic] = {"total": 0, "correct": 0}
            by_topic[topic]["total"] += 1
            if item.get("correct", item.get("passed", False)):
                by_topic[topic]["correct"] += 1

    lines = [f"总答题数: {total}", f"总正确数: {correct}", f"正确率: {correct/total*100:.1f}%" if total else "正确率: N/A"]
    lines.append("\n领域明细:")
    for topic, stats in sorted(by_topic.items()):
        rate = stats["correct"] / stats["total"] * 100 if stats["total"] else 0
        lines.append(f"  - {topic}: {stats['correct']}/{stats['total']} ({rate:.1f}%)")
    return "\n".join(lines)


@tool
def diagnose_weakness() -> str:
    """诊断薄弱点，识别正确率低的知识领域，并给出学习建议。"""
    try:
        weak = get_weak_areas()
    except Exception as e:
        return f"诊断失败: {str(e)}"

    if not weak:
        return "当前没有明显的薄弱点，继续保持！或者多做些练习让我有更多数据。"
    lines = ["以下领域需要加强:"]
    for area in weak[:5]:
        name = area.get("topic", area.get("domain", "未知"))
        rate = area.get("accuracy", area.get("correct_rate", 0))
        lines.append(f"  - {name}: 正确率 {rate:.0%}")
    lines.append("\n建议: 对这些领域进行针对性练习，可以从基础知识重新梳理，再做进阶题目。")
    return "\n".join(lines)


@tool
def save_question_to_trainer(question_json: str) -> str:
    """将生成的题目保存到训练器临时题库。当用户说"保存这道题""加入题库""存下来"时使用。
    参数 question_json: 题目的JSON字符串，包含字段 type(mcq/coding/flashcards)、question、options(仅mcq)、answer、explanation、topic、difficulty。"""
    try:
        item = json.loads(question_json)
    except json.JSONDecodeError:
        return "保存失败：题目数据格式错误，需要是合法的JSON。"
    required = ["type", "question", "answer"]
    missing = [f for f in required if f not in item]
    if missing:
        return f"保存失败：缺少必填字段 {', '.join(missing)}。"
    ex_type = item["type"]
    if ex_type not in ("mcq", "coding", "flashcards"):
        return f"保存失败：type 必须是 mcq/coding/flashcards 之一，收到 '{ex_type}'。"

    from services.exercise_store import add as store_add, load as store_load
    item["_source"] = "agent_saved"
    saved = store_add(item)
    total = sum(len(v) for v in store_load().values())
    return f"已保存到训练器临时题库（{ex_type} #{saved['id']}）。当前临时题库共 {total} 道题。"


@tool
def evaluate_answer(question: str, user_answer: str, reference_answer: str = "") -> str:
    """评估用户对简答题/概念题的回答质量。当用户提交了文字回答需要批改时使用。
    参数 question: 题目内容, user_answer: 用户提交的回答, reference_answer: 参考答案（可选）。"""
    template = load_prompt("tool_evaluate_answer")
    ref_section = f"参考答案: {reference_answer}" if reference_answer else ""
    prompt = template.format(question=question, user_answer=user_answer, reference_section=ref_section)
    try:
        reply, _ = chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一位严格但鼓励学生的评分老师。用中文回复。",
            temperature=0.3, max_tokens=400,
        )
        return reply
    except Exception as e:
        return f"评估失败: {str(e)}"


@tool
def deep_question(concept: str, user_level: str = "中级") -> str:
    """生成概念迁移/场景应用题。当用户说"换个角度问""深入理解""举一反三"时使用。
    参数 concept: 知识点名称, user_level: 用户水平(初级/中级/高级)。"""
    template = load_prompt("tool_deep_question")
    prompt = template.format(concept=concept, user_level=user_level)
    try:
        reply, _ = chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一位善于设计深度思考题的老师。用中文，题目控制在150字以内。",
            temperature=0.8, max_tokens=500,
        )
        return reply
    except Exception as e:
        return f"出题失败: {str(e)}"


@tool
def feynman_check(concept: str, explanation: str) -> str:
    """费曼检查：评估用户对一个概念的解释是否足够简单清晰。当用户说"费曼""用简单话解释""教我"时使用。
    参数 concept: 概念名称, explanation: 用户用自己的话写的解释。"""
    template = load_prompt("tool_feynman_check")
    prompt = template.format(concept=concept, explanation=explanation)
    try:
        reply, _ = chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一位费曼学习法教练。你的目标是帮用户把复杂概念讲到12岁孩子也能听懂。严格但鼓励。用中文。",
            temperature=0.3, max_tokens=500,
        )
        return reply
    except Exception as e:
        return f"费曼检查失败: {str(e)}"


@tool
def create_study_plan(weak_areas_json: str = "") -> str:
    """根据用户薄弱点生成个性化学习计划。当用户问"我该怎么学""学习计划""从哪里开始"时使用。
    参数 weak_areas_json: 薄弱点JSON数组，如 [{"topic":"CNN","accuracy":0.45}]。为空则自动从progress诊断。"""
    try:
        if weak_areas_json and weak_areas_json.strip():
            weak = json.loads(weak_areas_json)
        else:
            weak = get_weak_areas()
    except (json.JSONDecodeError, TypeError):
        weak = get_weak_areas()

    if not weak:
        return "当前没有明显的薄弱点。建议: 1) 保持每日闪卡复习 2) 尝试挑战高难度题目 3) 探索知识库中感兴趣的新领域。"

    topics = ", ".join([f"{w['topic']}(正确率{w['accuracy']:.0%})" for w in weak[:5]])
    template = load_prompt("tool_create_study_plan")
    prompt = template.format(topics=topics)
    try:
        reply, _ = chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt="你是一位资深学习教练，善于为学习者制定个性化计划。",
            temperature=0.5, max_tokens=500,
        )
        return reply
    except Exception as e:
        return f"生成学习计划失败: {str(e)}"


@tool
def web_search(query: str) -> str:
    """联网搜索最新信息。当知识库无法覆盖用户问题，或用户明确要求搜索互联网时使用。
    参数 query: 搜索关键词（中英文均可）。"""
    import re
    import requests

    results = []
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

    # 主: cn.bing.com (中国可达)
    try:
        r = requests.get("https://cn.bing.com/search",
                         params={"q": query, "count": 5},
                         headers={"User-Agent": ua}, timeout=10)
        r.encoding = "utf-8"
        hrefs = re.findall(r'href="(https?://[^"]+)"', r.text)
        seen = set()
        for url in hrefs:
            url = url.strip()
            if (url.startswith("http") and "bing.com" not in url
                    and "microsoft.com" not in url and url.count("/") >= 4
                    and url not in seen):
                seen.add(url)
                results.append({
                    "title": url.split("/")[2],
                    "url": url,
                    "snippet": "",
                })
                if len(results) >= 5:
                    break
    except Exception:
        pass

    if not results:
        return "未找到相关搜索结果。请尝试更换关键词或直接粘贴链接到知识管道。"

    lines = ["[联网搜索] 以下来自互联网:\n"]
    for i, r in enumerate(results[:5], 1):
        lines.append(f"{i}. **{r['title']}**")
        lines.append(f"   {r['snippet']}")
        lines.append(f"   {r['url']}\n")
    return "\n".join(lines)


# ══════════════════════════════════════════════
# Agent 工厂
# ══════════════════════════════════════════════

def _build_tools(profile: set = None) -> list:
    """根据用户配置动态构建工具列表。

    profile: 可选工具组集合，None=全部。用于意图驱动的工具路由。
    """
    _ALL_TOOLS = {
        "search_knowledge": search_knowledge,
        "generate_question": generate_question,
        "analyze_progress": analyze_progress,
        "diagnose_weakness": diagnose_weakness,
        "save_question_to_trainer": save_question_to_trainer,
        "evaluate_answer": evaluate_answer,
        "deep_question": deep_question,
        "feynman_check": feynman_check,
        "create_study_plan": create_study_plan,
        "web_search": web_search,
    }

    if profile is not None:
        # 筛选工具：仅保留请求组中的工具
        allowed_names = set()
        for group_name in profile:
            allowed_names.update(_TOOL_GROUPS.get(group_name, ()))
        allowed_names.discard("web_search")  # web_search 单独判断
    else:
        allowed_names = set(_ALL_TOOLS.keys())
        allowed_names.discard("web_search")

    tools = [t for name, t in _ALL_TOOLS.items()
             if name in allowed_names and name != "web_search"]

    # web_search: 用户设置开关 + profile 允许
    try:
        from services.user_settings import get_setting
        ws_enabled = get_setting("web_search_enabled", True)
    except Exception:
        ws_enabled = True
    if ws_enabled and (profile is None or "retrieval" in profile):
        tools.append(web_search)

    return tools

_BASE_TOOLS_CACHE = None
_BASE_TOOLS_CACHE_TS = 0
_BASE_TOOLS_PROFILE_CACHE = None

def get_tools(message: str = "") -> list:
    """获取当前工具列表（带缓存，5秒过期）。

    message: 可选用户消息，用于意图驱动的工具路由。空字符串=全部工具。
    """
    global _BASE_TOOLS_CACHE, _BASE_TOOLS_CACHE_TS, _BASE_TOOLS_PROFILE_CACHE
    now = time.time()
    if message:
        profile = _get_tool_profile(message)
        tools = _build_tools(profile)
    else:
        if _BASE_TOOLS_CACHE is not None and (now - _BASE_TOOLS_CACHE_TS) < 5:
            return _BASE_TOOLS_CACHE
        tools = _build_tools(None)
        _BASE_TOOLS_CACHE_TS = now

    # ── 追加数据源工具（动态注入，不污染静态 _ALL_TOOLS）──
    try:
        from services.data_sources import get_manager as _ds_manager
        ds_tools = _ds_manager().get_all_tools()
        for t in ds_tools:
            if t.name not in {tool.name for tool in tools}:
                tools.append(t)
    except Exception:
        pass  # 数据源不可用时不影响 Agent 启动

    if not message:
        _BASE_TOOLS_CACHE = tools
    return tools

_TOOL_MAP = {t.name: t for t in _build_tools(None)}

# ══════════════════════════════════════════════
# 历史压缩
# ══════════════════════════════════════════════

def _build_tool_result_summary(tool_name: str, result_text: str) -> str:
    """规则压缩：取工具返回的第一行作为摘要（对 search_knowledge 等结构化返回有效）"""
    first_line = result_text.strip().split("\n")[0][:120]
    return f"[{tool_name}] {first_line}"


def _compress_messages(messages: list) -> list:
    """压缩消息历史：保留 system prompt + 最近 6 条，更早的压缩为摘要。
    如果本地模型可用则调用本地模型；否则用规则截取第一行。
    """
    if len(messages) <= COMPRESS_THRESHOLD:
        return messages

    system_msg = messages[0] if messages[0].type == "system" else None
    start = 1 if system_msg else 0
    recent = messages[-6:]  # 最近 6 条保留原文
    old = messages[start:-6]

    if not old:
        return messages

    # 尝试本地模型压缩
    try:
        from services.local_llm import compress_history as _local_compress, is_available
        if is_available():
            raw = []
            for m in old:
                role = "assistant" if (isinstance(m, AIMessage) or hasattr(m, "tool_calls")) else "tool" if isinstance(m, ToolMessage) else "user"
                content = str(m.content)[:200] if m.content else ""
                raw.append({"role": role, "content": content})
            summary = _local_compress(raw)
            if summary and len(summary) > 5:
                result = [system_msg] if system_msg else []
                result.append(HumanMessage(content=f"[对话历史摘要] {summary}"))
                result.extend(recent)
                return result
    except Exception:
        pass

    # 规则回退：每条旧消息取第一行
    parts = []
    for m in old:
        content = str(m.content)[:150] if m.content else ""
        first = content.strip().split("\n")[0][:100]
        if isinstance(m, ToolMessage):
            label = getattr(m, "name", "tool")
            parts.append(f"[{label}] {first}")
        elif isinstance(m, AIMessage) or hasattr(m, "tool_calls"):
            if first:
                parts.append(f"[思考] {first}")
    brief = " | ".join(parts[:5])

    if system_msg and brief:
        return [system_msg, HumanMessage(content=f"[历史摘要] {brief}")] + recent
    return [system_msg] + recent if system_msg else recent

import time

# ── Session 管理 ──
_SESSION_HISTORY: dict[str, list] = {}    # session_id → compressed message history
_SESSION_META: dict[str, dict] = {}       # session_id → {"created": float, "last_accessed": float}
_SWEEP_COUNTER = 0
_WEB_SEARCH_COUNTS: dict[str, int] = {}


def generate_course_stream(topic, sources=None, persona="teacher", depth="standard"):
    """SSE generator: 搜索素材 → LLM 生成结构化课程 → 逐章产出

    Yields dicts with keys: type, ...
    """
    import json as _json_module

    session_id = f"course_{int(time.time())}"

    # Phase 1: Searching
    yield {"type": "searching", "message": "正在搜索相关素材..."}

    # Search knowledge base
    kb_results = []
    try:
        from services.vector_search import search_knowledge_base
        kb_results = search_knowledge_base(topic, top_k=5)
    except Exception:
        pass

    # Web search if enabled
    web_results = []
    try:
        from services.web_search import web_search
        web_results = web_search(topic, num_results=3)
    except Exception:
        pass

    all_sources = []
    for item in kb_results[:3]:
        all_sources.append({"type": "kb", "name": item.get("title", item.get("concept", "")), "content": item.get("content", item.get("answer", ""))[:800]})
    for item in web_results[:2]:
        all_sources.append({"type": "search", "url": item.get("url", ""), "title": item.get("title", ""), "content": item.get("snippet", "")[:500]})

    if sources:
        # user-selected sources passed as names — mark matching kb_results as user_selected
        pass

    source_text = "\n\n".join([
        f"[来源: {s.get('name', s.get('title', ''))}]\n{s.get('content', '')}"
        for s in all_sources
    ])

    depth_instruction = "深度讲解，包含数学推导和代码示例" if depth == "deep" else "标准讲解，适合初学者理解核心概念"

    # Phase 2: Generate outline
    yield {"type": "outline", "message": "正在规划课程大纲..."}

    outline_prompt = f"""你是一位资深课程设计师。请为以下主题规划一个课程大纲。

主题：{topic}
深度要求：{depth_instruction}

参考资料：
{source_text[:2000]}

请输出 4-6 个章节标题，每行一个，格式为 "## 章节标题"。
不要输出其他内容。"""

    from services.deepseek_client import chat

    try:
        outline_text, _ = chat(
            messages=[{"role": "user", "content": outline_prompt}],
            temperature=0.5,
            max_tokens=600,
            timeout=30,
        )
    except Exception as e:
        yield {"type": "error", "message": f"大纲生成失败: {str(e)}"}
        return

    # Parse outline: lines starting with ##
    section_headings = []
    for line in outline_text.split("\n"):
        line = line.strip()
        if line.startswith("## "):
            section_headings.append(line[3:].strip())
    if not section_headings:
        section_headings = ["核心概念", f"{topic}详解", "关键要点与总结"]

    yield {"type": "outline", "sections": section_headings}

    # Phase 3: Generate each section
    sections = []
    for i, heading in enumerate(section_headings):
        yield {"type": "section", "index": i, "heading": heading, "status": "generating"}

        section_prompt = f"""你是一位资深课程设计师。请为课程《{topic}》撰写章节 "{heading}"。

参考资料：
{source_text[:1500]}

请用 Markdown 格式撰写，包含：
1. 该章节的核心知识点讲解
2. 如果合适，包含一个对比表格或列表
3. 一个简短的应用案例或示例

控制在 200-400 字，语言清晰有深度。"""

        try:
            section_body, _ = chat(
                messages=[{"role": "user", "content": section_prompt}],
                temperature=0.6,
                max_tokens=600,
                timeout=30,
            )
        except Exception:
            section_body = f"（{heading}内容生成失败，请重试）"

        sections.append({
            "heading": heading,
            "body": section_body.strip(),
            "chart": None,
            "examples": [],
            "refs": [],
        })

        yield {"type": "section", "index": i, "heading": heading, "body": sections[-1]["body"], "status": "done"}

    # Phase 4: Generate quiz
    yield {"type": "quiz", "status": "generating"}

    quiz_prompt = f"""你是一位资深课程设计师。请为课程《{topic}》设计 3 道检验题。

课程章节：{', '.join(section_headings)}

请输出 JSON 数组，每道题格式为：
{{"type": "feynman"|"choice", "prompt": "题目内容", "options": ["A", "B", "C", "D"]}}

注意：feynman 类型不需要 options 字段，choice 类型需要 options 字段（4个选项）。
只输出 JSON 数组，不要其他内容。"""

    try:
        quiz_text, _ = chat(
            messages=[{"role": "user", "content": quiz_prompt}],
            temperature=0.5,
            max_tokens=500,
            timeout=30,
        )
        # Try to extract JSON array
        json_match = re.search(r'\[[\s\S]*\]', quiz_text)
        quiz = _json_module.loads(json_match.group(0)) if json_match else []
    except Exception:
        quiz = [{"type": "feynman", "prompt": f"用你自己的话解释：{topic} 的核心思想是什么？"}]

    yield {"type": "quiz", "items": quiz, "status": "done"}

    # Phase 5: Assemble final
    course = {
        "id": f"course_{int(time.time())}_{topic[:8].replace(' ', '_')}",
        "title": topic,
        "generated_at": int(time.time()),
        "sources": [{"type": s["type"], "name": s.get("name", s.get("title", ""))} for s in all_sources],
        "sections": sections,
        "quiz": quiz,
    }

    # Store course in session for classroom pickup
    _SESSION_META.setdefault("teacher_active", {})["last_course"] = course

    yield {"type": "final", "course": course}


def _sweep_expired_sessions():
    """移除 idle 超过 SESSION_TTL_SECONDS 的 session。"""
    from config import SESSION_TTL_SECONDS
    now = time.time()
    expired = [
        sid for sid, data in _SESSION_META.items()
        if now - data.get("last_accessed", data.get("created", now)) > SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _SESSION_META.pop(sid, None)
        _SESSION_HISTORY.pop(sid, None)
        _WEB_SEARCH_COUNTS.pop(sid, None)
    return len(expired)


def send_course_to_classroom(course, teacher_session_id="teacher_active"):
    """将办公室生成的课程推送到教室 session，供下一次 SSE final 携带"""
    if teacher_session_id in _SESSION_META:
        _SESSION_META[teacher_session_id]["pending_course"] = course
    else:
        _SESSION_META[teacher_session_id] = {"pending_course": course, "last_tool_profile": None, "active_plan": []}


def _touch_session(session_id: str):
    """更新 session 访问时间。超过 SESSION_MAX_COUNT 时 LRU 淘汰。"""
    from config import SESSION_MAX_COUNT
    now = time.time()
    if session_id not in _SESSION_META:
        _SESSION_META[session_id] = {
            "created": now,
            "last_accessed": now,
            "last_tool_profile": None,
            "active_plan": [],
        }
        # LRU 淘汰: 超过上限时移除最久未访问的 session
        if len(_SESSION_META) > SESSION_MAX_COUNT:
            sorted_sessions = sorted(
                _SESSION_META.items(),
                key=lambda kv: kv[1].get("last_accessed", kv[1].get("created", 0))
            )
            to_remove = sorted_sessions[:len(_SESSION_META) - SESSION_MAX_COUNT]
            for sid, _ in to_remove:
                _SESSION_META.pop(sid, None)
                _SESSION_HISTORY.pop(sid, None)
                _WEB_SEARCH_COUNTS.pop(sid, None)
    else:
        _SESSION_META[session_id]["last_accessed"] = now


# ── Plan-first preamble (HOOK 3.5 #3) ──

def _generate_plan(message: str, history: list) -> list:
    """生成结构化执行计划（JSON数组），失败时返回空列表。

    返回格式: [{"step": 1, "goal": "...", "tool": "tool_name"}, ...]
    如果规划失败或质量差，调用方自动回退到标准 ReAct。
    """
    history_context = ""
    if history:
        recent = history[-3:]
        history_context = "\n".join([
            f"用户: {m.content[:200] if hasattr(m, 'content') and m.content else '...'}"
            for m in recent if hasattr(m, 'content')
        ])[:500]

    available_tools = ", ".join(sorted(_TOOL_MAP.keys()))
    prompt = (
        "你是一个学习助手规划器。根据用户问题，生成3-5步的执行计划。"
        f"当前可用工具: {available_tools}。\n"
        "输出一个JSON数组，每个元素包含: step(步骤序号), goal(本步骤目标,≤30字), tool(工具名,必须来自上述可用工具列表)。\n"
        "格式示例: [{\"step\":1,\"goal\":\"搜索知识库获取相关概念\",\"tool\":\"search_knowledge\"},"
        "{\"step\":2,\"goal\":\"用费曼检查验证理解\",\"tool\":\"feynman_check\"}]\n"
        "规则: 1) 只输出JSON数组 2) tool必须是可用工具之一 3) 3-5步 4) 不确定时输出空数组 []\n"
    )
    user_msg = f"用户问题: {message}"
    if history_context:
        user_msg = f"对话历史:\n{history_context}\n\n{user_msg}"

    try:
        plan_text, _ = chat(
            messages=[{"role": "user", "content": user_msg}],
            system_prompt=prompt,
            temperature=0.1,
            max_tokens=250,
            timeout=10,
        )
        plan_text = plan_text.strip()
        if not plan_text or "[]" in plan_text:
            return []
        # 提取 JSON 数组
        import re
        json_match = re.search(r'\[[\s\S]*\]', plan_text)
        if not json_match:
            return []
        plan = json.loads(json_match.group(0))
        if not isinstance(plan, list) or len(plan) < 1:
            return []
        # 验证工具名有效性
        valid_plan = []
        for item in plan[:6]:  # 最多5步
            tool = item.get("tool", "")
            if tool not in _TOOL_MAP:
                continue  # 跳过幻觉工具引用
            valid_plan.append({
                "step": len(valid_plan) + 1,
                "goal": str(item.get("goal", ""))[:30],
                "tool": tool,
            })
        return valid_plan if valid_plan else []
    except Exception:
        return []


def _format_plan_for_prompt(plan: list) -> str:
    """将结构化计划格式化为 prompt 可注入的文本。"""
    if not plan:
        return ""
    lines = ["## 执行计划（结构化）"]
    for p in plan:
        lines.append(f"  Step {p['step']}: {p['goal']} → 工具: {p['tool']}")
    lines.append("每完成一步后继续执行下一步。如果计划不再适用，忽略剩余步骤直接回答。")
    return "\n".join(lines)


def _plan_progress_reminder(plan: list, current_step: int) -> str:
    """生成计划进度提示，注入到 observation 中。"""
    if not plan or current_step > len(plan):
        return ""
    total = len(plan)
    parts = [f"\n\n[计划进度: {current_step}/{total}]"]
    for i, p in enumerate(plan):
        mark = "[x]" if i + 1 < current_step else ("[>]" if i + 1 == current_step else "[ ]")
        parts.append(f"  {mark} Step {p['step']}: {p['goal']}")
    return "\n".join(parts)


def _get_system_prompt(persona: str = ""):
    """返回指定 persona 的 system prompt，注入跨 agent 上下文。
    persona 可选: deskmate, teacher, interviewer, 默认加载 agent_system
    """
    # 面试官 persona 使用 mock_interview prompt
    if persona == "interviewer":
        prompt = load_prompt("mock_interview") or load_prompt("agent_system")
    else:
        prompt = load_prompt(f"agent_{persona}") if persona else ""
        if not prompt:
            prompt = load_prompt("agent_system")
    if not prompt:
        prompt = (
            "你是一个智能学习助手。帮助用户搜索知识库、生成练习题、"
            "查看学习进度、诊断薄弱环节。用中文回答。"
        )

    # 跨 Agent 通信：注入结构化上下文气泡
    try:
        from services.session_store import get_bubble_context
        other_context = get_bubble_context(exclude_persona=persona, limit=3)
        if other_context:
            other_persona = {"deskmate": "同桌", "teacher": "老师", "interviewer": "面试官"}
            other_label = other_persona.get(
                "teacher" if persona == "deskmate" else "deskmate", "学习伙伴"
            )
            if persona == "teacher":
                inject = (
                    "\n\n## 跨 Agent 上下文气泡（结构化记忆共享）\n"
                    "用户最近与「同桌」的交流记录如下。每条包含话题、用户问题、同桌回答。"
                    "如果用户继续讨论相关概念，请主动说「我听你同桌聊到过…」并引用具体内容。"
                    "不要只泛泛而谈——提到同桌给出的具体洞察会让用户感到学习伙伴真正在配合。\n\n"
                    f"{other_context}"
                )
            elif persona == "deskmate":
                inject = (
                    "\n\n## 跨 Agent 上下文气泡（结构化记忆共享）\n"
                    "用户最近与「老师」的交流记录如下。每条包含话题、用户问题、老师回答。"
                    "如果用户继续讨论相关话题，可以说「老师在那边讲过这个…」并引用老师的原话。"
                    "引用老师给出的具体解释会让衔接更自然。\n\n"
                    f"{other_context}"
                )
            elif persona == "interviewer":
                inject = (
                    "\n\n## 跨 Agent 上下文气泡\n"
                    "用户在面试前与学习伙伴的交流记录如下：\n\n"
                    f"{other_context}"
                    "\n可以利用这些信息了解用户的知识背景和薄弱环节，针对性地调整面试问题。"
                )
            else:
                inject = ""
            prompt += inject
    except Exception:
        pass  # session_store 不可用时不影响主流程

    return prompt


def _execute_tool(tool_name: str, tool_args: dict) -> str:
    """执行工具并返回结果字符串，同时记录 eval trace span"""
    func = _TOOL_MAP.get(tool_name)
    if func is None:
        # 数据源工具 fallback — 不在 _TOOL_MAP 中，由 get_tools 动态注入
        try:
            from services.data_sources import get_manager as _ds_mgr
            for t in _ds_mgr().get_all_tools():
                if t.name == tool_name:
                    func = t
                    break
        except Exception:
            pass
    if func is None:
        return f"未知工具: {tool_name}"
    t0 = time.time()
    input_summary = str(tool_args)[:200]
    try:
        result = func.invoke(tool_args)
        output = str(result)
        _safe_record_tool_span(
            tool_name=tool_name,
            duration_ms=int((time.time() - t0) * 1000),
            input_params=input_summary,
            output_summary=output[:200],
            status="success",
        )
        return output
    except Exception as e:
        _safe_record_tool_span(
            tool_name=tool_name,
            duration_ms=int((time.time() - t0) * 1000),
            input_params=input_summary,
            output_summary=str(e)[:200],
            status="error",
            error_type=type(e).__name__,
        )
        return f"工具执行失败 ({tool_name}): {str(e)}"


def _run_react_loop(llm, system_prompt: str, user_message: str, history: list,
                     max_steps: int = 0, provider_used: str = "",
                     plan: list = None, session_id: str = "") -> dict:
    """自定义 ReAct 循环：LLM 思考→调用工具→观察→循环，含历史压缩和步数限制。

    plan: 可选结构化执行计划（list of {step, goal, tool}），注入 system prompt 引导 ReAct。
    """
    full_prompt = system_prompt
    if plan:
        plan_text = _format_plan_for_prompt(plan)
        if plan_text:
            full_prompt += "\n\n" + plan_text

    messages = [SystemMessage(content=full_prompt)]
    if history:
        messages.extend(history)
    messages.append(HumanMessage(content=user_message))

    steps = []
    reply = ""
    plan_step_idx = 0  # 当前执行到的计划步骤 (1-indexed)
    if max_steps <= 0:
        max_steps = _get_max_steps()

    for i in range(max_steps):
        response = llm.invoke(messages)

        # 记录 LangChain 路径的 token 用量
        try:
            from services.agent_logger import log_token_usage
            meta = getattr(response, "response_metadata", None) or {}
            tu = meta.get("token_usage") or meta.get("usage", {})
            if tu:
                import config as _cfg
                log_token_usage(
                    model=getattr(_cfg, "MODEL", ""),
                    provider=provider_used or getattr(_cfg, "LLM_PROVIDER", ""),
                    prompt_tokens=tu.get("prompt_tokens", 0),
                    completion_tokens=tu.get("completion_tokens", 0),
                )
        except Exception:
            pass

        has_tool_calls = (hasattr(response, "tool_calls")
                          and response.tool_calls
                          and len(response.tool_calls) > 0)

        if has_tool_calls:
            # ── Thought 阶段 ──
            if response.content and str(response.content).strip():
                steps.append({"phase": "thought", "content": str(response.content)[:500]})

            messages.append(response)

            # ── Action + Observation ──
            for tc in response.tool_calls:
                tc_name = tc.get("name", "unknown")
                tc_args = tc.get("args", {})
                tc_id = tc.get("id", "")

                steps.append({"phase": "action", "tool": tc_name, "input": tc_args})

                # web_search per-session limit
                if tc_name == "web_search":
                    cnt = _WEB_SEARCH_COUNTS.get(session_id, 0)
                    if cnt >= 3:
                        observation = "本对话已进行 3 次联网搜索，已达上限。请基于已有信息回答。"
                        steps.append({"phase": "observation", "tool": tc_name, "output": observation})
                        messages.append(ToolMessage(content=observation, tool_call_id=tc_id, name=tc_name))
                        continue
                    _WEB_SEARCH_COUNTS[session_id] = cnt + 1

                result = _execute_tool(tc_name, tc_args)
                # Plan progress injection: 如果计划匹配当前工具，追加进度提示
                if plan and plan_step_idx < len(plan):
                    plan_step_idx += 1
                    # NEW: update SESSION_META plan step statuses
                    if session_id in _SESSION_META:
                        meta_plan = _SESSION_META[session_id].get("active_plan", [])
                        if plan_step_idx - 1 < len(meta_plan):
                            meta_plan[plan_step_idx - 1]["status"] = "done"
                        if plan_step_idx < len(meta_plan):
                            meta_plan[plan_step_idx]["status"] = "doing"
                    progress = _plan_progress_reminder(plan, plan_step_idx)
                    if progress:
                        result += progress
                steps.append({"phase": "observation", "tool": tc_name, "output": result[:800]})
                messages.append(ToolMessage(content=result, tool_call_id=tc_id, name=tc_name))

            # ── 历史压缩 ──
            if len(messages) > COMPRESS_THRESHOLD:
                messages = _compress_messages(messages)
        else:
            reply = response.content or ""
            messages.append(response)
            break

    max_steps_reached = not reply and bool(steps)
    if max_steps_reached:
        reply = (
            f"已达到最大步数限制（{max_steps}步）。以下是已完成的步骤：\n"
            + "\n".join(f"- {s.get('phase', '?')}: {str(s.get('tool', s.get('content', '')))[:100]}"
                        for s in steps)
            + "\n\n请重新描述你的问题，或拆分为更小的请求。"
        )

    return {"reply": reply, "steps": steps, "final_messages": messages,
            "max_steps_reached": max_steps_reached}


# ══════════════════════════════════════════════
# Session & Public API
# ══════════════════════════════════════════════

def _load_history(session_id: str) -> list:
    return _SESSION_HISTORY.get(session_id, [])


def _save_history(session_id: str, messages: list, persona: str = ""):
    """保存时做一次压缩，避免历史无限增长，并持久化到磁盘"""
    # 去掉 system prompt
    user_messages = [m for m in messages if m.type != "system"]
    if len(user_messages) > 8:
        # 只保留最近 8 条消息原文，更早的压缩
        recent = user_messages[-8:]
        older = user_messages[:-8]
        try:
            from services.local_llm import compress_history as _local_compress, is_available
            if is_available():
                raw = []
                for m in older:
                    role = "assistant" if (isinstance(m, AIMessage) or hasattr(m, "tool_calls")) else "tool" if isinstance(m, ToolMessage) else "user"
                    raw.append({"role": role, "content": str(m.content)[:200] if m.content else ""})
                summary = _local_compress(raw)
                if summary and len(summary) > 5:
                    user_messages = [HumanMessage(content=f"[历史摘要] {summary}")] + recent
        except Exception:
            pass
        if len(user_messages) > 8:
            # 仍超限：规则截断
            user_messages = user_messages[-8:]
    _SESSION_HISTORY[session_id] = user_messages

    # 持久化到磁盘（跨页面/跨 agent 共享）
    try:
        from services.session_store import save as _disk_save
        serializable = []
        for m in user_messages:
            # 跳过 tool 消息（前端不展示）和空内容的 assistant 消息（仅 tool_calls 无文本）
            if isinstance(m, ToolMessage):
                continue
            role = "assistant" if (isinstance(m, AIMessage) or hasattr(m, "tool_calls")) else "user"
            content = str(m.content)[:1000] if m.content else ""
            if role == "assistant" and not content.strip():
                continue
            serializable.append({"role": role, "content": content})
        _disk_save(session_id, persona, serializable)
    except Exception:
        pass  # 磁盘写入失败不影响主流程


def agent_chat(message: str, session_id: str = "default", persona: str = ""):
    """一次 Agent 对话回合 — 自定义 ReAct 循环"""
    global _SWEEP_COUNTER
    _SWEEP_COUNTER += 1
    if _SWEEP_COUNTER % 10 == 0:
        _sweep_expired_sessions()
    _touch_session(session_id)

    t0 = time.time()

    # ── 快速路径：简单问候/闲聊绕过 ReAct ──
    if _is_simple_query(message):
        try:
            from services.llm_fallback import chat_with_fallback
            reply_text, _usage, _prov = chat_with_fallback(
                messages=[{"role": "user", "content": message}],
                system_prompt=_get_system_prompt(persona),
                temperature=0.7,
                max_tokens=200,
            )
        except Exception:
            reply_text = "你好！有什么可以帮你的吗？"

        fast_steps = [{"phase": "thought", "content": "Fast-path: simple query detected"}]
        _save_history(session_id, [HumanMessage(content=message),
                                   AIMessage(content=reply_text)], persona)
        public_result = {
            "reply": reply_text,
            "steps": fast_steps,
            "tool_calls": 0,
            "harness": {"passed": True, "issues": [], "warnings": [], "details": []},
            "provider_used": "fast-path",
            "tool_profile": None,
            "plan": [],
        }
        log_agent_call(
            session_id=session_id, message=message, result=public_result,
            duration_ms=(time.time() - t0) * 1000, model="fast-path",
            max_steps_reached=False,
        )
        return public_result

    # ── 单轮模式：深度思考关闭时，所有消息走单次 LLM 调用 ──
    try:
        from services.user_settings import get_setting
        deep_thinking = get_setting("deep_thinking", False)
    except Exception:
        deep_thinking = False
    if not deep_thinking:
        try:
            from services.llm_fallback import chat_with_fallback
            history = _load_history(session_id)
            sp = _get_system_prompt(persona)
            msgs = [{"role": "system", "content": sp}] if sp else []
            if history:
                for hm in history[-8:]:
                    role = "assistant" if isinstance(hm, AIMessage) else "user"
                    msgs.append({"role": role, "content": str(hm.content)})
            msgs.append({"role": "user", "content": message})
            reply_text, _usage, _prov = chat_with_fallback(
                messages=msgs,
                temperature=0.7,
                max_tokens=1200,
            )
        except Exception:
            reply_text = "抱歉，请求失败，请重试。"

        steps = [{"phase": "thought", "content": "Single-pass (deep thinking off)"}]
        _save_history(session_id, [HumanMessage(content=message),
                                   AIMessage(content=reply_text)], persona)
        public_result = {
            "reply": reply_text,
            "steps": steps,
            "tool_calls": 0,
            "harness": {"passed": True, "issues": [], "warnings": [], "details": []},
            "provider_used": "single-pass",
            "tool_profile": None,
            "plan": [],
        }
        log_agent_call(
            session_id=session_id, message=message, result=public_result,
            duration_ms=(time.time() - t0) * 1000, model="single-pass",
            max_steps_reached=False,
        )
        return public_result

    # ── 正常路径：ReAct 循环 ──
    tools = get_tools(message)

    # NEW: persist tool profile to session meta
    if session_id in _SESSION_META:
        _SESSION_META[session_id]["last_tool_profile"] = {
            "groups": list(_get_tool_profile(message)),
            "tool_count": len(tools),
            "tool_names": [t.name for t in tools],
        }

    llm, provider_used = get_llm_with_fallback(temperature=0.3, tools=tools)
    system_prompt = _get_system_prompt(persona)
    history = _load_history(session_id)

    # Plan-first preamble: 为学习意图生成执行计划
    intent = _classify_intent(message)
    plan = []
    if intent == "learning":
        plan = _generate_plan(message, history)

    # NEW: persist plan to session meta
    if session_id in _SESSION_META:
        _SESSION_META[session_id]["active_plan"] = [
            {"step": s["step"], "goal": s["goal"], "tool": s["tool"], "status": "pending"}
            for s in plan
        ]

    try:
        result = _run_react_loop(llm, system_prompt, message, history,
                                 max_steps=_get_max_steps(), provider_used=provider_used,
                                 plan=plan, session_id=session_id)
    except Exception as e:
        error_msg = str(e)
        error_type = fingerprint_error(e, error_msg)
        from services.agent_logger import list_recent_events
        recent = list_recent_events(days=7)
        recurring = any(
            ev.get("error_type") == error_type
            for ev in recent if ev.get("event_type") == "error"
        )
        log_event("error", {
            "error_type": error_type,
            "phase": "agent_chat",
            "error_message": error_msg,
            "recurring": recurring,
        }, session_id)
        result = {
            "reply": f"Agent 执行出错: {str(e)}",
            "steps": [],
            "final_messages": [],
            "max_steps_reached": False,
        }

    _save_history(session_id, result["final_messages"], persona)

    result["reply"] = _auto_inject_sources(result["reply"], result["steps"])

    # Check if KB search returned empty
    had_empty_kb = any(
        s.get("phase") == "observation"
        and s.get("tool") == "search_knowledge"
        and "未找到" in s.get("output", "")
        for s in result["steps"]
    )
    if had_empty_kb and "知识管道" not in result["reply"]:
        result["reply"] = (
            "🔍 知识库中暂未收录相关信息，已将问题加入待学习列表。"
            "你可以去 [知识管道](/knowledge-pipeline) 页面用联网搜索引入新知识！\n\n"
            + result["reply"]
        )

    harness = run_harness(result["reply"], result["steps"],
                          sum(1 for s in result["steps"] if s["phase"] == "action"))

    if not harness["passed"]:
        issues_text = "\n".join(f"  - {i}" for i in harness["issues"])
        result["reply"] = (
            f"⚠️ Harness 校验未通过，以下问题已拦截:\n{issues_text}\n\n"
            f"── 原始回复(仅供参考) ──\n{result['reply']}"
        )
        emit_event("harness_failure", {
            "session_id": session_id,
            "issues": harness["issues"],
            "tool_calls": sum(1 for s in result["steps"] if s["phase"] == "action"),
        })

    # Check for pending course (sent from office) — one-time consumption
    pending_course = None
    if session_id in _SESSION_META:
        pending_course = _SESSION_META[session_id].pop("pending_course", None)

    public_result = {
        "reply": result["reply"],
        "steps": result["steps"],
        "tool_calls": sum(1 for s in result["steps"] if s["phase"] == "action"),
        "harness": harness,
        "provider_used": provider_used,
        "tool_profile": _SESSION_META.get(session_id, {}).get("last_tool_profile"),
        "plan": _SESSION_META.get(session_id, {}).get("active_plan", []),
        "course": pending_course,
    }

    log_agent_call(
        session_id=session_id,
        message=message,
        result=public_result,
        duration_ms=(time.time() - t0) * 1000,
        model=provider_used,
        max_steps_reached=result["max_steps_reached"],
    )

    _maybe_save_bubble(session_id, persona, message, result["reply"])

    return public_result


async def agent_chat_stream(message: str, session_id: str = "default", persona: str = "", force_tools: bool = False):
    """SSE 流式 — 自定义 ReAct 循环 + LLM streaming 桥接 (Phase 3: async)"""
    t0 = time.time()

    # Phase 3: asyncio.Event 取消标志
    cancel_flag: asyncio.Event = _cancel_flags.pop(session_id, asyncio.Event())
    if cancel_flag.is_set():
        yield {"type": "cancelled", "session_id": session_id}
        return
    _cancel_flags[session_id] = cancel_flag

    # ── 快速路径：简单问候/闲聊绕过 ReAct ──
    if _is_simple_query(message):
        system_prompt = _get_system_prompt(persona)
        try:
            from services.llm_fallback import chat_with_fallback
            def _do_fast_chat():
                return chat_with_fallback(
                    messages=[{"role": "user", "content": message}],
                    system_prompt=system_prompt,
                    temperature=0.7,
                    max_tokens=200,
                )
            reply_text, _usage, _prov = await asyncio.to_thread(_do_fast_chat)
        except Exception:
            reply_text = "你好！有什么可以帮你的吗？"

        async def _fast_generate():
            yield {"type": "thought", "content": "Fast-path: simple query detected"}
            for j in range(0, len(reply_text), 4):
                if cancel_flag.is_set():
                    _cancel_flags.pop(session_id, None)
                    yield {"type": "cancelled", "session_id": session_id}
                    return
                yield {"type": "token", "content": reply_text[j:j+4]}
            pending_course = None
            if session_id in _SESSION_META:
                pending_course = _SESSION_META[session_id].pop("pending_course", None)
            yield {
                "type": "final",
                "reply": reply_text,
                "steps": [{"phase": "thought", "content": "Fast-path: simple query detected"}],
                "session_id": session_id,
                "tool_calls": 0,
                "harness": {"passed": True, "issues": [], "warnings": [], "details": []},
                "provider_used": "fast-path",
                "tool_profile": None,
                "plan": [],
                "course": pending_course,
            }
        async for event in _fast_generate():
            yield event
        _cancel_flags.pop(session_id, None)
        return

    # ── 单轮模式：深度思考关闭时，所有消息走单次 LLM 调用 ──
    try:
        from services.user_settings import get_setting
        deep_thinking = get_setting("deep_thinking", False)
    except Exception:
        deep_thinking = False
    if not deep_thinking:
        sp = _get_system_prompt(persona)
        history = _load_history(session_id)
        msgs = [{"role": "system", "content": sp}] if sp else []
        if history:
            for hm in history[-8:]:
                role = "assistant" if isinstance(hm, AIMessage) else "user"
                msgs.append({"role": role, "content": str(hm.content)})
        msgs.append({"role": "user", "content": message})
        try:
            from services.llm_fallback import chat_with_fallback
            def _do_single_chat():
                return chat_with_fallback(
                    messages=msgs,
                    temperature=0.7,
                    max_tokens=1200,
                )
            reply_text, _usage, _prov = await asyncio.to_thread(_do_single_chat)
        except Exception:
            reply_text = "抱歉，请求失败，请重试。"

        async def _single_generate():
            yield {"type": "thought", "content": "Single-pass (deep thinking off)"}
            for j in range(0, len(reply_text), 4):
                if cancel_flag.is_set():
                    _cancel_flags.pop(session_id, None)
                    yield {"type": "cancelled", "session_id": session_id}
                    return
                yield {"type": "token", "content": reply_text[j:j+4]}
            pending_course = None
            if session_id in _SESSION_META:
                pending_course = _SESSION_META[session_id].pop("pending_course", None)
            _save_history(session_id, [HumanMessage(content=message),
                                       AIMessage(content=reply_text)], persona)
            yield {
                "type": "final",
                "reply": reply_text,
                "steps": [{"phase": "thought", "content": "Single-pass (deep thinking off)"}],
                "session_id": session_id,
                "tool_calls": 0,
                "harness": {"passed": True, "issues": [], "warnings": [], "details": []},
                "provider_used": "single-pass",
                "tool_profile": None,
                "plan": [],
                "course": pending_course,
            }
        async for event in _single_generate():
            yield event
        _cancel_flags.pop(session_id, None)
        return

    # ── 正常路径：ReAct 流式循环 ──
    tools = get_tools(message)

    if session_id in _SESSION_META:
        _SESSION_META[session_id]["last_tool_profile"] = {
            "groups": list(_get_tool_profile(message)),
            "tool_count": len(tools),
            "tool_names": [t.name for t in tools],
        }

    llm, provider_used = get_llm_with_fallback(temperature=0.3, tools=tools)
    system_prompt = _get_system_prompt(persona)
    if force_tools:
        system_prompt += (
            "\n\n## 重要指令：本次对话必须使用工具\n"
            "本次对话你必须调用工具获取信息，不要直接凭记忆回答。"
            "先使用合适的工具（search_knowledge、web_search 等），再基于工具返回的结果组织回答。"
        )
    history = _load_history(session_id)

    intent = _classify_intent(message)
    plan = []
    if intent == "learning":
        plan = _generate_plan(message, history)

    if session_id in _SESSION_META:
        _SESSION_META[session_id]["active_plan"] = [
            {"step": s["step"], "goal": s["goal"], "tool": s["tool"], "status": "pending"}
            for s in plan
        ]

    if plan:
        plan_text = _format_plan_for_prompt(plan)
        if plan_text:
            system_prompt += "\n\n" + plan_text

    messages = [SystemMessage(content=system_prompt)]
    if history:
        messages.extend(history)
    messages.append(HumanMessage(content=message))

    steps = []
    reply = ""
    plan_step_idx = 0

    q: asyncio.Queue = asyncio.Queue()
    _agent_queues[session_id] = q

    async def _run():
        nonlocal reply, messages, plan_step_idx
        try:
            for i in range(_get_max_steps()):
                if cancel_flag.is_set():
                    await q.put({"type": "cancelled", "session_id": session_id})
                    return
                response = await llm.ainvoke(messages)

                try:
                    from services.agent_logger import log_token_usage
                    meta = getattr(response, "response_metadata", None) or {}
                    tu = meta.get("token_usage") or meta.get("usage", {})
                    if tu:
                        import config as _cfg2
                        log_token_usage(
                            model=getattr(_cfg2, "MODEL", ""),
                            provider=provider_used or getattr(_cfg2, "LLM_PROVIDER", ""),
                            prompt_tokens=tu.get("prompt_tokens", 0),
                            completion_tokens=tu.get("completion_tokens", 0),
                        )
                except Exception:
                    pass

                has_tool_calls = (hasattr(response, "tool_calls")
                                  and response.tool_calls
                                  and len(response.tool_calls) > 0)

                if has_tool_calls:
                    if response.content and str(response.content).strip():
                        thought = str(response.content)[:500]
                        steps.append({"phase": "thought", "content": thought})
                        await q.put({"type": "thought", "content": thought})

                    messages.append(response)

                    for tc in response.tool_calls:
                        if cancel_flag.is_set():
                            await q.put({"type": "cancelled", "session_id": session_id})
                            return
                        tc_name = tc.get("name", "unknown")
                        tc_args = tc.get("args", {})
                        tc_id = tc.get("id", "")
                        steps.append({"phase": "action", "tool": tc_name, "input": tc_args})
                        await q.put({"type": "action", "tool": tc_name, "input": tc_args})

                        if tc_name == "web_search":
                            cnt = _WEB_SEARCH_COUNTS.get(session_id, 0)
                            if cnt >= 3:
                                observation = "本对话已进行 3 次联网搜索，已达上限。请基于已有信息回答。"
                                steps.append({"phase": "observation", "tool": tc_name, "output": observation})
                                await q.put({"type": "observation", "tool": tc_name, "output": observation})
                                messages.append(ToolMessage(content=observation, tool_call_id=tc_id, name=tc_name))
                                continue
                            _WEB_SEARCH_COUNTS[session_id] = cnt + 1

                        result = await asyncio.to_thread(_execute_tool, tc_name, tc_args)
                        if plan and plan_step_idx < len(plan):
                            plan_step_idx += 1
                            if session_id in _SESSION_META:
                                meta_plan = _SESSION_META[session_id].get("active_plan", [])
                                if plan_step_idx - 1 < len(meta_plan):
                                    meta_plan[plan_step_idx - 1]["status"] = "done"
                                if plan_step_idx < len(meta_plan):
                                    meta_plan[plan_step_idx]["status"] = "doing"
                            progress = _plan_progress_reminder(plan, plan_step_idx)
                            if progress:
                                result += progress
                        steps.append({"phase": "observation", "tool": tc_name, "output": result[:800]})
                        await q.put({"type": "observation", "tool": tc_name, "output": result[:800]})
                        messages.append(ToolMessage(content=result, tool_call_id=tc_id, name=tc_name))

                    if len(messages) > COMPRESS_THRESHOLD:
                        messages = _compress_messages(messages)
                else:
                    reply = response.content or ""
                    messages.append(response)
                    for j in range(0, len(reply), 5):
                        await q.put({"type": "token", "content": reply[j:j+5]})
                    break

            if not reply and steps:
                reply = f"已达到最大步数限制（{_get_max_steps()}步），请重新描述你的问题。"
        except Exception as e:
            error_msg = str(e)
            error_type = fingerprint_error(e, error_msg)
            from services.agent_logger import list_recent_events
            recent = list_recent_events(days=7)
            recurring = any(
                ev.get("error_type") == error_type
                for ev in recent if ev.get("event_type") == "error"
            )
            log_event("error", {
                "error_type": error_type,
                "phase": "agent_chat",
                "error_message": error_msg,
                "recurring": recurring,
            }, session_id)
            await q.put({"type": "error", "content": str(e)})
        pending_course = None
        if session_id in _SESSION_META:
            pending_course = _SESSION_META[session_id].pop("pending_course", None)

        await q.put({"type": "final", "reply": reply, "steps": steps, "session_id": session_id,
               "tool_calls": sum(1 for s in steps if s["phase"] == "action"),
               "provider_used": provider_used,
               "tool_profile": _SESSION_META.get(session_id, {}).get("last_tool_profile"),
               "plan": _SESSION_META.get(session_id, {}).get("active_plan", []),
               "course": pending_course})

    _agent_tasks[session_id] = asyncio.create_task(_run())

    while True:
        try:
            event = await asyncio.wait_for(q.get(), timeout=3.0)
        except asyncio.TimeoutError:
            yield {"type": "heartbeat"}
            continue
        if event.get("type") == "final" or event.get("type") == "error" or event.get("type") == "cancelled":
            _agent_queues.pop(session_id, None)
            _agent_tasks.pop(session_id, None)
            _cancel_flags.pop(session_id, None)
            if event.get("type") != "cancelled":
                _save_history(session_id, messages, persona)
            if event.get("type") == "final":
                event["reply"] = _auto_inject_sources(event.get("reply", ""), event.get("steps", []))

                had_empty_kb = any(
                    s.get("phase") == "observation"
                    and s.get("tool") == "search_knowledge"
                    and "未找到" in s.get("output", "")
                    for s in event.get("steps", [])
                )
                if had_empty_kb and "知识管道" not in event.get("reply", ""):
                    event["reply"] = (
                        "🔍 知识库中暂未收录相关信息，已将问题加入待学习列表。"
                        "你可以去 [知识管道](/knowledge-pipeline) 页面用联网搜索引入新知识！\n\n"
                        + event.get("reply", "")
                    )

                harness = run_harness(event.get("reply", ""), event.get("steps", []),
                                      event.get("tool_calls", 0))
                event["harness"] = harness
                if not harness["passed"]:
                    issues_text = "\n".join(f"  - {i}" for i in harness["issues"])
                    event["reply"] = (
                        f"⚠️ Harness 校验未通过，以下问题已拦截:\n{issues_text}\n\n"
                        f"── 原始回复(仅供参考) ──\n{event.get('reply', '')}"
                    )
                    emit_event("harness_failure", {
                        "session_id": session_id,
                        "issues": harness["issues"],
                        "tool_calls": event.get("tool_calls", 0),
                    })

                log_agent_call(
                    session_id=session_id,
                    message=message,
                    result={"reply": event.get("reply", ""),
                            "steps": event.get("steps", []),
                            "tool_calls": event.get("tool_calls", 0)},
                    duration_ms=(time.time() - t0) * 1000,
                    model=provider_used,
                )

                _maybe_save_bubble(session_id, persona, message, event.get("reply", ""))
            yield event
            break
        yield event

"""
llm_judge — LLM Judge: 独立交叉验证 CODE 评分

Phase 4 Step 3. 核心职责:
  - 异步任务队列 (deque, max 50, 独立消费者线程)
  - judge_data_completeness(): 调用 LLM 交叉验证数据完整度
  - _validate_llm_output(): 安全校验层 (SA 约束 3)

工程约束:
  - LLM 调用不在同步路径中执行
  - 30s 硬超时，失败重试最多 3 次 (间隔 60s)
  - 6h 防风暴 (手动触发无限制)
  - 视觉词汇冻结: Judge 结果使用现有颜色/图标系统
"""
import json
import time
import logging
import threading
import collections
from datetime import datetime, timedelta
from pathlib import Path

from services.eval import eval_store
from services.eval.trace_logger import _generate_id

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent.parent / "data" / "eval"

# ── 异步任务队列 ──
_crossval_queue = collections.deque(maxlen=50)
_queue_lock = threading.Lock()
_worker_thread = None
_worker_running = False
_last_judge_run_at = 0.0  # 防风暴时间戳


def _log_security_event(event_type, detail):
    """记录安全事件到审计日志。"""
    try:
        audit_file = DATA_DIR / "audit.jsonl"
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "detail": str(detail)[:500],
        }
        with open(audit_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ══════════════════════════════════════════════
# LLM 输出校验 (SA 约束 3)
# ══════════════════════════════════════════════

def _validate_llm_output(output):
    """
    LLM Judge 输出安全校验。不通过 → 拒绝写入 + 记录安全事件。

    检查:
      1. value 在 [0.0, 1.0]
      2. 文本字段 ≤ 1000 字符
      3. 无 <script>/<iframe>/javascript: 注入
    """
    if not isinstance(output, dict):
        _log_security_event("llm_output_not_dict", str(output)[:200])
        return False

    # 值域检查
    value = output.get("value")
    if value is not None and not (0.0 <= float(value) <= 1.0):
        _log_security_event("llm_value_out_of_range", {"value": value})
        return False

    # 文本长度 + XSS 检查
    for field in ("judgment", "reasoning", "note"):
        text = str(output.get(field, ""))
        if len(text) > 1000:
            _log_security_event("llm_text_too_long", {"field": field, "length": len(text)})
            return False
        lower = text.lower()
        if any(tag in lower for tag in ("<script", "<iframe", "javascript:")):
            _log_security_event("llm_xss_attempt", {"field": field})
            return False

    return True


# ══════════════════════════════════════════════
# LLM Judge Prompt
# ══════════════════════════════════════════════

def _build_judge_prompt(item):
    """构造 LLM Judge prompt。"""
    return (
        "你是评估系统的独立审查者。你的任务是交叉验证代码评分系统"
        "对一条 Trace 的「数据完整度」判定是否正确。\n\n"
        f"**Trace 信息:**\n"
        f"- 名称: {item.get('trace_name', '?')}\n"
        f"- 类型: {item.get('trace_type', '?')}\n"
        f"- 实际记录的 Span 种类: {', '.join(item.get('span_kinds_present', [])) or '(none)'}\n"
        f"- 该类型 Trace 必需的 Span 种类: {', '.join(item.get('span_kinds_required', []))}\n\n"
        f"**CODE 评分系统的判定:** {item.get('code_judgment', '?')}\n\n"
        "**你的任务:**\n"
        "根据 Span 覆盖情况，独立判断这条 Trace 是否数据完整。\n"
        '回答格式: {"judgment": "complete|incomplete", "reasoning": "...", "confidence": 0.0-1.0}\n'
        "只输出 JSON，不要有其他文字。"
    )


# ══════════════════════════════════════════════
# LLM Judge 核心
# ══════════════════════════════════════════════

def judge_data_completeness(item, timeout=30):
    """
    调用 DeepSeek LLM 对单条 Trace 进行数据完整度交叉验证。

    参数:
      item: CROSSVAL_PENDING 条目 (含 trace_id, span_kinds_present, span_kinds_required, code_judgment, llm_prompt)
      timeout: LLM 调用超时秒数

    返回:
      {"judgment": "complete"|"incomplete", "reasoning": "...", "confidence": 0.0-1.0, "value": float}
      或 {"error": "..."}
    """
    try:
        from services.deepseek_client import chat

        prompt = _build_judge_prompt(item)
        messages = [{"role": "user", "content": prompt}]
        system = "You are an independent evaluator. Respond ONLY with valid JSON. No markdown, no explanation outside the JSON."

        response, _usage = chat(
            messages=messages,
            system_prompt=system,
            temperature=0.3,
            max_tokens=300,
            timeout=timeout,
        )

        raw = (response or "").strip()
        # 清理 markdown code fences
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1] if "\n" in raw else raw[3:]
            if raw.endswith("```"):
                raw = raw[:-3]
            raw = raw.strip()

        try:
            result = json.loads(raw)
        except json.JSONDecodeError:
            # 尝试提取 JSON 片段
            import re
            m = re.search(r'\{[^}]+\}', raw)
            if m:
                result = json.loads(m.group())
            else:
                return {"error": "LLM response not valid JSON", "raw": raw[:200]}

        # 安全校验
        if not _validate_llm_output(result):
            return {"error": "LLM output failed security validation"}

        # 计算评分值: complete + confidence → [0.6, 1.0]; incomplete → [0.0, 0.4]
        judgment = result.get("judgment", "unknown")
        confidence = float(result.get("confidence", 0.5))
        if judgment == "complete":
            result["value"] = round(0.6 + 0.4 * confidence, 4)
        elif judgment == "incomplete":
            result["value"] = round(0.4 * (1 - confidence), 4)
        else:
            result["value"] = -1.0

        return result

    except Exception as e:
        logger.error("llm_judge: judge_data_completeness failed: %s", e, exc_info=True)
        return {"error": str(e)}


# ══════════════════════════════════════════════
# 任务队列管理
# ══════════════════════════════════════════════

def enqueue_crossval(items):
    """将 CROSSVAL_PENDING 条目加入消费者队列。返回入队数量。"""
    count = 0
    with _queue_lock:
        for item in items:
            if len(_crossval_queue) >= 50:
                logger.warning("llm_judge: queue full, dropping oldest item")
                _crossval_queue.popleft()
            _crossval_queue.append(item)
            count += 1
    return count


def queue_depth():
    """当前队列深度。"""
    return len(_crossval_queue)


def _crossval_consumer():
    """
    后台消费者线程: 从队列取任务 → LLM Judge → 保存评分。
    失败重试最多 3 次 (60s 间隔)。
    """
    global _worker_running
    _worker_running = True

    while _worker_running:
        item = None
        with _queue_lock:
            if _crossval_queue:
                item = _crossval_queue.popleft()

        if item is None:
            time.sleep(5)
            continue

        attempt = 0
        max_attempts = 3
        success = False

        while attempt < max_attempts and not success:
            attempt += 1
            result = judge_data_completeness(item, timeout=30)

            if "error" not in result:
                # 保存判定结果
                score = {
                    "score_id": _generate_id(),
                    "config_id": "data_completeness_crossval",
                    "target_type": "system",
                    "target_id": "eval_system",
                    "value": result.get("value", -1.0),
                    "details": {
                        "trace_id": item.get("trace_id"),
                        "code_judgment": item.get("code_judgment"),
                        "llm_judgment": result.get("judgment"),
                        "llm_reasoning": result.get("reasoning", ""),
                        "llm_confidence": result.get("confidence"),
                        "crossval_id": item.get("crossval_id"),
                    },
                    "created_at": datetime.now().isoformat(),
                    "source": "LLM_JUDGE",
                }
                eval_store.save_score(score)
                success = True
            else:
                logger.warning(
                    "llm_judge: attempt %d/%d failed for %s: %s",
                    attempt, max_attempts, item.get("trace_id", "?"), result.get("error", "?")[:100],
                )
                if attempt < max_attempts:
                    time.sleep(60)

        if not success:
            _log_security_event("llm_judge_exhausted_retries", {
                "trace_id": item.get("trace_id"),
                "attempts": max_attempts,
            })

    _worker_running = False


def start_worker():
    """启动消费者线程（daemon，server.py 启动时调用）。幂等。"""
    global _worker_thread, _worker_running
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_running = True
    _worker_thread = threading.Thread(target=_crossval_consumer, daemon=True, name="crossval-worker")
    _worker_thread.start()
    logger.info("llm_judge: crossval worker started")


def stop_worker():
    """停止消费者线程。"""
    global _worker_running
    _worker_running = False


def worker_alive():
    """检查消费者线程是否存活。"""
    return _worker_thread is not None and _worker_thread.is_alive()


def get_last_judge_run():
    """上次 LLM Judge 运行时间戳（用于防风暴检查）。"""
    return _last_judge_run_at


# ══════════════════════════════════════════════
# 防风暴 + 批量入队
# ══════════════════════════════════════════════

def run_crossval_batch(force=False):
    """
    从最近的 CROSSVAL_PENDING 评分中提取待验证条目，入队消费。

    force=True: 手动触发，无视防风暴
    force=False: 6h 防风暴保护
    """
    global _last_judge_run_at

    if not force:
        now = time.time()
        if now - _last_judge_run_at < 21600:  # 6h
            return {"status": "skipped", "reason": "anti-storm: < 6h since last run"}

    _last_judge_run_at = time.time()

    # 查找 CROSSVAL_PENDING 评分
    scores = eval_store.query_scores(
        config_id="data_completeness_crossval",
        limit=20,
        exclude_empty_traces=False,
        exclude_orphan_spans=False,
    )
    pending = [s for s in scores if s.get("source") == "CROSSVAL_PENDING"]
    if not pending:
        return {"status": "skipped", "reason": "no CROSSVAL_PENDING items"}

    # 提取采样条目
    items = []
    for score in pending[:1]:  # 只取最近一批（每次 cross-validate 产生 1 条含 3-5 子条目）
        for item in score.get("details", {}).get("items", []):
            items.append(item)

    if not items:
        return {"status": "skipped", "reason": "no items in pending scores"}

    count = enqueue_crossval(items)
    start_worker()

    return {
        "status": "processing",
        "enqueued": count,
        "queue_depth": queue_depth(),
        "note": "LLM Judge processing in background — check scores for LLM_JUDGE source",
    }

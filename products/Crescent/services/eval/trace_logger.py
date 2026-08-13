"""
trace_logger — 强制性核心埋点 (链1)

三条 core path 共用此模块:
  1. deepseek_client.chat()    → _safe_record_llm_span()
  2. main.py FastAPI 中间件       → start_trace() / end_trace()
  3. agent_service 工具调度      → _safe_record_tool_span()

设计保证:
  - 防崩盖: 所有 _record_* 函数吞异常, 绝不阻断业务
  - 影子模式: EVAL_SHADOW_MODE=true 时运行但不写文件
  - 全局开关: EVAL_ENABLED=false 时完全跳过
  - 孤儿检测: trace_id=None 时 Span 标记 orphan=True
"""
import os
import time
import uuid
import json
import logging
import threading
import contextvars
import shutil
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

# ── ContextVar: FastAPI 中间件设置，跨异步边界传播 ──
_trace_id_ctx = contextvars.ContextVar('eval_trace_id', default=None)

# ── 线程局部存储 (非 HTTP 上下文中传播 trace_id，如后台任务) ──
_thread_local = threading.local()

# ── 数据目录 ──
DATA_DIR = Path(__file__).parent.parent.parent / "data" / "eval"
DATA_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_DIR = DATA_DIR / "snapshots"
SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
SNAPSHOT_MAX_VERSIONS = 10

# ── 全局开关 ──

def _is_tracing_enabled():
    try:
        import config
        return getattr(config, "EVAL_ENABLED", False)
    except Exception:
        return False


def _is_shadow_mode():
    try:
        import config
        # Runtime override file takes priority (set by /api/eval/shadow/toggle)
        from pathlib import Path as _Path
        override = _Path(__file__).parent.parent.parent / "data" / "eval" / "shadow_override.txt"
        if override.exists():
            try:
                val = override.read_text().strip()
                if val in ("true", "false"):
                    return val == "true"
            except Exception:
                pass
        return getattr(config, "EVAL_SHADOW_MODE", True)
    except Exception:
        return True


# ══════════════════════════════════════════════
# TraceContext — 后台任务入口
# ══════════════════════════════════════════════

class TraceContext:
    """
    上下文管理器：为后台任务创建 Trace，注入线程局部存储。

    用法:
        with TraceContext(name="scheduled_review", kind="system_task") as ctx:
            review_agent.run_review()
    """
    def __init__(self, name, kind="system_task", metadata=None):
        self.name = name
        self.kind = kind
        self.metadata = metadata or {}
        self.trace_id = None

    def __enter__(self):
        self.trace_id = start_trace(
            name=self.name,
            kind=self.kind,
            metadata=self.metadata,
        )
        _thread_local.trace_id = self.trace_id
        _thread_local.trace_start = time.time()
        _thread_local.span_count = 0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        duration_ms = int((time.time() - getattr(_thread_local, 'trace_start', time.time())) * 1000)
        span_count = getattr(_thread_local, 'span_count', 0)
        end_trace(
            trace_id=self.trace_id,
            duration_ms=duration_ms,
            span_count=span_count,
            error=(exc_type is not None),
        )
        _thread_local.trace_id = None
        _thread_local.trace_start = None
        _thread_local.span_count = 0
        return False


# ══════════════════════════════════════════════
# Trace ID 获取 (三级回退)
# ══════════════════════════════════════════════

def _current_trace_id():
    """
    获取当前 Trace ID。优先级：
    1. ContextVar（FastAPI 中间件设置，跨 async 边界传播）
    2. 线程局部变量（后台任务 TraceContext）
    3. None（无上下文 → Span 成为孤儿）
    """
    ctx_id = _trace_id_ctx.get()
    if ctx_id is not None:
        return ctx_id

    return getattr(_thread_local, 'trace_id', None)


def _increment_span_count():
    # FastAPI: ContextVar
    if _trace_id_ctx.get() is not None:
        _thread_local.span_count = getattr(_thread_local, 'span_count', 0) + 1
        return
    if hasattr(_thread_local, 'trace_id') and _thread_local.trace_id is not None:
        _thread_local.span_count = getattr(_thread_local, 'span_count', 0) + 1


# ══════════════════════════════════════════════
# Trace 生命周期
# ══════════════════════════════════════════════

def _generate_id():
    return uuid.uuid4().hex[:12]


def start_trace(name, kind="http_request", metadata=None):
    """创建新 Trace，返回 trace_id。由 Flask 钩子或 TraceContext 调用。"""
    if not _is_tracing_enabled():
        return None
    trace_id = _generate_id()
    trace = {
        "trace_id": trace_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "name": name,
        "kind": kind,
        "status": "running",
        "metadata": metadata or {},
        "span_count": 0,
    }
    if _is_shadow_mode():
        return trace_id
    try:
        _append_jsonl("traces.jsonl", trace)
    except Exception:
        logger.error("eval: start_trace write failed", exc_info=True)
    return trace_id


def end_trace(trace_id, duration_ms=0, span_count=0, status_code=None, error=False):
    """关闭 Trace。由 Flask after_request 或 TraceContext.__exit__ 调用。"""
    if not _is_tracing_enabled() or not trace_id:
        return
    end_entry = {
        "trace_id": trace_id,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "event": "trace_end",
        "duration_ms": duration_ms,
        "span_count": span_count,
        "status_code": status_code,
        "error": error,
    }
    if _is_shadow_mode():
        return
    try:
        _append_jsonl("traces.jsonl", end_entry)
    except Exception:
        logger.error("eval: end_trace write failed", exc_info=True)


# ══════════════════════════════════════════════
# Span 记录 (带防崩盖)
# ══════════════════════════════════════════════

def _record_span(kind, name, duration_ms, input_summary="", output_summary="",
                 model=None, token_usage=None, status="success", error_type=None,
                 metadata=None):
    """内部: 写入一条 Span 到 traces.jsonl"""
    if not _is_tracing_enabled():
        return
    _increment_span_count()
    if _is_shadow_mode():
        return
    trace_id = _current_trace_id()
    span = {
        "span_id": _generate_id(),
        "trace_id": trace_id,
        "orphan": (trace_id is None),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "kind": kind,
        "name": name,
        "duration_ms": duration_ms,
        "input_summary": input_summary[:200] if input_summary else "",
        "output_summary": output_summary[:200] if output_summary else "",
        "model": model,
        "token_usage": token_usage,
        "status": status,
        "error_type": error_type,
        "metadata": metadata or {},
    }
    try:
        _append_jsonl("traces.jsonl", span)
    except Exception:
        logger.error("eval: span write failed", exc_info=True)


def _safe_record_llm_span(trace_id=None, kind="LLM", name="deepseek_chat",
                           duration_ms=0, input_summary="", output_summary="",
                           model=None, token_usage=None, status="success",
                           error_type=None):
    """★ 防崩盖: LLM Span 记录。任何异常吞掉，绝不向上传播。"""
    try:
        _record_span(
            kind=kind, name=name, duration_ms=duration_ms,
            input_summary=input_summary, output_summary=output_summary,
            model=model, token_usage=token_usage, status=status,
            error_type=error_type,
        )
    except Exception:
        logger.error("eval: _safe_record_llm_span failed", exc_info=True)


def _safe_record_tool_span(trace_id=None, tool_name="unknown",
                            duration_ms=0, input_params="", output_summary="",
                            status="success", error_type=None):
    """★ 防崩盖: Tool Span 记录。任何异常吞掉，绝不向上传播。"""
    try:
        _record_span(
            kind="TOOL", name=tool_name, duration_ms=duration_ms,
            input_summary=input_params[:200] if input_params else "",
            output_summary=output_summary[:200] if output_summary else "",
            status=status, error_type=error_type,
        )
    except Exception:
        logger.error("eval: _safe_record_tool_span failed", exc_info=True)


# ══════════════════════════════════════════════
# 底层文件操作
# ══════════════════════════════════════════════

def _snapshot_before_write(filename):
    """在覆写/追加前将当前文件复制到 snapshots/，保留最近10个版本"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return
    ts = datetime.now().strftime("%Y%m%dT%H%M%S")
    snapshot_name = f"{filepath.stem}.{ts}{filepath.suffix}"
    snapshot_path = SNAPSHOT_DIR / snapshot_name
    shutil.copy2(filepath, snapshot_path)

    stem = filepath.stem
    suffix = filepath.suffix
    existing = sorted(
        [p for p in SNAPSHOT_DIR.iterdir() if p.name.startswith(stem + ".") and p.suffix == suffix],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    for old in existing[SNAPSHOT_MAX_VERSIONS:]:
        old.unlink()


def _append_jsonl(filename, data):
    """追加一行 JSON 到文件。先快照，再追加。"""
    _snapshot_before_write(filename)
    filepath = DATA_DIR / filename
    try:
        line = json.dumps(data, ensure_ascii=False, default=str) + "\n"
        with open(filepath, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        raise


def _read_jsonl(filename):
    """读取 JSONL 文件，返回 list[dict]"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return []
    results = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    results.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return results


def _read_json(filename):
    """读取 JSON 文件"""
    filepath = DATA_DIR / filename
    if not filepath.exists():
        return {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(filename, data):
    """原子写入 JSON 文件。先快照，再写入。"""
    _snapshot_before_write(filename)
    filepath = DATA_DIR / filename
    tmp = DATA_DIR / f".{filename}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=str)
    os.replace(tmp, filepath)


# ══════════════════════════════════════════════
# 通用事件发射器 (M1: 双轨并行 — 新增来源用 emit_event, 核心路径保持硬编码)
# ══════════════════════════════════════════════

from datetime import datetime as _dt

_event_types_registry = {}  # event_type -> {"description": str, "water_type": "retrospective"|"prospective"}


def register_event_type(event_type, description, water_type="retrospective"):
    """注册一个事件类型。已注册类型才能被 emit_event 接受。"""
    _event_types_registry[event_type] = {
        "description": description,
        "water_type": water_type,
    }


def emit_event(event_type, payload, timeout=5):
    """
    通用事件发射器 — 不依赖 Flask request context。

    安全约束:
      - event_type 必须在 _event_types_registry 中注册，否则拒绝写入 + 触发安全告警
      - payload 值序列化为 JSON，写入 events.jsonl
      - 内部委托现有 _record_span() 确保事件进入同一存储体系

    返回: True(成功) / False(被拒绝)
    """
    if event_type not in _event_types_registry:
        _log_security_event("emit_event_rejected_unregistered", {
            "event_type": event_type,
        })
        return False

    try:
        data_dir = DATA_DIR
        data_dir.mkdir(parents=True, exist_ok=True)
        events_file = data_dir / "events.jsonl"

        entry = {
            "event_id": _generate_id(),
            "event_type": event_type,
            "timestamp": _dt.now().isoformat(),
            "water_type": _event_types_registry[event_type]["water_type"],
            "payload": payload,
        }
        _append_jsonl("events.jsonl", entry)
        return True
    except Exception:
        return False


def _log_security_event(event_type, payload):
    """记录安全事件到 security_events.jsonl（不依赖 emit_event 避免循环）"""
    try:
        security_file = DATA_DIR / "security_events.jsonl"
        entry = {
            "event_id": _generate_id(),
            "event_type": event_type,
            "timestamp": _dt.now().isoformat(),
            "payload": payload,
        }
        with open(security_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False, default=str) + "\n")
    except Exception:
        pass


# 预注册已知事件类型
register_event_type("review_agent.finding", "Review Agent 审查发现", "retrospective")
register_event_type("knowledge.health_check", "知识管线健康检查", "retrospective")
register_event_type("eval.error_pattern_match", "历史错误模式匹配", "retrospective")
register_event_type("git.commit", "Git 提交事件", "retrospective")
register_event_type("test.run", "测试运行结果", "retrospective")
register_event_type("feedback.received", "用户反馈接收", "retrospective")
register_event_type("ui.interaction", "前端行为追踪", "retrospective")
register_event_type("eval.decision_surface_load_failed", "决策面加载失败", "retrospective")
register_event_type("harness_failure", "Harness 校验拦截", "retrospective")
register_event_type("rag.empty", "RAG 检索无结果 — 领域空白", "retrospective")
register_event_type("rag.coverage_gap", "RAG 检索覆盖不足 — 有相关知识但深度/精度不够", "retrospective")
register_event_type("rag.intent_mismatch", "RAG 查询意图匹配失败 — 语义相近但内容不答问", "retrospective")

"""LLM 双路径自动 Fallback — local ↔ deepseek 互备 + Mock 种子数据兜底"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import config

OLLAMA_URL = "http://localhost:11434"


# ── Tier 3 Mock 种子数据 ──

_MOCK_RESPONSES = {
    "greeting": "你好！我是 Crescent 学习助手。当前 AI 模型服务暂时不可用，但我可以帮你查看已入库的知识库内容。",
    "learning": "抱歉，DeepSeek API 和本地 Ollama 服务当前均不可用，我无法进行深度推理。请检查网络连接或启动 Ollama 后重试。在此期间，你可以在知识管道页面搜索和浏览已有资料。",
    "fallback": "我暂时无法处理这个问题。所有 LLM 后端（DeepSeek API、Ollama 本地模型）均不可达。请确保至少一个后端可用后重试。",
}

_MOCK_USAGE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}


def _mock_chat_response(message: str) -> tuple[str, dict, str]:
    """Tier 3: Mock 种子数据兜底 — 当所有 LLM 后端不可用时返回引导性回复。"""
    msg_lower = message.strip().lower()
    simple_greetings = ("你好", "hi", "hello", "嗨", "hey", "在吗")
    if any(msg_lower.startswith(g) for g in simple_greetings) or len(message.strip()) < 6:
        reply = _MOCK_RESPONSES["greeting"]
    elif any(kw in msg_lower for kw in ("?", "？", "什么", "怎么", "如何", "为什么")):
        reply = _MOCK_RESPONSES["learning"]
    else:
        reply = _MOCK_RESPONSES["fallback"]
    return reply, _MOCK_USAGE, "mock(fallback)"


# ── Tier 1 + Tier 2 ──


def _check_local_available(timeout: float = 3.0) -> bool:
    """快速检测 Ollama 是否在线且有模型（短超时，不阻塞）"""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=timeout)
        if r.status_code != 200:
            return False
        models = r.json().get("models", [])
        return len(models) > 0
    except Exception:
        return False


def _check_deepseek_available() -> bool:
    """检测 DeepSeek API Key 是否已配置"""
    return bool(config.API_KEY)


def get_llm_with_fallback(temperature: float = 0.3, streaming: bool = False, tools: list = None):
    """Path A: 获取 LangChain LLM 实例，带自动 fallback。

    Returns:
        (llm_instance, provider_used: str)
        provider_used 取值: "local", "deepseek", "local(fallback)", "deepseek(fallback)"
    """
    from services.llm_service import get_llm

    primary = config.LLM_PROVIDER
    fallback_provider = "deepseek" if primary == "local" else "local"

    # 尝试主 provider
    try:
        llm = get_llm(temperature=temperature, streaming=streaming, tools=tools)
        return llm, primary
    except Exception as e:
        primary_error = str(e)[:200]

    # 尝试 fallback
    if fallback_provider == "local" and _check_local_available():
        pass  # local is available
    elif fallback_provider == "deepseek" and _check_deepseek_available():
        pass  # deepseek is available
    else:
        # Tier 3: Mock 种子数据兜底 — 返回模拟 LLM 实例
        from langchain_core.language_models.llms import LLM
        class _MockLLM(LLM):
            @property
            def _llm_type(self): return "mock"
            def _call(self, prompt, stop=None, run_manager=None, **kwargs):
                return _MOCK_RESPONSES["fallback"]
        print(f"[fallback] All providers down ({primary} + {fallback_provider}) — using Mock seed data")
        return _MockLLM(), "mock(fallback)"

    original_provider = config.LLM_PROVIDER
    try:
        config.LLM_PROVIDER = fallback_provider
        llm = get_llm(temperature=temperature, streaming=streaming, tools=tools)
        provider_label = f"{fallback_provider}(fallback)"
        print(f"[fallback] Switched from {primary} to {fallback_provider} because: {primary_error}")
        return llm, provider_label
    except Exception as e:
        raise RuntimeError(
            f"No LLM provider available: {primary} unavailable ({primary_error}), "
            f"{fallback_provider} also failed: {str(e)[:200]}"
        )
    finally:
        config.LLM_PROVIDER = original_provider


def chat_with_fallback(
    messages: list,
    system_prompt: str = "",
    temperature: float = 0.7,
    max_tokens: int = 800,
    timeout: int = 30,
):
    """Path B: 调用 chat()，带自动 fallback。

    Returns:
        (reply_text: str, usage_dict: dict, provider_used: str)
    """
    from services.deepseek_client import chat as _chat

    primary = config.LLM_PROVIDER
    fallback_provider = "deepseek" if primary == "local" else "local"

    try:
        reply, usage = _chat(messages, system_prompt, temperature, max_tokens, timeout)
        return reply, usage, primary
    except Exception as e:
        primary_error = str(e)[:200]

    if fallback_provider == "local" and _check_local_available():
        pass
    elif fallback_provider == "deepseek" and _check_deepseek_available():
        pass
    else:
        # Tier 3: Mock 种子数据兜底
        print(f"[fallback] Chat all providers down ({primary} + {fallback_provider}) — using Mock seed data")
        last_msg = messages[-1]["content"] if isinstance(messages[-1], dict) else str(messages[-1])
        return _mock_chat_response(last_msg)

    original_provider = config.LLM_PROVIDER
    try:
        config.LLM_PROVIDER = fallback_provider
        reply, usage = _chat(messages, system_prompt, temperature, max_tokens, timeout)
        provider_label = f"{fallback_provider}(fallback)"
        print(f"[fallback] Chat switched from {primary} to {fallback_provider} because: {primary_error}")
        return reply, usage, provider_label
    except Exception as e:
        # Tier 3: Mock 种子数据兜底 — fallback 也失败时
        print(f"[fallback] Both providers failed: {primary_error} | {str(e)[:200]} — using Mock seed data")
        last_msg = messages[-1]["content"] if isinstance(messages[-1], dict) else str(messages[-1])
        return _mock_chat_response(last_msg)
    finally:
        config.LLM_PROVIDER = original_provider

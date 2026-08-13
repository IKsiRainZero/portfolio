"""
DeepSeek API 客户端 — 通用封装
"""
import time as _time
import requests as http_requests
import config
from services.eval.trace_logger import _safe_record_llm_span


def _log_chat_usage(provider, prompt_tokens, completion_tokens):
    try:
        from services.agent_logger import log_token_usage
        log_token_usage(
            model=config.MODEL,
            provider=provider,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
    except Exception:
        pass


def chat(messages, system_prompt="", temperature=0.7, max_tokens=800, timeout=30):
    """发送聊天请求，返回 (reply_text, usage_dict)
    根据 config.LLM_PROVIDER 自动选择 DeepSeek API 或本地 Ollama。"""
    t0 = _time.time()
    if config.LLM_PROVIDER == "local":
        from services.local_llm import chat as _local_chat
        reply, usage = _local_chat(messages, system_prompt, temperature, max_tokens, timeout)
        _log_chat_usage("local", usage.get("prompt_tokens", 0), usage.get("completion_tokens", 0))
        _safe_record_llm_span(
            duration_ms=int((_time.time() - t0) * 1000),
            input_summary=str(messages)[:200], output_summary=reply[:200],
            model=config.MODEL, token_usage=usage, status="success",
        )
        return reply, usage

    if not config.API_KEY:
        raise ValueError("API Key 未配置")

    full_messages = []
    if system_prompt:
        full_messages.append({"role": "system", "content": system_prompt})
    full_messages.extend(messages)

    resp = http_requests.post(
        f"{config.BASE_URL}/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {config.API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": config.MODEL,
            "messages": full_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=timeout,
    )

    if resp.status_code != 200:
        # CWE-209: 不将上游 API 原始错误暴露给调用方
        _safe_record_llm_span(
            duration_ms=int((_time.time() - t0) * 1000),
            input_summary=str(messages)[:200], output_summary="",
            model=config.MODEL, status="error", error_type="APIError",
        )
        import sys
        print(f"[ERROR] deepseek API returned {resp.status_code}: {resp.text[:300]}", file=sys.stderr)
        raise RuntimeError(f"API 返回错误 (状态码 {resp.status_code})，详细信息已记录服务端日志")

    result = resp.json()
    reply = result["choices"][0]["message"]["content"]
    usage = result.get("usage", {})

    # 成本估算 (deepseek-chat flash 定价)
    cost = (
        usage.get("prompt_tokens", 0) * 0.14 / 1_000_000
        + usage.get("completion_tokens", 0) * 0.28 / 1_000_000
    )

    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    _log_chat_usage("deepseek", prompt_tokens, completion_tokens)
    _safe_record_llm_span(
        duration_ms=int((_time.time() - t0) * 1000),
        input_summary=str(messages)[:200], output_summary=reply[:200],
        model=config.MODEL, token_usage=usage, status="success",
    )

    return reply, {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "cost_usd": round(cost, 6),
    }


def load_prompt(name):
    """加载 prompts/ 目录下的提示词文件"""
    from config import PROMPTS_DIR
    prompt_file = PROMPTS_DIR / f"{name}.txt"
    if prompt_file.exists():
        return prompt_file.read_text(encoding="utf-8").strip()
    return ""

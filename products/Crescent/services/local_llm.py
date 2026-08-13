"""本地模型服务 — Ollama 调用（压缩 + Agent 推理）"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
import json
from dataclasses import dataclass, field

OLLAMA_URL = "http://localhost:11434"

# 模型名从 config 读取（有默认值兜底）
try:
    import config as _cfg
    COMPRESS_MODEL = getattr(_cfg, "LOCAL_COMPRESS_MODEL", "qwen2.5:0.5b")
    AGENT_MODEL = getattr(_cfg, "LOCAL_MODEL_NAME", "llama3.1:8b")
except Exception:
    COMPRESS_MODEL = "qwen2.5:0.5b"
    AGENT_MODEL = "llama3.1:8b"


# ── 压缩工具 (始终用小模型) ──

def _call_ollama_generate(prompt: str, model: str = COMPRESS_MODEL, max_tokens: int = 200) -> str:
    """调用 Ollama /api/generate（非流式），用于简单文本任务"""
    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={"model": model, "prompt": prompt, "stream": False,
                  "options": {"num_predict": max_tokens, "temperature": 0.1}},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json().get("response", "")
    except Exception as e:
        return f"[本地模型错误: {e}]"


def is_available(model: str = COMPRESS_MODEL) -> bool:
    """检查 Ollama 服务是否可用 + 指定模型是否存在"""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.status_code != 200:
            return False
        models = [m["name"] for m in r.json().get("models", [])]
        return model in models
    except Exception:
        return False


def list_models() -> list:
    """返回已安装的 Ollama 模型列表"""
    try:
        r = requests.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        if r.status_code != 200:
            return []
        return [m["name"] for m in r.json().get("models", [])]
    except Exception:
        return []


def compress_history(messages: list, max_summary_chars: int = 300) -> str:
    """将对话历史压缩为简短摘要"""
    if not messages:
        return ""

    lines = []
    for m in messages:
        role = m.get("role", "?")
        content = str(m.get("content", ""))[:200]
        if role == "tool":      label = "工具返回"
        elif role == "assistant": label = "助手"
        elif role == "user":    label = "用户"
        else:                   label = role
        lines.append(f"[{label}] {content}")

    prompt = (
        "你是一个对话历史压缩器。请将以下对话历史压缩为简短的要点摘要（中文，不超过300字）。"
        "只保留关键事实：问了什么问题、调用了什么工具、找到了什么结论。"
        "不要添加任何评价或建议。\n\n"
        + "\n".join(lines)
        + "\n\n摘要："
    )
    result = _call_ollama_generate(prompt, max_tokens=200)
    return result.strip() if result else ""


def summarize_tool_result(tool_name: str, result_text: str, max_chars: int = 200) -> str:
    """压缩单个工具返回为一句话摘要"""
    snippet = result_text[:500].replace("\n", " ")
    prompt = (
        f"将以下工具返回压缩为一句话（不超过{max_chars}字）：\n"
        f"工具: {tool_name}\n返回: {snippet}\n\n一句话摘要:"
    )
    result = _call_ollama_generate(prompt, max_tokens=100)
    return result.strip() if result else f"{tool_name}: {snippet[:max_chars]}"


# ── Agent LLM (可切换模型) ──

def chat(messages, system_prompt="", temperature=0.7, max_tokens=800, timeout=30):
    """调用 Ollama /api/chat，签名与 deepseek_client.chat() 一致 → (reply, usage)"""
    ollama_msgs = []
    if system_prompt:
        ollama_msgs.append({"role": "system", "content": system_prompt})
    for m in messages:
        role = m.get("role", "user")
        content = m.get("content", "")
        ollama_msgs.append({"role": role, "content": str(content)})

    try:
        resp = requests.post(
            f"{OLLAMA_URL}/api/chat",
            json={
                "model": AGENT_MODEL,
                "messages": ollama_msgs,
                "stream": False,
                "options": {"temperature": temperature, "num_predict": max_tokens},
            },
            timeout=timeout,
        )
        if resp.status_code != 200:
            raise RuntimeError(f"Ollama 返回错误 ({resp.status_code}): {resp.text[:300]}")
        data = resp.json()
        reply = data["message"]["content"]
        usage = {
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "cost_usd": 0.0,
        }
        return reply, usage
    except requests.exceptions.ConnectionError:
        raise RuntimeError("无法连接 Ollama，请确认 ollama serve 已启动")
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"本地模型响应超时 ({timeout}s)，建议: 1) 在设置页切换到更快的模型(如 qwen2.5:3b) "
            f"2) 切换到云端 DeepSeek 3) 检查是否有其他程序占用 GPU"
        )



@dataclass
class _FakeAIMessage:
    """模拟 LangChain AIMessage，兼容我们的 ReAct 循环"""
    content: str = ""
    tool_calls: list = field(default_factory=list)
    type: str = "ai"


def _langchain_to_ollama_messages(messages: list) -> list:
    """LangChain 消息格式 → Ollama /api/chat 格式"""
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage

    result = []
    for m in messages:
        if isinstance(m, SystemMessage):
            result.append({"role": "system", "content": str(m.content)})
        elif isinstance(m, HumanMessage):
            result.append({"role": "user", "content": str(m.content)})
        elif isinstance(m, ToolMessage):
            result.append({
                "role": "tool",
                "content": str(m.content),
                "tool_call_id": getattr(m, "tool_call_id", ""),
            })
        elif isinstance(m, AIMessage) or isinstance(m, _FakeAIMessage):
            msg = {"role": "assistant", "content": str(m.content) if m.content else ""}
            if hasattr(m, "tool_calls") and m.tool_calls:
                # Ollama /api/chat 需要 OpenAI 格式的 tool_calls
                msg["tool_calls"] = []
                for tc in m.tool_calls:
                    msg["tool_calls"].append({
                        "id": tc.get("id", ""),
                        "type": "function",
                        "function": {
                            "name": tc.get("name", ""),
                            "arguments": tc.get("args", {}),
                        }
                    })
                if not msg["content"]:
                    msg.pop("content")
            result.append(msg)
    return result


def _langchain_tools_to_ollama(tools: list) -> list:
    """LangChain Tool → Ollama /api/chat tools 格式"""
    result = []
    for t in tools:
        schema = {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.args_schema.schema() if hasattr(t, "args_schema") else {
                    "type": "object", "properties": {}, "required": []
                },
            }
        }
        result.append(schema)
    return result


def _parse_ollama_response(resp_data: dict) -> _FakeAIMessage:
    """解析 Ollama /api/chat 响应 → 兼容 AIMessage 的对象"""
    msg = resp_data.get("message", {})
    content = msg.get("content", "") or ""
    raw_tool_calls = msg.get("tool_calls", [])

    tool_calls = []
    for tc in raw_tool_calls:
        func = tc.get("function", {})
        args_str = func.get("arguments", "{}")
        try:
            args = json.loads(args_str) if isinstance(args_str, str) else args_str
        except json.JSONDecodeError:
            args = {}
        tool_calls.append({
            "id": tc.get("id", ""),
            "name": func.get("name", ""),
            "args": args,
        })

    return _FakeAIMessage(content=content, tool_calls=tool_calls)


def get_agent_llm(model: str = None, tools: list = None, temperature: float = 0.3):
    """返回一个兼容 LangChain invoke(messages) 接口的本地 LLM 可调用对象。

    用法:
        llm = get_agent_llm(model="llama3.1:8b", tools=TOOLS)
        response = llm.invoke(messages)  # → 含 .content 和 .tool_calls
    """
    model_name = model or AGENT_MODEL
    tool_list = tools or []

    class _OllamaAgentLLM:
        def invoke(self, messages: list):
            payload = {
                "model": model_name,
                "messages": _langchain_to_ollama_messages(messages),
                "stream": False,
                "options": {"temperature": temperature, "num_predict": 2048},
            }
            if tool_list:
                payload["tools"] = _langchain_tools_to_ollama(tool_list)

            try:
                resp = requests.post(
                    f"{OLLAMA_URL}/api/chat",
                    json=payload,
                    timeout=120,
                )
                resp.raise_for_status()
                return _parse_ollama_response(resp.json())
            except requests.exceptions.Timeout:
                return _FakeAIMessage(
                    content="[本地模型超时] qwen3:8b 响应超过 120s。请在设置页尝试: "
                            "1) 切换更快的本地模型(如 qwen2.5:3b) 2) 切换到 DeepSeek 云端模型。"
                )
            except requests.exceptions.ConnectionError:
                return _FakeAIMessage(
                    content="[本地模型未连接] Ollama 服务未运行。请运行 'ollama serve' 启动，"
                            "或在设置页切换到 DeepSeek 云端模型。"
                )
            except Exception as e:
                return _FakeAIMessage(content=f"[本地模型调用失败: {e}]")

    return _OllamaAgentLLM()

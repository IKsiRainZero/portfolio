"""LLM 服务 — 统一入口，支持本地(Ollama)和云端(DeepSeek)切换"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import config

# HF 镜像 (国内加速)
if not os.environ.get("HF_ENDPOINT"):
    os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"


def get_llm(temperature: float = 0.3, streaming: bool = False, tools: list = None):
    """根据 config.LLM_PROVIDER 返回 LangChain 兼容的 LLM 实例。

    - "local": 使用 Ollama 本地模型 (llama3.1:8b)
    - "deepseek": 使用 DeepSeek API
    """
    if config.LLM_PROVIDER == "local":
        from services.local_llm import get_agent_llm, is_available, list_models
        model = getattr(config, "LOCAL_MODEL_NAME", "llama3.1:8b")
        # 如果指定模型不可用，自动选一个可用的
        if not is_available(model):
            available = list_models()
            local_models = [m for m in available if ":cloud" not in m and "gemini" not in m.lower()]
            if local_models:
                model = local_models[0]
                print(f"[llm] {config.LOCAL_MODEL_NAME} 不可用，改用 {model}")
            else:
                raise RuntimeError("没有可用的本地模型。请运行 ollama pull llama3.1:8b")
        return get_agent_llm(model=model, tools=tools, temperature=temperature)

    # cloud (DeepSeek)
    from langchain_deepseek import ChatDeepSeek
    llm = ChatDeepSeek(
        api_key=config.API_KEY,
        api_base=config.BASE_URL,
        model=config.MODEL,
        temperature=temperature,
        streaming=streaming,
    )
    if tools:
        llm = llm.bind_tools(tools)
    return llm


def get_embeddings():
    """获取 BGE Embeddings（始终本地）"""
    from langchain_huggingface import HuggingFaceEmbeddings
    return HuggingFaceEmbeddings(
        model_name=config.EMBEDDING_MODEL,
        model_kwargs={"device": "cpu"},
        encode_kwargs={"normalize_embeddings": True},
    )


_embeddings = None


def embeddings():
    global _embeddings
    if _embeddings is None:
        _embeddings = get_embeddings()
    return _embeddings

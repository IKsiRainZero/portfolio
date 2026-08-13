"""通用 AI 对话 + RAG 问答"""
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from services.deepseek_client import chat, load_prompt
import config

router = APIRouter(prefix="/api")


@router.post("/ai/tutor")
async def tutor(request: Request):
    """通用 AI 答疑"""
    if not config.API_KEY:
        return JSONResponse(content={"error": "请先配置 DeepSeek API Key"}, status_code=401)

    data = await request.json()
    messages = data.get("messages", [])
    if not messages:
        return JSONResponse(content={"error": "消息不能为空"}, status_code=400)

    system_prompt = load_prompt("tutor") or (
        "你是一位耐心的学习教练。请用中文回答，用白话解释技术概念，"
        "结合真实场景举例。如果用户问的是代码问题，给出简洁的代码示例。"
        "回答控制在300字以内。"
    )

    try:
        reply, usage = chat(
            messages=messages,
            system_prompt=system_prompt,
            max_tokens=data.get("max_tokens", 800),
        )
        return {"reply": reply, "usage": usage}
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=401)
    except RuntimeError as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)
    except Exception as e:
        return JSONResponse(content={"error": f"请求失败: {str(e)}"}, status_code=500)


@router.post("/ai/rag-query")
async def rag_ask(request: Request):
    """RAG 检索增强问答：向量检索 + LLM 生成"""
    if not config.API_KEY:
        return JSONResponse(content={"error": "请先配置 API Key"}, status_code=401)

    data = await request.json()
    question = (data.get("question") or "").strip()
    if not question:
        return JSONResponse(content={"error": "问题不能为空"}, status_code=400)

    try:
        from services.rag_service import rag_query  # lazy, heavy deps
        result = rag_query(
            question=question,
            history=data.get("history"),
            k=data.get("k", 5),
        )
        return result
    except ValueError as e:
        return JSONResponse(content={"error": str(e)}, status_code=401)
    except RuntimeError as e:
        return JSONResponse(content={"error": str(e)}, status_code=502)
    except Exception as e:
        return JSONResponse(content={"error": f"RAG 请求失败: {str(e)}"}, status_code=500)

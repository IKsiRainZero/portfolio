import json
import asyncio
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from anthropic import AsyncAnthropic
from ..config import config
from ..tracer import get_tracer, Trace
from .context import build_context
from .tools import TOOLS, execute_tool

router = APIRouter(prefix="/api", tags=["chat"])

WRITE_TOOLS = {"create_project", "commit_changes"}


async def _stream_events(user_message: str, view: dict | None = None):
    tracer = get_tracer()
    ctx = build_context(user_message, view)

    system_prompt = (
        "You are the Portfolio Console Agent. You help manage a portfolio workspace "
        "with multiple projects. You can read project statuses, run tests, search knowledge, "
        "create projects, and commit changes. "
        "Always use tools to get current data — never make up status information. "
        "When asked to modify files or commit, explain what you'll do before calling the tool. "
        "Keep responses in Chinese (the user's language)."
    )

    messages = [{"role": "user", "content": user_message}]

    yield f"event: context\ndata: {json.dumps(ctx['hot'], ensure_ascii=False)}\n\n"

    try:
        client = AsyncAnthropic(api_key=config.ANTHROPIC_API_KEY)

        msg_id = f"msg-{tracer.session_id[:8]}"
        yield f"event: message_start\ndata: {json.dumps({'message_id': msg_id})}\n\n"

        response = await client.messages.create(
            model=config.ANTHROPIC_MODEL,
            max_tokens=4096,
            system=system_prompt,
            messages=messages,
            tools=TOOLS,
        )

        for block in response.content:
            if block.type == "text":
                yield f"event: message_delta\ndata: {json.dumps({'content': block.text}, ensure_ascii=False)}\n\n"

            elif block.type == "tool_use":
                tool_name = block.name
                tool_input = block.input or {}

                trace = tracer.trace(
                    operation=f"tool.{tool_name}",
                    target=tool_input.get("project_name", tool_input.get("name", "")),
                    input_summary=json.dumps(tool_input, ensure_ascii=False)[:200],
                )

                yield f"event: tool_start\ndata: {json.dumps({'tool': tool_name, 'trace_id': trace.id, 'input': tool_input}, ensure_ascii=False)}\n\n"

                if tool_name in WRITE_TOOLS:
                    yield f"event: confirm_required\ndata: {json.dumps({'tool': tool_name, 'plan': tool_input}, ensure_ascii=False)}\n\n"
                else:
                    result = execute_tool(tool_name, tool_input)
                    trace.output_summary = json.dumps(result, ensure_ascii=False)[:200]
                    trace.status = "error" if "error" in str(result).lower() else "ok"
                    tracer.write(trace)
                    yield f"event: tool_end\ndata: {json.dumps({'tool': tool_name, 'trace_id': trace.id, 'result': result}, ensure_ascii=False)}\n\n"

        yield f"event: message_end\ndata: {json.dumps({'message_id': msg_id, 'tokens_used': response.usage.input_tokens + response.usage.output_tokens if response.usage else 0})}\n\n"

    except Exception as e:
        yield f"event: error\ndata: {json.dumps({'code': 'chat_error', 'message': str(e)})}\n\n"


@router.post("/chat/stream")
async def chat_stream(request: Request):
    body = await request.json()
    message = body.get("message", "")
    view = body.get("context", {})

    return StreamingResponse(
        _stream_events(message, view),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.post("/exec/confirm")
async def exec_confirm(request: Request):
    body = await request.json()
    tool_name = body.get("tool", "")
    tool_args = body.get("args", {})
    result = execute_tool(tool_name, tool_args)
    return {"status": "executed", "result": result}

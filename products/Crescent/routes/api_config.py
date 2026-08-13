from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import time as _time
import config
from pathlib import Path

router = APIRouter(prefix="/api")

# 本地模型可用性缓存 (避免每次 /api/config 轮询都请求 Ollama)
_local_avail_cache = {"value": None, "ts": 0, "ttl": 60}


def _is_local_available():
    now = _time.time()
    if _local_avail_cache["value"] is not None and (now - _local_avail_cache["ts"]) < _local_avail_cache["ttl"]:
        return _local_avail_cache["value"]
    try:
        from services.local_llm import is_available
        avail = is_available(config.LOCAL_MODEL_NAME)
    except Exception:
        avail = False
    _local_avail_cache["value"] = avail
    _local_avail_cache["ts"] = now
    return avail


@router.get("/config")
async def get_config(request: Request):
    # 从 model_providers.json 读取当前活跃模型名
    try:
        from services.model_config import get_active
        active = get_active()
        model_name = active["active_model"]
        provider = active["active_provider"]
    except Exception:
        model_name = config.LOCAL_MODEL_NAME if config.LLM_PROVIDER == "local" else config.MODEL
        provider = config.LLM_PROVIDER

    if provider == "local":
        api_ok = _is_local_available()
    else:
        api_ok = bool(config.API_KEY)

    return {
        "api_configured": api_ok,
        "model": model_name,
        "llm_provider": provider,
    }


@router.post("/config")
async def set_config(request: Request):
    data = await request.json()
    key = data.get("api_key", "").strip()
    if key:
        key_file = config.USER_DATA_DIR / ".api_key"
        key_file.write_text(key)
        config.API_KEY = key
        return {"ok": True, "message": "API Key 已保存"}
    return JSONResponse(content={"ok": False, "message": "API Key 不能为空"}, status_code=400)


# ── Model management ──

@router.get("/config/models")
async def get_models(request: Request):
    from services.model_config import get_active
    return get_active()


@router.post("/config/models")
async def add_model(request: Request):
    data = await request.json()
    name = (data.get("name", "") or "").strip()
    provider = (data.get("provider", "") or "").strip()
    if not name or not provider:
        return JSONResponse(content={"ok": False, "message": "模型名称和 Provider 不能为空"}, status_code=400)
    from services.model_config import add_provider
    cfg = add_provider(name, provider,
                       api_key=data.get("api_key", ""),
                       base_url=data.get("base_url", ""))
    return {"ok": True, "providers": cfg["providers"]}


@router.delete("/config/models/{name}")
async def delete_model(name: str, request: Request):
    from services.model_config import remove_provider
    try:
        cfg = remove_provider(name)
        return {"ok": True, "providers": cfg["providers"]}
    except ValueError as e:
        return JSONResponse(content={"ok": False, "message": str(e)}, status_code=400)


@router.put("/config/models/active")
async def set_active_model(request: Request):
    data = await request.json()
    provider = (data.get("provider", "") or "").strip()
    model = (data.get("model", "") or "").strip()
    if not provider or not model:
        return JSONResponse(content={"ok": False, "message": "provider 和 model 不能为空"}, status_code=400)

    if provider == "local":
        from services.local_llm import is_available
        if not is_available(model):
            return JSONResponse(content={"ok": False, "message": f"本地模型 {model} 不可用，请先 ollama pull {model}"}, status_code=400)

    from services.model_config import set_active
    cfg = set_active(provider, model)

    # 运行时切换
    config.LLM_PROVIDER = provider
    if provider == "local":
        config.LOCAL_MODEL_NAME = model
    else:
        config.MODEL = model
        # 从 providers 中查找对应的 api_key
        for p in cfg.get("providers", []):
            if p["name"] == model and p.get("api_key"):
                config.API_KEY = p["api_key"]
                break

    return {"ok": True, "active_provider": provider, "active_model": model}


# ── User Settings ──

@router.get("/config/settings")
async def get_user_settings(request: Request):
    from services.user_settings import load_user_settings, TEMPLATES
    from services.rate_limiter import get_daily_call_count
    settings = load_user_settings()
    return {
        "settings": settings,
        "templates": {k: {"label": {"light": "轻量", "moderate": "中度", "heavy": "重度"}[k], **v} for k, v in TEMPLATES.items()},
        "daily_call_count": get_daily_call_count(),
    }


@router.post("/config/settings")
async def save_user_settings(request: Request):
    from services.user_settings import load_user_settings, save_user_settings as save_s, apply_template
    from services.rate_limiter import apply_user_rate_limits
    data = await request.json() or {}

    tpl = data.get("template")
    if tpl and tpl != "custom":
        settings = apply_template(tpl)
    else:
        current = load_user_settings()
        current.update(data)
        current["template"] = "custom"
        save_s(current)
        settings = current

    apply_user_rate_limits()
    return {"ok": True, "settings": settings}

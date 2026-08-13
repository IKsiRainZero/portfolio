"""用户设置持久化 — data/user_data/user_settings.json"""
import json
from pathlib import Path

SETTINGS_PATH = Path(__file__).parent.parent / "data" / "user_data" / "user_settings.json"

TEMPLATES = {
    "light": {
        "agent_max_iterations": 3,
        "agent_max_iterations_unlimited": False,
        "rate_limit_per_minute": 5,
        "rate_limit_unlimited": False,
        "max_conversation_rounds": 5,
        "max_conversation_rounds_unlimited": False,
        "session_token_limit": 8000,
        "session_token_limit_unlimited": False,
        "daily_token_limit": 50000,
        "daily_token_limit_unlimited": False,
        "streaming_enabled": False,
        "web_search_enabled": True,
        "deep_thinking": False,
        "news_enabled": True,
        "news_categories": ["technology"],
        "news_count": 3,
        "news_api_key": "",
    },
    "moderate": {
        "agent_max_iterations": 6,
        "agent_max_iterations_unlimited": False,
        "rate_limit_per_minute": 15,
        "rate_limit_unlimited": False,
        "max_conversation_rounds": 15,
        "max_conversation_rounds_unlimited": False,
        "session_token_limit": 30000,
        "session_token_limit_unlimited": False,
        "daily_token_limit": 200000,
        "daily_token_limit_unlimited": False,
        "streaming_enabled": True,
        "web_search_enabled": True,
        "deep_thinking": False,
        "news_enabled": True,
        "news_categories": ["technology", "science"],
        "news_count": 5,
        "news_api_key": "",
    },
    "heavy": {
        "agent_max_iterations": 10,
        "agent_max_iterations_unlimited": True,
        "rate_limit_per_minute": 30,
        "rate_limit_unlimited": True,
        "max_conversation_rounds": 30,
        "max_conversation_rounds_unlimited": True,
        "session_token_limit": 100000,
        "session_token_limit_unlimited": True,
        "daily_token_limit": 500000,
        "daily_token_limit_unlimited": True,
        "streaming_enabled": True,
        "web_search_enabled": True,
        "deep_thinking": True,
        "news_enabled": True,
        "news_categories": ["technology", "science", "business", "general"],
        "news_count": 8,
        "news_api_key": "",
    },
}

DEFAULT_SETTINGS = {
    **TEMPLATES["moderate"],
    "template": "moderate",
    "deep_thinking": False,
    "news_enabled": True,
    "news_categories": ["technology", "science"],
    "news_count": 5,
    "news_api_key": "",
}


def _ensure_file():
    if not SETTINGS_PATH.exists():
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, ensure_ascii=False, indent=2)


def load_user_settings() -> dict:
    _ensure_file()
    with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_user_settings(settings: dict):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)


def get_setting(key, default=None):
    """读取单个设置项，fallback 到 DEFAULT_SETTINGS → default"""
    try:
        s = load_user_settings()
        if key in s:
            return s[key]
        return DEFAULT_SETTINGS.get(key, default)
    except Exception:
        return DEFAULT_SETTINGS.get(key, default)


def apply_template(name: str) -> dict:
    """应用预设模板，返回更新后的 settings"""
    if name not in TEMPLATES:
        name = "moderate"
    settings = load_user_settings()
    settings.update(TEMPLATES[name])
    settings["template"] = name
    save_user_settings(settings)
    return settings

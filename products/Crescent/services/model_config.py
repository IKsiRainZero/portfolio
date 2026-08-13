"""模型配置持久化 — user_data/model_providers.json"""
import json
import os
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "data" / "user_data" / "model_providers.json"

DEFAULT_CONFIG = {
    "active_provider": "deepseek",
    "active_model": "deepseek-v4-flash",
    "providers": [
        {"name": "deepseek-v4-flash", "provider": "deepseek", "api_key": "", "base_url": "https://api.deepseek.com"},
    ],
}


def _ensure_file():
    if not CONFIG_PATH.exists():
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)


def load_model_config() -> dict:
    _ensure_file()
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_model_config(cfg: dict):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def add_provider(name: str, provider: str, api_key: str = "", base_url: str = "") -> dict:
    cfg = load_model_config()
    existing = [p for p in cfg["providers"] if p["name"] == name]
    if existing:
        existing[0]["provider"] = provider
        existing[0]["api_key"] = api_key
        existing[0]["base_url"] = base_url
    else:
        cfg["providers"].append({
            "name": name, "provider": provider,
            "api_key": api_key, "base_url": base_url,
        })
    save_model_config(cfg)
    return cfg


def remove_provider(name: str) -> dict:
    cfg = load_model_config()
    if cfg["active_model"] == name:
        raise ValueError(f"不能删除当前正在使用的模型「{name}」，请先切换到其他模型")
    cfg["providers"] = [p for p in cfg["providers"] if p["name"] != name]
    save_model_config(cfg)
    return cfg


def set_active(provider: str, model: str) -> dict:
    cfg = load_model_config()
    cfg["active_provider"] = provider
    cfg["active_model"] = model
    save_model_config(cfg)
    return cfg


def get_active() -> dict:
    cfg = load_model_config()
    return {
        "active_provider": cfg["active_provider"],
        "active_model": cfg["active_model"],
        "providers": cfg["providers"],
    }

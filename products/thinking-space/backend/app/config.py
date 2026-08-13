import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PORTFOLIO_ROOT = Path(os.getenv("PORTFOLIO_ROOT", Path(__file__).parent.parent.parent.parent.parent))
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)


class Config:
    DATABASE_URL = f"sqlite:///{DATA_DIR / 'thinking-space.db'}"
    PORTFOLIO_ROOT = PORTFOLIO_ROOT
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")

import os
from pathlib import Path

class Config:
    PORTFOLIO_ROOT: Path = Path(os.environ.get(
        "PORTFOLIO_ROOT",
        Path(__file__).resolve().parent.parent.parent.parent.parent
    ))
    TRACES_DIR: Path = PORTFOLIO_ROOT / ".context" / "observability" / "traces"
    STATUS_PATH: Path = PORTFOLIO_ROOT / "STATUS.md"
    PRODUCTS_DIR: Path = PORTFOLIO_ROOT / "products"
    ANTHROPIC_API_KEY: str = os.environ.get("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

config = Config()

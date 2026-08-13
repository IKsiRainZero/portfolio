from pathlib import Path
from ..config import config


def read_constitution(project_name: str) -> list[str]:
    const_dir = config.PRODUCTS_DIR / project_name / ".context" / "constitution"
    if not const_dir.exists():
        return []
    return sorted([f.name for f in const_dir.glob("*.md")])


def read_constitution_summary(project_name: str) -> str:
    """Extract first meaningful paragraph from architecture.md for AI context."""
    const_dir = config.PRODUCTS_DIR / project_name / ".context" / "constitution"
    arch_file = const_dir / "architecture.md"
    if not arch_file.exists():
        return ""
    try:
        lines = arch_file.read_text(encoding="utf-8").split("\n")
        paragraphs = []
        for line in lines:
            line = line.strip()
            if line and not line.startswith("#") and not line.startswith("<!--"):
                paragraphs.append(line)
            if len("\n".join(paragraphs)) > 200:
                break
        return "\n".join(paragraphs)[:300]
    except Exception:
        return ""

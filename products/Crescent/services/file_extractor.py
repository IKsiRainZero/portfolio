"""多格式文件文本提取 — 支持 txt/md/pdf/docx/html，纯函数无状态"""
from __future__ import annotations
from pathlib import Path


def extract_text(filepath: str | Path) -> str | None:
    """根据扩展名选择提取器，返回纯文本或 None（不支持/提取失败）"""
    filepath = Path(filepath)
    if not filepath.exists():
        return None

    ext = filepath.suffix.lower()
    handlers = {
        ".txt": _extract_text,
        ".md": _extract_text,
        ".markdown": _extract_text,
        ".pdf": _extract_pdf,
        ".docx": _extract_docx,
        ".html": _extract_html,
        ".htm": _extract_html,
    }
    handler = handlers.get(ext)
    if handler is None:
        return None
    try:
        return handler(filepath)
    except Exception:
        return None


def supported_extensions() -> list[str]:
    return [".txt", ".md", ".markdown", ".pdf", ".docx", ".html", ".htm"]


def _extract_text(filepath: Path) -> str:
    return filepath.read_text(encoding="utf-8", errors="replace")


def _extract_pdf(filepath: Path) -> str:
    import pdfplumber
    parts = []
    with pdfplumber.open(str(filepath)) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                parts.append(text)
    return "\n".join(parts)


def _extract_docx(filepath: Path) -> str:
    from docx import Document
    doc = Document(str(filepath))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _extract_html(filepath: Path) -> str:
    import io
    from markitdown import MarkItDown
    md = MarkItDown()
    result = md.convert(io.BytesIO(filepath.read_bytes()))
    return result.text_content or ""

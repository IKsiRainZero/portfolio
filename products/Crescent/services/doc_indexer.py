"""知识文档轻量索引 — 错误文档/审查清单/checkpoints/论文 → 结构化提取"""
import re
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).parent.parent.parent
ERROR_DIR = ROOT / "知识库" / "错误与修正与优化"
CHECKLIST_FILE = ROOT / "知识库" / "参考" / "审查清单.md"
CHECKPOINT_DIR = ROOT / "Crescent" / "docs" / "checkpoints"
PAPER_INDEX_FILE = ROOT / "知识库" / "论文索引.md"


def index_error_docs() -> list[dict]:
    if not ERROR_DIR.exists():
        return []
    results = []
    for md_file in sorted(ERROR_DIR.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")[:3000]
        except Exception:
            continue
        title = md_file.stem
        error_type = _extract_field(text, r'error_type[：:]\s*(.+)')
        occurred = _extract_field(text, r'occurred_date[：:]\s*(.+)')
        fix_status = _extract_field(text, r'fix_status[：:]\s*(.+)')
        if not error_type:
            error_type = title
        if not fix_status:
            if any(kw in text for kw in ["已修复", "已解决", "fixed", "resolved"]):
                fix_status = "fixed"
            elif any(kw in text for kw in ["未修复", "待修复", "unresolved", "复现"]):
                fix_status = "unresolved"
            else:
                fix_status = "unknown"
        results.append({
            "title": title,
            "error_type": error_type.strip() if error_type else title,
            "description": text[:500],
            "occurred_date": occurred.strip() if occurred else "",
            "fix_status": fix_status.strip() if fix_status else "unknown",
            "source_file": str(md_file.relative_to(ROOT)),
        })
    return results


def index_checklist() -> list[dict]:
    if not CHECKLIST_FILE.exists():
        return []
    try:
        text = CHECKLIST_FILE.read_text(encoding="utf-8")
    except Exception:
        return []
    categories = []
    sections = re.split(r'\n##\s+', text)
    for section in sections[1:]:
        lines = section.strip().split("\n")
        category = lines[0].strip() if lines else ""
        items = [line.strip()[6:] for line in lines[1:] if line.strip().startswith("- [ ]")]
        if category:
            categories.append({"category": category, "items": items})
    return categories


def index_checkpoints() -> list[dict]:
    if not CHECKPOINT_DIR.exists():
        return []
    results = []
    for f in sorted(CHECKPOINT_DIR.glob("checkpoint-*.md"), reverse=True)[:10]:
        try:
            text = f.read_text(encoding="utf-8")[:5000]
        except Exception:
            continue
        completed, pending = [], []
        in_completed, in_pending = False, False
        for line in text.split("\n"):
            if "完成" in line and ("事项" in line or "##" in line):
                in_completed, in_pending = True, False; continue
            if "未完成" in line or "待续" in line or "待办" in line:
                in_completed, in_pending = False, True; continue
            if line.startswith("##") and "完成" not in line:
                in_completed, in_pending = False, False; continue
            stripped = line.strip().lstrip("- [x]").lstrip("- [X]").lstrip("- [ ]").lstrip("-").strip()
            if stripped and not stripped.startswith("#"):
                if in_completed: completed.append(stripped[:200])
                elif in_pending: pending.append(stripped[:200])
        results.append({"date": f.stem.replace("checkpoint-", ""), "completed": completed[:20], "pending": pending[:20]})
    return results


def index_papers() -> list[dict]:
    if not PAPER_INDEX_FILE.exists():
        return []
    try:
        text = PAPER_INDEX_FILE.read_text(encoding="utf-8")
    except Exception:
        return []
    papers = []
    for m in re.compile(r'\d+\.\s+(.+?)\n\s+https?://\S+\n\s+核心[：:]\s*(.+)').finditer(text):
        papers.append({"title": m.group(1).strip(), "core_insight": m.group(2).strip()})
    return papers


def get_all_indexed() -> dict:
    return {
        "errors": index_error_docs(),
        "checklist": index_checklist(),
        "checkpoints": index_checkpoints()[:5],
        "papers": index_papers(),
        "indexed_at": datetime.now(timezone.utc).isoformat(),
    }


def _extract_field(text: str, pattern: str) -> str:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1) if m else ""

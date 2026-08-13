"""Paper knowledge base storage — structured paper records in papers.json"""
import json
from datetime import datetime
from config import DATA_DIR

PAPERS_FILE = DATA_DIR / "knowledge" / "papers.json"


def load():
    if not PAPERS_FILE.exists():
        return {"meta": {}, "papers": []}
    try:
        return json.loads(PAPERS_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, IOError):
        return {"meta": {}, "papers": []}


def _save(data):
    PAPERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    PAPERS_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def add_paper(paper, overwrite=False):
    """Add a paper record. Returns (status, canonical_id).
    status: 1=added, 0=skipped(duplicate), 2=updated
    """
    data = load()
    canonical_id = paper.get("canonical_id", paper.get("arxiv_id", "").split("v")[0])

    existing_ids = {
        p.get("canonical_id", p.get("arxiv_id", "").split("v")[0])
        for p in data.get("papers", [])
    }

    if canonical_id in existing_ids:
        if not overwrite:
            return 0, canonical_id
        data["papers"] = [
            p for p in data["papers"]
            if p.get("canonical_id", "").split("v")[0] != canonical_id
        ]

    now = datetime.now().isoformat()
    record = {
        "canonical_id": canonical_id,
        "arxiv_id": paper.get("arxiv_id", ""),
        "title": paper.get("title", ""),
        "authors": paper.get("authors", []),
        "categories": paper.get("categories", []),
        "published": paper.get("published", ""),
        "pdf_url": paper.get("pdf_url", ""),
        "abs_url": paper.get("abs_url", ""),
        "abstract": paper.get("abstract", ""),
        "core_problem": paper.get("core_problem", ""),
        "method": paper.get("method", ""),
        "experiment_design": paper.get("experiment_design", ""),
        "key_data_metrics": paper.get("key_data_metrics", ""),
        "extraction_confidence": paper.get("confidence", 0.0),
        "credibility_score": paper.get("credibility_score") or paper.get("score"),
        "credibility_flags": paper.get("credibility_flags") or paper.get("flags", []),
        "md_path": paper.get("md_path", ""),
        "imported_at": now,
        "tags": paper.get("tags", []),
        "relevance_score": paper.get("relevance_score"),
    }
    data.setdefault("papers", []).append(record)
    data["meta"] = {
        "domain": "papers",
        "display_name": "论文知识库",
        "description": "结构化论文摘要与方法论提取",
        "last_updated": now,
    }
    _save(data)
    status = 1 if canonical_id not in existing_ids else 2
    return status, canonical_id


def list_papers():
    return load().get("papers", [])


def get_paper(canonical_id):
    for p in load().get("papers", []):
        if p.get("canonical_id", "").split("v")[0] == canonical_id:
            return p
    return None


def paper_to_searchable_text(paper):
    """Convert a paper record to searchable text for ChromaDB embedding."""
    parts = [
        f"标题: {paper.get('title', '')}",
        f"作者: {', '.join(paper.get('authors', []))}",
        f"摘要: {paper.get('abstract', '')}",
        f"核心问题: {paper.get('core_problem', '')}",
        f"方法: {paper.get('method', '')}",
        f"实验设计: {paper.get('experiment_design', '')}",
        f"关键数据: {paper.get('key_data_metrics', '')}",
    ]
    tags = paper.get("tags", [])
    if tags:
        parts.append(f"标签: {', '.join(tags)}")
    return "\n".join(parts)

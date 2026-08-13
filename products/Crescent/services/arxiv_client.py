"""arXiv API client — search, fetch metadata, download PDFs"""
import time
import requests
import feedparser
from pathlib import Path
from config import ARXIV_API_BASE, ARXIV_RATE_LIMIT

_last_request_time = 0.0


def _rate_limit():
    global _last_request_time
    elapsed = time.time() - _last_request_time
    if elapsed < ARXIV_RATE_LIMIT:
        time.sleep(ARXIV_RATE_LIMIT - elapsed)
    _last_request_time = time.time()


def search(query, max_results=20, start=0, date_from=None, date_to=None,
           categories=None):
    """Search arXiv. Returns list of paper metadata dicts."""
    _rate_limit()
    params = {
        "search_query": _build_query(query, date_from, date_to, categories),
        "start": start,
        "max_results": max_results,
        "sortBy": "submittedDate",
        "sortOrder": "descending",
    }
    resp = requests.get(ARXIV_API_BASE, params=params, timeout=30)
    resp.raise_for_status()
    feed = feedparser.parse(resp.text)
    return [_parse_entry(e) for e in feed.entries]


def _build_query(query, date_from, date_to, categories):
    parts = []
    if query:
        parts.append(f"(all:{query})")
    if categories:
        cat_query = " OR ".join(f"cat:{c}" for c in categories)
        parts.append(f"({cat_query})")
    if date_from or date_to:
        df = date_from.replace("-", "") if date_from else "20260401"
        dt = date_to.replace("-", "") if date_to else "20260630"
        parts.append(f"submittedDate:[{df}0000 TO {dt}2359]")
    return " AND ".join(parts)


def _parse_entry(entry):
    arxiv_id = entry.id.split("/abs/")[-1]
    canonical_id = arxiv_id.split("v")[0] if "v" in arxiv_id else arxiv_id
    authors = [a.get("name", "") for a in entry.get("authors", [])]
    cats = [t.get("term", "") for t in entry.get("tags", [])]
    return {
        "arxiv_id": arxiv_id,
        "canonical_id": canonical_id,
        "title": entry.get("title", "").strip().replace("\n", " "),
        "authors": authors,
        "abstract": entry.get("summary", "").strip().replace("\n", " "),
        "categories": cats,
        "published": entry.get("published", ""),
        "pdf_url": f"https://arxiv.org/pdf/{arxiv_id}.pdf",
        "abs_url": entry.get("id", ""),
        "comment": entry.get("arxiv_comment", ""),
    }


def download_pdf(arxiv_id, output_dir):
    """Download PDF for a given arXiv ID. Returns path to saved file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{arxiv_id}.pdf"
    if out_path.exists():
        return out_path
    _rate_limit()
    url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return out_path


def get_paper_metadata(arxiv_id):
    """Fetch metadata for a single paper by arXiv ID."""
    results = search(f"id:{arxiv_id}", max_results=1)
    return results[0] if results else None

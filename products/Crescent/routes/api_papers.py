"""Paper pipeline API routes"""
import json
from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse
from services.safe_error import safe_error

router = APIRouter(prefix="/api")


@router.post("/papers/search")
async def search_papers(request: Request):
    """Search arXiv for papers."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(content={"error": "JSON body required"}, status_code=400)
    query = (data.get("query") or "").strip()
    if not query:
        return JSONResponse(content={"error": "query is required"}, status_code=400)

    from services.arxiv_client import search as arxiv_search
    try:
        results = arxiv_search(
            query,
            max_results=data.get("max_results", 10),
            date_from=data.get("date_from", "2026-04-01"),
            date_to=data.get("date_to", "2026-06-30"),
            categories=data.get("categories"),
        )
        return {"papers": results, "count": len(results)}
    except Exception:
        return JSONResponse(content=safe_error(Exception("arxiv_search 失败"), "papers/search"), status_code=500)


@router.post("/papers/summarize")
async def summarize(request: Request):
    """Summarize a paper from MD text."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(content={"error": "JSON body required"}, status_code=400)
    md_text = (data.get("text") or "").strip()
    if len(md_text) < 100:
        return JSONResponse(content={"error": "text too short (min 100 chars)"}, status_code=400)

    from services.paper_summarizer import summarize_paper
    result = summarize_paper(md_text, data.get("meta"))
    return result


@router.get("/papers/list")
async def list_all_papers(request: Request):
    """List all papers in knowledge base."""
    from services.paper_index import list_papers
    papers = list_papers()
    return {"papers": papers, "count": len(papers)}


@router.get("/papers/{canonical_id}")
async def get_one_paper(canonical_id: str, request: Request):
    """Get a single paper by canonical ID."""
    from services.paper_index import get_paper
    paper = get_paper(canonical_id)
    if paper is None:
        return JSONResponse(content={"error": "paper not found"}, status_code=404)
    return paper


@router.post("/papers/evaluate")
async def evaluate_paper(request: Request):
    """Evaluate paper credibility."""
    try:
        data = await request.json()
    except Exception:
        return JSONResponse(content={"error": "JSON body required"}, status_code=400)
    from services.credibility_gate import evaluate
    result = evaluate(data, data.get("threshold"))
    return result


@router.post("/papers/reprocess")
async def reprocess(request: Request):
    """Reprocess existing MD files through structured pipeline (SSE)."""
    ROOT = Path(__file__).parent.parent.parent
    cleaned_dir = ROOT / "知识库" / "精炼笔记" / "cleaned"

    def generate():
        from services.paper_summarizer import summarize_paper
        from services.credibility_gate import evaluate as credibility_evaluate
        from services.paper_index import add_paper

        md_files = sorted(cleaned_dir.glob("*.md")) if cleaned_dir.exists() else []
        yield f"data: {json.dumps({'type': 'progress', 'step': 'start', 'total': len(md_files)}, ensure_ascii=False)}\n\n"

        results = []
        for i, md_file in enumerate(md_files):
            yield f"data: {json.dumps({'type': 'progress', 'step': 'summarize', 'current': i+1, 'total': len(md_files), 'file': md_file.name}, ensure_ascii=False)}\n\n"

            text = md_file.read_text(encoding="utf-8")
            summary = summarize_paper(text)
            if summary.get("error"):
                results.append({"file": md_file.name, "status": "error", "error": summary["error"]})
                continue

            summary["md_path"] = str(md_file)
            ev = credibility_evaluate(summary)
            combined = {**summary, **ev}

            if combined.get("passed", False):
                status, cid = add_paper(combined, overwrite=True)
                combined["import_status"] = "added" if status == 1 else "updated"
            else:
                combined["import_status"] = "skipped_low_credibility"
            results.append({
                "file": md_file.name, "status": "ok",
                "canonical_id": combined.get("canonical_id", ""),
                "credibility": combined.get("score", 0),
                "title": combined.get("title", ""),
                "import_status": combined.get("import_status", "unknown"),
            })

        yield f"data: {json.dumps({'type': 'done', 'results': results}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

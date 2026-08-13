"""run_paper_pipeline.py — End-to-end paper discovery → import pipeline"""
import sys
import argparse
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Init config from persisted settings (same as server.py)
import config
try:
    from services.model_config import load_model_config
    mc = load_model_config()
    config.LLM_PROVIDER = mc.get("active_provider", config.LLM_PROVIDER)
    if config.LLM_PROVIDER != "local":
        config.MODEL = mc.get("active_model", config.MODEL)
    key_file = config.USER_DATA_DIR / ".api_key"
    if key_file.exists():
        config.API_KEY = key_file.read_text().strip()
except Exception:
    pass

ROOT = Path(__file__).parent.parent.parent
PAPERS_DIR = ROOT / "知识库" / "论文原文"
NOTES_DIR = ROOT / "知识库" / "精炼笔记"
CLEANED_DIR = NOTES_DIR / "cleaned"

DEFAULT_SEARCHES = [
    ("RAG retrieval augmented generation optimization", 15),
    ("LLM agent self-evolution framework autonomous", 15),
    ("knowledge graph information verification fact-checking LLM", 10),
    ("LLM reliability hallucination evaluation benchmark detection", 10),
    ("efficient LLM inference token optimization KV cache", 10),
]

PIPELINE_STAGES = [
    "search", "download", "convert", "clean",
    "summarize", "filter", "import", "embed", "verify",
]


def run_search(searches=None):
    if searches is None:
        searches = DEFAULT_SEARCHES
    from services.arxiv_client import search
    all_papers = []
    seen = set()
    for query, max_r in searches:
        print(f"  Searching: {query} ...")
        try:
            papers = search(query, max_results=max_r,
                            date_from="2026-04-01", date_to="2026-06-30")
            print(f"    Found {len(papers)}")
        except Exception as e:
            print(f"    Failed: {e}")
            continue
        for p in papers:
            cid = p["canonical_id"]
            if cid not in seen:
                seen.add(cid)
                all_papers.append(p)
    print(f"  Total unique: {len(all_papers)}")
    return all_papers


def run_download(papers, output_dir=None):
    if output_dir is None:
        output_dir = PAPERS_DIR
    output_dir = Path(output_dir)
    from services.arxiv_client import download_pdf
    ok = 0
    for p in papers:
        try:
            out = download_pdf(p["arxiv_id"], output_dir)
            ok += 1
        except Exception as e:
            print(f"    FAIL: {p['arxiv_id']} - {e}")
    print(f"  Downloaded {ok}/{len(papers)}")
    return ok


def run_convert(pdf_dir=None, md_dir=None):
    if pdf_dir is None:
        pdf_dir = PAPERS_DIR
    if md_dir is None:
        md_dir = NOTES_DIR
    from scripts.pdf_to_md import convert_all
    return convert_all(papers_dir=pdf_dir, output_dir=md_dir)


def run_clean(md_dir=None, cleaned_dir=None):
    if md_dir is None:
        md_dir = NOTES_DIR
    if cleaned_dir is None:
        cleaned_dir = CLEANED_DIR
    from scripts.clean_md import clean_all
    return clean_all(notes_dir=md_dir, output_dir=cleaned_dir)


def run_summarize(src_dir=None):
    if src_dir is None:
        src_dir = CLEANED_DIR
    from services.paper_summarizer import summarize_paper
    summaries = []
    src_dir = Path(src_dir)
    md_files = sorted(src_dir.glob("*.md")) if src_dir.exists() else []
    for md_file in md_files:
        print(f"    {md_file.name} ...")
        text = md_file.read_text(encoding="utf-8")
        # Extract arXiv ID from filename
        arxiv_match = re.match(r'(\d+\.\d+)', md_file.stem)
        arxiv_meta = {"arxiv_id": arxiv_match.group(1) if arxiv_match else md_file.stem,
                      "title": "", "authors": []}
        result = summarize_paper(text, arxiv_meta=arxiv_meta)
        result["arxiv_id"] = arxiv_meta["arxiv_id"]
        result["md_path"] = str(md_file)
        summaries.append(result)
        if result.get("error"):
            print(f"      Error: {result['error'][:100]}")
        else:
            conf = result.get("confidence", 0)
            print(f"      OK (confidence={conf})")
    print(f"  Summarized {len(summaries)} papers")
    return summaries


def run_filter(summaries):
    from services.credibility_gate import evaluate
    results = []
    passed = 0
    for s in summaries:
        ev = evaluate(s)
        combined = {**s, **ev}
        results.append(combined)
        if ev.get("passed"):
            passed += 1
        print(f"    {s.get('md_path', '?')[:60]}: "
              f"score={ev.get('score', 0):.2f} "
              f"{'PASS' if ev.get('passed') else 'SKIP'}")
        if ev.get("flags"):
            for flag in ev["flags"]:
                print(f"      flag: {flag}")
    print(f"  Gate: {passed}/{len(results)} passed")
    return results


def run_import(filtered):
    from services.paper_index import add_paper
    added, skipped = 0, 0
    for p in filtered:
        if not p.get("passed", False):
            continue
        status, cid = add_paper(p, overwrite=False)
        if status == 1:
            added += 1
            print(f"    ADDED: {cid} — {p.get('title', '?')[:80]}")
        elif status == 0:
            skipped += 1
    print(f"  Imported: {added} new, {skipped} skipped")
    return added, skipped


def run_embed():
    from services.knowledge_sync import sync_knowledge_to_chroma
    return sync_knowledge_to_chroma()


def run_verify():
    from services.rag_service import search as rag_search
    queries = [
        "RAG retrieval augmented generation method",
        "self-evolving agent framework",
        "hallucination detection evaluation",
        "knowledge graph information verification",
        "efficient LLM inference optimization",
    ]
    for q in queries:
        results = rag_search(q, k=3)
        print(f"\n  Query: {q}")
        for i, r in enumerate(results[:3]):
            print(f"    [{i+1}] {r.get('title', '?')[:80]} "
                  f"(sim={r.get('similarity', 0):.3f})")


def main(stages):
    stage_set = set(stages)
    papers = []
    summaries = []
    filtered = []

    if "search" in stage_set:
        print("\n=== STAGE 1: Search arXiv ===")
        papers = run_search()

    if "download" in stage_set:
        if not papers:
            print("\n=== STAGE 2: No papers to download ===")
        else:
            print(f"\n=== STAGE 2: Download {len(papers)} PDFs ===")
            run_download(papers)

    if "convert" in stage_set:
        print("\n=== STAGE 3: Convert PDF → MD ===")
        run_convert()

    if "clean" in stage_set:
        print("\n=== STAGE 4: Clean Markdown ===")
        run_clean()

    if "summarize" in stage_set:
        print("\n=== STAGE 5: Structured Summarization ===")
        summaries = run_summarize()

    if "filter" in stage_set:
        if not summaries:
            print("\n=== STAGE 6: No summaries to filter ===")
        else:
            print("\n=== STAGE 6: Credibility Gate ===")
            filtered = run_filter(summaries)

    if "import" in stage_set:
        if not filtered:
            print("\n=== STAGE 7: No papers to import ===")
        else:
            print("\n=== STAGE 7: Import to papers.json ===")
            run_import(filtered)

    if "embed" in stage_set:
        print("\n=== STAGE 8: Embed into ChromaDB ===")
        run_embed()

    if "verify" in stage_set:
        print("\n=== STAGE 9: Search Verification ===")
        run_verify()

    print("\n=== Pipeline Complete ===")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Paper discovery pipeline")
    parser.add_argument("--stages", nargs="+", choices=PIPELINE_STAGES,
                        default=["summarize"],
                        help="Pipeline stages to run")
    parser.add_argument("--all", action="store_true",
                        help="Run all stages (search through verify)")
    parser.add_argument("--reprocess", action="store_true",
                        help="Reprocess existing papers (summarize→filter→import→embed→verify)")
    args = parser.parse_args()

    if args.all:
        stages = PIPELINE_STAGES
    elif args.reprocess:
        stages = ["summarize", "filter", "import", "embed", "verify"]
    else:
        stages = args.stages

    main(stages)

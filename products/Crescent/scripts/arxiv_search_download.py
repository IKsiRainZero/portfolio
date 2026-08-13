"""arxiv_search_download.py — Search arXiv and download papers"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from services.arxiv_client import search, download_pdf

ROOT = Path(__file__).parent.parent.parent
PAPERS_DIR = ROOT / "知识库" / "论文原文"

# Our project-related searches for April-June 2026
DEFAULT_SEARCHES = [
    ("RAG retrieval augmented generation optimization", 15),
    ("LLM agent self-evolution framework autonomous", 15),
    ("knowledge graph information verification fact-checking", 10),
    ("LLM reliability hallucination evaluation benchmark", 10),
    ("efficient LLM inference token optimization KV cache", 10),
]


def main():
    parser = argparse.ArgumentParser(description="arXiv paper search and download")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--max", type=int, default=10, help="Max results per search")
    parser.add_argument("--date-from", default="2026-04-01")
    parser.add_argument("--date-to", default="2026-06-30")
    parser.add_argument("--download", action="store_true", help="Download PDFs")
    parser.add_argument("--output-dir", default=str(PAPERS_DIR))
    parser.add_argument("--all", action="store_true",
                        help="Run all default searches")
    args = parser.parse_args()

    queries_to_run = []
    if args.all or not args.query:
        queries_to_run = [(q, args.max) for q, _ in DEFAULT_SEARCHES]
    else:
        queries_to_run = [(args.query, args.max)]

    all_papers = []
    seen = set()

    for q, max_r in queries_to_run:
        print(f"\n=== Searching: {q} (max {max_r}) ===")
        try:
            papers = search(q, max_results=max_r,
                            date_from=args.date_from, date_to=args.date_to)
            print(f"  Found {len(papers)} results")
        except Exception as e:
            print(f"  Search failed: {e}")
            continue

        for p in papers:
            cid = p["canonical_id"]
            if cid not in seen:
                seen.add(cid)
                all_papers.append(p)

    print(f"\n=== Total unique papers: {len(all_papers)} ===")
    for i, p in enumerate(all_papers):
        print(f"\n{i+1}. [{p['arxiv_id']}] {p['title'][:120]}")
        print(f"   Categories: {', '.join(p['categories'][:3])}")
        print(f"   {p['abstract'][:200]}...")

    if args.download and all_papers:
        print(f"\n=== Downloading {len(all_papers)} PDFs ===")
        ok = 0
        output_dir = Path(args.output_dir)
        for p in all_papers:
            try:
                out = download_pdf(p["arxiv_id"], output_dir)
                print(f"  OK: {out.name}")
                ok += 1
            except Exception as e:
                print(f"  FAIL: {p['arxiv_id']} - {e}")
        print(f"\nDownloaded {ok}/{len(all_papers)}")


if __name__ == "__main__":
    main()

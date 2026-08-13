"""PDF→MD 转换脚本 — pypdf 提取论文原文为 Markdown"""
import sys
import io
import re
from pathlib import Path

# Windows 终端可能用 GBK，强制 UTF-8
try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

from pypdf import PdfReader

ROOT = Path(__file__).parent.parent.parent
PAPERS_DIR = ROOT / "知识库" / "论文原文"
OUTPUT_DIR = ROOT / "知识库" / "精炼笔记"


def extract_metadata(reader, filepath):
    """从 PDF 元数据和文件名提取信息"""
    meta = reader.metadata or {}
    filename = filepath.stem
    arxiv_id = filename
    if filename.endswith(("v1", "v2", "v3", "v4", "v5")):
        arxiv_id = filename
    return {
        "arxiv_id": arxiv_id,
        "title": str(meta.get("/Title", "")).strip() or filename,
        "author": str(meta.get("/Author", "")).strip() or "Unknown",
        "subject": str(meta.get("/Subject", "")).strip(),
        "filename": filepath.name,
    }


def clean_text(text):
    """基础清洗：去页眉页脚、合并断行"""
    # 去除行号（如 "1\n2\n3\n"）
    text = re.sub(r"^\s*\d+\s*$", "", text, flags=re.MULTILINE)
    # 合并 hyphen 断词 (word-\nbreak → wordbreak)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # 多空行 → 双空行
    text = re.sub(r"\n{3,}", "\n\n", text)
    # 去除首尾空白
    text = text.strip()
    return text


def extract_references(text):
    """尝试分离参考文献"""
    ref_patterns = [
        r"\n[Rr]eferences?\s*\n",
        r"\nREFERENCES\s*\n",
        r"\nBibliography\s*\n",
        r"\nBIBLIOGRAPHY\s*\n",
    ]
    for pat in ref_patterns:
        m = re.search(pat, text)
        if m:
            body = text[: m.start()].strip()
            refs = text[m.start() :].strip()
            return body, refs
    return text, ""


def pdf_to_markdown(filepath):
    """单文件转换：PDF → Markdown 字符串"""
    reader = PdfReader(str(filepath))
    meta = extract_metadata(reader, filepath)

    pages = []
    for page in reader.pages:
        text = page.extract_text() or ""
        if text.strip():
            pages.append(text)

    full_text = "\n\n".join(pages)
    full_text = clean_text(full_text)
    body, refs = extract_references(full_text)

    return meta, body, refs


def build_markdown(meta, body, refs):
    """组装 Markdown 输出"""
    lines = []
    title = meta["title"].replace("\n", " ")
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"> arXiv: `{meta['arxiv_id']}` | 作者: {meta['author']}")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(body)
    if refs:
        lines.append("")
        lines.append("---")
        lines.append("")
        lines.append(refs)
    return "\n".join(lines)


def convert_all(papers_dir=None, output_dir=None, limit=None):
    """批量转换所有 PDF"""
    papers_dir = Path(papers_dir) if papers_dir else PAPERS_DIR
    output_dir = Path(output_dir) if output_dir else OUTPUT_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    pdfs = sorted(papers_dir.glob("*.pdf"))
    if limit:
        pdfs = pdfs[:limit]

    results = []
    for pdf_path in pdfs:
        print(f"Converting: {pdf_path.name} ...")
        try:
            meta, body, refs = pdf_to_markdown(pdf_path)
            md = build_markdown(meta, body, refs)
            out_path = output_dir / f"{pdf_path.stem}.md"
            out_path.write_text(md, encoding="utf-8")
            print(f"  → {out_path.name} ({len(body)} chars)")
            results.append({"status": "ok", "file": pdf_path.name, "out": str(out_path)})
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            results.append({"status": "error", "file": pdf_path.name, "error": str(e)})

    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\nDone: {ok}/{len(results)} converted")
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PDF → Markdown 转换")
    parser.add_argument("--input", "-i", help="单个 PDF 文件路径")
    parser.add_argument("--papers-dir", help="PDF 目录", default=str(PAPERS_DIR))
    parser.add_argument("--output-dir", help="输出目录", default=str(OUTPUT_DIR))
    parser.add_argument("--limit", "-n", type=int, help="只转换前 N 篇")
    parser.add_argument("--stdout", action="store_true", help="输出到 stdout 而非文件")
    args = parser.parse_args()

    if args.input:
        meta, body, refs = pdf_to_markdown(Path(args.input))
        md = build_markdown(meta, body, refs)
        if args.stdout:
            print(md)
        else:
            out = Path(args.output_dir) / f"{Path(args.input).stem}.md"
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(md, encoding="utf-8")
            print(f"→ {out}")
    else:
        convert_all(args.papers_dir, args.output_dir, args.limit)

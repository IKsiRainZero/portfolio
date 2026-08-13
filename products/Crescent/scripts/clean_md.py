"""数据清洗管道 — 去噪/去重/格式标准化，为向量化做准备"""
import sys
import io
import re
from pathlib import Path

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).parent.parent.parent
NOTES_DIR = ROOT / "知识库" / "精炼笔记"
CLEANED_DIR = ROOT / "知识库" / "精炼笔记" / "cleaned"


def clean_markdown(text):
    """单篇 Markdown 清洗管线"""
    # 1. 去除独立数字行（页码残留）
    text = re.sub(r"^\s*\d{1,4}\s*$", "", text, flags=re.MULTILINE)

    # 2. 合并 hyphen 断词
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # 3. 统一 ArXiv 引用格式 [N] → [N]
    # (保持原样，但去除行内换行)

    # 4. 去除多余空行 (>2 → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # 5. 修复段落被截断 (小写字母后换行 + 下一行以小写开头)
    text = re.sub(r"([a-z])\n([a-z])", r"\1 \2", text)

    # 6. 标准化 section 标题 (确保 # 前无内容)
    text = re.sub(r"^\s*(#{1,6}\s)", r"\n\1", text, flags=re.MULTILINE)

    # 7. 去除尾部空白
    text = text.strip()

    return text


def extract_sections(text):
    """按 # 标题切分为结构化 sections，用于后续 chunk 策略"""
    sections = []
    current_title = "preamble"
    current_content = []

    for line in text.split("\n"):
        if re.match(r"^#{1,3}\s", line):
            if current_content:
                sections.append({
                    "title": current_title,
                    "content": "\n".join(current_content).strip(),
                })
            current_title = line.strip()
            current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections.append({
            "title": current_title,
            "content": "\n".join(current_content).strip(),
        })

    return sections


def deduplicate_paragraphs(paragraphs, threshold=0.8):
    """基于 Jaccard 相似度的段落去重（简化版）"""
    seen = []
    unique = []
    for para in paragraphs:
        words = set(para.lower().split())
        is_dup = False
        for s in seen:
            if not s or not words:
                continue
            jaccard = len(words & s) / len(words | s)
            if jaccard > threshold:
                is_dup = True
                break
        if not is_dup:
            seen.append(words)
            unique.append(para)
    return unique


def clean_one(filepath, output_dir=None):
    """清洗单篇论文"""
    text = filepath.read_text(encoding="utf-8")
    cleaned = clean_markdown(text)

    # 按段落去重
    paragraphs = [p for p in cleaned.split("\n\n") if p.strip()]
    unique_paras = deduplicate_paragraphs(paragraphs)
    cleaned = "\n\n".join(unique_paras)

    if output_dir:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / filepath.name
        out_path.write_text(cleaned, encoding="utf-8")
        return out_path
    return cleaned


def clean_all(notes_dir=None, output_dir=None):
    """批量清洗所有 Markdown"""
    notes_dir = Path(notes_dir) if notes_dir else NOTES_DIR
    output_dir = Path(output_dir) if output_dir else CLEANED_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    mds = sorted(notes_dir.glob("*.md"))
    results = []
    for md_path in mds:
        print(f"Cleaning: {md_path.name} ...")
        try:
            out = clean_one(md_path, output_dir)
            orig = len(md_path.read_text(encoding="utf-8"))
            new = len(out.read_text(encoding="utf-8"))
            reduction = (1 - new / orig) * 100 if orig else 0
            print(f"  → {out.name} ({orig} → {new} chars, -{reduction:.1f}%)")
            results.append({"status": "ok", "file": md_path.name, "reduction": reduction})
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            results.append({"status": "error", "file": md_path.name, "error": str(e)})
    return results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Markdown 数据清洗管道")
    parser.add_argument("--input", "-i", help="单个 Markdown 文件")
    parser.add_argument("--notes-dir", help="精炼笔记目录", default=str(NOTES_DIR))
    parser.add_argument("--output-dir", help="输出目录", default=str(CLEANED_DIR))
    parser.add_argument("--stdout", action="store_true", help="输出到 stdout")
    args = parser.parse_args()

    if args.input:
        path = Path(args.input)
        if args.stdout:
            print(clean_one(path))
        else:
            clean_one(path, args.output_dir)
            print(f"→ {args.output_dir}/{path.name}")
    else:
        clean_all(args.notes_dir, args.output_dir)

from __future__ import annotations
import os
from pathlib import Path
from services.docindex.store import L1Store, L2Store, L1Entry, L2Entry, _doc_path_to_slug


def build_index(docs_root: str = "docs", index_root: str | None = None) -> dict:
    """扫描 docs_root 下的所有 .md/.txt 文件，为尚无 L1 索引的文档生成桩文件。"""
    docs_root = os.path.abspath(docs_root)
    if index_root is None:
        index_root = os.path.join(docs_root, ".index")
    index_root = os.path.abspath(index_root)
    l1_dir = os.path.join(index_root, "L1")
    l2_dir = os.path.join(index_root, "L2")

    if not os.path.isdir(docs_root):
        return {"created_l1": 0, "created_l2": 0, "skipped": 0, "error": "docs_root not found"}

    created_l1 = 0
    created_l2 = 0
    skipped = 0

    for dirpath, _, filenames in os.walk(docs_root):
        # 跳过 .index 目录自身
        if ".index" in dirpath:
            continue

        for fname in filenames:
            if not (fname.endswith(".md") or fname.endswith(".txt")):
                continue

            full_path = os.path.join(dirpath, fname)
            rel_path = os.path.relpath(full_path, os.path.dirname(docs_root))
            # 统一用正斜杠
            rel_path = rel_path.replace("\\", "/")

            slug = _doc_path_to_slug(rel_path)
            l1_file = os.path.join(l1_dir, slug)

            # 已有 L1 文件 → 跳过
            if os.path.exists(l1_file):
                skipped += 1
                continue

            # 生成 L1 桩
            entry = _build_l1_entry(rel_path, full_path)
            L1Store.write(entry, l1_dir)
            created_l1 += 1

            # 生成 L2 桩
            l2_entry = L2Entry(
                doc=rel_path,
                updated="",
                summary=f"## 内容摘要\n（待填写）\n\n## 关键决策\n（待填写）\n\n## 已知问题\n（待填写）",
            )
            L2Store.write(l2_entry, l2_dir)
            created_l2 += 1

    return {"created_l1": created_l1, "created_l2": created_l2, "skipped": skipped}


def _build_l1_entry(rel_path: str, full_path: str) -> L1Entry:
    """从文档路径和内容自动推断 L1 条目。"""
    # depth 推断：文件大小越大越深
    try:
        size_kb = os.path.getsize(full_path) / 1024
    except OSError:
        size_kb = 0
    if size_kb < 1:
        depth = 1
    elif size_kb < 10:
        depth = 2
    else:
        depth = 3

    # covers 推断：从目录路径提取
    parts = rel_path.replace("\\", "/").split("/")
    covers = []
    for part in parts[:-1]:  # 跳过文件名
        if part and part not in ("docs", "."):
            covers.append(f"{part}相关")

    # tags 推断：目录名
    tags = [p for p in parts[:-1] if p and p not in ("docs", ".")]
    # 如果根目录文件无子目录可用，用文件名 stem 作为 tag
    if not tags:
        stem = os.path.splitext(os.path.basename(rel_path))[0]
        tags = [stem.lower()]

    # summary 推断：读文件的前几行
    summary = ""
    try:
        with open(full_path, encoding="utf-8") as f:
            lines = []
            for i, line in enumerate(f):
                if i >= 10:
                    break
                stripped = line.strip()
                if stripped and not stripped.startswith("---") and not stripped.startswith("#"):
                    lines.append(stripped)
            summary = " ".join(lines)[:200]
    except Exception:
        summary = f"（来自 {rel_path} 的文档）"

    return L1Entry(
        doc=rel_path,
        depth=depth,
        covers=covers,
        tags=tags,
        summary=summary,
    )

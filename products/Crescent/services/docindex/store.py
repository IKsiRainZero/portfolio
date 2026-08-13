from __future__ import annotations
import re
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class L1Entry:
    """一级映射条目：一句话摘要 + 覆盖范围 + 深度标记 + L2 地址。"""
    doc: str           # 原文档路径，如 "docs/checkpoints/foo.md"
    depth: int = 1     # 1=浅(不需要L2) 2=中 3=深(L1摘要不够)
    covers: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    summary: str = ""  # 一句话摘要 (≤80字)


@dataclass
class L2Entry:
    """二级映射条目：结构化摘要 + 原文档地址。"""
    doc: str           # 原文档路径
    updated: str = ""  # 日期 "2026-06-29"
    summary: str = ""  # 结构化摘要 (≤500字)


# ── Frontmatter parser (零依赖，正则手写) ──

_FM_RE = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)', re.DOTALL)


def _parse_frontmatter(filepath: str) -> tuple[dict, str]:
    """读取 Markdown 文件，返回 (frontmatter_dict, body_text)。无 frontmatter 时返回 ({}, 全文)。"""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
    except (FileNotFoundError, OSError):
        return {}, ""
    m = _FM_RE.match(content)
    if not m:
        return {}, content
    yaml_str = m.group(1)
    body = m.group(2).strip()
    return _parse_simple_yaml(yaml_str), body


def _parse_simple_yaml(text: str) -> dict:
    """解析最简单的 YAML 子集：顶级标量、字符串列表、内联列表。"""
    result = {}
    for line in text.split("\n"):
        line = line.rstrip()
        if not line or line.startswith("#"):
            continue
        # 列表项 (covers / tags 子项)
        if line.strip().startswith("- "):
            continue  # 由父级处理
        if ":" in line:
            key, _, raw_val = line.partition(":")
            key = key.strip()
            val = raw_val.strip()
            # 空值 → 跳过（下一行是子列表）
            if val == "" or val == "[]":
                # 可能后续有列表项，预初始化
                result[key] = []
                continue
            # 内联列表 [a, b, c]
            if val.startswith("[") and val.endswith("]"):
                inner = val[1:-1]
                result[key] = [x.strip().strip("'\"") for x in inner.split(",") if x.strip()]
                continue
            # 引号包裹的字符串
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                result[key] = val[1:-1]
            else:
                # 尝试数字
                try:
                    result[key] = int(val)
                except ValueError:
                    result[key] = val

    # 处理多行列表 (covers / tags 子项)
    lines = text.split("\n")
    current_list_key = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if not stripped.startswith("- ") and ":" in stripped:
            key, _, val = stripped.partition(":")
            if val.strip() == "" or val.strip() == "[]":
                current_list_key = key.strip()
                if current_list_key not in result:
                    result[current_list_key] = []
            else:
                current_list_key = None
        elif stripped.startswith("- ") and current_list_key:
            item = stripped[2:].strip().strip("'\"")
            result[current_list_key].append(item)

    return result


_LIST_TYPES = {"covers", "tags"}


def _serialize_frontmatter(meta: dict, body: str) -> str:
    """将 dict + body 序列化为带 frontmatter 的 Markdown。"""
    lines = ["---"]
    # doc 必须排第一
    if "doc" in meta:
        lines.append(f"doc: {meta['doc']}")
    for key, val in meta.items():
        if key == "doc":
            continue
        if key in _LIST_TYPES and isinstance(val, list):
            items = ", ".join(val)
            lines.append(f"{key}: [{items}]")
        elif isinstance(val, list):
            lines.append(f"{key}:")
            for item in val:
                lines.append(f"  - {item}")
        elif isinstance(val, int):
            lines.append(f"{key}: {val}")
        else:
            lines.append(f"{key}: {val}")
    lines.append("---")
    lines.append("")
    lines.append(body)
    return "\n".join(lines) + "\n"


def _doc_path_to_slug(doc_path: str) -> str:
    """将原文档路径转为索引文件名。docs/a/b/foo.md → a_b_foo.md"""
    # 去掉 docs/ 前缀和 .md 后缀，斜杠换下划线
    p = doc_path.replace("\\", "/")
    if p.startswith("docs/"):
        p = p[5:]
    if p.endswith(".md"):
        p = p[:-3]
    return p.replace("/", "_") + ".md"


# ── Stores ──

class L1Store:
    """L1 索引文件读写。"""

    @staticmethod
    def read(filepath: str) -> L1Entry | None:
        meta, body = _parse_frontmatter(filepath)
        if not meta:
            return None
        # 去掉正文中可能存在的 Markdown 标题行（# heading）
        body_clean = body.strip()
        if body_clean.startswith("# "):
            nl = body_clean.find("\n")
            if nl != -1:
                body_clean = body_clean[nl + 1:].strip()
            else:
                body_clean = ""
        return L1Entry(
            doc=meta.get("doc", ""),
            depth=meta.get("depth", 1),
            covers=meta.get("covers", []),
            tags=meta.get("tags", []),
            summary=body_clean[:200].strip(),  # 正文即摘要，截断到安全长度
        )

    @staticmethod
    def write(entry: L1Entry, dir_path: str) -> str:
        os.makedirs(dir_path, exist_ok=True)
        meta = {
            "doc": entry.doc,
            "depth": entry.depth,
            "covers": entry.covers,
            "tags": entry.tags,
        }
        body = f"# {os.path.basename(entry.doc)}\n{entry.summary}"
        content = _serialize_frontmatter(meta, body)
        slug = _doc_path_to_slug(entry.doc)
        filepath = os.path.join(dir_path, slug)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath


class L2Store:
    """L2 索引文件读写。"""

    @staticmethod
    def read(filepath: str) -> L2Entry | None:
        meta, body = _parse_frontmatter(filepath)
        if not meta:
            return None
        return L2Entry(
            doc=meta.get("doc", ""),
            updated=meta.get("updated", ""),
            summary=body.strip(),
        )

    @staticmethod
    def write(entry: L2Entry, dir_path: str) -> str:
        os.makedirs(dir_path, exist_ok=True)
        meta = {
            "doc": entry.doc,
            "updated": entry.updated,
        }
        body = f"# {os.path.basename(entry.doc)}\n{entry.summary}"
        content = _serialize_frontmatter(meta, body)
        slug = _doc_path_to_slug(entry.doc)
        filepath = os.path.join(dir_path, slug)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

from __future__ import annotations
from pathlib import Path
from app.config import Config
from app.models import Entry, Layer, Dimension

INDEX_PATTERNS = [
    "products/*/.context/constitution/*.md",
    "products/*/CLAUDE.md",
]

LAYER_KEYWORDS = {
    "细胞": ["细胞", "分子", "DNA", "RNA", "蛋白", "基因"],
    "组织": ["组织", "上皮", "结缔", "肌肉", "神经"],
    "器官": ["器官", "心脏", "肺", "肝", "肾", "脑"],
    "系统": ["系统", "循环", "呼吸", "消化", "神经", "内分泌", "免疫"],
    "人": ["人", "个体", "意识", "行为", "健康", "心理", "Python", "React", "FastAPI", "TypeScript", "Rust", "代码", "编程"],
    "社会": ["社会", "文化", "关系", "群体", "沟通", "资本", "市场", "经济"],
    "国家": ["国家", "治理", "制度", "法律", "政策", "政府"],
    "世界": ["世界", "全球", "国际", "地缘", "环境", "气候"],
    "星系": ["星系", "恒星", "行星", "引力", "天体", "宇宙"],
    "宇宙": ["宇宙", "起源", "法则", "存在", "量子", "熵", "暗物质", "暗能量"],
}

class FileScanner:
    def scan(self, root: Path) -> list[Path]:
        results = []
        for pattern in INDEX_PATTERNS:
            for match in root.glob(pattern):
                if match.is_file():
                    results.append(match)
        return results

class TextExtractor:
    def extract(self, filepath: Path) -> dict:
        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception:
            return {"title": filepath.stem, "content": ""}
        lines = text.split("\n")
        title = filepath.stem
        for line in lines:
            if line.startswith("# "):
                title = line[2:].strip()
                break
        content = text[:500]
        return {"title": title, "content": content, "filepath": str(filepath)}

class EntryMapper:
    def map_to_layer(self, text: str, layers: list[Layer]) -> tuple[str | None, int]:
        text_lower = text.lower()
        for layer in layers:
            keywords = LAYER_KEYWORDS.get(layer.name, [])
            for kw in keywords:
                if kw.lower() in text_lower:
                    return (layer.id, 30)
        return (None, 0)

def run_index_scan(db) -> list[Entry]:
    scanner = FileScanner()
    extractor = TextExtractor()
    mapper = EntryMapper()

    dim = db.query(Dimension).filter(Dimension.name == "物质层次").first()
    if not dim:
        return []
    layers = db.query(Layer).filter(Layer.dimension_id == dim.id).order_by(Layer.level).all()

    existing_links = {e.source_link for e in db.query(Entry.source_link).filter(Entry.source_link != "").all()}
    created = []

    for filepath in scanner.scan(Config.PORTFOLIO_ROOT):
        path_str = str(filepath)
        if path_str in existing_links:
            continue

        extracted = extractor.extract(filepath)
        if not extracted["content"]:
            continue

        layer_id, confidence = mapper.map_to_layer(extracted["content"], layers)

        entry = Entry(
            title=extracted["title"],
            content=extracted["content"],
            entry_type="known",
            layer_id=layer_id,
            dimension_id=dim.id,
            source_type="portfolio_index",
            source_link=path_str,
            status="pending",
            confidence=confidence,
        )
        db.add(entry)
        created.append(entry)

    db.commit()
    return created

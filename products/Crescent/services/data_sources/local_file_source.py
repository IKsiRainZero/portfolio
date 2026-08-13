"""本地文件数据源 — 扫描 user_files/ 文件夹，自动索引到 ChromaDB

即插即用：用户丢文件到 data/user_files/ → 系统自动检测 → 提取文本 →
清洗分块 → 嵌入入库 → Agent 可通过 RAG 管道搜索到。

索引状态持久化到 .index_state.json，仅处理新增/修改的文件。
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import hashlib
import json
import time
from services.data_sources.base import DataSource

# 复用知识摄取管道的清洗和分块逻辑
from services.knowledge_ingest import _clean_text, _chunk_text
from services.file_extractor import extract_text, supported_extensions

_USER_FILES_DIR = Path(__file__).parent.parent.parent / "data" / "user_files"
_STATE_FILE = _USER_FILES_DIR / ".index_state.json"

# ChromaDB 配置（与知识库共用 collection）
from config import CHROMA_PATH, CHROMA_COLLECTION

_LOCAL_FILE_TAG = "local_file"


def _load_state() -> dict:
    """加载索引状态：{filename: md5_hash}。"""
    if not _STATE_FILE.exists():
        return {}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_state(state: dict) -> None:
    _USER_FILES_DIR.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _file_hash(filepath: Path) -> str:
    return hashlib.md5(filepath.read_bytes()).hexdigest()


def _index_file(filepath: Path) -> int:
    """提取文件文本 → 清洗 → 分块 → 嵌入 → 写入 ChromaDB。返回 chunk 数。"""
    text = extract_text(filepath)
    if not text or len(text.strip()) < 20:
        return 0

    cleaned = _clean_text(text)
    chunks = _chunk_text(cleaned)

    if not chunks:
        return 0

    import chromadb
    from sentence_transformers import SentenceTransformer
    from config import EMBEDDING_MODEL

    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    col = client.get_collection(CHROMA_COLLECTION)
    emb = SentenceTransformer(EMBEDDING_MODEL, local_files_only=True, device="cpu")

    fname = filepath.name
    saved = 0
    batch_size = 10

    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        ids = []
        docs = []
        metas = []
        for j, chunk in enumerate(batch):
            cid = hashlib.md5(chunk.encode()).hexdigest()[:16]
            ids.append(f"local_{filepath.stem}_{cid}_{i+j}")
            docs.append(chunk)
            metas.append({
                "title": filepath.stem,
                "filename": fname,
                "source": _LOCAL_FILE_TAG,
            })

        vectors = emb.encode(batch, normalize_embeddings=True).tolist()
        col.add(ids=ids, documents=docs, metadatas=metas, embeddings=vectors)
        saved += len(batch)

    try:
        client._system.stop()
    except Exception:
        pass

    return saved


class LocalFileSource(DataSource):
    name = "local_file"

    def fetch(self, **params) -> list[dict]:
        """扫描文件夹，索引新/改文件，返回本次索引结果。"""
        _USER_FILES_DIR.mkdir(parents=True, exist_ok=True)
        state = _load_state()
        results = []
        supported = set(supported_extensions())

        for filepath in sorted(_USER_FILES_DIR.iterdir()):
            if filepath.name.startswith("."):
                continue
            if filepath.suffix.lower() not in supported:
                continue
            if not filepath.is_file():
                continue

            fhash = _file_hash(filepath)
            if state.get(filepath.name) == fhash:
                results.append({
                    "filename": filepath.name,
                    "status": "unchanged",
                    "size_kb": round(filepath.stat().st_size / 1024, 1),
                })
                continue

            # 新文件或已修改 → 索引
            chunk_count = _index_file(filepath)
            state[filepath.name] = fhash
            results.append({
                "filename": filepath.name,
                "status": "indexed",
                "chunks": chunk_count,
                "size_kb": round(filepath.stat().st_size / 1024, 1),
            })

        _save_state(state)
        return results

    def validate(self, raw: list[dict]) -> list[dict]:
        # 本地文件源无需校验，文件提取和索引在 fetch 中已处理
        return raw

    def transform(self, raw: list[dict]) -> list[dict]:
        return raw

    def format_for_agent(self, data: list[dict]) -> str:
        if not data:
            return "（用户文件夹中暂无文件。将文件放入 data/user_files/ 即可被系统索引和检索。）"

        lines = [f"📁 用户文件 ({len(data)} 个):"]
        for item in data:
            status_icon = "✓" if item["status"] in ("indexed", "unchanged") else "✗"
            detail = f"{item.get('chunks', 0)} 块" if item["status"] == "indexed" else item["status"]
            lines.append(f"  {status_icon} {item['filename']} ({detail}, {item['size_kb']} KB)")
        return "\n".join(lines)

    def format_for_ui(self, data: list[dict]) -> list[dict]:
        return [
            {
                "filename": item["filename"],
                "status": item["status"],
                "chunks": item.get("chunks", 0),
                "size_kb": item["size_kb"],
            }
            for item in data
        ]

    def health_check(self) -> bool:
        try:
            _USER_FILES_DIR.mkdir(parents=True, exist_ok=True)
            return _USER_FILES_DIR.is_dir()
        except Exception:
            return False

# 思考空间 V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a personal thinking meta-system that diagnoses what you know/don't know about any question along a hierarchical chain (细胞→宇宙), with ZUI canvas visualization.

**Architecture:** FastAPI backend with SQLite, React TypeScript frontend with ZUI canvas. LLM-powered diagnosis engine streams results via SSE. File scanner indexes portfolio knowledge into the entry database.

**Tech Stack:** Python 3.11+ / FastAPI / SQLAlchemy / SQLite / pytest | Node 20+ / React 18 / TypeScript 5 / Vite / CSS Modules / framer-motion / Vitest + React Testing Library

## Global Constraints

- Python >= 3.11, Node >= 20
- No new dependencies beyond: fastapi, uvicorn, sqlalchemy, pytest, httpx (backend) | react, react-dom, framer-motion, vitest, @testing-library/react (frontend)
- All file paths relative to `products/thinking-space/`
- SQLite database at `products/thinking-space/data/thinking-space.db`, excluded from git
- API prefix: `/api`
- No page switching — zoom-based navigation only
- V1 single dimension: "物质层次" with 10 fixed layers
- Entry status: `pending` | `confirmed` | `ignored`

---

## File Structure

```
products/thinking-space/
├── backend/
│   ├── requirements.txt
│   ├── run.py                          # uvicorn entry
│   ├── app/
│   │   ├── __init__.py
│   │   ├── config.py                   # DB path, LLM key, portfolio root
│   │   ├── database.py                 # SQLAlchemy engine + session
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── dimension.py
│   │   │   ├── layer.py
│   │   │   ├── entry.py
│   │   │   └── cross_link.py
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── dimensions.py
│   │   │   ├── entries.py
│   │   │   ├── diagnose.py
│   │   │   ├── index.py
│   │   │   ├── cross_links.py
│   │   │   └── export.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── diagnosis.py            # LLM diagnosis engine
│   │   │   ├── indexer.py              # File scanner + mapper
│   │   │   └── seed.py                 # V1 seed data
│   │   └── schemas.py                  # Pydantic request/response models
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_dimensions.py
│       ├── test_entries.py
│       ├── test_diagnose.py
│       ├── test_indexer.py
│       └── test_cross_links.py
├── frontend/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── App.module.css
│   │   ├── api/
│   │   │   └── client.ts              # fetch wrapper + SSE helper
│   │   ├── components/
│   │   │   ├── Canvas/
│   │   │   │   ├── Canvas.tsx
│   │   │   │   ├── Canvas.module.css
│   │   │   │   ├── LayerRow.tsx
│   │   │   │   ├── LayerRow.module.css
│   │   │   │   ├── EntryCard.tsx
│   │   │   │   └── EntryCard.module.css
│   │   │   ├── Dock/
│   │   │   │   ├── Dock.tsx
│   │   │   │   └── Dock.module.css
│   │   │   ├── EntryForm/
│   │   │   │   ├── EntryForm.tsx
│   │   │   │   └── EntryForm.module.css
│   │   │   └── DiagnosisOverlay/
│   │   │       ├── DiagnosisOverlay.tsx
│   │   │       └── DiagnosisOverlay.module.css
│   │   ├── hooks/
│   │   │   ├── useCanvasZoom.ts
│   │   │   ├── useDiagnosis.ts         # SSE stream consumer
│   │   │   └── useDockAutoHide.ts
│   │   └── types/
│   │       └── index.ts               # shared TS types
│   └── tests/
│       ├── setup.ts
│       ├── Canvas.test.tsx
│       ├── Dock.test.tsx
│       ├── EntryCard.test.tsx
│       └── EntryForm.test.tsx
├── data/                               # gitignored
│   └── .gitkeep
├── docs/superpowers/plans/
└── .gitignore
```

---

### Task 1: Backend Scaffold + Database Setup

**Files:**
- Create: `backend/requirements.txt`
- Create: `backend/run.py`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/app/database.py`

**Interfaces:**
- Produces: `get_db()` generator, `engine` object, `Base` declarative base, `Config` class with `DATABASE_URL`, `PORTFOLIO_ROOT`, `LLM_API_KEY`, `LLM_MODEL`

- [ ] **Step 1: Create requirements.txt**

```txt
fastapi==0.115.0
uvicorn[standard]==0.30.6
sqlalchemy==2.0.35
pytest==8.3.3
httpx==0.27.2
python-dotenv==1.0.1
openai==1.51.0
```

- [ ] **Step 2: Create app/config.py**

```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PORTFOLIO_ROOT = Path(os.getenv("PORTFOLIO_ROOT", Path(__file__).parent.parent.parent.parent.parent))
DATA_DIR = Path(__file__).parent.parent.parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

class Config:
    DATABASE_URL = f"sqlite:///{DATA_DIR / 'thinking-space.db'}"
    PORTFOLIO_ROOT = PORTFOLIO_ROOT
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
```

- [ ] **Step 3: Create app/database.py**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from .config import Config

engine = create_engine(Config.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 4: Create backend/run.py**

```python
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
```

- [ ] **Step 5: Verify**

Run: `cd backend && pip install -r requirements.txt && python -c "from app.database import engine; print('OK')"`
Expected: `OK`

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/run.py backend/app/__init__.py backend/app/config.py backend/app/database.py
git commit -m "feat: backend scaffold with FastAPI + SQLAlchemy + SQLite"
```

---

### Task 2: Data Models

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/dimension.py`
- Create: `backend/app/models/layer.py`
- Create: `backend/app/models/entry.py`
- Create: `backend/app/models/cross_link.py`

**Interfaces:**
- Produces: `Dimension` (id: UUID, name, description, sort_order, created_at, updated_at, layers relationship), `Layer` (id, dimension_id FK, name, level, description, sort_order, created_at, updated_at, entries relationship), `Entry` (id, title, content, entry_type, layer_id FK, dimension_id FK, source_type, source_link, status, tags JSON, confidence, created_at, updated_at, cross_links relationships), `CrossLink` (id, source_entry_id FK, target_entry_id FK, relation_type, note, created_at)

- [ ] **Step 1: Create models/__init__.py**

```python
from .dimension import Dimension
from .layer import Layer
from .entry import Entry
from .cross_link import CrossLink

__all__ = ["Dimension", "Layer", "Entry", "CrossLink"]
```

- [ ] **Step 2: Create models/dimension.py**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Dimension(Base):
    __tablename__ = "dimensions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    layers = relationship("Layer", back_populates="dimension", order_by="Layer.level", cascade="all, delete-orphan")
    entries = relationship("Entry", back_populates="dimension", cascade="all, delete-orphan")
```

- [ ] **Step 3: Create models/layer.py**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Layer(Base):
    __tablename__ = "layers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    dimension_id: Mapped[str] = mapped_column(String(36), ForeignKey("dimensions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(500), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    dimension = relationship("Dimension", back_populates="layers")
    entries = relationship("Entry", back_populates="layer", cascade="all, delete-orphan")
```

- [ ] **Step 4: Create models/entry.py**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class Entry(Base):
    __tablename__ = "entries"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    entry_type: Mapped[str] = mapped_column(String(20), nullable=False, default="known")
    layer_id: Mapped[str] = mapped_column(String(36), ForeignKey("layers.id"), nullable=True)
    dimension_id: Mapped[str] = mapped_column(String(36), ForeignKey("dimensions.id"), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), default="manual")
    source_link: Mapped[str] = mapped_column(String(500), default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="confirmed")
    tags: Mapped[dict] = mapped_column(JSON, default=list)
    confidence: Mapped[int] = mapped_column(Integer, default=100)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    layer = relationship("Layer", back_populates="entries")
    dimension = relationship("Dimension", back_populates="entries")
    source_links = relationship("CrossLink", foreign_keys="CrossLink.source_entry_id", back_populates="source_entry", cascade="all, delete-orphan")
    target_links = relationship("CrossLink", foreign_keys="CrossLink.target_entry_id", back_populates="target_entry", cascade="all, delete-orphan")
```

- [ ] **Step 5: Create models/cross_link.py**

```python
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base

class CrossLink(Base):
    __tablename__ = "cross_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_entry_id: Mapped[str] = mapped_column(String(36), ForeignKey("entries.id"), nullable=False)
    target_entry_id: Mapped[str] = mapped_column(String(36), ForeignKey("entries.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, default="relates_to")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))

    source_entry = relationship("Entry", foreign_keys=[source_entry_id], back_populates="source_links")
    target_entry = relationship("Entry", foreign_keys=[target_entry_id], back_populates="target_links")
```

- [ ] **Step 6: Verify models create tables**

Run: `cd backend && python -c "from app.database import engine, Base; Base.metadata.create_all(engine); print('Tables created')"`
Expected: `Tables created`

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/
git commit -m "feat: data models — Dimension, Layer, Entry, CrossLink"
```

---

### Task 3: Seed Data + FastAPI App Shell

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/seed.py`
- Create: `backend/app/main.py`
- Create: `backend/app/schemas.py`

**Interfaces:**
- Consumes: `Dimension`, `Layer` from Task 2
- Produces: `seed_v1_data(db)` function, FastAPI `app` with CORS, `DimensionResponse`, `LayerResponse`, `EntryResponse`, `EntryCreate`, `EntryUpdate` Pydantic schemas

- [ ] **Step 1: Create services/seed.py**

```python
from app.models import Dimension, Layer

V1_LAYERS = [
    (0, "细胞", "生命的基本单位，分子层面的运作"),
    (1, "组织", "细胞群落的协同与分化"),
    (2, "器官", "功能特化的结构单元"),
    (3, "系统", "多器官协调的生理网络"),
    (4, "人", "个体层面的意识、行为、健康"),
    (5, "社会", "人际关系、文化、群体动态"),
    (6, "国家", "治理、制度、经济、法律"),
    (7, "世界", "全球互联、地缘、环境"),
    (8, "星系", "天体物理、宇宙结构"),
    (9, "宇宙", "起源、法则、存在本身"),
]

def seed_v1_data(db):
    existing = db.query(Dimension).filter(Dimension.name == "物质层次").first()
    if existing:
        return existing

    dim = Dimension(name="物质层次", description="从物理本质出发的层级分解", sort_order=0)
    db.add(dim)
    db.flush()

    for level, name, desc in V1_LAYERS:
        layer = Layer(dimension_id=dim.id, name=name, level=level, description=desc, sort_order=level)
        db.add(layer)

    db.commit()
    return dim
```

- [ ] **Step 2: Create app/schemas.py**

```python
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime

class LayerResponse(BaseModel):
    id: str
    dimension_id: str
    name: str
    level: int
    description: str
    entry_count: int = 0
    model_config = {"from_attributes": True}

class DimensionResponse(BaseModel):
    id: str
    name: str
    description: str
    sort_order: int
    layers: list[LayerResponse] = []
    model_config = {"from_attributes": True}

class EntryCreate(BaseModel):
    title: str
    content: str = ""
    entry_type: str = "known"
    layer_id: Optional[str] = None
    dimension_id: str
    source_type: str = "manual"
    source_link: str = ""
    tags: list[str] = []
    confidence: int = 100

class EntryUpdate(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    entry_type: Optional[str] = None
    layer_id: Optional[str] = None
    source_link: Optional[str] = None
    tags: Optional[list[str]] = None
    confidence: Optional[int] = None

class EntryResponse(BaseModel):
    id: str
    title: str
    content: str
    entry_type: str
    layer_id: Optional[str]
    dimension_id: str
    source_type: str
    source_link: str
    status: str
    tags: list
    confidence: int
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}

class CrossLinkCreate(BaseModel):
    source_entry_id: str
    target_entry_id: str
    relation_type: str = "relates_to"
    note: str = ""

class CrossLinkResponse(BaseModel):
    id: str
    source_entry_id: str
    target_entry_id: str
    relation_type: str
    note: str
    created_at: datetime
    model_config = {"from_attributes": True}

class DiagnoseRequest(BaseModel):
    question: str
    dimension_id: str
```

- [ ] **Step 3: Create app/main.py**

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.services.seed import seed_v1_data
from app.database import SessionLocal

app = FastAPI(title="思考空间 API", version="0.1.0")

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_methods=["*"], allow_headers=["*"])

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_v1_data(db)
    finally:
        db.close()
```

- [ ] **Step 4: Verify**

Run: `cd backend && python -c "from app.main import app; print('App created:', app.title)"`
Expected: `App created: 思考空间 API`

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/__init__.py backend/app/services/seed.py backend/app/main.py backend/app/schemas.py
git commit -m "feat: FastAPI app shell, seed data, Pydantic schemas"
```

---

### Task 4: Backend Tests Setup

**Files:**
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`
- Create: `backend/tests/test_dimensions.py`

**Interfaces:**
- Consumes: `app` from Task 3, `get_db` from Task 1
- Produces: pytest fixtures `client` (TestClient), `db` (test database session)

- [ ] **Step 1: Create tests/conftest.py**

```python
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def client():
    return TestClient(app)

@pytest.fixture
def db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 2: Create tests/test_dimensions.py**

```python
def test_get_dimensions_returns_seeded_data(client):
    response = client.get("/api/dimensions")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["name"] == "物质层次"
    assert len(data[0]["layers"]) == 10
    assert data[0]["layers"][0]["name"] == "细胞"
    assert data[0]["layers"][9]["name"] == "宇宙"

def test_dimension_not_found(client):
    response = client.get("/api/dimensions/nonexistent")
    assert response.status_code == 404
```

- [ ] **Step 3: Run tests to verify they fail (no route yet)**

Run: `cd backend && python -m pytest tests/test_dimensions.py -v`
Expected: FAIL — 404 or 500 (no `/api/dimensions` route)

- [ ] **Step 4: Commit**

```bash
git add backend/tests/
git commit -m "test: conftest + dimension tests (failing, no route yet)"
```

---

### Task 5: Dimension + Layer API Routes

**Files:**
- Create: `backend/app/routes/__init__.py`
- Create: `backend/app/routes/dimensions.py`
- Modify: `backend/app/main.py` (register router)

**Interfaces:**
- Consumes: `get_db` from Task 1, `Dimension`, `Layer` from Task 2, schemas from Task 3
- Produces: `GET /api/dimensions`, `GET /api/dimensions/:id`

- [ ] **Step 1: Create routes/dimensions.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.models import Dimension
from app.schemas import DimensionResponse, LayerResponse

router = APIRouter(prefix="/api/dimensions", tags=["dimensions"])

@router.get("", response_model=list[DimensionResponse])
def list_dimensions(db: Session = Depends(get_db)):
    dims = db.query(Dimension).options(joinedload(Dimension.layers)).order_by(Dimension.sort_order).all()
    result = []
    for d in dims:
        layers = []
        for l in d.layers:
            entry_count = len(l.entries) if l.entries else 0
            layers.append(LayerResponse(id=l.id, dimension_id=l.dimension_id, name=l.name, level=l.level, description=l.description or "", entry_count=entry_count))
        result.append(DimensionResponse(id=d.id, name=d.name, description=d.description or "", sort_order=d.sort_order, layers=layers))
    return result

@router.get("/{dimension_id}", response_model=DimensionResponse)
def get_dimension(dimension_id: str, db: Session = Depends(get_db)):
    dim = db.query(Dimension).options(joinedload(Dimension.layers)).filter(Dimension.id == dimension_id).first()
    if not dim:
        raise HTTPException(status_code=404, detail="Dimension not found")
    layers = []
    for l in dim.layers:
        entry_count = len(l.entries) if l.entries else 0
        layers.append(LayerResponse(id=l.id, dimension_id=l.dimension_id, name=l.name, level=l.level, description=l.description or "", entry_count=entry_count))
    return DimensionResponse(id=dim.id, name=dim.name, description=dim.description or "", sort_order=dim.sort_order, layers=layers)
```

- [ ] **Step 2: Update app/main.py — add router registration after middleware**

```python
from app.routes import dimensions

app.include_router(dimensions.router)
```

- [ ] **Step 3: Run tests**

Run: `cd backend && python -m pytest tests/test_dimensions.py -v`
Expected: 2 PASS

- [ ] **Step 4: Commit**

```bash
git add backend/app/routes/__init__.py backend/app/routes/dimensions.py backend/app/main.py
git commit -m "feat: GET /api/dimensions + GET /api/dimensions/:id"
```

---

### Task 6: Entry CRUD API Routes

**Files:**
- Create: `backend/app/routes/entries.py`
- Create: `backend/tests/test_entries.py`
- Modify: `backend/app/main.py` (register router)

**Interfaces:**
- Consumes: `get_db`, `Entry`, schemas from Tasks 1-3
- Produces: `GET /api/entries`, `POST /api/entries`, `PUT /api/entries/:id`, `DELETE /api/entries/:id`, `PUT /api/entries/:id/confirm`, `PUT /api/entries/:id/ignore`

- [ ] **Step 1: Create routes/entries.py**

```python
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from app.database import get_db
from app.models import Entry
from app.schemas import EntryCreate, EntryUpdate, EntryResponse

router = APIRouter(prefix="/api/entries", tags=["entries"])

@router.get("", response_model=list[EntryResponse])
def list_entries(
    dimension_id: Optional[str] = Query(None),
    layer_id: Optional[str] = Query(None),
    entry_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    query = db.query(Entry)
    if dimension_id:
        query = query.filter(Entry.dimension_id == dimension_id)
    if layer_id:
        query = query.filter(Entry.layer_id == layer_id)
    if entry_type:
        query = query.filter(Entry.entry_type == entry_type)
    if status:
        query = query.filter(Entry.status == status)
    if q:
        query = query.filter(Entry.title.contains(q) | Entry.content.contains(q))
    return query.order_by(Entry.created_at.desc()).all()

@router.post("", response_model=EntryResponse, status_code=201)
def create_entry(body: EntryCreate, db: Session = Depends(get_db)):
    entry = Entry(
        title=body.title, content=body.content, entry_type=body.entry_type,
        layer_id=body.layer_id, dimension_id=body.dimension_id,
        source_type=body.source_type, source_link=body.source_link,
        tags=body.tags, confidence=body.confidence,
        status="pending" if body.source_type == "portfolio_index" else "confirmed",
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry

@router.put("/{entry_id}", response_model=EntryResponse)
def update_entry(entry_id: str, body: EntryUpdate, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry

@router.delete("/{entry_id}", status_code=204)
def delete_entry(entry_id: str, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    db.delete(entry)
    db.commit()

@router.put("/{entry_id}/confirm", response_model=EntryResponse)
def confirm_entry(entry_id: str, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry.status = "confirmed"
    entry.confidence = 100
    db.commit()
    db.refresh(entry)
    return entry

@router.put("/{entry_id}/ignore", response_model=EntryResponse)
def ignore_entry(entry_id: str, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    entry.status = "ignored"
    db.commit()
    db.refresh(entry)
    return entry
```

- [ ] **Step 2: Update app/main.py — add router**

```python
from app.routes import entries
app.include_router(entries.router)
```

- [ ] **Step 3: Write failing tests — create tests/test_entries.py**

```python
def test_create_entry(client):
    dims = client.get("/api/dimensions").json()
    layer_id = dims[0]["layers"][0]["id"]
    dim_id = dims[0]["id"]

    resp = client.post("/api/entries", json={
        "title": "线粒体功能",
        "content": "线粒体是细胞的能量工厂，负责ATP合成。",
        "entry_type": "known",
        "layer_id": layer_id,
        "dimension_id": dim_id,
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["title"] == "线粒体功能"
    assert data["status"] == "confirmed"
    assert data["entry_type"] == "known"

def test_list_entries_filtered(client):
    dims = client.get("/api/dimensions").json()
    layer_id = dims[0]["layers"][0]["id"]
    dim_id = dims[0]["id"]

    client.post("/api/entries", json={"title": "A", "dimension_id": dim_id, "layer_id": layer_id, "entry_type": "known"})
    client.post("/api/entries", json={"title": "B", "dimension_id": dim_id, "layer_id": layer_id, "entry_type": "unknown"})

    resp = client.get(f"/api/entries?layer_id={layer_id}&entry_type=known")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["title"] == "A"

def test_confirm_entry(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]

    resp = client.post("/api/entries", json={
        "title": "Test", "dimension_id": dim_id, "source_type": "portfolio_index"
    })
    assert resp.json()["status"] == "pending"

    entry_id = resp.json()["id"]
    confirm = client.put(f"/api/entries/{entry_id}/confirm")
    assert confirm.json()["status"] == "confirmed"

def test_delete_entry(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]
    resp = client.post("/api/entries", json={"title": "ToDelete", "dimension_id": dim_id})
    entry_id = resp.json()["id"]
    del_resp = client.delete(f"/api/entries/{entry_id}")
    assert del_resp.status_code == 204
    get_resp = client.get(f"/api/entries?q=ToDelete")
    assert len(get_resp.json()) == 0
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_entries.py -v`
Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add backend/app/routes/entries.py backend/app/main.py backend/tests/test_entries.py
git commit -m "feat: Entry CRUD API + confirm/ignore endpoints"
```

---

### Task 7: File Indexer Service

**Files:**
- Create: `backend/app/services/indexer.py`
- Create: `backend/app/routes/index.py`
- Create: `backend/tests/test_indexer.py`
- Modify: `backend/app/main.py` (register router)

**Interfaces:**
- Consumes: `Config.PORTFOLIO_ROOT` from Task 1, `Entry` from Task 2
- Produces: `FileScanner.scan()` → list of source paths, `TextExtractor.extract(path)` → dict with title/content, `EntryMapper.map(text, layers)` → layer_id + confidence, `run_index_scan(db)` → list of created pending entries, `POST /api/index/scan`

- [ ] **Step 1: Create services/indexer.py**

```python
import re
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
```

- [ ] **Step 2: Create routes/index.py**

```python
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.database import get_db
from app.services.indexer import run_index_scan

router = APIRouter(prefix="/api/index", tags=["index"])

@router.post("/scan")
def trigger_scan(db: Session = Depends(get_db)):
    created = run_index_scan(db)
    return {"scanned": len(created), "new_entries": [{"id": e.id, "title": e.title, "layer_id": e.layer_id, "status": e.status} for e in created]}
```

- [ ] **Step 3: Write tests — create tests/test_indexer.py**

```python
import tempfile
from pathlib import Path
from app.services.indexer import TextExtractor, EntryMapper
from app.models import Layer

def test_extract_title_from_markdown():
    extractor = TextExtractor()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("# 我的设计决策\n\n一些内容。")
        f.flush()
        result = extractor.extract(Path(f.name))
    assert result["title"] == "我的设计决策"
    assert "一些内容" in result["content"]

def test_extract_fallback_to_filename():
    extractor = TextExtractor()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write("没有标题\n只是内容。")
        f.flush()
        result = extractor.extract(Path(f.name))
    assert result["title"] != ""

def test_entry_mapper_finds_social_layer():
    mapper = EntryMapper()
    layers = [Layer(id="l1", name="社会", level=5), Layer(id="l2", name="人", level=4)]
    layer_id, conf = mapper.map_to_layer("关于社会和文化的分析", layers)
    assert layer_id == "l1"
    assert conf == 30

def test_entry_mapper_returns_none_for_no_match():
    mapper = EntryMapper()
    layers = [Layer(id="l1", name="细胞", level=0)]
    layer_id, conf = mapper.map_to_layer("xyzzy nothing matches", layers)
    assert layer_id is None
    assert conf == 0
```

- [ ] **Step 4: Run indexer tests**

Run: `cd backend && python -m pytest tests/test_indexer.py -v`
Expected: 4 PASS

- [ ] **Step 5: Register route in main.py and commit**

```python
from app.routes import index
app.include_router(index.router)
```

```bash
git add backend/app/services/indexer.py backend/app/routes/index.py backend/app/main.py backend/tests/test_indexer.py
git commit -m "feat: file indexer — scanner, extractor, keyword mapper, /api/index/scan"
```

---

### Task 8: Diagnosis Engine + SSE Endpoint

**Files:**
- Create: `backend/app/services/diagnosis.py`
- Create: `backend/app/routes/diagnose.py`
- Create: `backend/tests/test_diagnose.py`
- Modify: `backend/app/main.py` (register router)

**Interfaces:**
- Consumes: `Config.LLM_API_KEY`, `Config.LLM_MODEL` from Task 1, `Entry`, `Layer` from Task 2, `DiagnoseRequest` from Task 3
- Produces: `DiagnosisService.run(question, dimension_id, db)` → async generator of SSE events, `POST /api/diagnose` (SSE streaming), `GET /api/diagnose/:id`

- [ ] **Step 1: Create services/diagnosis.py**

```python
import json
import asyncio
from openai import AsyncOpenAI
from app.config import Config
from app.models import Entry, Layer, Dimension

DIAGNOSIS_PROMPT = """你是思维诊断助手。用户在思考「{question}」。

当前层级：{layer_name}（{layer_desc}）

用户在这一层已有的认知：
{known_entries}
未知缺口：
{unknown_entries}
待解答问题：
{question_entries}

请诊断：
1. 这一层跟「{question}」有什么关系？
2. 用户在这一层的认知中存在什么缺口？
3. 建议用户在这一层补充什么知识或提出什么问题？

输出严格 JSON（不要 markdown 代码块）：
{{"relation": "...", "gaps": ["...", "..."], "suggestions": ["...", "..."], "new_questions": ["...", "..."]}}"""

class DiagnosisService:
    def __init__(self):
        self.client = AsyncOpenAI(api_key=Config.LLM_API_KEY, base_url=Config.LLM_BASE_URL)

    async def run(self, question: str, dimension_id: str, db):
        dim = db.query(Dimension).filter(Dimension.id == dimension_id).first()
        if not dim:
            yield {"event": "error", "data": json.dumps({"message": "Dimension not found"})}
            return

        layers = db.query(Layer).filter(Layer.dimension_id == dimension_id).order_by(Layer.level).all()
        all_results = []

        for layer in layers:
            yield {"event": "layer_start", "data": json.dumps({"level": layer.level, "name": layer.name})}

            entries = db.query(Entry).filter(Entry.layer_id == layer.id, Entry.status == "confirmed").all()
            known = [e.title for e in entries if e.entry_type == "known"]
            unknown = [e.title for e in entries if e.entry_type == "unknown"]
            questions = [e.title for e in entries if e.entry_type == "question"]

            prompt = DIAGNOSIS_PROMPT.format(
                question=question,
                layer_name=layer.name,
                layer_desc=layer.description or "",
                known_entries="\n".join(f"- {k}" for k in known) if known else "（无）",
                unknown_entries="\n".join(f"- {u}" for u in unknown) if unknown else "（无）",
                question_entries="\n".join(f"- {q}" for q in questions) if questions else "（无）",
            )

            try:
                response = await self.client.chat.completions.create(
                    model=Config.LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.7,
                    max_tokens=500,
                )
                raw = response.choices[0].message.content or "{}"
                parsed = json.loads(raw.strip().removeprefix("```json").removesuffix("```").strip())
            except Exception as e:
                yield {"event": "error", "data": json.dumps({"level": layer.level, "message": str(e)})}
                parsed = {"relation": "", "gaps": [], "suggestions": [], "new_questions": []}

            result = {
                "level": layer.level,
                "name": layer.name,
                "relation": parsed.get("relation", ""),
                "gaps": parsed.get("gaps", []),
                "suggestions": parsed.get("suggestions", []),
                "new_questions": parsed.get("new_questions", []),
                "existing_entries_highlighted": [e.id for e in entries],
                "new_suggested_entries": [
                    {"title": q, "entry_type": "unknown", "content": ""}
                    for q in parsed.get("new_questions", [])
                ],
            }
            all_results.append(result)
            yield {"event": "layer_complete", "data": json.dumps(result, ensure_ascii=False)}

        gap_summary = self._summarize_gaps(all_results)
        yield {"event": "diagnose_end", "data": json.dumps({
            "question": question,
            "dimension": dim.name,
            "layers": all_results,
            "gap_summary": gap_summary,
        }, ensure_ascii=False)}

    def _summarize_gaps(self, results: list[dict]) -> str:
        empty_layers = [r["name"] for r in results if not r["relation"] and not r["gaps"]]
        gap_layers = [r["name"] for r in results if r["gaps"]]
        if empty_layers:
            return f"层级 {', '.join(empty_layers)} 几乎空白，建议优先探索。缺口集中在 {', '.join(gap_layers) if gap_layers else '暂无'}。"
        return f"缺口分布在 {', '.join(gap_layers)} 等层级。"
```

- [ ] **Step 2: Create routes/diagnose.py**

```python
import json
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import DiagnoseRequest
from app.services.diagnosis import DiagnosisService

router = APIRouter(prefix="/api", tags=["diagnose"])

@router.post("/diagnose")
async def diagnose(request: Request, body: DiagnoseRequest, db: Session = Depends(get_db)):
    service = DiagnosisService()

    async def event_stream():
        async for event in service.run(body.question, body.dimension_id, db):
            if await request.is_disconnected():
                break
            yield f"event: {event['event']}\ndata: {event['data']}\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
```

- [ ] **Step 3: Write tests — create tests/test_diagnose.py (mock LLM)**

```python
from unittest.mock import patch, AsyncMock
import json

def test_diagnose_endpoint_accepts_request(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]

    mock_response = AsyncMock()
    mock_response.choices = [AsyncMock()]
    mock_response.choices[0].message.content = json.dumps({
        "relation": "测试关系",
        "gaps": ["缺口1"],
        "suggestions": ["建议1"],
        "new_questions": ["问题1"],
    })

    with patch("app.services.diagnosis.AsyncOpenAI") as mock_client:
        mock_client.return_value.chat.completions.create = AsyncMock(return_value=mock_response)
        response = client.post("/api/diagnose", json={"question": "测试问题", "dimension_id": dim_id})
        assert response.status_code == 200
        assert "text/event-stream" in response.headers["content-type"]
        body = response.text
        assert "event: layer_start" in body
        assert "event: layer_complete" in body
        assert "event: diagnose_end" in body

def test_diagnose_invalid_dimension(client):
    response = client.post("/api/diagnose", json={"question": "测试", "dimension_id": "nonexistent"})
    assert response.status_code == 200
    assert "event: error" in response.text
```

- [ ] **Step 4: Run tests**

Run: `cd backend && python -m pytest tests/test_diagnose.py -v`
Expected: 2 PASS

- [ ] **Step 5: Register route and commit**

```python
from app.routes import diagnose
app.include_router(diagnose.router)
```

```bash
git add backend/app/services/diagnosis.py backend/app/routes/diagnose.py backend/app/main.py backend/tests/test_diagnose.py
git commit -m "feat: LLM diagnosis engine with SSE streaming endpoint"
```

---

### Task 9: CrossLink + Export API Routes

**Files:**
- Create: `backend/app/routes/cross_links.py`
- Create: `backend/app/routes/export.py`
- Create: `backend/tests/test_cross_links.py`
- Modify: `backend/app/main.py` (register routers)

**Interfaces:**
- Consumes: `CrossLink` from Task 2, schemas from Task 3
- Produces: `POST /api/cross-links`, `DELETE /api/cross-links/:id`, `GET /api/export/gap-map`

- [ ] **Step 1: Create routes/cross_links.py**

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import CrossLink
from app.schemas import CrossLinkCreate, CrossLinkResponse

router = APIRouter(prefix="/api/cross-links", tags=["cross-links"])

@router.post("", response_model=CrossLinkResponse, status_code=201)
def create_cross_link(body: CrossLinkCreate, db: Session = Depends(get_db)):
    link = CrossLink(source_entry_id=body.source_entry_id, target_entry_id=body.target_entry_id, relation_type=body.relation_type, note=body.note)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link

@router.delete("/{link_id}", status_code=204)
def delete_cross_link(link_id: str, db: Session = Depends(get_db)):
    link = db.query(CrossLink).filter(CrossLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="CrossLink not found")
    db.delete(link)
    db.commit()
```

- [ ] **Step 2: Create routes/export.py**

```python
from fastapi import APIRouter, Depends, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Entry, Layer

router = APIRouter(prefix="/api/export", tags=["export"])

@router.get("/gap-map", response_class=PlainTextResponse)
def export_gap_map(dimension_id: str = Query(...), db: Session = Depends(get_db)):
    layers = db.query(Layer).filter(Layer.dimension_id == dimension_id).order_by(Layer.level).all()
    lines = ["# 差距地图\n"]
    for layer in layers:
        entries = db.query(Entry).filter(Entry.layer_id == layer.id, Entry.status == "confirmed").all()
        known = sum(1 for e in entries if e.entry_type == "known")
        unknown = sum(1 for e in entries if e.entry_type == "unknown")
        questions = sum(1 for e in entries if e.entry_type == "question")
        lines.append(f"## {layer.name}")
        lines.append(f"- 已知: {known} | 未知缺口: {unknown} | 问题: {questions}")
        for e in entries:
            lines.append(f"  - [{e.entry_type}] {e.title}")
        lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 3: Write tests — create tests/test_cross_links.py**

```python
def test_create_and_delete_cross_link(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]

    e1 = client.post("/api/entries", json={"title": "E1", "dimension_id": dim_id}).json()
    e2 = client.post("/api/entries", json={"title": "E2", "dimension_id": dim_id}).json()

    resp = client.post("/api/cross-links", json={
        "source_entry_id": e1["id"], "target_entry_id": e2["id"], "relation_type": "supports"
    })
    assert resp.status_code == 201
    assert resp.json()["relation_type"] == "supports"

    del_resp = client.delete(f"/api/cross-links/{resp.json()['id']}")
    assert del_resp.status_code == 204
```

- [ ] **Step 4: Run tests + register routes + commit**

Run: `cd backend && python -m pytest tests/test_cross_links.py -v`
Expected: 1 PASS

```python
from app.routes import cross_links, export
app.include_router(cross_links.router)
app.include_router(export.router)
```

```bash
git add backend/app/routes/cross_links.py backend/app/routes/export.py backend/app/main.py backend/tests/test_cross_links.py
git commit -m "feat: CrossLink CRUD + gap-map markdown export"
```

---

### Task 10: Backend Integration Test + Gitignore

**Files:**
- Modify: `../../.gitignore` (add data/ exclusion)
- Create: backend integration smoke test

- [ ] **Step 1: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All tests PASS (11+ tests)

- [ ] **Step 2: Add data/ to gitignore**

Append to `products/thinking-space/.gitignore`:
```
data/*.db
__pycache__/
*.pyc
.env
```

- [ ] **Step 3: Commit**

```bash
git add .gitignore
git commit -m "chore: backend test suite passing, gitignore data/"
```

---

### Task 11: Frontend Scaffold

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/index.html`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/App.module.css`
- Create: `frontend/src/types/index.ts`
- Create: `frontend/src/api/client.ts`

**Interfaces:**
- Produces: Vite dev server on :5173, TypeScript types matching backend schemas, API client with `fetchDimensions()`, `fetchEntries()`, `createEntry()`, `updateEntry()`, `deleteEntry()`, `diagnose()` (SSE), `triggerIndexScan()`, `confirmEntry()`, `ignoreEntry()`

- [ ] **Step 1: Create package.json**

```json
{
  "name": "thinking-space",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest run",
    "test:watch": "vitest"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "framer-motion": "^11.5.0"
  },
  "devDependencies": {
    "@testing-library/react": "^16.0.1",
    "@testing-library/jest-dom": "^6.5.0",
    "@types/react": "^18.3.5",
    "@types/react-dom": "^18.3.0",
    "jsdom": "^25.0.0",
    "typescript": "^5.6.2",
    "vite": "^5.4.3",
    "vitest": "^2.0.5"
  }
}
```

- [ ] **Step 2: Create vite.config.ts**

```typescript
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
  },
});
```

- [ ] **Step 3: Create tsconfig.json**

```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "isolatedModules": true,
    "moduleDetection": "force",
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"]
}
```

- [ ] **Step 4: Create index.html**

```html
<!DOCTYPE html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>思考空间</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 5: Create src/types/index.ts**

```typescript
export interface Layer {
  id: string;
  dimension_id: string;
  name: string;
  level: number;
  description: string;
  entry_count: number;
}

export interface Dimension {
  id: string;
  name: string;
  description: string;
  sort_order: number;
  layers: Layer[];
}

export interface Entry {
  id: string;
  title: string;
  content: string;
  entry_type: 'known' | 'unknown' | 'question';
  layer_id: string | null;
  dimension_id: string;
  source_type: 'manual' | 'portfolio_index' | 'conversation';
  source_link: string;
  status: 'pending' | 'confirmed' | 'ignored';
  tags: string[];
  confidence: number;
  created_at: string;
  updated_at: string;
}

export interface LayerDiagnosis {
  level: number;
  name: string;
  relation: string;
  gaps: string[];
  suggestions: string[];
  new_questions: string[];
  existing_entries_highlighted: string[];
  new_suggested_entries: { title: string; entry_type: string; content: string }[];
}

export type DiagnosisEvent =
  | { event: 'layer_start'; data: { level: number; name: string } }
  | { event: 'layer_complete'; data: LayerDiagnosis }
  | { event: 'diagnose_end'; data: { question: string; dimension: string; layers: LayerDiagnosis[]; gap_summary: string } }
  | { event: 'error'; data: { level?: number; message: string } };
```

- [ ] **Step 6: Create src/api/client.ts**

```typescript
const BASE = '/api';

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  if (res.status === 204) return undefined as T;
  return res.json();
}

export function fetchDimensions(): Promise<Dimension[]> {
  return request<Dimension[]>('/dimensions');
}

export function fetchDimension(id: string): Promise<Dimension> {
  return request<Dimension>(`/dimensions/${id}`);
}

export function fetchEntries(params: Record<string, string> = {}): Promise<Entry[]> {
  const qs = new URLSearchParams(params).toString();
  return request<Entry[]>(`/entries${qs ? `?${qs}` : ''}`);
}

export function createEntry(data: Partial<Entry>): Promise<Entry> {
  return request<Entry>('/entries', { method: 'POST', body: JSON.stringify(data) });
}

export function updateEntry(id: string, data: Partial<Entry>): Promise<Entry> {
  return request<Entry>(`/entries/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}

export function deleteEntry(id: string): Promise<void> {
  return request<void>(`/entries/${id}`, { method: 'DELETE' });
}

export function confirmEntry(id: string): Promise<Entry> {
  return request<Entry>(`/entries/${id}/confirm`, { method: 'PUT' });
}

export function ignoreEntry(id: string): Promise<Entry> {
  return request<Entry>(`/entries/${id}/ignore`, { method: 'PUT' });
}

export function triggerIndexScan(): Promise<{ scanned: number; new_entries: Entry[] }> {
  return request('/index/scan', { method: 'POST' });
}

export function diagnoseStream(
  question: string,
  dimensionId: string,
  onEvent: (event: DiagnosisEvent) => void,
  onError: (err: Error) => void
): AbortController {
  const controller = new AbortController();
  fetch(`${BASE}/diagnose`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, dimension_id: dimensionId }),
    signal: controller.signal,
  })
    .then(async (res) => {
      const reader = res.body?.getReader();
      if (!reader) return;
      const decoder = new TextDecoder();
      let buffer = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split('\n\n');
        buffer = parts.pop() || '';
        for (const part of parts) {
          const eventMatch = part.match(/^event: (.+)\ndata: (.+)$/m);
          if (eventMatch) {
            onEvent({ event: eventMatch[1] as DiagnosisEvent['event'], data: JSON.parse(eventMatch[2]) });
          }
        }
      }
    })
    .catch(onError);
  return controller;
}
```

- [ ] **Step 7: Create src/main.tsx + App.tsx**

```tsx
// main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './App.module.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
```

```tsx
// App.tsx
export default function App() {
  return <div>思考空间</div>;
}
```

- [ ] **Step 8: Install and verify**

Run: `cd frontend && npm install && npm run dev`
Expected: Vite starts on :5173, page shows "思考空间"

- [ ] **Step 9: Commit**

```bash
git add frontend/
git commit -m "feat: frontend scaffold — Vite + React + TS + API client + types"
```

---

### Task 12: ZUI Canvas Component

**Files:**
- Create: `frontend/src/components/Canvas/Canvas.tsx`
- Create: `frontend/src/components/Canvas/Canvas.module.css`
- Create: `frontend/src/components/Canvas/LayerRow.tsx`
- Create: `frontend/src/components/Canvas/LayerRow.module.css`
- Create: `frontend/src/components/Canvas/EntryCard.tsx`
- Create: `frontend/src/components/Canvas/EntryCard.module.css`
- Create: `frontend/src/hooks/useCanvasZoom.ts`
- Create: `frontend/tests/setup.ts`
- Create: `frontend/tests/EntryCard.test.tsx`

**Interfaces:**
- Consumes: `fetchDimensions()`, `fetchEntries()` from Task 11, types from Task 11
- Produces: Canvas with zoom/pan, LayerRow × 10 with EntryCards, color-coded by entry_type and status

- [ ] **Step 1: Create hooks/useCanvasZoom.ts**

```typescript
import { useState, useCallback, WheelEvent } from 'react';

export function useCanvasZoom(initialScale = 1, min = 0.3, max = 3) {
  const [scale, setScale] = useState(initialScale);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  const onWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    setScale((s) => Math.min(max, Math.max(min, s + delta)));
  }, [min, max]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) {
      setIsPanning(true);
      setPanStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  }, [position]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return;
    setPosition({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
  }, [isPanning, panStart]);

  const onMouseUp = useCallback(() => setIsPanning(false), []);

  return { scale, position, isPanning, onWheel, onMouseDown, onMouseMove, onMouseUp };
}
```

- [ ] **Step 2: Create components/Canvas/Canvas.tsx**

```tsx
import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useCanvasZoom } from '../../hooks/useCanvasZoom';
import { fetchDimensions, fetchEntries } from '../../api/client';
import type { Dimension, Entry } from '../../types';
import LayerRow from './LayerRow';
import styles from './Canvas.module.css';

export default function Canvas() {
  const [dimension, setDimension] = useState<Dimension | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const { scale, position, isPanning, onWheel, onMouseDown, onMouseMove, onMouseUp } = useCanvasZoom(0.6, 0.2, 2);

  useEffect(() => {
    fetchDimensions().then((dims) => {
      if (dims.length > 0) {
        setDimension(dims[0]);
        fetchEntries({ dimension_id: dims[0].id, status: 'confirmed' }).then(setEntries);
      }
    });
  }, []);

  if (!dimension) return <div className={styles.loading}>加载中...</div>;

  const entriesByLayer: Record<string, Entry[]> = {};
  for (const e of entries) {
    if (e.layer_id) {
      (entriesByLayer[e.layer_id] ??= []).push(e);
    }
  }

  return (
    <div className={styles.canvasContainer} onWheel={onWheel} onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp}>
      <motion.div
        className={styles.canvas}
        style={{ transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`, cursor: isPanning ? 'grabbing' : 'grab' }}
      >
        {dimension.layers.map((layer) => (
          <LayerRow key={layer.id} layer={layer} entries={entriesByLayer[layer.id] || []} scale={scale} />
        ))}
      </motion.div>
    </div>
  );
}
```

- [ ] **Step 3: Create components/Canvas/Canvas.module.css**

```css
.canvasContainer {
  width: 100vw;
  height: 100vh;
  overflow: hidden;
  background: #f5f5f7;
}

.canvas {
  transform-origin: 0 0;
  padding: 40px;
  display: flex;
  flex-direction: column;
  gap: 32px;
  min-width: max-content;
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100vh;
  font-size: 18px;
  color: #86868b;
}
```

- [ ] **Step 4: Create components/Canvas/LayerRow.tsx**

```tsx
import type { Layer, Entry } from '../../types';
import EntryCard from './EntryCard';
import styles from './LayerRow.module.css';

const LAYER_TINTS: Record<number, string> = {
  0: '#f0f4e8', 1: '#e8f0f0', 2: '#f0e8ec', 3: '#e8ecf0', 4: '#f4f0e8',
  5: '#e8f4e8', 6: '#f0e8f0', 7: '#ece8f0', 8: '#e8e8f4', 9: '#f4e8e8',
};

interface Props {
  layer: Layer;
  entries: Entry[];
  scale: number;
}

export default function LayerRow({ layer, entries, scale }: Props) {
  const known = entries.filter((e) => e.entry_type === 'known');
  const unknown = entries.filter((e) => e.entry_type === 'unknown');
  const questions = entries.filter((e) => e.entry_type === 'question');
  const tint = LAYER_TINTS[layer.level] || '#f5f5f7';

  return (
    <div className={styles.row} style={{ backgroundColor: tint }}>
      <div className={styles.header}>
        <span className={styles.name}>{layer.name}</span>
        <span className={styles.counts}>
          <span className={styles.known}>🟢 {known.length}</span>
          <span className={styles.unknown}>🔴 {unknown.length}</span>
          <span className={styles.question}>🟡 {questions.length}</span>
        </span>
      </div>
      <div className={styles.cards}>
        {entries.map((entry) => (
          <EntryCard key={entry.id} entry={entry} scale={scale} />
        ))}
        {entries.length === 0 && <div className={styles.empty}>暂无记录</div>}
      </div>
    </div>
  );
}
```

- [ ] **Step 5: Create components/Canvas/LayerRow.module.css**

```css
.row {
  border-radius: 16px;
  padding: 20px;
  min-width: 600px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.name {
  font-size: 22px;
  font-weight: 600;
  color: #1d1d1f;
}

.counts {
  display: flex;
  gap: 12px;
  font-size: 14px;
}

.known, .unknown, .question {
  font-weight: 500;
}

.cards {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.empty {
  color: #86868b;
  font-size: 14px;
  font-style: italic;
}
```

- [ ] **Step 6: Create components/Canvas/EntryCard.tsx**

```tsx
import type { Entry } from '../../types';
import styles from './EntryCard.module.css';

const TYPE_COLORS: Record<string, string> = {
  known: '#34c759',
  unknown: '#ff3b30',
  question: '#ffcc00',
};

interface Props {
  entry: Entry;
  scale: number;
}

export default function EntryCard({ entry }: Props) {
  const isPending = entry.status === 'pending';
  const borderColor = TYPE_COLORS[entry.entry_type] || '#86868b';

  return (
    <div
      className={`${styles.card} ${isPending ? styles.pending : ''}`}
      style={{ borderLeft: `3px solid ${borderColor}` }}
      title={entry.content}
    >
      <span className={styles.title}>{entry.title}</span>
      {isPending && <span className={styles.badge}>待确认</span>}
    </div>
  );
}
```

- [ ] **Step 7: Create components/Canvas/EntryCard.module.css**

```css
.card {
  background: white;
  border-radius: 8px;
  padding: 10px 14px;
  font-size: 14px;
  color: #1d1d1f;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.08);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.12);
}

.pending {
  border-style: dashed;
  opacity: 0.7;
}

.title {
  font-weight: 500;
  max-width: 200px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.badge {
  font-size: 11px;
  background: #f5f5f7;
  color: #86868b;
  padding: 2px 6px;
  border-radius: 4px;
}
```

- [ ] **Step 8: Create tests/setup.ts + tests/EntryCard.test.tsx**

```typescript
// tests/setup.ts
import '@testing-library/jest-dom';
```

```tsx
// tests/EntryCard.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import EntryCard from '../src/components/Canvas/EntryCard';

describe('EntryCard', () => {
  it('renders title', () => {
    const entry = {
      id: '1', title: '线粒体功能', content: '...', entry_type: 'known' as const,
      layer_id: 'l1', dimension_id: 'd1', source_type: 'manual' as const,
      source_link: '', status: 'confirmed' as const, tags: [], confidence: 100,
      created_at: '', updated_at: '',
    };
    render(<EntryCard entry={entry} scale={1} />);
    expect(screen.getByText('线粒体功能')).toBeInTheDocument();
  });

  it('shows pending badge', () => {
    const entry = {
      id: '1', title: 'Test', content: '', entry_type: 'known' as const,
      layer_id: 'l1', dimension_id: 'd1', source_type: 'portfolio_index' as const,
      source_link: '/test', status: 'pending' as const, tags: [], confidence: 30,
      created_at: '', updated_at: '',
    };
    render(<EntryCard entry={entry} scale={1} />);
    expect(screen.getByText('待确认')).toBeInTheDocument();
  });
});
```

- [ ] **Step 9: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: 2 PASS

- [ ] **Step 10: Commit**

```bash
git add frontend/src/components/Canvas/ frontend/src/hooks/useCanvasZoom.ts frontend/tests/
git commit -m "feat: ZUI canvas — LayerRow + EntryCard + zoom/pan hook"
```

---

### Task 13: Bottom Dock Component

**Files:**
- Create: `frontend/src/components/Dock/Dock.tsx`
- Create: `frontend/src/components/Dock/Dock.module.css`
- Create: `frontend/src/hooks/useDockAutoHide.ts`
- Modify: `frontend/src/App.tsx` (integrate Canvas + Dock)
- Create: `frontend/tests/Dock.test.tsx`

**Interfaces:**
- Consumes: Canvas from Task 12
- Produces: Dock with diagnose input, state management for add mode, link mode

- [ ] **Step 1: Create hooks/useDockAutoHide.ts**

```typescript
import { useState, useRef, useCallback, useEffect } from 'react';

export function useDockAutoHide(delay = 2000) {
  const [visible, setVisible] = useState(true);
  const timer = useRef<ReturnType<typeof setTimeout>>();

  const show = useCallback(() => {
    clearTimeout(timer.current);
    setVisible(true);
  }, []);

  const hide = useCallback(() => {
    timer.current = setTimeout(() => setVisible(false), delay);
  }, [delay]);

  useEffect(() => () => clearTimeout(timer.current), []);

  return { visible, show, hide };
}
```

- [ ] **Step 2: Create components/Dock/Dock.tsx**

```tsx
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useDockAutoHide } from '../../hooks/useDockAutoHide';
import styles from './Dock.module.css';

interface Props {
  onDiagnose: (question: string) => void;
  isDiagnosing: boolean;
}

export default function Dock({ onDiagnose, isDiagnosing }: Props) {
  const [question, setQuestion] = useState('');
  const { visible, show, hide } = useDockAutoHide(2000);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (question.trim()) {
      onDiagnose(question.trim());
    }
  };

  return (
    <div className={styles.dockArea} onMouseEnter={show} onMouseLeave={hide}>
      <AnimatePresence>
        {visible && (
          <motion.div
            className={styles.dock}
            initial={{ y: 80, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            exit={{ y: 80, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          >
            <form onSubmit={handleSubmit} className={styles.form}>
              <input
                className={styles.input}
                type="text"
                placeholder="输入问题诊断..."
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                disabled={isDiagnosing}
              />
            </form>
            <div className={styles.divider} />
            <button className={styles.action} title="添加条目">+</button>
          </motion.div>
        )}
      </AnimatePresence>
      {!visible && <div className={styles.handle} />}
    </div>
  );
}
```

- [ ] **Step 3: Create components/Dock/Dock.module.css**

```css
.dockArea {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  height: 80px;
  display: flex;
  justify-content: center;
  align-items: flex-end;
  z-index: 100;
}

.dock {
  background: rgba(255, 255, 255, 0.85);
  backdrop-filter: blur(20px);
  border-radius: 20px 20px 0 0;
  padding: 12px 24px 20px;
  display: flex;
  align-items: center;
  gap: 12px;
  box-shadow: 0 -2px 20px rgba(0, 0, 0, 0.08);
}

.form {
  flex: 1;
}

.input {
  border: none;
  background: #f5f5f7;
  border-radius: 12px;
  padding: 10px 16px;
  font-size: 16px;
  width: 400px;
  outline: none;
  color: #1d1d1f;
}

.input:focus {
  background: #ebebed;
}

.input::placeholder {
  color: #86868b;
}

.divider {
  width: 1px;
  height: 24px;
  background: #e0e0e0;
}

.action {
  width: 36px;
  height: 36px;
  border: none;
  background: #f5f5f7;
  border-radius: 50%;
  font-size: 20px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #1d1d1f;
}

.action:hover {
  background: #e0e0e0;
}

.handle {
  width: 40px;
  height: 4px;
  background: #d1d1d6;
  border-radius: 2px;
  margin-bottom: 8px;
}
```

- [ ] **Step 4: Update App.tsx**

```tsx
import { useState } from 'react';
import Canvas from './components/Canvas/Canvas';
import Dock from './components/Dock/Dock';
import { diagnoseStream } from './api/client';
import type { DiagnosisEvent } from './types';

export default function App() {
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [diagnosisState, setDiagnosisState] = useState<Map<number, DiagnosisEvent['data']>>(new Map());

  const handleDiagnose = (question: string) => {
    setIsDiagnosing(true);
    setDiagnosisState(new Map());
    diagnoseStream(
      question,
      '物质层次',
      (event) => {
        if (event.event === 'layer_complete') {
          setDiagnosisState((prev) => new Map(prev).set(event.data.level, event.data));
        }
        if (event.event === 'diagnose_end') {
          setIsDiagnosing(false);
          alert(event.data.gap_summary);
        }
      },
      (err) => {
        console.error(err);
        setIsDiagnosing(false);
      }
    );
  };

  return (
    <>
      <Canvas />
      <Dock onDiagnose={handleDiagnose} isDiagnosing={isDiagnosing} />
    </>
  );
}
```

- [ ] **Step 5: Create tests/Dock.test.tsx**

```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Dock from '../src/components/Dock/Dock';

describe('Dock', () => {
  it('renders input', () => {
    render(<Dock onDiagnose={() => {}} isDiagnosing={false} />);
    expect(screen.getByPlaceholderText('输入问题诊断...')).toBeInTheDocument();
  });

  it('disables input while diagnosing', () => {
    render(<Dock onDiagnose={() => {}} isDiagnosing={true} />);
    expect(screen.getByPlaceholderText('输入问题诊断...')).toBeDisabled();
  });
});
```

- [ ] **Step 6: Run tests**

Run: `cd frontend && npx vitest run`
Expected: 4 PASS

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/Dock/ frontend/src/hooks/useDockAutoHide.ts frontend/src/App.tsx frontend/tests/Dock.test.tsx
git commit -m "feat: bottom dock with auto-hide + diagnosis trigger"
```

---

### Task 14: EntryForm (Create/Edit Entry Modal)

**Files:**
- Create: `frontend/src/components/EntryForm/EntryForm.tsx`
- Create: `frontend/src/components/EntryForm/EntryForm.module.css`
- Create: `frontend/tests/EntryForm.test.tsx`

**Interfaces:**
- Consumes: `createEntry()`, `updateEntry()`, `confirmEntry()` from Task 11, types from Task 11
- Produces: Modal form for creating/editing entries, triggered from Dock "+" or card click

- [ ] **Step 1: Create components/EntryForm/EntryForm.tsx**

```tsx
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Entry, Layer } from '../../types';
import styles from './EntryForm.module.css';

interface Props {
  layers: Layer[];
  dimensionId: string;
  entry?: Entry | null;
  onSave: (data: Partial<Entry>) => void;
  onClose: () => void;
  onConfirm?: (id: string) => void;
  onIgnore?: (id: string) => void;
}

export default function EntryForm({ layers, dimensionId, entry, onSave, onClose, onConfirm, onIgnore }: Props) {
  const [title, setTitle] = useState(entry?.title || '');
  const [content, setContent] = useState(entry?.content || '');
  const [entryType, setEntryType] = useState(entry?.entry_type || 'known');
  const [layerId, setLayerId] = useState(entry?.layer_id || '');

  useEffect(() => {
    if (entry) {
      setTitle(entry.title);
      setContent(entry.content);
      setEntryType(entry.entry_type);
      setLayerId(entry.layer_id || '');
    }
  }, [entry]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave({ title, content, entry_type: entryType as Entry['entry_type'], layer_id: layerId || null, dimension_id: dimensionId });
    onClose();
  };

  return (
    <AnimatePresence>
      <motion.div className={styles.overlay} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onClick={onClose}>
        <motion.div className={styles.modal} initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} exit={{ scale: 0.9, opacity: 0 }} onClick={(e) => e.stopPropagation()}>
          <h2>{entry ? '编辑条目' : '新建条目'}</h2>
          {entry?.status === 'pending' && (
            <div className={styles.pendingBar}>
              <span>此条目待确认</span>
              <button onClick={() => onConfirm?.(entry.id)}>确认</button>
              <button onClick={() => onIgnore?.(entry.id)}>忽略</button>
            </div>
          )}
          <form onSubmit={handleSubmit}>
            <input className={styles.titleInput} value={title} onChange={(e) => setTitle(e.target.value)} placeholder="标题" required />
            <textarea className={styles.contentInput} value={content} onChange={(e) => setContent(e.target.value)} placeholder="内容（可选）" rows={4} />
            <div className={styles.row}>
              <select value={entryType} onChange={(e) => setEntryType(e.target.value)}>
                <option value="known">已知</option>
                <option value="unknown">未知缺口</option>
                <option value="question">问题</option>
              </select>
              <select value={layerId} onChange={(e) => setLayerId(e.target.value)}>
                <option value="">未分类</option>
                {layers.map((l) => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>
            <div className={styles.actions}>
              <button type="button" onClick={onClose}>取消</button>
              <button type="submit">保存</button>
            </div>
          </form>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
}
```

- [ ] **Step 2: Create EntryForm.module.css + test**

```css
.overlay {
  position: fixed; inset: 0; background: rgba(0,0,0,0.3); display: flex; align-items: center; justify-content: center; z-index: 200;
}
.modal {
  background: white; border-radius: 16px; padding: 32px; width: 480px; max-height: 80vh; overflow-y: auto;
}
.modal h2 { margin: 0 0 16px; font-size: 20px; }
.titleInput, .contentInput { width: 100%; border: 1px solid #e0e0e0; border-radius: 8px; padding: 10px; font-size: 14px; margin-bottom: 12px; box-sizing: border-box; }
.contentInput { resize: vertical; font-family: inherit; }
.row { display: flex; gap: 12px; margin-bottom: 12px; }
.row select { flex: 1; border: 1px solid #e0e0e0; border-radius: 8px; padding: 8px; font-size: 14px; }
.actions { display: flex; gap: 12px; justify-content: flex-end; }
.actions button { padding: 8px 20px; border-radius: 8px; border: none; font-size: 14px; cursor: pointer; }
.actions button[type="submit"] { background: #1d1d1f; color: white; }
.actions button[type="button"] { background: #f5f5f7; color: #1d1d1f; }
.pendingBar { background: #fff8e0; padding: 8px 12px; border-radius: 8px; margin-bottom: 12px; display: flex; align-items: center; gap: 8px; font-size: 13px; }
.pendingBar button { padding: 4px 12px; border-radius: 6px; border: none; cursor: pointer; font-size: 12px; }
.pendingBar button:first-of-type { background: #34c759; color: white; }
.pendingBar button:last-of-type { background: #e0e0e0; }
```

```tsx
// tests/EntryForm.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import EntryForm from '../src/components/EntryForm/EntryForm';

describe('EntryForm', () => {
  it('renders create mode', () => {
    render(<EntryForm layers={[]} dimensionId="d1" onSave={() => {}} onClose={() => {}} />);
    expect(screen.getByText('新建条目')).toBeInTheDocument();
  });

  it('renders edit mode with entry data', () => {
    const entry = { id: '1', title: 'Test', content: 'content', entry_type: 'known' as const, layer_id: null, dimension_id: 'd1', source_type: 'manual' as const, source_link: '', status: 'confirmed' as const, tags: [], confidence: 100, created_at: '', updated_at: '' };
    render(<EntryForm layers={[]} dimensionId="d1" entry={entry} onSave={() => {}} onClose={() => {}} />);
    expect(screen.getByText('编辑条目')).toBeInTheDocument();
    expect(screen.getByDisplayValue('Test')).toBeInTheDocument();
  });

  it('shows confirm/ignore for pending entry', () => {
    const entry = { id: '1', title: 'Test', content: '', entry_type: 'known' as const, layer_id: null, dimension_id: 'd1', source_type: 'portfolio_index' as const, source_link: '', status: 'pending' as const, tags: [], confidence: 30, created_at: '', updated_at: '' };
    render(<EntryForm layers={[]} dimensionId="d1" entry={entry} onSave={() => {}} onClose={() => {}} onConfirm={() => {}} onIgnore={() => {}} />);
    expect(screen.getByText('此条目待确认')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run tests**

Run: `cd frontend && npx vitest run`
Expected: 7 PASS

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/EntryForm/ frontend/tests/EntryForm.test.tsx
git commit -m "feat: EntryForm modal — create/edit/confirm/ignore"
```

---

### Task 15: Wire Everything Together + Canvas Integration

**Files:**
- Modify: `frontend/src/App.tsx` (integrate all: Canvas loads data, Dock opens EntryForm, cards are clickable, diagnosis highlights)
- Modify: `frontend/src/components/Canvas/Canvas.tsx` (pass entry click handler, diagnosis highlights)
- Modify: `frontend/src/components/Dock/Dock.tsx` (wire "+" to open EntryForm)

**Interfaces:**
- Consumes: All components from Tasks 12-14
- Produces: Full working app flow

- [ ] **Step 1: Update App.tsx to orchestrate all state**

```tsx
import { useState, useEffect, useCallback } from 'react';
import Canvas from './components/Canvas/Canvas';
import Dock from './components/Dock/Dock';
import EntryForm from './components/EntryForm/EntryForm';
import { fetchDimensions, fetchEntries, createEntry, updateEntry, confirmEntry, ignoreEntry, diagnoseStream } from './api/client';
import type { Dimension, Entry, DiagnosisEvent } from './types';

export default function App() {
  const [dimension, setDimension] = useState<Dimension | null>(null);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [isDiagnosing, setIsDiagnosing] = useState(false);
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());
  const [showEntryForm, setShowEntryForm] = useState(false);
  const [editingEntry, setEditingEntry] = useState<Entry | null>(null);

  const loadData = useCallback(() => {
    fetchDimensions().then((dims) => {
      if (dims.length > 0) {
        setDimension(dims[0]);
        fetchEntries({ dimension_id: dims[0].id }).then(setEntries);
      }
    });
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleDiagnose = (question: string) => {
    if (!dimension) return;
    setIsDiagnosing(true);
    const highlights = new Set<string>();
    diagnoseStream(question, dimension.id,
      (event) => {
        if (event.event === 'layer_complete') {
          event.data.existing_entries_highlighted.forEach((id) => highlights.add(id));
          setHighlightedIds(new Set(highlights));
        }
        if (event.event === 'diagnose_end') {
          setIsDiagnosing(false);
          alert(event.data.gap_summary);
        }
      },
      (err) => { console.error(err); setIsDiagnosing(false); }
    );
  };

  const handleEntryClick = (entry: Entry) => {
    setEditingEntry(entry);
    setShowEntryForm(true);
  };

  const handleSave = async (data: Partial<Entry>) => {
    if (editingEntry) {
      await updateEntry(editingEntry.id, data);
    } else {
      await createEntry({ ...data, dimension_id: dimension!.id } as Entry);
    }
    loadData();
  };

  const handleConfirm = async (id: string) => {
    await confirmEntry(id);
    loadData();
  };

  const handleIgnore = async (id: string) => {
    await ignoreEntry(id);
    loadData();
  };

  return (
    <>
      <Canvas dimension={dimension} entries={entries} highlightedIds={highlightedIds} onEntryClick={handleEntryClick} />
      <Dock onDiagnose={handleDiagnose} isDiagnosing={isDiagnosing} onAdd={() => { setEditingEntry(null); setShowEntryForm(true); }} />
      {showEntryForm && (
        <EntryForm
          layers={dimension?.layers || []}
          dimensionId={dimension?.id || ''}
          entry={editingEntry}
          onSave={handleSave}
          onClose={() => setShowEntryForm(false)}
          onConfirm={handleConfirm}
          onIgnore={handleIgnore}
        />
      )}
    </>
  );
}
```

- [ ] **Step 2: Update Canvas.tsx to accept props instead of fetching**

```tsx
import { useCanvasZoom } from '../../hooks/useCanvasZoom';
import type { Dimension, Entry } from '../../types';
import LayerRow from './LayerRow';
import styles from './Canvas.module.css';

interface Props {
  dimension: Dimension | null;
  entries: Entry[];
  highlightedIds: Set<string>;
  onEntryClick: (entry: Entry) => void;
}

export default function Canvas({ dimension, entries, highlightedIds, onEntryClick }: Props) {
  const { scale, position, isPanning, onWheel, onMouseDown, onMouseMove, onMouseUp } = useCanvasZoom(0.6, 0.2, 2);

  if (!dimension) return <div className={styles.loading}>加载中...</div>;

  const entriesByLayer: Record<string, Entry[]> = {};
  for (const e of entries) {
    if (e.layer_id) (entriesByLayer[e.layer_id] ??= []).push(e);
  }

  return (
    <div className={styles.canvasContainer} onWheel={onWheel} onMouseDown={onMouseDown} onMouseMove={onMouseMove} onMouseUp={onMouseUp}>
      <div className={styles.canvas} style={{ transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`, cursor: isPanning ? 'grabbing' : 'grab' }}>
        {dimension.layers.map((layer) => (
          <LayerRow key={layer.id} layer={layer} entries={entriesByLayer[layer.id] || []} scale={scale} highlightedIds={highlightedIds} onEntryClick={onEntryClick} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: Update LayerRow to pass new props to EntryCard**

```tsx
interface Props {
  layer: Layer;
  entries: Entry[];
  scale: number;
  highlightedIds: Set<string>;
  onEntryClick: (entry: Entry) => void;
}

// In the cards div:
{entries.map((entry) => (
  <EntryCard key={entry.id} entry={entry} scale={scale} highlighted={highlightedIds.has(entry.id)} onClick={() => onEntryClick(entry)} />
))}
```

- [ ] **Step 4: Update EntryCard to accept highlighted + onClick**

```tsx
interface Props {
  entry: Entry;
  scale: number;
  highlighted?: boolean;
  onClick: () => void;
}

// On the card div:
<div
  className={`${styles.card} ${isPending ? styles.pending : ''} ${highlighted ? styles.highlighted : ''}`}
  style={{ borderLeft: `3px solid ${borderColor}`, opacity: highlighted === false ? 0.3 : 1 }}
  onClick={onClick}
  title={entry.content}
>
```

Add to EntryCard.module.css:
```css
.highlighted {
  box-shadow: 0 0 0 2px #007aff, 0 4px 16px rgba(0, 122, 255, 0.2);
}
```

- [ ] **Step 5: Update Dock to accept onAdd prop**

```tsx
interface Props {
  onDiagnose: (question: string) => void;
  isDiagnosing: boolean;
  onAdd: () => void;
}

// Change "+" button:
<button className={styles.action} title="添加条目" onClick={onAdd}>+</button>
```

- [ ] **Step 6: Full integration smoke test**

Run: `cd backend && python run.py` and `cd frontend && npm run dev`
Expected: Open browser, canvas shows 10 layers, dock at bottom, click "+" opens form, type question triggers diagnosis

- [ ] **Step 7: Commit**

```bash
git add frontend/src/
git commit -m "feat: full integration — canvas, dock, entry form, diagnosis flow wired together"
```

---

### Task 16: Final Polish + README

**Files:**
- Modify: `frontend/src/App.module.css` (global styles)
- Create: `frontend/tests/Canvas.test.tsx`

- [ ] **Step 1: Add global styles to App.module.css**

```css
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, 'SF Pro Text', 'Segoe UI', sans-serif; background: #f5f5f7; color: #1d1d1f; overflow: hidden; }
```

- [ ] **Step 2: Add Canvas smoke test**

```tsx
// tests/Canvas.test.tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import Canvas from '../src/components/Canvas/Canvas';

describe('Canvas', () => {
  it('shows loading when no dimension', () => {
    render(<Canvas dimension={null} entries={[]} highlightedIds={new Set()} onEntryClick={() => {}} />);
    expect(screen.getByText('加载中...')).toBeInTheDocument();
  });

  it('renders layer names', () => {
    const dim = { id: 'd1', name: '物质层次', description: '', sort_order: 0, layers: [{ id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 }] };
    render(<Canvas dimension={dim} entries={[]} highlightedIds={new Set()} onEntryClick={() => {}} />);
    expect(screen.getByText('细胞')).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Run all frontend tests**

Run: `cd frontend && npx vitest run`
Expected: 9 PASS

- [ ] **Step 4: Run all backend tests**

Run: `cd backend && python -m pytest tests/ -v`
Expected: All PASS

- [ ] **Step 5: Final commit**

```bash
git add -A
git commit -m "feat: thinking-space V1 complete — ZUI canvas, diagnosis engine, file indexer"
```

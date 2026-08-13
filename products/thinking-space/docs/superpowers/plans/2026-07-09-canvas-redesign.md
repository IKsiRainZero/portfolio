# 思考空间 V2 Canvas 重做 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把思考空间从固定层级色带重构为无限自由白板——卡片任意定位/缩放/连线/内联编辑/纵深，层级升级为用户可编排的多条有序逻辑链。

**Architecture:** 后端在现有 FastAPI+SQLAlchemy 上加字段与路由（Entry 几何字段、entry_tags 关联表、layer_links 表、Dimension/Layer CRUD）。前端拆两个视图：CanvasView（无限画布 + 卡片交互）与 ChainEditorView（层级链编排），用 App 顶层状态切换。诊断代码保留但前端隐藏。

**Tech Stack:** Python 3.9+ 兼容 FastAPI 0.115 / SQLAlchemy 2.0 / SQLite / pytest；Vite 5 / React 18 / TypeScript strict / Vitest + RTL / framer-motion。

## Global Constraints

- 所有新建或修改的后端 `.py` 文件，若用到 `X | None` 或运行时求值的内建泛型注解，**首行必须** `from __future__ import annotations`（裸 `pytest` 会解析到系统 Python 3.9）。
- 后端测试命令一律用 `python -m pytest`，**不要**用裸 `pytest`（PATH 上的 pytest 指向 3.9）。
- 前端一次性测试用 `npm run test -- --run`；类型检查用 `npx tsc --noEmit`。
- 无 Alembic：模型加字段后，运行前需删除 dev 库 `products/thinking-space/data/thinking-space.db` 让 `create_all` 重建。测试库每次 drop/create，无需处理。
- 测试禁止真实 LLM 调用；诊断相关代码保持不动，仅前端隐藏入口。
- 连线一律 SVG **三次贝塞尔曲线**，禁止直线。
- 提交只 `git add` 明确文件，禁止 `git add -A`（monorepo 有其他项目）。
- 工作目录：`C:\Users\16008\Desktop\personal\Write\portfolio\.claude\worktrees\thinking-space-v1\products\thinking-space`，分支 `thinking-space-v1`。
- 现有 SQLAlchemy 模型风格：`Mapped[...]` + `mapped_column(...)`，UUID 主键 `default=lambda: str(uuid.uuid4())`。

## File Structure

**后端：**
- `backend/app/models/entry.py` — 加几何字段 + entry_tags 关联表 + tag_ids 属性（修改）
- `backend/app/models/layer_link.py` — 层级间连线模型（新建）
- `backend/app/models/__init__.py` — 注册 LayerLink（修改）
- `backend/app/schemas.py` — Entry 几何/tag 字段、Dimension/Layer/LayerLink 增改 schema（修改）
- `backend/app/routes/entries.py` — geometry 端点 + tag_ids 同步（修改）
- `backend/app/routes/dimensions.py` — 加 POST/PUT/DELETE（修改）
- `backend/app/routes/layers.py` — 层级 CRUD + reorder（新建）
- `backend/app/routes/layer_links.py` — 层级连线路由（新建）
- `backend/app/main.py` — 注册 layers、layer_links 路由（修改）

**前端：**
- `frontend/src/types/index.ts` — Entry 几何/tag 字段、LayerLink 类型（修改）
- `frontend/src/api/client.ts` — 几何/tag/dimension CRUD/layer CRUD/layer_link 接口（修改）
- `frontend/src/hooks/useCanvasZoom.ts` — 增强 preventDefault（修改）
- `frontend/src/hooks/useUndoRedo.ts` — 操作栈（新建）
- `frontend/src/components/Canvas/CardNode.tsx` — 自由卡片（新建，替代 EntryCard）
- `frontend/src/components/Canvas/CardEditor.tsx` — 内联编辑器（新建，替代 EntryForm）
- `frontend/src/components/Canvas/ConnectionLayer.tsx` — SVG 贝塞尔连线层（新建）
- `frontend/src/components/Canvas/Canvas.tsx` — 无限画布重写（修改）
- `frontend/src/components/Canvas/TagPool.tsx` — 标签面板（新建）
- `frontend/src/components/Dock/Dock.tsx` — 视图切换 + 隐藏诊断（修改）
- `frontend/src/components/ChainEditor/ChainList.tsx` — 链增删改切换（新建）
- `frontend/src/components/ChainEditor/LayerList.tsx` — 层级重排/增删改（新建）
- `frontend/src/components/ChainEditor/LayerLinkArea.tsx` — 层级贝塞尔连线（新建）
- `frontend/src/components/ChainEditor/ChainEditorView.tsx` — 编排页容器（新建）
- `frontend/src/App.tsx` — 视图路由 + undo/redo 键盘 + 装配（修改）
- 删除：`LayerRow.tsx` `LayerRow.module.css` `EntryCard.tsx` `EntryCard.module.css` `EntryForm.tsx` `EntryForm.module.css` 及对应测试

---

### Task 1: Entry 几何字段 + geometry 端点

**Files:**
- Modify: `backend/app/models/entry.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routes/entries.py`
- Test: `backend/tests/test_entry_geometry.py` (create)

**Interfaces:**
- Consumes: 现有 Entry 模型、EntryResponse schema、get_db。
- Produces: Entry 新增列 `x,y,width,height,z_depth: float`；`PUT /api/entries/{id}/geometry`（body `EntryGeometryUpdate`，返回 `EntryResponse`）；schema `EntryGeometryUpdate(x,y,width,height,z_depth: float|None)`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_entry_geometry.py`:
```python
def test_update_geometry(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]
    e = client.post("/api/entries", json={"title": "G", "dimension_id": dim_id}).json()
    assert e["x"] == 0 and e["width"] == 200

    r = client.put(f"/api/entries/{e['id']}/geometry",
                   json={"x": 120.5, "y": 80.0, "width": 260, "height": 150, "z_depth": 0.4})
    assert r.status_code == 200
    d = r.json()
    assert d["x"] == 120.5 and d["y"] == 80.0
    assert d["width"] == 260 and d["z_depth"] == 0.4

def test_update_geometry_partial(client):
    dims = client.get("/api/dimensions").json()
    e = client.post("/api/entries", json={"title": "P", "dimension_id": dims[0]["id"]}).json()
    r = client.put(f"/api/entries/{e['id']}/geometry", json={"x": 10, "y": 20})
    assert r.json()["x"] == 10 and r.json()["width"] == 200  # 未传保持默认

def test_geometry_404(client):
    r = client.put("/api/entries/nope/geometry", json={"x": 1, "y": 2})
    assert r.status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_entry_geometry.py -v`
Expected: FAIL（字段/端点不存在，422 或 KeyError）

- [ ] **Step 3: 模型加字段**

`backend/app/models/entry.py` — import 加 `Float`，Entry 类加列（放在 `confidence` 后、`created_at` 前）：
```python
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Float
```
```python
    x: Mapped[float] = mapped_column(Float, default=0.0)
    y: Mapped[float] = mapped_column(Float, default=0.0)
    width: Mapped[float] = mapped_column(Float, default=200.0)
    height: Mapped[float] = mapped_column(Float, default=120.0)
    z_depth: Mapped[float] = mapped_column(Float, default=0.0)
```

- [ ] **Step 4: schema 加字段 + 几何更新体**

`backend/app/schemas.py` — `EntryResponse` 加（在 `confidence` 后）：
```python
    x: float
    y: float
    width: float
    height: float
    z_depth: float
```
`EntryCreate` 加（都带默认，创建时可省）：
```python
    x: float = 0.0
    y: float = 0.0
    width: float = 200.0
    height: float = 120.0
    z_depth: float = 0.0
```
新增 schema：
```python
class EntryGeometryUpdate(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = None
    height: Optional[float] = None
    z_depth: Optional[float] = None
```

- [ ] **Step 5: entries 路由加 geometry 端点 + create 写几何**

`backend/app/routes/entries.py` — import 加 `EntryGeometryUpdate`；`create_entry` 里 Entry(...) 补 `x=body.x, y=body.y, width=body.width, height=body.height, z_depth=body.z_depth,`；在 `confirm_entry` 前加：
```python
@router.put("/{entry_id}/geometry", response_model=EntryResponse)
def update_geometry(entry_id: str, body: EntryGeometryUpdate, db: Session = Depends(get_db)):
    entry = db.query(Entry).filter(Entry.id == entry_id).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(entry, key, value)
    db.commit()
    db.refresh(entry)
    return entry
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_entry_geometry.py -v`
Expected: PASS (3/3)

- [ ] **Step 7: 全后端测试回归**

Run: `python -m pytest -v`
Expected: PASS（原 13 + 新 3）。若 test_entries 因 EntryResponse 缺字段报错，说明已修好不会。

- [ ] **Step 8: 提交**

```bash
git add backend/app/models/entry.py backend/app/schemas.py backend/app/routes/entries.py backend/tests/test_entry_geometry.py
git commit -m "feat(backend): entry geometry fields + geometry endpoint"
```

---

### Task 2: entry_tags 多标签关联

**Files:**
- Modify: `backend/app/models/entry.py`
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routes/entries.py`
- Test: `backend/tests/test_entry_tags.py` (create)

**Interfaces:**
- Consumes: Task 1 后的 Entry；Layer 模型；EntryCreate/EntryUpdate/EntryResponse。
- Produces: 关联表 `entry_tags(entry_id, layer_id)`；Entry.tag_layers 关系 + `tag_ids` 属性（`list[str]`）；EntryCreate/Update 接受 `tag_ids: list[str]`；EntryResponse 输出 `tag_ids: list[str]`；create/update 同步写 entry_tags。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_entry_tags.py`:
```python
def _layer_ids(client):
    dims = client.get("/api/dimensions").json()
    return dims[0]["id"], [l["id"] for l in dims[0]["layers"]]

def test_create_with_tags(client):
    dim_id, layers = _layer_ids(client)
    e = client.post("/api/entries", json={
        "title": "多标签", "dimension_id": dim_id, "tag_ids": [layers[0], layers[4]]
    }).json()
    assert set(e["tag_ids"]) == {layers[0], layers[4]}

def test_update_tags(client):
    dim_id, layers = _layer_ids(client)
    e = client.post("/api/entries", json={"title": "T", "dimension_id": dim_id, "tag_ids": [layers[0]]}).json()
    upd = client.put(f"/api/entries/{e['id']}", json={"tag_ids": [layers[1], layers[2]]}).json()
    assert set(upd["tag_ids"]) == {layers[1], layers[2]}

def test_default_no_tags(client):
    dim_id, _ = _layer_ids(client)
    e = client.post("/api/entries", json={"title": "N", "dimension_id": dim_id}).json()
    assert e["tag_ids"] == []
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_entry_tags.py -v`
Expected: FAIL（tag_ids 未知）

- [ ] **Step 3: 定义关联表 + 关系 + 属性**

`backend/app/models/entry.py` — import 加 `Table, Column`：
```python
from sqlalchemy import String, Integer, DateTime, ForeignKey, Text, JSON, Float, Table, Column
```
在 `class Entry` **之前**定义关联表：
```python
entry_tags = Table(
    "entry_tags",
    Base.metadata,
    Column("entry_id", String(36), ForeignKey("entries.id"), primary_key=True),
    Column("layer_id", String(36), ForeignKey("layers.id"), primary_key=True),
)
```
`class Entry` 内 relationship 区加：
```python
    tag_layers = relationship("Layer", secondary=entry_tags)

    @property
    def tag_ids(self) -> list:
        return [l.id for l in self.tag_layers]
```

- [ ] **Step 4: schema 加 tag_ids**

`backend/app/schemas.py`：
- `EntryCreate` 加 `tag_ids: list[str] = []`
- `EntryUpdate` 加 `tag_ids: Optional[list[str]] = None`
- `EntryResponse` 加 `tag_ids: list[str] = []`

- [ ] **Step 5: 路由同步 entry_tags**

`backend/app/routes/entries.py` — import 加 `from app.models import Layer`（若未导入）。`create_entry` 里 `db.add(entry)` 后、`db.commit()` 前插入：
```python
    if body.tag_ids:
        entry.tag_layers = db.query(Layer).filter(Layer.id.in_(body.tag_ids)).all()
```
`update_entry` 里，替换 `update_data` 循环为（先取出 tag_ids 单独处理）：
```python
    update_data = body.model_dump(exclude_unset=True)
    tag_ids = update_data.pop("tag_ids", None)
    for key, value in update_data.items():
        setattr(entry, key, value)
    if tag_ids is not None:
        entry.tag_layers = db.query(Layer).filter(Layer.id.in_(tag_ids)).all()
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_entry_tags.py -v`
Expected: PASS (3/3)

- [ ] **Step 7: 全后端回归**

Run: `python -m pytest -v`
Expected: PASS（原有 + 新增全绿）

- [ ] **Step 8: 提交**

```bash
git add backend/app/models/entry.py backend/app/schemas.py backend/app/routes/entries.py backend/tests/test_entry_tags.py
git commit -m "feat(backend): entry_tags many-to-many tagging"
```

---

### Task 3: LayerLink 模型 + 路由

**Files:**
- Create: `backend/app/models/layer_link.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routes/layer_links.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_layer_links.py` (create)

**Interfaces:**
- Consumes: Base、Layer、get_db、Dimension（查同链层级）。
- Produces: LayerLink 模型（id, source_layer_id, target_layer_id, relation_type, note, created_at）；`GET /api/dimensions/{dim_id}/layer-links`、`POST /api/layer-links`、`DELETE /api/layer-links/{id}`；schema `LayerLinkCreate(source_layer_id, target_layer_id, relation_type="leads_to", note="")`、`LayerLinkResponse`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_layer_links.py`:
```python
def test_create_and_list_layer_link(client):
    dims = client.get("/api/dimensions").json()
    dim_id = dims[0]["id"]
    layers = dims[0]["layers"]
    r = client.post("/api/layer-links", json={
        "source_layer_id": layers[0]["id"], "target_layer_id": layers[1]["id"],
        "relation_type": "leads_to", "note": "细胞构成组织"
    })
    assert r.status_code == 201
    listed = client.get(f"/api/dimensions/{dim_id}/layer-links").json()
    assert len(listed) == 1
    assert listed[0]["note"] == "细胞构成组织"

def test_delete_layer_link(client):
    dims = client.get("/api/dimensions").json()
    layers = dims[0]["layers"]
    link = client.post("/api/layer-links", json={
        "source_layer_id": layers[0]["id"], "target_layer_id": layers[2]["id"]
    }).json()
    assert client.delete(f"/api/layer-links/{link['id']}").status_code == 204
    assert client.delete(f"/api/layer-links/{link['id']}").status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_layer_links.py -v`
Expected: FAIL（404，路由不存在）

- [ ] **Step 3: 建模型**

`backend/app/models/layer_link.py`:
```python
from __future__ import annotations
import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base


class LayerLink(Base):
    __tablename__ = "layer_links"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source_layer_id: Mapped[str] = mapped_column(String(36), ForeignKey("layers.id"), nullable=False)
    target_layer_id: Mapped[str] = mapped_column(String(36), ForeignKey("layers.id"), nullable=False)
    relation_type: Mapped[str] = mapped_column(String(50), nullable=False, default="leads_to")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: 注册模型**

`backend/app/models/__init__.py`:
```python
from .dimension import Dimension
from .layer import Layer
from .entry import Entry
from .cross_link import CrossLink
from .layer_link import LayerLink

__all__ = ["Dimension", "Layer", "Entry", "CrossLink", "LayerLink"]
```

- [ ] **Step 5: schema**

`backend/app/schemas.py` 末尾追加：
```python
class LayerLinkCreate(BaseModel):
    source_layer_id: str
    target_layer_id: str
    relation_type: str = "leads_to"
    note: str = ""

class LayerLinkResponse(BaseModel):
    id: str
    source_layer_id: str
    target_layer_id: str
    relation_type: str
    note: str
    model_config = {"from_attributes": True}
```

- [ ] **Step 6: 路由**

`backend/app/routes/layer_links.py`:
```python
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import LayerLink, Layer
from app.schemas import LayerLinkCreate, LayerLinkResponse

router = APIRouter(tags=["layer-links"])

@router.get("/api/dimensions/{dim_id}/layer-links", response_model=list[LayerLinkResponse])
def list_layer_links(dim_id: str, db: Session = Depends(get_db)):
    layer_ids = [l.id for l in db.query(Layer.id).filter(Layer.dimension_id == dim_id).all()]
    return db.query(LayerLink).filter(LayerLink.source_layer_id.in_(layer_ids)).all()

@router.post("/api/layer-links", response_model=LayerLinkResponse, status_code=201)
def create_layer_link(body: LayerLinkCreate, db: Session = Depends(get_db)):
    link = LayerLink(source_layer_id=body.source_layer_id, target_layer_id=body.target_layer_id,
                     relation_type=body.relation_type, note=body.note)
    db.add(link)
    db.commit()
    db.refresh(link)
    return link

@router.delete("/api/layer-links/{link_id}", status_code=204)
def delete_layer_link(link_id: str, db: Session = Depends(get_db)):
    link = db.query(LayerLink).filter(LayerLink.id == link_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="LayerLink not found")
    db.delete(link)
    db.commit()
```

- [ ] **Step 7: 注册路由**

`backend/app/main.py` — import 行改为：
```python
from app.routes import dimensions, entries, index, diagnose, cross_links, export, layer_links
```
末尾加：
```python
app.include_router(layer_links.router)
```

- [ ] **Step 8: 运行测试确认通过**

Run: `python -m pytest tests/test_layer_links.py -v`
Expected: PASS (2/2)

- [ ] **Step 9: 提交**

```bash
git add backend/app/models/layer_link.py backend/app/models/__init__.py backend/app/schemas.py backend/app/routes/layer_links.py backend/app/main.py backend/tests/test_layer_links.py
git commit -m "feat(backend): layer_links model + routes"
```

---

### Task 4: Dimension CRUD

**Files:**
- Modify: `backend/app/schemas.py`
- Modify: `backend/app/routes/dimensions.py`
- Test: `backend/tests/test_dimensions_crud.py` (create)

**Interfaces:**
- Consumes: Dimension 模型、DimensionResponse、get_db。
- Produces: `POST /api/dimensions`、`PUT /api/dimensions/{id}`、`DELETE /api/dimensions/{id}`；schema `DimensionCreate(name, description="", sort_order=0)`、`DimensionUpdate(name?, description?, sort_order?)`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_dimensions_crud.py`:
```python
def test_create_dimension(client):
    r = client.post("/api/dimensions", json={"name": "时间维度", "description": "以时间为轴"})
    assert r.status_code == 201
    assert r.json()["name"] == "时间维度"
    assert r.json()["layers"] == []

def test_update_dimension(client):
    d = client.post("/api/dimensions", json={"name": "旧名"}).json()
    r = client.put(f"/api/dimensions/{d['id']}", json={"name": "新名"})
    assert r.json()["name"] == "新名"

def test_delete_dimension(client):
    d = client.post("/api/dimensions", json={"name": "待删"}).json()
    assert client.delete(f"/api/dimensions/{d['id']}").status_code == 204
    assert client.get(f"/api/dimensions/{d['id']}").status_code == 404
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_dimensions_crud.py -v`
Expected: FAIL（405/404，端点不存在）

- [ ] **Step 3: schema**

`backend/app/schemas.py` — 在 `DimensionResponse` 后加：
```python
class DimensionCreate(BaseModel):
    name: str
    description: str = ""
    sort_order: int = 0

class DimensionUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    sort_order: Optional[int] = None
```

- [ ] **Step 4: 路由加 CRUD**

`backend/app/routes/dimensions.py` — import 加 `DimensionCreate, DimensionUpdate`，`from app.schemas import DimensionResponse, LayerResponse, DimensionCreate, DimensionUpdate`。追加：
```python
@router.post("", response_model=DimensionResponse, status_code=201)
def create_dimension(body: DimensionCreate, db: Session = Depends(get_db)):
    dim = Dimension(name=body.name, description=body.description, sort_order=body.sort_order)
    db.add(dim)
    db.commit()
    db.refresh(dim)
    return DimensionResponse(id=dim.id, name=dim.name, description=dim.description or "",
                             sort_order=dim.sort_order, layers=[])

@router.put("/{dimension_id}", response_model=DimensionResponse)
def update_dimension(dimension_id: str, body: DimensionUpdate, db: Session = Depends(get_db)):
    dim = db.query(Dimension).filter(Dimension.id == dimension_id).first()
    if not dim:
        raise HTTPException(status_code=404, detail="Dimension not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(dim, key, value)
    db.commit()
    db.refresh(dim)
    layers = [LayerResponse(id=l.id, dimension_id=l.dimension_id, name=l.name, level=l.level,
                            description=l.description or "", entry_count=len(l.entries) if l.entries else 0)
              for l in dim.layers]
    return DimensionResponse(id=dim.id, name=dim.name, description=dim.description or "",
                             sort_order=dim.sort_order, layers=layers)

@router.delete("/{dimension_id}", status_code=204)
def delete_dimension(dimension_id: str, db: Session = Depends(get_db)):
    dim = db.query(Dimension).filter(Dimension.id == dimension_id).first()
    if not dim:
        raise HTTPException(status_code=404, detail="Dimension not found")
    db.delete(dim)
    db.commit()
```

- [ ] **Step 5: 运行测试确认通过**

Run: `python -m pytest tests/test_dimensions_crud.py -v`
Expected: PASS (3/3)

- [ ] **Step 6: 全后端回归**

Run: `python -m pytest -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/schemas.py backend/app/routes/dimensions.py backend/tests/test_dimensions_crud.py
git commit -m "feat(backend): dimension CRUD"
```

---

### Task 5: Layer CRUD + reorder

**Files:**
- Modify: `backend/app/schemas.py`
- Create: `backend/app/routes/layers.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_layers_crud.py` (create)

**Interfaces:**
- Consumes: Dimension、Layer、LayerResponse、get_db。
- Produces: `POST /api/dimensions/{dim_id}/layers`、`PUT /api/layers/{id}`、`DELETE /api/layers/{id}`、`PUT /api/dimensions/{dim_id}/layers/reorder`（body `{"layer_ids": [...]}`）；schema `LayerCreate(name, description="")`、`LayerUpdate(name?, description?)`、`LayerReorderRequest(layer_ids: list[str])`。

- [ ] **Step 1: 写失败测试**

`backend/tests/test_layers_crud.py`:
```python
def test_create_layer(client):
    dim = client.post("/api/dimensions", json={"name": "自定义链"}).json()
    r = client.post(f"/api/dimensions/{dim['id']}/layers", json={"name": "起点", "description": "第一层"})
    assert r.status_code == 201
    assert r.json()["name"] == "起点"
    assert r.json()["level"] == 0

def test_update_layer(client):
    dims = client.get("/api/dimensions").json()
    lid = dims[0]["layers"][0]["id"]
    r = client.put(f"/api/layers/{lid}", json={"name": "细胞(改)", "description": "新描述"})
    assert r.json()["name"] == "细胞(改)"
    assert r.json()["description"] == "新描述"

def test_delete_layer(client):
    dim = client.post("/api/dimensions", json={"name": "L"}).json()
    lay = client.post(f"/api/dimensions/{dim['id']}/layers", json={"name": "临时"}).json()
    assert client.delete(f"/api/layers/{lay['id']}").status_code == 204
    assert client.delete(f"/api/layers/{lay['id']}").status_code == 404

def test_reorder_layers(client):
    dim = client.post("/api/dimensions", json={"name": "R"}).json()
    a = client.post(f"/api/dimensions/{dim['id']}/layers", json={"name": "A"}).json()
    b = client.post(f"/api/dimensions/{dim['id']}/layers", json={"name": "B"}).json()
    r = client.put(f"/api/dimensions/{dim['id']}/layers/reorder", json={"layer_ids": [b["id"], a["id"]]})
    assert r.status_code == 200
    got = client.get(f"/api/dimensions/{dim['id']}").json()["layers"]
    assert [l["name"] for l in got] == ["B", "A"]
```

- [ ] **Step 2: 运行确认失败**

Run: `python -m pytest tests/test_layers_crud.py -v`
Expected: FAIL（404，路由不存在）

- [ ] **Step 3: schema**

`backend/app/schemas.py` 末尾追加：
```python
class LayerCreate(BaseModel):
    name: str
    description: str = ""

class LayerUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None

class LayerReorderRequest(BaseModel):
    layer_ids: list[str]
```

- [ ] **Step 4: 路由**

`backend/app/routes/layers.py`:
```python
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Dimension, Layer
from app.schemas import LayerResponse, LayerCreate, LayerUpdate, LayerReorderRequest

router = APIRouter(tags=["layers"])

def _to_response(l: Layer) -> LayerResponse:
    return LayerResponse(id=l.id, dimension_id=l.dimension_id, name=l.name, level=l.level,
                         description=l.description or "", entry_count=len(l.entries) if l.entries else 0)

@router.post("/api/dimensions/{dim_id}/layers", response_model=LayerResponse, status_code=201)
def create_layer(dim_id: str, body: LayerCreate, db: Session = Depends(get_db)):
    dim = db.query(Dimension).filter(Dimension.id == dim_id).first()
    if not dim:
        raise HTTPException(status_code=404, detail="Dimension not found")
    next_level = db.query(Layer).filter(Layer.dimension_id == dim_id).count()
    layer = Layer(dimension_id=dim_id, name=body.name, level=next_level,
                  description=body.description, sort_order=next_level)
    db.add(layer)
    db.commit()
    db.refresh(layer)
    return _to_response(layer)

@router.put("/api/layers/{layer_id}", response_model=LayerResponse)
def update_layer(layer_id: str, body: LayerUpdate, db: Session = Depends(get_db)):
    layer = db.query(Layer).filter(Layer.id == layer_id).first()
    if not layer:
        raise HTTPException(status_code=404, detail="Layer not found")
    for key, value in body.model_dump(exclude_unset=True).items():
        setattr(layer, key, value)
    db.commit()
    db.refresh(layer)
    return _to_response(layer)

@router.delete("/api/layers/{layer_id}", status_code=204)
def delete_layer(layer_id: str, db: Session = Depends(get_db)):
    layer = db.query(Layer).filter(Layer.id == layer_id).first()
    if not layer:
        raise HTTPException(status_code=404, detail="Layer not found")
    db.delete(layer)
    db.commit()

@router.put("/api/dimensions/{dim_id}/layers/reorder")
def reorder_layers(dim_id: str, body: LayerReorderRequest, db: Session = Depends(get_db)):
    for index, lid in enumerate(body.layer_ids):
        layer = db.query(Layer).filter(Layer.id == lid, Layer.dimension_id == dim_id).first()
        if layer:
            layer.level = index
            layer.sort_order = index
    db.commit()
    return {"reordered": len(body.layer_ids)}
```

- [ ] **Step 5: 注册路由**

`backend/app/main.py` — import 加 `layers`：
```python
from app.routes import dimensions, entries, index, diagnose, cross_links, export, layer_links, layers
```
加：
```python
app.include_router(layers.router)
```

- [ ] **Step 6: 运行测试确认通过**

Run: `python -m pytest tests/test_layers_crud.py -v`
Expected: PASS (4/4)

- [ ] **Step 7: 全后端回归**

Run: `python -m pytest -v`
Expected: PASS（全部）

- [ ] **Step 8: 提交**

```bash
git add backend/app/schemas.py backend/app/routes/layers.py backend/app/main.py backend/tests/test_layers_crud.py
git commit -m "feat(backend): layer CRUD + reorder"
```

---

### Task 6: 前端类型 + API client 扩展

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/api/client.ts`
- Test: `frontend/tests/client.test.ts` (create)

**Interfaces:**
- Consumes: 后端 Task 1-5 的所有端点。
- Produces: `Entry` 加 `x,y,width,height,z_depth: number; tag_ids: string[]`；`LayerLink` 类型；client 函数 `updateGeometry(id, geo)`、`createDimension`、`updateDimension`、`deleteDimension`、`createLayer`、`updateLayer`、`deleteLayer`、`reorderLayers`、`fetchLayerLinks`、`createLayerLink`、`deleteLayerLink`、`createCrossLink`、`deleteCrossLink`。

- [ ] **Step 1: 写失败测试**

`frontend/tests/client.test.ts`:
```ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as client from '../src/api/client';

beforeEach(() => {
  global.fetch = vi.fn(async () => ({
    ok: true, status: 200, json: async () => ({ ok: true }),
  })) as unknown as typeof fetch;
});

describe('client geometry + chain endpoints', () => {
  it('updateGeometry calls PUT /geometry', async () => {
    await client.updateGeometry('e1', { x: 10, y: 20 });
    expect(global.fetch).toHaveBeenCalledWith(
      '/api/entries/e1/geometry',
      expect.objectContaining({ method: 'PUT' })
    );
  });

  it('reorderLayers posts layer_ids', async () => {
    await client.reorderLayers('d1', ['b', 'a']);
    const call = (global.fetch as any).mock.calls[0];
    expect(call[0]).toBe('/api/dimensions/d1/layers/reorder');
    expect(JSON.parse(call[1].body)).toEqual({ layer_ids: ['b', 'a'] });
  });

  it('createLayerLink posts to /layer-links', async () => {
    await client.createLayerLink({ source_layer_id: 's', target_layer_id: 't' });
    expect((global.fetch as any).mock.calls[0][0]).toBe('/api/layer-links');
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/client.test.ts`
Expected: FAIL（函数未导出）

- [ ] **Step 3: 类型扩展**

`frontend/src/types/index.ts` — `Entry` 接口加：
```ts
  x: number;
  y: number;
  width: number;
  height: number;
  z_depth: number;
  tag_ids: string[];
```
文件末尾加：
```ts
export interface LayerLink {
  id: string;
  source_layer_id: string;
  target_layer_id: string;
  relation_type: string;
  note: string;
}
```

- [ ] **Step 4: client 扩展**

`frontend/src/api/client.ts` — import 加 `LayerLink`：`import type { Dimension, Entry, DiagnosisEvent, LayerLink } from '../types';`。末尾追加：
```ts
export interface Geometry { x?: number; y?: number; width?: number; height?: number; z_depth?: number; }

export function updateGeometry(id: string, geo: Geometry): Promise<Entry> {
  return request<Entry>(`/entries/${id}/geometry`, { method: 'PUT', body: JSON.stringify(geo) });
}

export function createDimension(data: { name: string; description?: string }): Promise<Dimension> {
  return request<Dimension>('/dimensions', { method: 'POST', body: JSON.stringify(data) });
}
export function updateDimension(id: string, data: { name?: string; description?: string }): Promise<Dimension> {
  return request<Dimension>(`/dimensions/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}
export function deleteDimension(id: string): Promise<void> {
  return request<void>(`/dimensions/${id}`, { method: 'DELETE' });
}

export function createLayer(dimId: string, data: { name: string; description?: string }): Promise<import('../types').Layer> {
  return request(`/dimensions/${dimId}/layers`, { method: 'POST', body: JSON.stringify(data) });
}
export function updateLayer(id: string, data: { name?: string; description?: string }): Promise<import('../types').Layer> {
  return request(`/layers/${id}`, { method: 'PUT', body: JSON.stringify(data) });
}
export function deleteLayer(id: string): Promise<void> {
  return request<void>(`/layers/${id}`, { method: 'DELETE' });
}
export function reorderLayers(dimId: string, layerIds: string[]): Promise<{ reordered: number }> {
  return request(`/dimensions/${dimId}/layers/reorder`, { method: 'PUT', body: JSON.stringify({ layer_ids: layerIds }) });
}

export function fetchLayerLinks(dimId: string): Promise<LayerLink[]> {
  return request<LayerLink[]>(`/dimensions/${dimId}/layer-links`);
}
export function createLayerLink(data: { source_layer_id: string; target_layer_id: string; relation_type?: string; note?: string }): Promise<LayerLink> {
  return request<LayerLink>('/layer-links', { method: 'POST', body: JSON.stringify(data) });
}
export function deleteLayerLink(id: string): Promise<void> {
  return request<void>(`/layer-links/${id}`, { method: 'DELETE' });
}

export function createCrossLink(data: { source_entry_id: string; target_entry_id: string; relation_type?: string; note?: string }): Promise<{ id: string }> {
  return request('/cross-links', { method: 'POST', body: JSON.stringify(data) });
}
export function deleteCrossLink(id: string): Promise<void> {
  return request<void>(`/cross-links/${id}`, { method: 'DELETE' });
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `npm run test -- --run tests/client.test.ts`
Expected: PASS (3/3)

- [ ] **Step 6: 类型检查**

Run: `npx tsc --noEmit`
Expected: 无错误（注：现有 EntryCard/Canvas 测试引用旧 Entry 会缺字段，Task 9/12 会替换；本步若报这些旧文件错误，属预期，记录并继续——它们将在后续任务删除/重写）。

- [ ] **Step 7: 提交**

```bash
git add frontend/src/types/index.ts frontend/src/api/client.ts frontend/tests/client.test.ts
git commit -m "feat(frontend): types + api client for geometry/chain/links"
```

---

### Task 7: useCanvasZoom 增强

**Files:**
- Modify: `frontend/src/hooks/useCanvasZoom.ts`
- Test: `frontend/tests/useCanvasZoom.test.ts` (create)

**Interfaces:**
- Consumes: 无（自包含 hook）。
- Produces: `useCanvasZoom(initialScale, min, max)` 返回增补 `screenToCanvas(clientX, clientY, rect)` → `{x, y}`（屏幕坐标转画布坐标，供双击新建/拖拽定位）。onWheel 以鼠标位置为缩放中心。保留 `scale, position, isPanning, onWheel, onMouseDown, onMouseMove, onMouseUp`。

- [ ] **Step 1: 写失败测试**

`frontend/tests/useCanvasZoom.test.ts`:
```ts
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useCanvasZoom } from '../src/hooks/useCanvasZoom';

describe('useCanvasZoom', () => {
  it('screenToCanvas inverts translate+scale', () => {
    const { result } = renderHook(() => useCanvasZoom(1, 0.1, 3));
    const rect = { left: 0, top: 0 } as DOMRect;
    // position {0,0}, scale 1 → identity
    expect(result.current.screenToCanvas(50, 60, rect)).toEqual({ x: 50, y: 60 });
  });

  it('clamps scale within [min,max]', () => {
    const { result } = renderHook(() => useCanvasZoom(3, 0.1, 3));
    act(() => result.current.onWheel({ deltaY: -1, clientX: 0, clientY: 0, preventDefault() {}, currentTarget: { getBoundingClientRect: () => ({ left: 0, top: 0 }) } } as any));
    expect(result.current.scale).toBeLessThanOrEqual(3);
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/useCanvasZoom.test.ts`
Expected: FAIL（screenToCanvas 不存在）

- [ ] **Step 3: 重写 hook**

`frontend/src/hooks/useCanvasZoom.ts`:
```ts
import { useState, useCallback, WheelEvent } from 'react';

export function useCanvasZoom(initialScale = 1, min = 0.1, max = 3) {
  const [scale, setScale] = useState(initialScale);
  const [position, setPosition] = useState({ x: 0, y: 0 });
  const [isPanning, setIsPanning] = useState(false);
  const [panStart, setPanStart] = useState({ x: 0, y: 0 });

  const onWheel = useCallback((e: WheelEvent) => {
    e.preventDefault();
    const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    setScale((s) => {
      const factor = e.deltaY > 0 ? 0.9 : 1.1;
      const next = Math.min(max, Math.max(min, s * factor));
      setPosition((p) => ({
        x: mx - (mx - p.x) * (next / s),
        y: my - (my - p.y) * (next / s),
      }));
      return next;
    });
  }, [min, max]);

  const onMouseDown = useCallback((e: React.MouseEvent) => {
    if (e.button === 0) {
      e.preventDefault();
      setIsPanning(true);
      setPanStart({ x: e.clientX - position.x, y: e.clientY - position.y });
    }
  }, [position]);

  const onMouseMove = useCallback((e: React.MouseEvent) => {
    if (!isPanning) return;
    setPosition({ x: e.clientX - panStart.x, y: e.clientY - panStart.y });
  }, [isPanning, panStart]);

  const onMouseUp = useCallback(() => setIsPanning(false), []);

  const screenToCanvas = useCallback((clientX: number, clientY: number, rect: { left: number; top: number }) => ({
    x: (clientX - rect.left - position.x) / scale,
    y: (clientY - rect.top - position.y) / scale,
  }), [position, scale]);

  return { scale, position, isPanning, onWheel, onMouseDown, onMouseMove, onMouseUp, screenToCanvas };
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run tests/useCanvasZoom.test.ts`
Expected: PASS (2/2)

- [ ] **Step 5: 提交**

```bash
git add frontend/src/hooks/useCanvasZoom.ts frontend/tests/useCanvasZoom.test.ts
git commit -m "feat(frontend): canvas zoom with cursor-centered scale + screenToCanvas"
```

---

### Task 8: useUndoRedo 操作栈

**Files:**
- Create: `frontend/src/hooks/useUndoRedo.ts`
- Test: `frontend/tests/useUndoRedo.test.ts` (create)

**Interfaces:**
- Consumes: 无。
- Produces: `type CardOp = { kind: 'create' | 'delete'; entry: Entry } | { kind: 'update'; before: Entry; after: Entry }`；`useUndoRedo()` 返回 `{ record(op), undo(): CardOp | null, redo(): CardOp | null, canUndo, canRedo }`。undo 返回**需被反向应用**的 op，并移入 redo 栈；redo 返回需**正向应用**的 op。App（Task 19）负责把 op 应用到状态+后端。

- [ ] **Step 1: 写失败测试**

`frontend/tests/useUndoRedo.test.ts`:
```ts
import { renderHook, act } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import { useUndoRedo } from '../src/hooks/useUndoRedo';

const entry = (id: string) => ({ id, title: id } as any);

describe('useUndoRedo', () => {
  it('records and undoes in LIFO order', () => {
    const { result } = renderHook(() => useUndoRedo());
    act(() => result.current.record({ kind: 'create', entry: entry('a') }));
    act(() => result.current.record({ kind: 'create', entry: entry('b') }));
    expect(result.current.canUndo).toBe(true);
    let op: any;
    act(() => { op = result.current.undo(); });
    expect(op.entry.id).toBe('b');
  });

  it('redo returns last undone op', () => {
    const { result } = renderHook(() => useUndoRedo());
    act(() => result.current.record({ kind: 'create', entry: entry('a') }));
    act(() => { result.current.undo(); });
    let op: any;
    act(() => { op = result.current.redo(); });
    expect(op.entry.id).toBe('a');
    expect(result.current.canRedo).toBe(false);
  });

  it('record clears redo stack', () => {
    const { result } = renderHook(() => useUndoRedo());
    act(() => result.current.record({ kind: 'create', entry: entry('a') }));
    act(() => { result.current.undo(); });
    act(() => result.current.record({ kind: 'create', entry: entry('c') }));
    expect(result.current.canRedo).toBe(false);
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/useUndoRedo.test.ts`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 hook**

`frontend/src/hooks/useUndoRedo.ts`:
```ts
import { useState, useCallback } from 'react';
import type { Entry } from '../types';

export type CardOp =
  | { kind: 'create'; entry: Entry }
  | { kind: 'delete'; entry: Entry }
  | { kind: 'update'; before: Entry; after: Entry };

export function useUndoRedo() {
  const [past, setPast] = useState<CardOp[]>([]);
  const [future, setFuture] = useState<CardOp[]>([]);

  const record = useCallback((op: CardOp) => {
    setPast((p) => [...p, op]);
    setFuture([]);
  }, []);

  const undo = useCallback((): CardOp | null => {
    let popped: CardOp | null = null;
    setPast((p) => {
      if (p.length === 0) return p;
      popped = p[p.length - 1];
      setFuture((f) => [...f, popped as CardOp]);
      return p.slice(0, -1);
    });
    return popped;
  }, []);

  const redo = useCallback((): CardOp | null => {
    let popped: CardOp | null = null;
    setFuture((f) => {
      if (f.length === 0) return f;
      popped = f[f.length - 1];
      setPast((p) => [...p, popped as CardOp]);
      return f.slice(0, -1);
    });
    return popped;
  }, []);

  return { record, undo, redo, canUndo: past.length > 0, canRedo: future.length > 0 };
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run tests/useUndoRedo.test.ts`
Expected: PASS (3/3)

- [ ] **Step 5: 提交**

```bash
git add frontend/src/hooks/useUndoRedo.ts frontend/tests/useUndoRedo.test.ts
git commit -m "feat(frontend): useUndoRedo operation stack"
```

---

### Task 9: CardNode 自由卡片

**Files:**
- Create: `frontend/src/components/Canvas/CardNode.tsx`
- Create: `frontend/src/components/Canvas/CardNode.module.css`
- Test: `frontend/tests/CardNode.test.tsx` (create)

**Interfaces:**
- Consumes: `Entry` 类型。
- Produces: `CardNode` props `{ entry: Entry; scale: number; selected: boolean; onSelect(id): void; onDragEnd(id, x, y): void; onResizeEnd(id, w, h): void; onStartConnect(id): void }`。渲染在 `position:absolute; left:entry.x; top:entry.y`，尺寸 `entry.width×height`，按 `z_depth` 施加 `filter:blur` + `opacity` + 轻微缩放；宽度 < 120 时折叠为仅标题栏；右下角 resize 手柄；悬停显示连线圆点触发 onStartConnect。

- [ ] **Step 1: 写失败测试**

`frontend/tests/CardNode.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CardNode from '../src/components/Canvas/CardNode';

const entry = (over: any = {}) => ({
  id: '1', title: '线粒体', content: 'ATP', entry_type: 'known',
  layer_id: null, dimension_id: 'd1', source_type: 'manual', source_link: '',
  status: 'confirmed', tags: [], tag_ids: [], confidence: 100,
  x: 40, y: 50, width: 200, height: 120, z_depth: 0, created_at: '', updated_at: '', ...over,
});

describe('CardNode', () => {
  it('renders title at its position', () => {
    render(<CardNode entry={entry()} scale={1} selected={false}
      onSelect={() => {}} onDragEnd={() => {}} onResizeEnd={() => {}} onStartConnect={() => {}} />);
    expect(screen.getByText('线粒体')).toBeInTheDocument();
  });

  it('calls onSelect on click', () => {
    const onSelect = vi.fn();
    render(<CardNode entry={entry()} scale={1} selected={false}
      onSelect={onSelect} onDragEnd={() => {}} onResizeEnd={() => {}} onStartConnect={() => {}} />);
    fireEvent.mouseDown(screen.getByText('线粒体'));
    fireEvent.mouseUp(screen.getByText('线粒体'));
    expect(onSelect).toHaveBeenCalledWith('1');
  });

  it('collapses content when width below threshold', () => {
    render(<CardNode entry={entry({ width: 100 })} scale={1} selected={false}
      onSelect={() => {}} onDragEnd={() => {}} onResizeEnd={() => {}} onStartConnect={() => {}} />);
    expect(screen.queryByText('ATP')).not.toBeInTheDocument();
    expect(screen.getByText('线粒体')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/CardNode.test.tsx`
Expected: FAIL（组件不存在）

- [ ] **Step 3: CSS**

`frontend/src/components/Canvas/CardNode.module.css`:
```css
.card {
  position: absolute;
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.12);
  padding: 10px 12px;
  box-sizing: border-box;
  user-select: none;
  cursor: grab;
  overflow: hidden;
  transition: box-shadow 0.15s;
}
.selected { box-shadow: 0 0 0 2px #0a84ff, 0 4px 14px rgba(0,0,0,0.18); }
.title { font-size: 14px; font-weight: 600; color: #1d1d1f; display: block; }
.content { font-size: 12px; color: #6e6e73; margin-top: 6px; white-space: pre-wrap; }
.badge { font-size: 10px; color: #ff9f0a; margin-left: 6px; }
.resizeHandle {
  position: absolute; right: 2px; bottom: 2px; width: 12px; height: 12px;
  cursor: nwse-resize; border-right: 2px solid #c7c7cc; border-bottom: 2px solid #c7c7cc;
}
.connectDot {
  position: absolute; right: -6px; top: 50%; width: 12px; height: 12px;
  margin-top: -6px; border-radius: 50%; background: #0a84ff; cursor: crosshair;
  opacity: 0; transition: opacity 0.15s;
}
.card:hover .connectDot { opacity: 1; }
```

- [ ] **Step 4: 组件**

`frontend/src/components/Canvas/CardNode.tsx`:
```tsx
import { useRef } from 'react';
import type { Entry } from '../../types';
import styles from './CardNode.module.css';

const TYPE_COLORS: Record<string, string> = { known: '#34c759', unknown: '#ff3b30', question: '#ffcc00' };
const COLLAPSE_WIDTH = 120;

interface Props {
  entry: Entry;
  scale: number;
  selected: boolean;
  onSelect: (id: string) => void;
  onDragEnd: (id: string, x: number, y: number) => void;
  onResizeEnd: (id: string, width: number, height: number) => void;
  onStartConnect: (id: string) => void;
}

export default function CardNode({ entry, scale, selected, onSelect, onDragEnd, onResizeEnd, onStartConnect }: Props) {
  const dragRef = useRef<{ startX: number; startY: number; origX: number; origY: number; moved: boolean } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; origW: number; origH: number } | null>(null);

  const depth = entry.z_depth || 0;
  const collapsed = entry.width < COLLAPSE_WIDTH;

  const onCardMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation();
    dragRef.current = { startX: e.clientX, startY: e.clientY, origX: entry.x, origY: entry.y, moved: false };
    window.addEventListener('mousemove', onDragMove);
    window.addEventListener('mouseup', onDragUp);
  };
  const onDragMove = (e: MouseEvent) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = (e.clientX - d.startX) / scale;
    const dy = (e.clientY - d.startY) / scale;
    if (Math.abs(dx) > 2 || Math.abs(dy) > 2) d.moved = true;
    onDragEnd(entry.id, d.origX + dx, d.origY + dy); // live update; parent may throttle persist
  };
  const onDragUp = (e: MouseEvent) => {
    const d = dragRef.current;
    window.removeEventListener('mousemove', onDragMove);
    window.removeEventListener('mouseup', onDragUp);
    if (d && !d.moved) onSelect(entry.id);
    dragRef.current = null;
  };

  const onResizeMouseDown = (e: React.MouseEvent) => {
    e.stopPropagation();
    resizeRef.current = { startX: e.clientX, startY: e.clientY, origW: entry.width, origH: entry.height };
    window.addEventListener('mousemove', onResizeMove);
    window.addEventListener('mouseup', onResizeUp);
  };
  const onResizeMove = (e: MouseEvent) => {
    const r = resizeRef.current;
    if (!r) return;
    const w = Math.max(80, r.origW + (e.clientX - r.startX) / scale);
    const h = Math.max(60, r.origH + (e.clientY - r.startY) / scale);
    onResizeEnd(entry.id, w, h);
  };
  const onResizeUp = () => {
    window.removeEventListener('mousemove', onResizeMove);
    window.removeEventListener('mouseup', onResizeUp);
    resizeRef.current = null;
  };

  return (
    <div
      className={`${styles.card} ${selected ? styles.selected : ''}`}
      style={{
        left: entry.x, top: entry.y, width: entry.width, height: entry.height,
        borderLeft: `3px solid ${TYPE_COLORS[entry.entry_type] || '#86868b'}`,
        filter: depth > 0 ? `blur(${depth * 1.5}px)` : undefined,
        opacity: 1 - depth * 0.5,
      }}
      onMouseDown={onCardMouseDown}
    >
      <span className={styles.title}>
        {entry.title}
        {entry.status === 'pending' && <span className={styles.badge}>待确认</span>}
      </span>
      {!collapsed && entry.content && <span className={styles.content}>{entry.content}</span>}
      <div className={styles.connectDot} onMouseDown={(e) => { e.stopPropagation(); onStartConnect(entry.id); }} />
      <div className={styles.resizeHandle} onMouseDown={onResizeMouseDown} />
    </div>
  );
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `npm run test -- --run tests/CardNode.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/Canvas/CardNode.tsx frontend/src/components/Canvas/CardNode.module.css frontend/tests/CardNode.test.tsx
git commit -m "feat(frontend): CardNode free-positioned draggable card"
```

---

### Task 10: CardEditor 内联编辑器

**Files:**
- Create: `frontend/src/components/Canvas/CardEditor.tsx`
- Create: `frontend/src/components/Canvas/CardEditor.module.css`
- Test: `frontend/tests/CardEditor.test.tsx` (create)

**Interfaces:**
- Consumes: `Entry`、`Layer` 类型。
- Produces: `CardEditor` props `{ entry: Entry; layers: Layer[]; onSave(patch): void; onDelete(id): void; onClose(): void; onConfirm?(id): void; onIgnore?(id): void }`。浮在卡片旁（`left:entry.x+entry.width+8, top:entry.y`），字段：标题、内容、类型、多标签复选、z_depth 滑块、删除按钮。

- [ ] **Step 1: 写失败测试**

`frontend/tests/CardEditor.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import CardEditor from '../src/components/Canvas/CardEditor';

const entry = () => ({
  id: '1', title: 'T', content: 'C', entry_type: 'known', layer_id: null,
  dimension_id: 'd1', source_type: 'manual', source_link: '', status: 'confirmed',
  tags: [], tag_ids: [], confidence: 100, x: 0, y: 0, width: 200, height: 120, z_depth: 0,
  created_at: '', updated_at: '',
} as any);
const layers = [{ id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 }];

describe('CardEditor', () => {
  it('saves edited title', () => {
    const onSave = vi.fn();
    render(<CardEditor entry={entry()} layers={layers} onSave={onSave} onDelete={() => {}} onClose={() => {}} />);
    fireEvent.change(screen.getByPlaceholderText('标题'), { target: { value: '新标题' } });
    fireEvent.click(screen.getByText('保存'));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ title: '新标题' }));
  });

  it('toggles a layer tag', () => {
    const onSave = vi.fn();
    render(<CardEditor entry={entry()} layers={layers} onSave={onSave} onDelete={() => {}} onClose={() => {}} />);
    fireEvent.click(screen.getByText('细胞'));
    fireEvent.click(screen.getByText('保存'));
    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ tag_ids: ['l1'] }));
  });

  it('calls onDelete', () => {
    const onDelete = vi.fn();
    render(<CardEditor entry={entry()} layers={layers} onSave={() => {}} onDelete={onDelete} onClose={() => {}} />);
    fireEvent.click(screen.getByText('删除'));
    expect(onDelete).toHaveBeenCalledWith('1');
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/CardEditor.test.tsx`
Expected: FAIL（组件不存在）

- [ ] **Step 3: CSS**

`frontend/src/components/Canvas/CardEditor.module.css`:
```css
.editor {
  position: absolute; z-index: 20; width: 260px; background: #fff;
  border-radius: 12px; box-shadow: 0 8px 30px rgba(0,0,0,0.2); padding: 14px;
  display: flex; flex-direction: column; gap: 8px;
}
.editor input, .editor textarea, .editor select {
  border: 1px solid #d2d2d7; border-radius: 8px; padding: 6px 8px; font-size: 13px; font-family: inherit;
}
.tags { display: flex; flex-wrap: wrap; gap: 6px; }
.tag { font-size: 12px; padding: 3px 8px; border-radius: 12px; border: 1px solid #d2d2d7; cursor: pointer; }
.tagOn { background: #0a84ff; color: #fff; border-color: #0a84ff; }
.row { display: flex; gap: 8px; align-items: center; }
.actions { display: flex; justify-content: space-between; margin-top: 4px; }
.del { color: #ff3b30; background: none; border: none; cursor: pointer; font-size: 13px; }
```

- [ ] **Step 4: 组件**

`frontend/src/components/Canvas/CardEditor.tsx`:
```tsx
import { useState } from 'react';
import type { Entry, Layer } from '../../types';
import styles from './CardEditor.module.css';

interface Props {
  entry: Entry;
  layers: Layer[];
  onSave: (patch: Partial<Entry>) => void;
  onDelete: (id: string) => void;
  onClose: () => void;
  onConfirm?: (id: string) => void;
  onIgnore?: (id: string) => void;
}

export default function CardEditor({ entry, layers, onSave, onDelete, onClose, onConfirm, onIgnore }: Props) {
  const [title, setTitle] = useState(entry.title);
  const [content, setContent] = useState(entry.content);
  const [entryType, setEntryType] = useState(entry.entry_type);
  const [tagIds, setTagIds] = useState<string[]>(entry.tag_ids || []);
  const [zDepth, setZDepth] = useState(entry.z_depth || 0);

  const toggleTag = (id: string) =>
    setTagIds((t) => (t.includes(id) ? t.filter((x) => x !== id) : [...t, id]));

  const save = () => {
    onSave({ title, content, entry_type: entryType, tag_ids: tagIds, z_depth: zDepth });
    onClose();
  };

  return (
    <div className={styles.editor} style={{ left: entry.x + entry.width + 8, top: entry.y }} onMouseDown={(e) => e.stopPropagation()}>
      {entry.status === 'pending' && (
        <div className={styles.row}>
          <span>待确认</span>
          <button onClick={() => onConfirm?.(entry.id)}>确认</button>
          <button onClick={() => onIgnore?.(entry.id)}>忽略</button>
        </div>
      )}
      <input placeholder="标题" value={title} onChange={(e) => setTitle(e.target.value)} />
      <textarea placeholder="内容" rows={3} value={content} onChange={(e) => setContent(e.target.value)} />
      <select value={entryType} onChange={(e) => setEntryType(e.target.value as Entry['entry_type'])}>
        <option value="known">已知</option>
        <option value="unknown">未知缺口</option>
        <option value="question">问题</option>
      </select>
      <div className={styles.tags}>
        {layers.map((l) => (
          <span key={l.id} className={`${styles.tag} ${tagIds.includes(l.id) ? styles.tagOn : ''}`}
                onClick={() => toggleTag(l.id)}>{l.name}</span>
        ))}
      </div>
      <div className={styles.row}>
        <span>纵深</span>
        <input type="range" min={0} max={1} step={0.1} value={zDepth}
               onChange={(e) => setZDepth(parseFloat(e.target.value))} />
      </div>
      <div className={styles.actions}>
        <button className={styles.del} onClick={() => onDelete(entry.id)}>删除</button>
        <div>
          <button onClick={onClose}>取消</button>
          <button onClick={save}>保存</button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `npm run test -- --run tests/CardEditor.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/Canvas/CardEditor.tsx frontend/src/components/Canvas/CardEditor.module.css frontend/tests/CardEditor.test.tsx
git commit -m "feat(frontend): CardEditor inline editor with multi-tag + depth"
```

---

### Task 11: ConnectionLayer 贝塞尔连线

**Files:**
- Create: `frontend/src/components/Canvas/ConnectionLayer.tsx`
- Test: `frontend/tests/ConnectionLayer.test.tsx` (create)

**Interfaces:**
- Consumes: `Entry` 类型；CrossLink 数据形状 `{ id, source_entry_id, target_entry_id }`。
- Produces: `ConnectionLayer` props `{ entries: Entry[]; links: { id: string; source_entry_id: string; target_entry_id: string }[]; onDeleteLink(id): void }`。输出一个覆盖全画布的 `<svg>`，每条 link 渲染一条三次贝塞尔 `<path>`（从 source 右缘到 target 左缘），点击 path 调 onDeleteLink。

- [ ] **Step 1: 写失败测试**

`frontend/tests/ConnectionLayer.test.tsx`:
```tsx
import { render } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ConnectionLayer from '../src/components/Canvas/ConnectionLayer';

const entries = [
  { id: 'a', x: 0, y: 0, width: 100, height: 60 },
  { id: 'b', x: 300, y: 200, width: 100, height: 60 },
] as any;

describe('ConnectionLayer', () => {
  it('renders a cubic bezier path per link', () => {
    const { container } = render(
      <ConnectionLayer entries={entries} links={[{ id: 'L', source_entry_id: 'a', target_entry_id: 'b' }]} onDeleteLink={() => {}} />
    );
    const path = container.querySelector('path');
    expect(path).toBeTruthy();
    expect(path!.getAttribute('d')).toMatch(/^M.*C/); // cubic bezier command present
  });

  it('deletes link on path click', () => {
    const onDelete = vi.fn();
    const { container } = render(
      <ConnectionLayer entries={entries} links={[{ id: 'L', source_entry_id: 'a', target_entry_id: 'b' }]} onDeleteLink={onDelete} />
    );
    const path = container.querySelector('path')!;
    path.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    expect(onDelete).toHaveBeenCalledWith('L');
  });

  it('skips links with missing endpoints', () => {
    const { container } = render(
      <ConnectionLayer entries={entries} links={[{ id: 'X', source_entry_id: 'a', target_entry_id: 'ghost' }]} onDeleteLink={() => {}} />
    );
    expect(container.querySelector('path')).toBeNull();
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/ConnectionLayer.test.tsx`
Expected: FAIL（组件不存在）

- [ ] **Step 3: 组件**

`frontend/src/components/Canvas/ConnectionLayer.tsx`:
```tsx
import type { Entry } from '../../types';

interface LinkShape { id: string; source_entry_id: string; target_entry_id: string; }
interface Props {
  entries: Entry[];
  links: LinkShape[];
  onDeleteLink: (id: string) => void;
}

function bezier(sx: number, sy: number, tx: number, ty: number): string {
  const dx = Math.max(40, Math.abs(tx - sx) * 0.5);
  return `M ${sx} ${sy} C ${sx + dx} ${sy}, ${tx - dx} ${ty}, ${tx} ${ty}`;
}

export default function ConnectionLayer({ entries, links, onDeleteLink }: Props) {
  const byId = new Map(entries.map((e) => [e.id, e]));
  return (
    <svg style={{ position: 'absolute', top: 0, left: 0, width: '100%', height: '100%', overflow: 'visible', pointerEvents: 'none' }}>
      {links.map((link) => {
        const s = byId.get(link.source_entry_id);
        const t = byId.get(link.target_entry_id);
        if (!s || !t) return null;
        const sx = s.x + s.width, sy = s.y + s.height / 2;
        const tx = t.x, ty = t.y + t.height / 2;
        return (
          <path key={link.id} d={bezier(sx, sy, tx, ty)} fill="none" stroke="#8e8e93" strokeWidth={2}
                style={{ pointerEvents: 'stroke', cursor: 'pointer' }}
                onClick={() => onDeleteLink(link.id)} />
        );
      })}
    </svg>
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run tests/ConnectionLayer.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/Canvas/ConnectionLayer.tsx frontend/tests/ConnectionLayer.test.tsx
git commit -m "feat(frontend): ConnectionLayer SVG cubic bezier links"
```

---

### Task 12: Canvas 无限画布重写

**Files:**
- Modify: `frontend/src/components/Canvas/Canvas.tsx`
- Modify: `frontend/src/components/Canvas/Canvas.module.css`
- Delete: `frontend/src/components/Canvas/LayerRow.tsx`, `LayerRow.module.css`, `frontend/src/components/Canvas/EntryCard.tsx`, `EntryCard.module.css`
- Delete: `frontend/tests/EntryCard.test.tsx`
- Modify: `frontend/tests/Canvas.test.tsx`

**Interfaces:**
- Consumes: Task 7 `useCanvasZoom`、Task 9 `CardNode`、Task 10 `CardEditor`、Task 11 `ConnectionLayer`；`Entry, Layer, LayerLink` 类型。
- Produces: `Canvas` props `{ entries: Entry[]; layers: Layer[]; crossLinks: {id;source_entry_id;target_entry_id}[]; selectedId: string | null; onSelect(id|null); onDragEnd(id,x,y); onResizeEnd(id,w,h); onCreateAt(x,y); onSave(id,patch); onDelete(id); onConnect(sourceId,targetId); onDeleteCrossLink(id); onConfirm(id); onIgnore(id) }`。空白双击→onCreateAt(画布坐标)；空白单击→onSelect(null)；管理"连线进行中"本地状态。

- [ ] **Step 1: 改写 Canvas 测试**

`frontend/tests/Canvas.test.tsx`（整体替换）:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Canvas from '../src/components/Canvas/Canvas';

const base = {
  entries: [], layers: [], crossLinks: [], selectedId: null,
  onSelect: () => {}, onDragEnd: () => {}, onResizeEnd: () => {},
  onCreateAt: vi.fn(), onSave: () => {}, onDelete: () => {},
  onConnect: () => {}, onDeleteCrossLink: () => {}, onConfirm: () => {}, onIgnore: () => {},
};

describe('Canvas', () => {
  it('renders a card for each entry', () => {
    const entries = [{ id: '1', title: '细胞', content: '', entry_type: 'known', layer_id: null,
      dimension_id: 'd1', source_type: 'manual', source_link: '', status: 'confirmed', tags: [], tag_ids: [],
      confidence: 100, x: 10, y: 10, width: 200, height: 120, z_depth: 0, created_at: '', updated_at: '' }] as any;
    render(<Canvas {...base} entries={entries} />);
    expect(screen.getByText('细胞')).toBeInTheDocument();
  });

  it('double click on empty space creates a card at canvas coords', () => {
    const onCreateAt = vi.fn();
    const { container } = render(<Canvas {...base} onCreateAt={onCreateAt} />);
    const surface = container.querySelector('[data-canvas-surface]')!;
    fireEvent.doubleClick(surface, { clientX: 100, clientY: 100 });
    expect(onCreateAt).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/Canvas.test.tsx`
Expected: FAIL（旧 Canvas 签名不符）

- [ ] **Step 3: 删除旧文件**

```bash
git rm frontend/src/components/Canvas/LayerRow.tsx frontend/src/components/Canvas/LayerRow.module.css frontend/src/components/Canvas/EntryCard.tsx frontend/src/components/Canvas/EntryCard.module.css frontend/tests/EntryCard.test.tsx
```

- [ ] **Step 4: 重写 Canvas.module.css**

`frontend/src/components/Canvas/Canvas.module.css`（整体替换）:
```css
.container {
  position: fixed; inset: 0; overflow: hidden; background: #f5f5f7;
  user-select: none; touch-action: none;
}
.surface { position: absolute; top: 0; left: 0; transform-origin: 0 0; will-change: transform; }
.loading { display: flex; align-items: center; justify-content: center; height: 100vh; color: #86868b; }
```

- [ ] **Step 5: 重写 Canvas.tsx**

`frontend/src/components/Canvas/Canvas.tsx`（整体替换）:
```tsx
import { useState, useRef } from 'react';
import { useCanvasZoom } from '../../hooks/useCanvasZoom';
import type { Entry, Layer } from '../../types';
import CardNode from './CardNode';
import CardEditor from './CardEditor';
import ConnectionLayer from './ConnectionLayer';
import styles from './Canvas.module.css';

interface CrossLinkShape { id: string; source_entry_id: string; target_entry_id: string; }
interface Props {
  entries: Entry[];
  layers: Layer[];
  crossLinks: CrossLinkShape[];
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  onDragEnd: (id: string, x: number, y: number) => void;
  onResizeEnd: (id: string, width: number, height: number) => void;
  onCreateAt: (x: number, y: number) => void;
  onSave: (id: string, patch: Partial<Entry>) => void;
  onDelete: (id: string) => void;
  onConnect: (sourceId: string, targetId: string) => void;
  onDeleteCrossLink: (id: string) => void;
  onConfirm: (id: string) => void;
  onIgnore: (id: string) => void;
}

export default function Canvas(props: Props) {
  const { entries, layers, crossLinks, selectedId } = props;
  const { scale, position, isPanning, onWheel, onMouseDown, onMouseMove, onMouseUp, screenToCanvas } = useCanvasZoom(1, 0.1, 3);
  const containerRef = useRef<HTMLDivElement>(null);
  const [connectFrom, setConnectFrom] = useState<string | null>(null);

  const rect = () => containerRef.current?.getBoundingClientRect() ?? { left: 0, top: 0 };

  const handleSurfaceMouseDown = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget || (e.target as HTMLElement).dataset.canvasSurface !== undefined) {
      props.onSelect(null);
      onMouseDown(e);
    }
  };

  const handleDoubleClick = (e: React.MouseEvent) => {
    const p = screenToCanvas(e.clientX, e.clientY, rect());
    props.onCreateAt(p.x, p.y);
  };

  const handleStartConnect = (sourceId: string) => setConnectFrom(sourceId);
  const handleCardSelect = (id: string) => {
    if (connectFrom && connectFrom !== id) {
      props.onConnect(connectFrom, id);
      setConnectFrom(null);
    } else {
      props.onSelect(id);
    }
  };

  const selected = entries.find((e) => e.id === selectedId) || null;

  return (
    <div ref={containerRef} className={styles.container}
         onWheel={onWheel} onMouseMove={onMouseMove} onMouseUp={onMouseUp}
         style={{ cursor: isPanning ? 'grabbing' : 'default' }}>
      <div className={styles.surface} data-canvas-surface
           style={{ transform: `translate(${position.x}px, ${position.y}px) scale(${scale})`, width: 1, height: 1 }}
           onMouseDown={handleSurfaceMouseDown}
           onDoubleClick={handleDoubleClick}>
        <ConnectionLayer entries={entries} links={crossLinks} onDeleteLink={props.onDeleteCrossLink} />
        {entries.map((entry) => (
          <CardNode key={entry.id} entry={entry} scale={scale} selected={entry.id === selectedId}
            onSelect={handleCardSelect} onDragEnd={props.onDragEnd} onResizeEnd={props.onResizeEnd}
            onStartConnect={handleStartConnect} />
        ))}
        {selected && (
          <CardEditor entry={selected} layers={layers}
            onSave={(patch) => props.onSave(selected.id, patch)} onDelete={props.onDelete}
            onClose={() => props.onSelect(null)} onConfirm={props.onConfirm} onIgnore={props.onIgnore} />
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 6: 运行 Canvas 测试**

Run: `npm run test -- --run tests/Canvas.test.tsx`
Expected: PASS (2/2)

- [ ] **Step 7: 全前端测试 + 类型检查**

Run: `npm run test -- --run`
Expected: 除 App/Dock/EntryForm 相关（后续任务处理）外，Canvas/CardNode/CardEditor/Connection/client/hooks 全绿。EntryForm.test.tsx 仍存在会引用旧组件——本步保留，Task 14 处理。
Run: `npx tsc --noEmit`
Expected: App.tsx 会因 Canvas 新签名报错（Task 19 修）；记录预期错误继续。

- [ ] **Step 8: 提交**

```bash
git add frontend/src/components/Canvas/Canvas.tsx frontend/src/components/Canvas/Canvas.module.css frontend/tests/Canvas.test.tsx
git commit -m "feat(frontend): infinite canvas rewrite with free cards + connections"
```

---

### Task 13: TagPool 标签分布面板

**Files:**
- Create: `frontend/src/components/Canvas/TagPool.tsx`
- Create: `frontend/src/components/Canvas/TagPool.module.css`
- Test: `frontend/tests/TagPool.test.tsx` (create)

**Interfaces:**
- Consumes: `Layer, Entry` 类型。
- Produces: `TagPool` props `{ layers: Layer[]; entries: Entry[] }`。侧边浮层，列出每个层级名 + 引用该标签的卡片数（统计 `entries` 中 `tag_ids` 含该 layer 的数量），数量为 0 高亮为"盲区提示"。

- [ ] **Step 1: 写失败测试**

`frontend/tests/TagPool.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect } from 'vitest';
import TagPool from '../src/components/Canvas/TagPool';

const layers = [
  { id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 },
  { id: 'l2', dimension_id: 'd1', name: '社会', level: 5, description: '', entry_count: 0 },
];
const entries = [{ id: 'e1', tag_ids: ['l1'] }] as any;

describe('TagPool', () => {
  it('shows count per layer tag', () => {
    render(<TagPool layers={layers} entries={entries} />);
    expect(screen.getByText('细胞')).toBeInTheDocument();
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('marks empty layers as blind spots', () => {
    const { container } = render(<TagPool layers={layers} entries={entries} />);
    expect(container.querySelectorAll('[data-empty="true"]').length).toBe(1);
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/TagPool.test.tsx`
Expected: FAIL（组件不存在）

- [ ] **Step 3: CSS**

`frontend/src/components/Canvas/TagPool.module.css`:
```css
.pool {
  position: fixed; top: 16px; right: 16px; z-index: 10; width: 160px;
  background: rgba(255,255,255,0.9); backdrop-filter: blur(8px);
  border-radius: 12px; box-shadow: 0 4px 16px rgba(0,0,0,0.1); padding: 10px; font-size: 13px;
}
.item { display: flex; justify-content: space-between; padding: 3px 4px; border-radius: 6px; }
.empty { color: #ff3b30; }
.count { color: #86868b; }
</style>
```
（注：CSS 文件不要 `</style>`，仅保留上面的规则；删除该行。）

- [ ] **Step 4: 组件**

`frontend/src/components/Canvas/TagPool.tsx`:
```tsx
import type { Layer, Entry } from '../../types';
import styles from './TagPool.module.css';

interface Props { layers: Layer[]; entries: Entry[]; }

export default function TagPool({ layers, entries }: Props) {
  const count = (layerId: string) => entries.filter((e) => (e.tag_ids || []).includes(layerId)).length;
  return (
    <div className={styles.pool}>
      {layers.map((l) => {
        const c = count(l.id);
        return (
          <div key={l.id} className={`${styles.item} ${c === 0 ? styles.empty : ''}`} data-empty={c === 0}>
            <span>{l.name}</span>
            <span className={styles.count}>{c}</span>
          </div>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `npm run test -- --run tests/TagPool.test.tsx`
Expected: PASS (2/2)

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/Canvas/TagPool.tsx frontend/src/components/Canvas/TagPool.module.css frontend/tests/TagPool.test.tsx
git commit -m "feat(frontend): TagPool distribution + blind-spot panel"
```

---

### Task 14: Dock 视图切换 + 隐藏诊断，删除 EntryForm

**Files:**
- Modify: `frontend/src/components/Dock/Dock.tsx`
- Modify: `frontend/tests/Dock.test.tsx`
- Delete: `frontend/src/components/EntryForm/EntryForm.tsx`, `EntryForm.module.css`, `frontend/tests/EntryForm.test.tsx`

**Interfaces:**
- Consumes: `useDockAutoHide`。
- Produces: `Dock` props `{ onAdd(): void; onScan(): void; onToggleView(): void; view: 'canvas' | 'chains' }`。移除诊断输入框（代码删除，非隐藏——诊断入口后续重设计）。按钮：`⟳` 扫描、`+` 新建、`⇄` 切换视图（依 view 显示"层级"或"画布"标签）。

- [ ] **Step 1: 改写 Dock 测试**

`frontend/tests/Dock.test.tsx`（整体替换）:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import Dock from '../src/components/Dock/Dock';

describe('Dock', () => {
  const base = { onAdd: vi.fn(), onScan: vi.fn(), onToggleView: vi.fn(), view: 'canvas' as const };

  it('shows actions on hover', () => {
    const { container } = render(<Dock {...base} />);
    fireEvent.mouseEnter(container.firstChild as Element);
    expect(screen.getByTitle('添加条目')).toBeInTheDocument();
    expect(screen.getByTitle('扫描知识库')).toBeInTheDocument();
  });

  it('toggles view', () => {
    const onToggleView = vi.fn();
    const { container } = render(<Dock {...base} onToggleView={onToggleView} />);
    fireEvent.mouseEnter(container.firstChild as Element);
    fireEvent.click(screen.getByTitle('切换视图'));
    expect(onToggleView).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/Dock.test.tsx`
Expected: FAIL（props 不符/无切换按钮）

- [ ] **Step 3: 删除 EntryForm**

```bash
git rm frontend/src/components/EntryForm/EntryForm.tsx frontend/src/components/EntryForm/EntryForm.module.css frontend/tests/EntryForm.test.tsx
```

- [ ] **Step 4: 重写 Dock.tsx**

`frontend/src/components/Dock/Dock.tsx`（整体替换）:
```tsx
import { motion, AnimatePresence } from 'framer-motion';
import { useDockAutoHide } from '../../hooks/useDockAutoHide';
import styles from './Dock.module.css';

interface Props {
  onAdd: () => void;
  onScan: () => void;
  onToggleView: () => void;
  view: 'canvas' | 'chains';
}

export default function Dock({ onAdd, onScan, onToggleView, view }: Props) {
  const { visible, show, hide } = useDockAutoHide(2000);
  return (
    <div className={styles.dockArea} onMouseEnter={show} onMouseLeave={hide}>
      <AnimatePresence>
        {visible && (
          <motion.div className={styles.dock}
            initial={{ y: 80, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: 80, opacity: 0 }}
            transition={{ type: 'spring', stiffness: 300, damping: 30 }}>
            <button className={styles.action} title="切换视图" onClick={onToggleView}>
              {view === 'canvas' ? '层级' : '画布'}
            </button>
            <div className={styles.divider} />
            <button className={styles.action} title="扫描知识库" onClick={onScan}>&#8631;</button>
            <button className={styles.action} title="添加条目" onClick={onAdd}>+</button>
          </motion.div>
        )}
      </AnimatePresence>
      {!visible && <div className={styles.handle} />}
    </div>
  );
}
```

- [ ] **Step 5: 运行 Dock 测试确认通过**

Run: `npm run test -- --run tests/Dock.test.tsx`
Expected: PASS (2/2)

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/Dock/Dock.tsx frontend/tests/Dock.test.tsx
git commit -m "feat(frontend): dock view toggle, remove diagnosis input + EntryForm"
```

---

### Task 15: ChainList 维度增删改切换

**Files:**
- Create: `frontend/src/components/ChainEditor/ChainList.tsx`
- Create: `frontend/src/components/ChainEditor/ChainEditor.module.css`
- Test: `frontend/tests/ChainList.test.tsx` (create)

**Interfaces:**
- Consumes: `Dimension` 类型。
- Produces: `ChainList` props `{ dimensions: Dimension[]; activeId: string; onSelect(id): void; onCreate(name): void; onRename(id, name): void; onDelete(id): void }`。列出所有链，点击切换，"+新链"输入创建，每项可改名/删除。CSS 文件复用于 Task 16/17。

- [ ] **Step 1: 写失败测试**

`frontend/tests/ChainList.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChainList from '../src/components/ChainEditor/ChainList';

const dims = [
  { id: 'd1', name: '物质层次', description: '', sort_order: 0, layers: [] },
  { id: 'd2', name: '时间维度', description: '', sort_order: 1, layers: [] },
] as any;

describe('ChainList', () => {
  const base = { dimensions: dims, activeId: 'd1', onSelect: vi.fn(), onCreate: vi.fn(), onRename: vi.fn(), onDelete: vi.fn() };

  it('lists all chains', () => {
    render(<ChainList {...base} />);
    expect(screen.getByText('物质层次')).toBeInTheDocument();
    expect(screen.getByText('时间维度')).toBeInTheDocument();
  });

  it('selects a chain on click', () => {
    const onSelect = vi.fn();
    render(<ChainList {...base} onSelect={onSelect} />);
    fireEvent.click(screen.getByText('时间维度'));
    expect(onSelect).toHaveBeenCalledWith('d2');
  });

  it('creates a new chain', () => {
    const onCreate = vi.fn();
    render(<ChainList {...base} onCreate={onCreate} />);
    fireEvent.change(screen.getByPlaceholderText('新链名称'), { target: { value: '空间维度' } });
    fireEvent.click(screen.getByText('新建链'));
    expect(onCreate).toHaveBeenCalledWith('空间维度');
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/ChainList.test.tsx`
Expected: FAIL（组件不存在）

- [ ] **Step 3: CSS（共享）**

`frontend/src/components/ChainEditor/ChainEditor.module.css`:
```css
.view { position: fixed; inset: 0; background: #f5f5f7; display: flex; padding: 24px; gap: 20px; box-sizing: border-box; }
.panel { background: #fff; border-radius: 14px; box-shadow: 0 2px 12px rgba(0,0,0,0.08); padding: 16px; overflow-y: auto; }
.chainPanel { width: 220px; flex-shrink: 0; }
.layerPanel { width: 300px; flex-shrink: 0; }
.linkPanel { flex: 1; position: relative; }
.item { display: flex; justify-content: space-between; align-items: center; padding: 8px; border-radius: 8px; cursor: pointer; }
.active { background: #e8f0ff; }
.item input { border: none; background: transparent; font-size: 14px; width: 100%; }
.item input:focus { background: #f0f0f2; outline: none; }
.del { color: #ff3b30; background: none; border: none; cursor: pointer; }
.addRow { display: flex; gap: 6px; margin-top: 10px; }
.addRow input { flex: 1; border: 1px solid #d2d2d7; border-radius: 8px; padding: 6px; font-size: 13px; }
.dragItem { cursor: grab; }
.h { font-size: 12px; color: #86868b; margin-bottom: 8px; text-transform: uppercase; }
```

- [ ] **Step 4: 组件**

`frontend/src/components/ChainEditor/ChainList.tsx`:
```tsx
import { useState } from 'react';
import type { Dimension } from '../../types';
import styles from './ChainEditor.module.css';

interface Props {
  dimensions: Dimension[];
  activeId: string;
  onSelect: (id: string) => void;
  onCreate: (name: string) => void;
  onRename: (id: string, name: string) => void;
  onDelete: (id: string) => void;
}

export default function ChainList({ dimensions, activeId, onSelect, onCreate, onRename, onDelete }: Props) {
  const [newName, setNewName] = useState('');
  const create = () => { if (newName.trim()) { onCreate(newName.trim()); setNewName(''); } };
  return (
    <div className={`${styles.panel} ${styles.chainPanel}`}>
      <div className={styles.h}>思维链</div>
      {dimensions.map((d) => (
        <div key={d.id} className={`${styles.item} ${d.id === activeId ? styles.active : ''}`} onClick={() => onSelect(d.id)}>
          <input value={d.name} onClick={(e) => e.stopPropagation()}
                 onChange={(e) => onRename(d.id, e.target.value)} />
          <button className={styles.del} onClick={(e) => { e.stopPropagation(); onDelete(d.id); }}>×</button>
        </div>
      ))}
      <div className={styles.addRow}>
        <input placeholder="新链名称" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <button onClick={create}>新建链</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `npm run test -- --run tests/ChainList.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 6: 提交**

```bash
git add frontend/src/components/ChainEditor/ChainList.tsx frontend/src/components/ChainEditor/ChainEditor.module.css frontend/tests/ChainList.test.tsx
git commit -m "feat(frontend): ChainList dimension management"
```

---

### Task 16: LayerList 层级重排/增删改

**Files:**
- Create: `frontend/src/components/ChainEditor/LayerList.tsx`
- Test: `frontend/tests/LayerList.test.tsx` (create)

**Interfaces:**
- Consumes: `Layer` 类型；共享 CSS。
- Produces: `LayerList` props `{ layers: Layer[]; onCreate(name): void; onRename(id, name): void; onUpdateDesc(id, desc): void; onDelete(id): void; onReorder(orderedIds): void }`。列出激活链层级（按 level），可改名、编辑描述、删除、增；用原生 HTML5 drag 重排（拖动项到另一项上触发 onReorder 新顺序）。

- [ ] **Step 1: 写失败测试**

`frontend/tests/LayerList.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LayerList from '../src/components/ChainEditor/LayerList';

const layers = [
  { id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '基本单位', entry_count: 0 },
  { id: 'l2', dimension_id: 'd1', name: '组织', level: 1, description: '', entry_count: 0 },
];

describe('LayerList', () => {
  const base = { layers, onCreate: vi.fn(), onRename: vi.fn(), onUpdateDesc: vi.fn(), onDelete: vi.fn(), onReorder: vi.fn() };

  it('renders layers in order', () => {
    render(<LayerList {...base} />);
    const inputs = screen.getAllByDisplayValue(/细胞|组织/);
    expect(inputs[0]).toHaveValue('细胞');
  });

  it('creates a layer', () => {
    const onCreate = vi.fn();
    render(<LayerList {...base} onCreate={onCreate} />);
    fireEvent.change(screen.getByPlaceholderText('新层级名称'), { target: { value: '器官' } });
    fireEvent.click(screen.getByText('新增层级'));
    expect(onCreate).toHaveBeenCalledWith('器官');
  });

  it('deletes a layer', () => {
    const onDelete = vi.fn();
    render(<LayerList {...base} onDelete={onDelete} />);
    fireEvent.click(screen.getAllByText('×')[0]);
    expect(onDelete).toHaveBeenCalledWith('l1');
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/LayerList.test.tsx`
Expected: FAIL（组件不存在）

- [ ] **Step 3: 组件**

`frontend/src/components/ChainEditor/LayerList.tsx`:
```tsx
import { useState, useRef } from 'react';
import type { Layer } from '../../types';
import styles from './ChainEditor.module.css';

interface Props {
  layers: Layer[];
  onCreate: (name: string) => void;
  onRename: (id: string, name: string) => void;
  onUpdateDesc: (id: string, desc: string) => void;
  onDelete: (id: string) => void;
  onReorder: (orderedIds: string[]) => void;
}

export default function LayerList({ layers, onCreate, onRename, onUpdateDesc, onDelete, onReorder }: Props) {
  const [newName, setNewName] = useState('');
  const dragId = useRef<string | null>(null);

  const create = () => { if (newName.trim()) { onCreate(newName.trim()); setNewName(''); } };

  const onDrop = (targetId: string) => {
    const from = dragId.current;
    if (!from || from === targetId) return;
    const ids = layers.map((l) => l.id);
    const next = ids.filter((i) => i !== from);
    next.splice(next.indexOf(targetId), 0, from);
    onReorder(next);
    dragId.current = null;
  };

  return (
    <div className={`${styles.panel} ${styles.layerPanel}`}>
      <div className={styles.h}>层级（拖拽重排）</div>
      {layers.map((l) => (
        <div key={l.id} className={`${styles.item} ${styles.dragItem}`} draggable
             onDragStart={() => (dragId.current = l.id)}
             onDragOver={(e) => e.preventDefault()}
             onDrop={() => onDrop(l.id)}>
          <div style={{ flex: 1 }}>
            <input value={l.name} onChange={(e) => onRename(l.id, e.target.value)} />
            <input value={l.description} placeholder="描述" style={{ fontSize: 12, color: '#86868b' }}
                   onChange={(e) => onUpdateDesc(l.id, e.target.value)} />
          </div>
          <button className={styles.del} onClick={() => onDelete(l.id)}>×</button>
        </div>
      ))}
      <div className={styles.addRow}>
        <input placeholder="新层级名称" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <button onClick={create}>新增层级</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run tests/LayerList.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/ChainEditor/LayerList.tsx frontend/tests/LayerList.test.tsx
git commit -m "feat(frontend): LayerList reorder/rename/desc/CRUD"
```

---

### Task 17: LayerLinkArea 层级间贝塞尔连线

**Files:**
- Create: `frontend/src/components/ChainEditor/LayerLinkArea.tsx`
- Test: `frontend/tests/LayerLinkArea.test.tsx` (create)

**Interfaces:**
- Consumes: `Layer, LayerLink` 类型；共享 CSS。
- Produces: `LayerLinkArea` props `{ layers: Layer[]; links: LayerLink[]; onCreateLink(sourceId, targetId): void; onDeleteLink(id): void }`。把层级按 level 竖排为节点，点击一个节点再点另一个创建连线；连线用 SVG 三次贝塞尔渲染，点击删除。

- [ ] **Step 1: 写失败测试**

`frontend/tests/LayerLinkArea.test.tsx`:
```tsx
import { render, screen, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import LayerLinkArea from '../src/components/ChainEditor/LayerLinkArea';

const layers = [
  { id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 },
  { id: 'l2', dimension_id: 'd1', name: '组织', level: 1, description: '', entry_count: 0 },
];
const links = [{ id: 'k1', source_layer_id: 'l1', target_layer_id: 'l2', relation_type: 'leads_to', note: '' }];

describe('LayerLinkArea', () => {
  const base = { layers, links, onCreateLink: vi.fn(), onDeleteLink: vi.fn() };

  it('renders layer nodes', () => {
    render(<LayerLinkArea {...base} />);
    expect(screen.getByText('细胞')).toBeInTheDocument();
    expect(screen.getByText('组织')).toBeInTheDocument();
  });

  it('renders a bezier path per link', () => {
    const { container } = render(<LayerLinkArea {...base} />);
    const path = container.querySelector('path');
    expect(path).toBeTruthy();
    expect(path!.getAttribute('d')).toMatch(/C/);
  });

  it('creates link by clicking two nodes', () => {
    const onCreateLink = vi.fn();
    render(<LayerLinkArea {...base} links={[]} onCreateLink={onCreateLink} />);
    fireEvent.click(screen.getByText('细胞'));
    fireEvent.click(screen.getByText('组织'));
    expect(onCreateLink).toHaveBeenCalledWith('l1', 'l2');
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/LayerLinkArea.test.tsx`
Expected: FAIL（组件不存在）

- [ ] **Step 3: 组件**

`frontend/src/components/ChainEditor/LayerLinkArea.tsx`:
```tsx
import { useState } from 'react';
import type { Layer, LayerLink } from '../../types';
import styles from './ChainEditor.module.css';

interface Props {
  layers: Layer[];
  links: LayerLink[];
  onCreateLink: (sourceId: string, targetId: string) => void;
  onDeleteLink: (id: string) => void;
}

const NODE_H = 56;
const NODE_X = 40;
const NODE_W = 120;

export default function LayerLinkArea({ layers, links, onCreateLink, onDeleteLink }: Props) {
  const [pending, setPending] = useState<string | null>(null);
  const ordered = [...layers].sort((a, b) => a.level - b.level);
  const yOf = (id: string) => {
    const i = ordered.findIndex((l) => l.id === id);
    return 20 + i * NODE_H + 18;
  };

  const clickNode = (id: string) => {
    if (pending && pending !== id) { onCreateLink(pending, id); setPending(null); }
    else setPending(id);
  };

  const bez = (sy: number, ty: number) => {
    const sx = NODE_X + NODE_W, tx = NODE_X + NODE_W;
    const bulge = 60 + Math.abs(ty - sy) * 0.3;
    return `M ${sx} ${sy} C ${sx + bulge} ${sy}, ${tx + bulge} ${ty}, ${tx} ${ty}`;
  };

  return (
    <div className={`${styles.panel} ${styles.linkPanel}`}>
      <div className={styles.h}>层级逻辑链（点两个节点连线）</div>
      <svg style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none' }}>
        {links.map((k) => (
          <path key={k.id} d={bez(yOf(k.source_layer_id), yOf(k.target_layer_id))} fill="none"
                stroke="#0a84ff" strokeWidth={2} style={{ pointerEvents: 'stroke', cursor: 'pointer' }}
                onClick={() => onDeleteLink(k.id)} />
        ))}
      </svg>
      {ordered.map((l, i) => (
        <div key={l.id} onClick={() => clickNode(l.id)}
             style={{ position: 'absolute', left: NODE_X, top: 20 + i * NODE_H, width: NODE_W,
                      padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
                      background: pending === l.id ? '#0a84ff' : '#f0f0f2',
                      color: pending === l.id ? '#fff' : '#1d1d1f' }}>
          {l.name}
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run tests/LayerLinkArea.test.tsx`
Expected: PASS (3/3)

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/ChainEditor/LayerLinkArea.tsx frontend/tests/LayerLinkArea.test.tsx
git commit -m "feat(frontend): LayerLinkArea bezier logic-chain editor"
```

---

### Task 18: ChainEditorView 容器

**Files:**
- Create: `frontend/src/components/ChainEditor/ChainEditorView.tsx`
- Test: `frontend/tests/ChainEditorView.test.tsx` (create)

**Interfaces:**
- Consumes: Task 15 ChainList、16 LayerList、17 LayerLinkArea；`Dimension, Layer, LayerLink` 类型；共享 CSS。
- Produces: `ChainEditorView` props `{ dimensions: Dimension[]; activeId: string; layers: Layer[]; layerLinks: LayerLink[]; onSelectChain(id); onCreateChain(name); onRenameChain(id,name); onDeleteChain(id); onCreateLayer(name); onRenameLayer(id,name); onUpdateLayerDesc(id,desc); onDeleteLayer(id); onReorderLayers(ids); onCreateLayerLink(s,t); onDeleteLayerLink(id) }`。三栏布局，把回调透传给三个子面板。

- [ ] **Step 1: 写失败测试**

`frontend/tests/ChainEditorView.test.tsx`:
```tsx
import { render, screen } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import ChainEditorView from '../src/components/ChainEditor/ChainEditorView';

const dims = [{ id: 'd1', name: '物质层次', description: '', sort_order: 0, layers: [] }] as any;
const layers = [{ id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 }];

const noop = vi.fn();
const base = {
  dimensions: dims, activeId: 'd1', layers, layerLinks: [],
  onSelectChain: noop, onCreateChain: noop, onRenameChain: noop, onDeleteChain: noop,
  onCreateLayer: noop, onRenameLayer: noop, onUpdateLayerDesc: noop, onDeleteLayer: noop,
  onReorderLayers: noop, onCreateLayerLink: noop, onDeleteLayerLink: noop,
};

describe('ChainEditorView', () => {
  it('renders all three panels', () => {
    render(<ChainEditorView {...base} />);
    expect(screen.getByText('物质层次')).toBeInTheDocument();
    expect(screen.getByText('层级（拖拽重排）')).toBeInTheDocument();
    expect(screen.getByText('层级逻辑链（点两个节点连线）')).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/ChainEditorView.test.tsx`
Expected: FAIL（组件不存在）

- [ ] **Step 3: 组件**

`frontend/src/components/ChainEditor/ChainEditorView.tsx`:
```tsx
import type { Dimension, Layer, LayerLink } from '../../types';
import ChainList from './ChainList';
import LayerList from './LayerList';
import LayerLinkArea from './LayerLinkArea';
import styles from './ChainEditor.module.css';

interface Props {
  dimensions: Dimension[];
  activeId: string;
  layers: Layer[];
  layerLinks: LayerLink[];
  onSelectChain: (id: string) => void;
  onCreateChain: (name: string) => void;
  onRenameChain: (id: string, name: string) => void;
  onDeleteChain: (id: string) => void;
  onCreateLayer: (name: string) => void;
  onRenameLayer: (id: string, name: string) => void;
  onUpdateLayerDesc: (id: string, desc: string) => void;
  onDeleteLayer: (id: string) => void;
  onReorderLayers: (ids: string[]) => void;
  onCreateLayerLink: (s: string, t: string) => void;
  onDeleteLayerLink: (id: string) => void;
}

export default function ChainEditorView(p: Props) {
  return (
    <div className={styles.view}>
      <ChainList dimensions={p.dimensions} activeId={p.activeId} onSelect={p.onSelectChain}
        onCreate={p.onCreateChain} onRename={p.onRenameChain} onDelete={p.onDeleteChain} />
      <LayerList layers={p.layers} onCreate={p.onCreateLayer} onRename={p.onRenameLayer}
        onUpdateDesc={p.onUpdateLayerDesc} onDelete={p.onDeleteLayer} onReorder={p.onReorderLayers} />
      <LayerLinkArea layers={p.layers} links={p.layerLinks}
        onCreateLink={p.onCreateLayerLink} onDeleteLink={p.onDeleteLayerLink} />
    </div>
  );
}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `npm run test -- --run tests/ChainEditorView.test.tsx`
Expected: PASS (1/1)

- [ ] **Step 5: 提交**

```bash
git add frontend/src/components/ChainEditor/ChainEditorView.tsx frontend/tests/ChainEditorView.test.tsx
git commit -m "feat(frontend): ChainEditorView three-panel container"
```

---

### Task 19: App 装配 + 视图路由 + undo/redo 键盘

**Files:**
- Modify: `frontend/src/App.tsx`
- Test: `frontend/tests/App.test.tsx` (create)

**Interfaces:**
- Consumes: Task 12 Canvas、13 TagPool、14 Dock、18 ChainEditorView、8 useUndoRedo、6 client。
- Produces: 顶层状态与全部回调装配；`view` 切换 canvas/chains；Ctrl+Z/Ctrl+Y 触发 undo/redo（应用 CardOp 到状态 + 后端）；地址无关的纯组件根。

- [ ] **Step 1: 写测试（用 mock client）**

`frontend/tests/App.test.tsx`:
```tsx
import { render, screen, waitFor } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import * as client from '../src/api/client';
import App from '../src/App';

const dim = { id: 'd1', name: '物质层次', description: '', sort_order: 0,
  layers: [{ id: 'l1', dimension_id: 'd1', name: '细胞', level: 0, description: '', entry_count: 0 }] };

beforeEach(() => {
  vi.spyOn(client, 'fetchDimensions').mockResolvedValue([dim] as any);
  vi.spyOn(client, 'fetchEntries').mockResolvedValue([] as any);
  vi.spyOn(client, 'fetchLayerLinks').mockResolvedValue([] as any);
});

describe('App', () => {
  it('loads and renders canvas surface', async () => {
    const { container } = render(<App />);
    await waitFor(() => expect(container.querySelector('[data-canvas-surface]')).toBeTruthy());
  });
});
```

- [ ] **Step 2: 运行确认失败**

Run: `npm run test -- --run tests/App.test.tsx`
Expected: FAIL（旧 App 引用已删除的 EntryForm/旧 Canvas）

- [ ] **Step 3: 重写 App.tsx**

`frontend/src/App.tsx`（整体替换）:
```tsx
import { useState, useEffect, useCallback } from 'react';
import Canvas from './components/Canvas/Canvas';
import TagPool from './components/Canvas/TagPool';
import Dock from './components/Dock/Dock';
import ChainEditorView from './components/ChainEditor/ChainEditorView';
import { useUndoRedo, CardOp } from './hooks/useUndoRedo';
import {
  fetchDimensions, fetchEntries, createEntry, updateEntry, deleteEntry, updateGeometry,
  confirmEntry, ignoreEntry, triggerIndexScan, createCrossLink, deleteCrossLink,
  fetchLayerLinks, createLayerLink, deleteLayerLink,
  createDimension, updateDimension, deleteDimension,
  createLayer, updateLayer, deleteLayer, reorderLayers,
} from './api/client';
import type { Dimension, Entry, LayerLink } from './types';

export default function App() {
  const [dimensions, setDimensions] = useState<Dimension[]>([]);
  const [activeId, setActiveId] = useState<string>('');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [crossLinks, setCrossLinks] = useState<{ id: string; source_entry_id: string; target_entry_id: string }[]>([]);
  const [layerLinks, setLayerLinks] = useState<LayerLink[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<'canvas' | 'chains'>('canvas');
  const undoRedo = useUndoRedo();

  const active = dimensions.find((d) => d.id === activeId) || null;
  const layers = active?.layers || [];

  const loadDimensions = useCallback(async () => {
    const dims = await fetchDimensions();
    setDimensions(dims);
    if (dims.length > 0 && !dims.find((d) => d.id === activeId)) setActiveId(dims[0].id);
  }, [activeId]);

  const loadEntries = useCallback(async (dimId: string) => {
    setEntries(await fetchEntries({ dimension_id: dimId }));
  }, []);

  const loadLayerLinks = useCallback(async (dimId: string) => {
    setLayerLinks(await fetchLayerLinks(dimId));
  }, []);

  useEffect(() => { loadDimensions().catch(console.error); }, [loadDimensions]);
  useEffect(() => {
    if (!activeId) return;
    loadEntries(activeId).catch(console.error);
    loadLayerLinks(activeId).catch(console.error);
  }, [activeId, loadEntries, loadLayerLinks]);

  // ---- card ops ----
  const applyOp = useCallback(async (op: CardOp, inverse: boolean) => {
    const kind = op.kind;
    if ((kind === 'create' && !inverse) || (kind === 'delete' && inverse)) {
      const e = (op as any).entry as Entry;
      setEntries((prev) => [...prev, e]);
      await createEntry(e).catch(console.error);
    } else if ((kind === 'delete' && !inverse) || (kind === 'create' && inverse)) {
      const e = (op as any).entry as Entry;
      setEntries((prev) => prev.filter((x) => x.id !== e.id));
      await deleteEntry(e.id).catch(console.error);
    } else if (kind === 'update') {
      const target = inverse ? op.before : op.after;
      setEntries((prev) => prev.map((x) => (x.id === target.id ? target : x)));
      await updateEntry(target.id, target).catch(console.error);
    }
  }, []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'z' && !e.shiftKey) {
        e.preventDefault();
        const op = undoRedo.undo();
        if (op) applyOp(op, true);
      } else if ((e.ctrlKey || e.metaKey) && (e.key.toLowerCase() === 'y' || (e.shiftKey && e.key.toLowerCase() === 'z'))) {
        e.preventDefault();
        const op = undoRedo.redo();
        if (op) applyOp(op, false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [undoRedo, applyOp]);

  const handleCreateAt = async (x: number, y: number) => {
    if (!active) return;
    const created = await createEntry({ title: '新想法', dimension_id: active.id, x, y } as Partial<Entry>);
    setEntries((prev) => [...prev, created]);
    undoRedo.record({ kind: 'create', entry: created });
    setSelectedId(created.id);
  };

  const flushGeom = useCallback((id: string, geo: Partial<Entry>) => {
    updateGeometry(id, geo).catch(console.error);
  }, []);

  const handleDragEnd = (id: string, x: number, y: number) => {
    setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, x, y } : e)));
    flushGeom(id, { x, y });
  };
  const handleResizeEnd = (id: string, width: number, height: number) => {
    setEntries((prev) => prev.map((e) => (e.id === id ? { ...e, width, height } : e)));
    flushGeom(id, { width, height });
  };

  const handleSave = async (id: string, patch: Partial<Entry>) => {
    const before = entries.find((e) => e.id === id);
    const updated = await updateEntry(id, patch);
    setEntries((prev) => prev.map((e) => (e.id === id ? updated : e)));
    if (before) undoRedo.record({ kind: 'update', before, after: updated });
  };

  const handleDelete = async (id: string) => {
    const before = entries.find((e) => e.id === id);
    await deleteEntry(id);
    setEntries((prev) => prev.filter((e) => e.id !== id));
    setSelectedId(null);
    if (before) undoRedo.record({ kind: 'delete', entry: before });
  };

  const handleConnect = async (sourceId: string, targetId: string) => {
    const link = await createCrossLink({ source_entry_id: sourceId, target_entry_id: targetId });
    setCrossLinks((prev) => [...prev, { id: link.id, source_entry_id: sourceId, target_entry_id: targetId }]);
  };
  const handleDeleteCrossLink = async (id: string) => {
    await deleteCrossLink(id);
    setCrossLinks((prev) => prev.filter((l) => l.id !== id));
  };

  const handleConfirm = async (id: string) => { const u = await confirmEntry(id); setEntries((p) => p.map((e) => e.id === id ? u : e)); };
  const handleIgnore = async (id: string) => { const u = await ignoreEntry(id); setEntries((p) => p.map((e) => e.id === id ? u : e)); };
  const handleScan = async () => { await triggerIndexScan(); if (activeId) loadEntries(activeId); };

  // ---- chain editor ops ----
  const handleCreateChain = async (name: string) => { const d = await createDimension({ name }); await loadDimensions(); setActiveId(d.id); };
  const handleRenameChain = async (id: string, name: string) => { await updateDimension(id, { name }); loadDimensions(); };
  const handleDeleteChain = async (id: string) => { await deleteDimension(id); await loadDimensions(); };
  const handleCreateLayer = async (name: string) => { await createLayer(activeId, { name }); loadDimensions(); };
  const handleRenameLayer = async (id: string, name: string) => { await updateLayer(id, { name }); loadDimensions(); };
  const handleUpdateLayerDesc = async (id: string, description: string) => { await updateLayer(id, { description }); loadDimensions(); };
  const handleDeleteLayer = async (id: string) => { await deleteLayer(id); loadDimensions(); };
  const handleReorderLayers = async (ids: string[]) => { await reorderLayers(activeId, ids); loadDimensions(); };
  const handleCreateLayerLink = async (s: string, t: string) => { const k = await createLayerLink({ source_layer_id: s, target_layer_id: t }); setLayerLinks((p) => [...p, k]); };
  const handleDeleteLayerLink = async (id: string) => { await deleteLayerLink(id); setLayerLinks((p) => p.filter((l) => l.id !== id)); };

  if (view === 'chains') {
    return (
      <>
        <ChainEditorView
          dimensions={dimensions} activeId={activeId} layers={layers} layerLinks={layerLinks}
          onSelectChain={setActiveId} onCreateChain={handleCreateChain} onRenameChain={handleRenameChain}
          onDeleteChain={handleDeleteChain} onCreateLayer={handleCreateLayer} onRenameLayer={handleRenameLayer}
          onUpdateLayerDesc={handleUpdateLayerDesc} onDeleteLayer={handleDeleteLayer}
          onReorderLayers={handleReorderLayers} onCreateLayerLink={handleCreateLayerLink}
          onDeleteLayerLink={handleDeleteLayerLink} />
        <Dock onAdd={handleCreateAtCenter} onScan={handleScan} onToggleView={() => setView('canvas')} view="chains" />
      </>
    );
  }

  function handleCreateAtCenter() { handleCreateAt(200, 200); }

  return (
    <>
      <Canvas
        entries={entries} layers={layers} crossLinks={crossLinks} selectedId={selectedId}
        onSelect={setSelectedId} onDragEnd={handleDragEnd} onResizeEnd={handleResizeEnd}
        onCreateAt={handleCreateAt} onSave={handleSave} onDelete={handleDelete}
        onConnect={handleConnect} onDeleteCrossLink={handleDeleteCrossLink}
        onConfirm={handleConfirm} onIgnore={handleIgnore} />
      <TagPool layers={layers} entries={entries} />
      <Dock onAdd={handleCreateAtCenter} onScan={handleScan} onToggleView={() => setView('chains')} view="canvas" />
    </>
  );
}
```

**坐标持久化说明（一个方案，勿混淆）：** `CardNode` 拖拽/缩放时会连续调用 `onDragEnd`/`onResizeEnd` 实时更新内存态（React 重渲染跟手）。松手的最终值通过 `updateGeometry` 直接入库——上面 `handleDragEnd` 末尾已 `flushGeom(id, { x, y })`，`handleResizeEnd` 末尾已 `flushGeom(id, { width, height })`（`flushGeom` 定义见上）。因每次 `onDragEnd` 都会触发一次 PUT，拖动中会有多次请求，MVP 可接受（后端 geometry 端点轻量）；不做去抖，YAGNI。`handleSave` 只管内容字段，不重复写坐标。

- [ ] **Step 4: 运行 App 测试确认通过**

Run: `npm run test -- --run tests/App.test.tsx`
Expected: PASS (1/1)

- [ ] **Step 5: 全前端测试 + 类型检查**

Run: `npm run test -- --run`
Expected: 全部 PASS（client, hooks, CardNode, CardEditor, ConnectionLayer, Canvas, TagPool, Dock, ChainList, LayerList, LayerLinkArea, ChainEditorView, App）
Run: `npx tsc --noEmit`
Expected: 无错误

- [ ] **Step 6: 提交**

```bash
git add frontend/src/App.tsx frontend/tests/App.test.tsx
git commit -m "feat(frontend): App wiring — views, undo/redo, geometry persist"
```

---

### Task 20: 联调冒烟 + dev 库重建

**Files:**
- 无代码变更（人工/脚本冒烟）

**Interfaces:**
- Consumes: 全部。
- Produces: 可运行的 V2 应用。

- [ ] **Step 1: 重建 dev 库**

```bash
rm -f products/thinking-space/data/thinking-space.db
```
（首次启动 lifespan 会 create_all + seed 重建含新字段的库）

- [ ] **Step 2: 后端全量测试**

Run: `cd backend && python -m pytest -v`
Expected: 全绿

- [ ] **Step 3: 前端全量测试 + 类型**

Run: `cd frontend && npm run test -- --run && npx tsc --noEmit`
Expected: 全绿、无类型错误

- [ ] **Step 4: 启动冒烟（人工）**

后端 `python run.py`，前端 `npm run dev`。验证：双击空白建卡 → 拖动 → 编辑打标签 → 连线（贝塞尔）→ 缩放折叠 → Ctrl+Z 撤销 → 切到层级页增删层级/重排/层级连线 → 切回画布。**不测诊断**（已隐藏）。

- [ ] **Step 5: 提交（若有 .gitignore 或杂项调整）**

```bash
git add -A products/thinking-space/.gitignore 2>/dev/null; git commit -m "chore: v2 smoke pass" --allow-empty
```

---

## Self-Review

**1. Spec coverage：**
- 无限画布/平移/缩放/防浏览器默认 → Task 7 + 12 ✅
- 卡片自由定位（x/y）→ Task 1 + 9 ✅
- 卡片缩放内容自适应 → Task 9（COLLAPSE_WIDTH）✅
- 视觉纵深 z_depth → Task 1 + 9（blur/opacity）✅
- 双击空白新建 → Task 12 ✅
- 内联编辑（非模态）→ Task 10 ✅
- 多标签 entry_tags → Task 2 + 10 ✅
- 贝塞尔连线（卡片间）→ Task 11 ✅
- 连线手势（边缘圆点）→ Task 9 + 12 ✅
- 撤销/重做 → Task 8 + 19 ✅
- 多条链（Dimension CRUD）→ Task 4 + 15 ✅
- 层级增删改/重排/描述 → Task 5 + 16 ✅
- 层级间连线 → Task 3 + 17 ✅
- 独立层级编排页 → Task 18 + 19 ✅
- TagPool 盲区分布 → Task 13 ✅
- Dock 隐藏诊断/保留扫描/视图切换 → Task 14 ✅
- 删除 LayerRow/EntryCard/EntryForm → Task 12 + 14 ✅
- 诊断代码保留不动 → 未改 diagnose.py/routes ✅

**2. Placeholder scan：** 无 TBD/TODO；每个代码步含完整代码。Task 19 Step 3 含较多补充说明但均为具体代码。

**3. Type consistency：** `Entry` 字段 `x,y,width,height,z_depth,tag_ids` 前后端一致；`updateGeometry(id, Geometry)`、`reorderLayers(dimId, ids)`、`createLayerLink({source_layer_id,target_layer_id})`、`CardOp` 三态 kind 全流程一致；Canvas props 与 App 传参一致；ChainEditorView props 与子面板一致。

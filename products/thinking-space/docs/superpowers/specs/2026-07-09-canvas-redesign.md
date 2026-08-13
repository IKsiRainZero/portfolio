# 思考空间 V2：Canvas 自由画布重做

> **状态：** 设计已批准（含 07-09 补充）| **日期：** 2026-07-09

**目标：** 将画布从"固定层级色带堆叠"重构为"无限自由白板"——卡片可拖到任意位置、卡片间贝塞尔连线、多标签标注、内联编辑、可缩放、有视觉纵深、支持撤销重做。层级升级为**用户可编排的多条有序逻辑链**（元认知框架），拥有独立编辑页面。

**范围：** 画布 + 卡片核心交互 + 层级编排（本轮 A 范围）。思维链库（B）和时间线视图（C）后续迭代，已记录到 `.context/backlog/v2-future.md`。

## 核心隐喻

- **画布（空间维）** = 无限白板，卡片自由排布，承载思维内容产出
- **层级（元认知维）** = 用户手动编排的多条逻辑链，每条链是一种"解读世界的角度"，提醒思考的盲区。层级不强制卡片位置，只作为可多选的标签。

一切可移动、可编辑、可缩放。工具为思考服务，不限制思考。

## 数据模型变更

### Entry（卡片）新增字段
```sql
ALTER TABLE entries ADD COLUMN x REAL DEFAULT 0;        -- 画布 X 坐标
ALTER TABLE entries ADD COLUMN y REAL DEFAULT 0;        -- 画布 Y 坐标
ALTER TABLE entries ADD COLUMN width REAL DEFAULT 200;  -- 卡片宽（内容自适应）
ALTER TABLE entries ADD COLUMN height REAL DEFAULT 120; -- 卡片高
ALTER TABLE entries ADD COLUMN z_depth REAL DEFAULT 0;  -- 视觉纵深 0=前景，越大越远
```

### 新增：多标签关联表
```sql
CREATE TABLE entry_tags (
    entry_id TEXT NOT NULL,
    layer_id TEXT NOT NULL,
    PRIMARY KEY (entry_id, layer_id),
    FOREIGN KEY (entry_id) REFERENCES entries(id),
    FOREIGN KEY (layer_id) REFERENCES layers(id)
);
```

### 新增：层级间连线表（显式逻辑链，超越顺序）
```sql
CREATE TABLE layer_links (
    id TEXT PRIMARY KEY,
    source_layer_id TEXT NOT NULL,
    target_layer_id TEXT NOT NULL,
    relation_type TEXT DEFAULT 'leads_to',
    note TEXT DEFAULT '',
    FOREIGN KEY (source_layer_id) REFERENCES layers(id),
    FOREIGN KEY (target_layer_id) REFERENCES layers(id)
);
```

### 复用现有模型
- **Dimension** = 一条层级链（一种解析角度）。现有仅 GET，补全 POST/PUT/DELETE。
- **Layer** = 链上一个节点。现有仅种子数据，补全 POST/PUT/DELETE + reorder。`level` 字段复用为链内顺序（拖拽重排时重写）。
- **CrossLink** = 卡片间连线，已有 source/target，直接用。

## 后端 API 变更

### entries 路由
- schema 新增 `x, y, width, height, z_depth: float`, `tag_ids: list[str]`
- `PUT /api/entries/{id}/geometry` — 仅更新 x/y/width/height/z_depth（拖拽/缩放松手后调，避免频繁存内容）
- `POST /api/entries` 创建时同步写 `entry_tags`
- `PUT /api/entries/{id}` 更新时同步改 `entry_tags`

### dimensions 路由（补全 CRUD）
- `POST /api/dimensions` — 新建一条链
- `PUT /api/dimensions/{id}` — 改名/描述/排序
- `DELETE /api/dimensions/{id}` — 删除链（级联删除其 layers）

### layers 路由（新建文件 routes/layers.py）
- `GET /api/dimensions/{dim_id}/layers`
- `POST /api/dimensions/{dim_id}/layers` — 新增层级
- `PUT /api/layers/{id}` — 改名/描述
- `DELETE /api/layers/{id}`
- `PUT /api/dimensions/{dim_id}/layers/reorder` — body 传有序 id 列表，重写 level

### layer_links 路由（新建文件 routes/layer_links.py）
- `GET /api/dimensions/{dim_id}/layer-links`
- `POST /api/layer-links` — 创建层级间连线
- `DELETE /api/layer-links/{id}`

### 前端类型变更
```ts
interface Entry {
  // ...现有字段
  x: number; y: number;
  width: number; height: number;
  z_depth: number;
  tag_ids: string[];
}
interface LayerLink {
  id: string;
  source_layer_id: string;
  target_layer_id: string;
  relation_type: string;
  note: string;
}
```

## 画布交互模型（CanvasView）

### 缩放 & 平移
- 滚轮缩放（以鼠标位置为中心），0.1× ~ 3×
- 按住空白区域拖动平移
- `user-select: none` + `e.preventDefault()` 彻底阻止浏览器搜索/文本选择/新标签页
- 触控板双指手势同步支持

### 视觉纵深
- 卡片按 `z_depth` 渲染：越大 → 越小、越模糊（CSS blur）、越淡（opacity）
- 内联编辑器可调 z_depth（把卡片"推远"或"拉近"）
- MVP 只做 scale+blur+opacity 三项叠加，不做视差滚动

### 卡片操作（CardNode）
- **新建：** Dock `+` 在视野中心新建空白卡片，自动进入编辑态。双击画布空白处在该位置新建。
- **拖拽移动：** 按住卡片拖动，松手调 `PUT geometry`
- **点击编辑：** 单击卡片旁弹出内联编辑器（非模态遮罩），改标题/内容/类型/标签/z_depth
- **缩放：** 右下角拖拽手柄改 width/height。**内容自适应**——放大显示更多内容，缩到阈值以下折叠为仅标题栏
- **删除：** 内联编辑器中删除按钮

### 标签系统
- 编辑卡片时显示**当前激活链**的层级作为标签，点击选中/取消（多选）
- 标签存 `entry_tags`，不锁定位置，仅记录"这次从哪个层面切入"

### 卡片间连线（Connection）
- **触发手势：** 鼠标悬停卡片时边缘出现小圆点，从圆点拖到目标卡片创建 CrossLink
- **渲染：** SVG **贝塞尔曲线**（三次），禁止直线
- CrossLink 类型：`relates_to` / `leads_to` / `contradicts`

### 撤销 / 重做
- `useUndoRedo` hook，操作栈记录：新建、移动、编辑、删除、连线、缩放
- Ctrl+Z 撤销 / Ctrl+Y（或 Ctrl+Shift+Z）重做
- MVP：内存栈，不跨页面刷新持久化

## 层级编排页（ChainEditorView，独立页面）

- **链列表（ChainList）：** 列出所有 Dimension，可新建/改名/删除/切换激活链
- **层级列表（LayerList）：** 展示激活链的层级，可拖拽重排顺序、改名、编辑描述、增删
- **层级连线（LayerLinkArea）：** 层级间画贝塞尔连线，形成显式逻辑链（超越单纯顺序）
- 从画布页通过 Dock 或角落按钮切换到此页

## 组件树

```
App (视图切换: canvas | chains)
├── CanvasView
│   ├── Canvas              (无限画布：缩放/平移/纵深/防浏览器默认/空白双击新建)
│   │   ├── CardNode × N    (拖拽、内联编辑、缩放手柄、z_depth、连线圆点)
│   │   └── ConnectionLayer (SVG 贝塞尔曲线，卡片间连线)
│   ├── Dock                (⟳ 扫描、+ 新建、⇄ 切换到层级页；诊断输入隐藏)
│   └── TagPool             (激活链的层级 = 可多选标签)
└── ChainEditorView
    ├── ChainList           (Dimension 增删改切换)
    ├── LayerList           (层级重排/改名/描述/增删)
    └── LayerLinkArea       (层级间贝塞尔连线)
```

## 删除 & 替换

| 文件 | 动作 |
|------|------|
| `LayerRow.tsx` + `.css` | **删除** |
| `EntryCard.tsx` + `.css` | **重写为** `CardNode.tsx` + `.css` |
| `EntryForm.tsx` + `.css` | **删除**（内联编辑器替代模态弹窗） |
| `Canvas.tsx` / `Canvas.module.css` | **重写** |
| `LayerRow.module.css` | **删除** |
| `useCanvasZoom.ts` | **保留增强**（加 preventDefault + 纵深） |

## 保留 & 不动

- 后端现有路由（indexer, diagnose, cross_links, export）逻辑不变
- 诊断功能代码完整保留，仅前端 Dock 诊断输入框 `display: none`
- 种子数据（初始"物质层次"链 + 10 层级）不动，作为默认链
- 扫描按钮保留

## 测试策略

- **后端：** `test_entry_geometry.py`（坐标/尺寸/纵深更新）、`test_entry_tags.py`（多标签增改）、`test_layers_crud.py`（层级增删改+重排）、`test_layer_links.py`（层级连线）、`test_dimensions_crud.py`（链增删改）
- **前端：** `CardNode.test.tsx`（拖拽、内联编辑、缩放折叠）、`Canvas.test.tsx`（平移/缩放、空白双击新建）、`useUndoRedo.test.ts`（撤销重做栈）、`ChainEditor.test.tsx`（层级重排/增删）
- 贝塞尔连线纯视觉，不写单元测试（视觉验证）

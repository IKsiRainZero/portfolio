# 前端重构 & 三合一融合 — 实施计划

> 计划产出 | 2026-06-13 | 基于 design-brief v2 + 架构文档 v4
> 执行环境: git worktree `feat/design-constructivism`
> 原则: 每阶段独立可验证，不破坏已有功能，随时可回滚

## 系统现状

| 组件 | 文件 | 规模 |
|------|------|------|
| portfolio-app 入口 | `server.py` | 284行, 16个Blueprint |
| portfolio-app 布局 | `templates/base.html` | 170行, 侧边栏+内容区 |
| portfolio-app CSS | `global.css` + `components.css` | 524+342=866行, 浅色主题 |
| cv-lab 入口 | `cv-lab-v3.3/cv-lab/app.py` | 1850行, 单体Flask, 无Blueprint |
| cv-lab 模板 | `index.html` `cnn.html` `convolution.html` | 3个独立模板, 自有`<head>` |
| cv-lab CSS/JS | `features.css`(127行) + `features.js`(169行) | 独立样式和交互 |
| cv-lab 静态资源 | `background.png` | 6MB (需压缩) |
| portfolio-site | `index.html`(493行) + `server.py`(20行) | 单页, 视频背景 |
| 测试 | `tests/` | 175+ tests (173 pass, 7 batch-order flaky) |

---

## Phase 0: 结构合并（旧样式验证）

> **目标**: 3个应用 → 单端口 localhost:5000。功能不退化，样式不改。
> **时间估计**: 2-3小时
> **验收**: 173 tests pass + cv-lab 交互不退化 + Landing 可访问

### 0.1 准备工作

```bash
# 创建隔离 worktree
cd C:/Users/16008/Desktop/personal/Write/portfolio
git worktree add -b feat/design-constructivism ../portfolio-constructivism main
cd ../portfolio-constructivism
```

### 0.2 目录重构

```
portfolio-main/                         ← 当前 portfolio-app/ 不变名(暂时)
├── blueprints/
│   ├── cvlab/                          ← 新建: cv-lab Blueprint
│   │   ├── __init__.py                 ← create_blueprint() 工厂
│   │   ├── routes.py                   ← cv-lab 页面路由 (/, /cnn, /convolution)
│   │   └── api.py                      ← cv-lab API 路由 (/api/sobel, /api/harris, ...)
│   └── landing/                        ← 新建: Landing Blueprint
│       ├── __init__.py
│       └── routes.py                   ← / 大门页面
├── templates/
│   ├── cvlab/                          ← cv-lab 3个模板移入
│   │   ├── index.html
│   │   ├── cnn.html
│   │   └── convolution.html
│   └── landing/
│       └── index.html                  ← 原 portfolio-site/index.html
├── static/
│   ├── cvlab/                          ← cv-lab 静态资源 (background.png, css/, js/)
│   └── landing/                        ← Landing 静态资源 (视频文件)
└── services/
    └── cvlab/                          ← cv-lab 算法代码移入
        ├── harris.py
        ├── sift.py
        └── ...
```

### 0.3 cv-lab Blueprint 化

**改造 cv-lab app.py (1850行) → 两个 Blueprint 文件:**

1. 创建 `blueprints/cvlab/__init__.py`:
   - `create_cvlab_blueprint()` 工厂函数
   - 模板文件夹指向 `templates/cvlab/`
   - 静态文件夹指向 `static/cvlab/`

2. 创建 `blueprints/cvlab/routes.py`:
   - 提取 `/` → `cvlab.index()` 
   - 提取 `/convolution` → `cvlab.convolution_page()`
   - 提取 `/cnn` → `cvlab.cnn_page()`

3. 创建 `blueprints/cvlab/api.py`:
   - 提取所有 `/api/*` 路由
   - 算法函数移入 `services/cvlab/`

4. **安全扫描** (提前于迁移):
   - 检查所有 `request.args` / `request.form` 输入是否转义
   - 检查 `send_file` / `send_from_directory` 使用是否安全
   - 确认 `SESSION_COOKIE_HTTPONLY` 和 `SESSION_COOKIE_SAMESITE` 生效

5. **cv-lab 模板适配**:
   - 3个模板保持独立的 `<head>` 和 `<script>` — **不强制继承 base.html**
   - 这是"第一步挂载"，不是"逐模板迁移"——样式和JS路径调整指向 `static/cvlab/`
   - 功能验证: Harris角点检测、SIFT特征提取、CNN训练/推理、卷积可视化全部正常

### 0.4 Landing Blueprint

1. 创建 `blueprints/landing/__init__.py` + `routes.py`
2. `portfolio-site/index.html` → `templates/landing/index.html`
3. 视频资源移至 `static/landing/`
4. Landing页面暂不改样式——仅调整静态资源路径

### 0.5 合并 server.py

1. **重命名**: `server.py` → `app.py`
2. **config.VERSION**: 从 git commit 短哈希自动读取，用于静态资源缓存破坏:
   ```python
   import subprocess
   try:
       VERSION = subprocess.check_output(['git', 'rev-parse', '--short', 'HEAD']).decode().strip()
   except Exception:
       VERSION = 'dev'
   ```
3. **CSP 报告模式**: 添加 `@app.after_request` 钩子设置 `Content-Security-Policy-Report-Only` 头:
   ```
   default-src 'self'; script-src 'self' https://cdn.jsdelivr.net; 
   style-src 'self' 'unsafe-inline'; img-src 'self' data:;
   ```
4. **注册新 Blueprint**:
   ```python
   from blueprints.cvlab import create_cvlab_blueprint
   from blueprints.landing import create_landing_blueprint
   app.register_blueprint(create_cvlab_blueprint())
   app.register_blueprint(create_landing_blueprint())
   ```
5. **启动顺序**: (在 app.py 中明确注释)
   ```
   1. Flask app 创建
   2. 安全响应头 + CSP Report-Only 注册
   3. Trace 钩子注册 (before_request / after_request)
   4. 所有 Blueprint 注册
   5. 后台 daemon 线程启动 (评估引擎 + L2 Timer + LLM Judge consumer)
   6. app.run()
   ```
6. **静态资源版本化**: `base.html` 中 `<link>` 和 `<script>` 引用增加版本查询参数:
   ```html
   <link rel="stylesheet" href="{{ url_for('static', filename='css/variables.css', v=config.VERSION) }}">
   ```
7. **预埋轨道网络 SVG 容器**: 在 `templates/base.html` 中添加空的 `<svg id="orbit-network" style="display:none"></svg>`
8. **预埋骨架屏结构**: 在 `base.html` 内容区最外层添加骨架屏占位:
   ```html
   <div id="skeleton-loader" style="background: var(--bg-layer-1); opacity: 1; transition: opacity 200ms;">
     <!-- 全宽半透明矩形，内容加载完成后 opacity: 0 -->
   </div>
   ```

### 0.6 Landing 底部数据条

**文件**: `blueprints/landing/routes.py` (实现服务端渲染逻辑)

不通过前端 fetch 异步获取，服务端渲染时同步读取本地文件:
1. `data/eval/heartbeat.json` → 获取 `last_run` 时间戳
2. `data/eval/scores.json` → 获取最新 `total_score`

渲染逻辑:
- heartbeat 正常 + scores 正常 → 显示 "系统健康度: 0.85 | 上次评估: 2小时前"
- heartbeat 正常 + scores 缺失 → 显示 "评估引擎运行中，数据暂不可用"
- heartbeat 缺失 → 显示 "评估引擎离线 | 最后心跳: 3小时前"（锈红色警告）

### 0.7 perf_check.sh 创建 + 基线快照

**文件**: `scripts/perf_check.sh` (新建或修改)

```bash
# 必须包含:
# 1. /api/eval/summary p95 < 500ms
# 2. /api/eval/heartbeat p95 < 100ms
# 3. python app.py 启动时间 < 5s
```

Phase 0 验收前运行并保存基线:
```bash
bash scripts/perf_check.sh | tee data/eval/perf_baseline.txt
python -c "from services.eval.eval_engine import _compute_data_completeness; print(_compute_data_completeness())" > data/eval/coverage_baseline.txt
```

### 0.8 静态资源处理

- `background.png` (6MB) → 压缩至 ≤500KB (resize + pngquant)
- `演示.mp4` → 不入 git (已在 .gitignore)
- portfolio-site 视频文件 → 压缩版 + 不入 git (已在 .gitignore)

### 0.9 验证

```bash
python app.py                           # 单命令启动, 无 ImportError
curl http://localhost:5000/             # Landing 可访问
curl http://localhost:5000/cvlab/       # cv-lab 首页可访问
curl http://localhost:5000/cnn          # CNN 页面可访问
curl http://localhost:5000/convolution   # 卷积页面可访问
curl http://localhost:5000/api/eval/summary  # 评估API正常
python -m pytest tests/ -x              # 全部通过
bash scripts/perf_check.sh              # 与 baseline 对比
pytest tests/test_eval_api.py -k "test_apply_reject_no_token_returns_403"  # 安全回归
```

**验收门禁:**
- [ ] `python app.py` 单命令启动，无报错
- [ ] 173+ tests pass (pre-existing flaky 不计)
- [ ] Landing 页面可访问，底部数据条显示真实状态
- [ ] CV Lab 三个页面交互不退化 (Harris/SIFT/CNN 功能完整)
- [ ] Eval Dashboard 所有 Tab 正常
- [ ] 骨架屏结构在 `base.html` 预埋并可见
- [ ] `perf_check.sh` 通过，基线已保存到 `data/eval/perf_baseline.txt`
- [ ] 追踪覆盖率基线已保存到 `data/eval/coverage_baseline.txt`
- [ ] CSP 报告模式无违规（浏览器 Console 无 CSP 报错）
- [ ] `X-Admin-Token` 在所有评估写操作端点上生效，影子模式返回 403
- [ ] cv-lab 安全扫描通过 (XSS/输入转义/文件服务)

**提交 checkpoint:**
```
git add -A && git commit -m "feat(phase0): structural merge — 3 apps → single port 5000"
```

---

## Phase 1 (P0): 设计基础 — CSS变量 + 字体 + 深色基底

> **目标**: 深色构造主义基底上线，但保留旧模板样式不受影响
> **时间估计**: 4-6小时
> **验收**: FCP ≤ 1.5s + 所有页面可渲染 + `perf_check.sh` 通过

### 1.1 CSS 变量体系

**文件**: `static/css/variables.css` (新建)

定义完整 CSS 变量（从 design-brief Section 3）:
```css
:root {
  /* 背景层级 (层积岩: 深层=深, 上层=亮) */
  --bg-deep: #0f0f1a;
  --bg-layer-1: #1a1a2e;
  --bg-layer-2: #222240;
  --bg-layer-3: #2a2a4a;
  
  /* 语义色 */
  --steel-blue: #3b82f6;
  --rust-red: #c44536;
  --copper-green: #00b4d8;
  --amber: #f59e0b;
  
  /* 文字 */
  --ink-primary: #e8e8f0;
  --ink-secondary: #a0a0b8;
  --ink-muted: #6a6a80;
  
  /* 阴影 (地质分界线) */
  --shadow-layer: 0 4px 16px rgba(0,0,0,0.5);
  --shadow-card: 0 2px 8px rgba(0,0,0,0.3);
  
  /* 玻璃态 (仅三处使用) */
  --glass-bg: rgba(26, 26, 46, 0.85);
  --glass-blur: 12px;
  
  /* 间距 */
  --space-xs: 4px;
  --space-sm: 8px;
  --space-md: 16px;
  --space-lg: 24px;
  --space-xl: 40px;
  
  /* 圆角 */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  
  /* 过渡 */
  --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
  --duration-fast: 150ms;
  --duration-normal: 200ms;
  --duration-slow: 300ms;
}
```

### 1.2 字体本地化

1. 下载 Inter (Regular + Bold + SemiBold) woff2 → `static/fonts/`
2. 下载 JetBrains Mono (Regular + Bold) woff2 → `static/fonts/`
3. 在 `variables.css` 中添加 `@font-face` 声明
4. 设置字体栈: `--font-body: 'Inter', system-ui, sans-serif; --font-mono: 'JetBrains Mono', monospace;`

### 1.3 全局样式覆盖

**文件**: `static/css/global.css` (修改)

- `body`: 背景 `var(--bg-deep)`, 文字 `var(--ink-primary)`, 字体 `var(--font-body)`
- `a`: 颜色 `var(--steel-blue)`
- 引入 `variables.css`

**文件**: `static/css/components.css` (修改)

- 替换硬编码色值为 CSS 变量引用
- 卡片: 背景 `var(--bg-layer-1)`, 阴影 `var(--shadow-card)`
- 按钮/输入框: 适配深色主题

### 1.4 磨砂玻璃（仅三处）

| 位置 | CSS | 触发 |
|------|-----|------|
| 追溯面板 | `background: var(--glass-bg); backdrop-filter: blur(var(--glass-blur));` | 滑出时 |
| 评分卡 hover | `backdrop-filter: blur(8px);` | `:hover` |
| Landing 入口节点 hover | `backdrop-filter: blur(8px);` | `:hover` |

其他所有卡片/面板使用 `background: rgba(26,26,46,0.95)` 纯色。

### 1.5 motion-safe / motion-reduce 系统

在 `variables.css` 或 `global.css` 中:

```css
@media (prefers-reduced-motion: no-preference) {
  .motion-safe { /* 动画在此生效 */ }
}
@media (prefers-reduced-motion: reduce) {
  .motion-reduce { /* 降级规则 */ }
}
```

### 1.6 浅色主题 (prefers-color-scheme)

```css
@media (prefers-color-scheme: light) {
  :root {
    --bg-deep: #f0f0f5;
    --bg-layer-1: #ffffff;
    --bg-layer-2: #f5f5fa;
    --ink-primary: #1a1a2e;
    /* ... 完整浅色变量覆盖 */
  }
}
```

手动切换按钮在 `base.html` 页脚（`data-theme-toggle`），JS 写 localStorage 并切换 `[data-theme]` 属性。

### 1.7 模板适配

| 模板 | 操作 |
|------|------|
| `base.html` | 引入 `variables.css`，body 用新变量，预埋 `<svg id="orbit-network">` |
| 12个 `pages/*.html` | 替换硬编码色值为 CSS 变量（批量搜索替换） |
| `cvlab/*.html` | **暂不改** — 保持独立样式，P1 阶段迁移 |
| `landing/index.html` | **暂不改** — P1 阶段重构 |

### 1.8 验证

```bash
python app.py                           # 正常启动
# 浏览器检查:
# - 深色主题渲染正确
# - prefers-color-scheme: light 切换正常
# - 手动切换按钮工作
# - 磨砂玻璃仅在三处出现
# - motion-reduce 降级正常
python -m pytest tests/ -x
bash scripts/perf_check.sh              # FCP ≤ 1.5s
```

**验收门禁:**
- [ ] 深色主题为默认，所有页面可渲染
- [ ] `prefers-color-scheme: light` 自动切换 + 手动按钮切换
- [ ] 磨砂玻璃仅限三处（用浏览器 DevTools 搜索 `backdrop-filter` 确认）
- [ ] `.motion-safe` / `.motion-reduce` CSS 类生效
- [ ] 字体从本地加载（DevTools Network 确认无 Google Fonts 请求）
- [ ] FCP ≤ 1.5s (Lighthouse)
- [ ] `perf_check.sh` 通过(对比 Phase 0 baseline)
- [ ] 所有测试通过
- [ ] 安全回归: `pytest tests/test_eval_api.py -k "test_403"` 全部通过

**提交 checkpoint:**
```
git add -A && git commit -m "feat(P0): design foundation — CSS variables + fonts + dark theme + glassmorphism constraint"
```

---

## Phase 2 (P1): 视觉系统 — 追溯链SVG + 轨道网络 + 三级导航

> **目标**: "透明性"和"构造主义"核心视觉落地
> **时间估计**: 5-7小时
> **验收**: 追踪覆盖 ≥ 70% + 轨道线基于真实JSON

### 2.1 `_build_import_graph()` 实现

**文件**: `services/eval/import_graph.py` (新建)

```python
def _build_import_graph(scan_dirs=None):
    """
    扫描指定目录下所有 .py 文件的 import 语句，
    生成模块依赖图 JSON。
    
    性能约束: 执行时间 ≤500ms (当前项目规模)。
    超过则触发 warnings.warn("import_graph slow")。
    
    Returns:
        {"nodes": [{"id": "eval_engine", "path": "services/eval/eval_engine.py"}],
         "edges": [{"from": "eval_engine", "to": "eval_store"}]}
    
    实现: 用 ast 模块解析 (更精确)，降级方案为正则匹配。
    """
```

**执行与缓存策略:**
1. 在应用启动时执行一次（`app.py` 中），结果写入 `data/eval/import_graph.json`
2. 前端通过 `GET /api/eval/orbit-graph` 获取缓存 JSON（该端点直接读取静态文件，不重新计算）
3. 缓存文件不存在（首次启动）→ 端点返回空 JSON → 轨道隐藏

**此为 P1 门禁条件** — JSON 为空则轨道隐藏，不可降级为静态坐标。`perf_check.sh` 增加执行时间测量:
```bash
python -c "from services.eval.import_graph import _build_import_graph; import time; t0=time.time(); g=_build_import_graph(); print(f'{time.time()-t0:.3f}s')"
```

### 2.2 轨道网络 SVG 组件

**文件**: `templates/components/orbit_network.svg` (新建) 或内联在 `base.html`

1. 读取 `_build_import_graph()` JSON（从 `/api/eval/orbit-graph` 端点）
2. 节点坐标: 层级布局 (layer-by-layer, 从上到下)
3. 边: SVG `<path>` 二次贝塞尔曲线，`stroke` 颜色按轨道类型:
   - 链1 (数据采集): `var(--copper-green)`
   - 链2 (评估引擎): `var(--steel-blue)`
   - 链3 (元评估): `var(--amber)`
4. 正常状态: `opacity: 0.12`
5. hover 关联模块: `opacity: 0.4`, `transition: opacity 300ms ease-out`
6. 旋转: 120s/圈, ease-in-out, CSS `transform: rotate()` (绕中心点)
7. **文字标签**: 每条轨道起始端和结束端各一个微小标签（`font-size: 9px`, `opacity: 0.4`, `var(--ink-muted)`），标签文本来自 JSON 模块名称。hover 时标签 `opacity` 提升到 0.8。

### 2.3 追溯链六环 SVG

**文件**: `static/js/modules/trace-chain.js` (新建)

- 六环水平排列: 事件→指标→告警→建议→决策→效果
- 环: SVG `<circle>` 1.5px线宽, 圆角连接线
- 正常: `opacity: 0.08` (水印)
- hover 指标: `opacity: 0.6`, 环依次高亮 (涟漪)
- 点击: 从背景提取到前景, 磨砂玻璃卡片展示完整信息
- 断裂: 断裂处红色虚线 + 脉冲闪烁
- **文字标签**: 每个环下方微小标签（`font-size: 9px`, `opacity: 0.5`），显示环名称。水印状态下 `opacity: 0.3` 仍可见，hover 时 `opacity: 0.8`
- **数据脱敏规则** (硬编码在渲染函数中，不可配置):
  - commit SHA: 仅显示前7位（如 `a3f2c11`）
  - 事件ID: 仅显示事件类型标签（如 "LLM调用"），不显示完整UUID
  - 时间戳: 仅显示相对时间（如 "2h前"），不显示精确ISO时间

### 2.4 三级导航结构

**文件**: `templates/base.html` (修改)

```
L1 (顶部固定, position: sticky):
  [Landing] [评估系统] [知识库] [CV实验室]

L2 (侧边栏, 随L1切换):
  评估系统 → 总览 | 模块详情 | Agent追踪 | 元评估
  CV实验室 → Harris | SIFT | CNN

L3 (页面内):
  追溯面板、评分卡折叠区
```

- L1 4个入口始终可见
- L2 内容动态切换 (当前选中: 铜绿色下划线 2px)
- 移动端 (<768px): L1 横向滚动 + L2 下拉选择

### 2.5 Landing 页面重构

**文件**: `templates/landing/index.html` (修改)

- 应用 CSS 变量体系
- 品牌标记: 1px铜绿圆环24px + "P"字，加载动画 `scale(0.8) → 1` (1.5s, ease-out-expo)
- **品牌动画仅首次播放**: `sessionStorage` 中检查 `brand_animation_played` 标记，首次播放后设置。同一会话内再次访问直接显示最终状态。
- 轨道网络 SVG 背景 (opacity: 0.08, 120s/圈)
- 三大入口节点 (磨砂玻璃卡片, hover 抬升+轨道高亮)
- 底部数据条: Jinja2 服务端渲染, 两步检查逻辑 (已在 Phase 0.6 实现, 此处适配新样式)
- Landing 单独性能预算: **FCP ≤ 1.2s**

### 2.6 CV Lab 模板逐模板迁移

逐个迁移 cv-lab 3个模板到 CSS 变量体系:
1. `index.html` → 适配深色主题 + 继承 base.html
2. `cnn.html` → 适配 + 功能验证
3. `convolution.html` → 适配 + 功能验证

每次迁移一个, 验证功能完整后继续下一个。

**视觉一致性检查清单** (每次迁移必须核对):
1. 所有硬编码色值（`#xxx`、`rgb()`）替换为 CSS 变量引用
2. 按钮、输入框、表格边框统一使用 `var(--bg-layer-3)` 或 `var(--steel-blue)`
3. 图片和图表在深色背景上的对比度检查（文字与背景 ≥4.5:1）
4. 原模板独立 CSS（如 `features.css`）合并到统一 `variables.css` 变量体系，不保留两份独立样式

### 2.7 验证

```bash
# 轨道网络数据源验证
python -c "from services.eval.import_graph import _build_import_graph; g=_build_import_graph(); assert g['nodes']; print(f'{len(g[\"nodes\"])} nodes, {len(g[\"edges\"])} edges')"

# 性能验证
bash scripts/perf_check.sh                  # 对比 Phase 0 baseline python -c "from services.eval.import_graph import _build_import_graph; import time; t0=time.time(); g=_build_import_graph(); assert time.time()-t0 <= 0.5"

# 功能验证
curl http://localhost:5000/                  # Landing 新设计
curl http://localhost:5000/cvlab/harris      # Harris 正常
curl http://localhost:5000/eval              # Dashboard 正常
python -m pytest tests/ -x
# 安全回归
pytest tests/test_eval_api.py -k "test_403"

# 移动端验证 (Chrome DevTools 设备模拟器)
# - iPhone 14: Landing 三节点纵向堆叠、Dashboard 评分卡单列、导航可用
# - iPad: 布局正常, 轨道网络可见
```

**验收门禁:**
- [ ] `_build_import_graph()` 返回非空 JSON (≥5 nodes)，执行时间 ≤500ms
- [ ] 轨道网络 SVG 基于 JSON 渲染 (DevTools 检查 SVG `<path>` 数量)
- [ ] 轨道线带文字标签 (hover 时 opacity 0.4→0.8)
- [ ] 追溯链六环水平排列, hover 涟漪效果正常, 环下方带名称标签
- [ ] 追溯链水印数据脱敏: SHA仅前7位/事件仅类型标签/时间仅相对时间
- [ ] 三级导航 L1/L2/L3 工作正常
- [ ] Landing 品牌标记动画仅首次播放 (sessionStorage)
- [ ] Landing FCP ≤ 1.2s (Lighthouse 单独测量)
- [ ] CV Lab 3个模板全部迁移, 视觉一致性检查清单全部通过
- [ ] 移动端 (<768px) 主流程不中断: 导航可用/卡片单列/轨道隐藏
- [ ] 追踪覆盖率 ≥ 70% (对比 Phase 0 baseline `coverage_baseline.txt`)
- [ ] 浏览器 Console 无 CSP 违规报告
- [ ] 安全回归测试通过
- [ ] `perf_check.sh` 通过 (对比 Phase 0 baseline)

**提交 checkpoint:**
```
git add -A && git commit -m "feat(P1): visual systems — orbit SVG + trace chain + 3-tier nav + cv-lab migration"
```

---

## Phase 3 (P2): 交互与动画 — 微动效 + 水印开关 + 追踪

> **目标**: 系统"活"起来, 但克制——每处动画有触发条件
> **时间估计**: 4-5小时
> **验收**: 6种动画全部可降级 + data-track 覆盖不下降 >30%

### 3.1 六种微动画实现

| 动画 | 实现方式 | 时长 | 缓动 |
|------|---------|------|------|
| 呼吸 | CSS `@keyframes breathe` (scale) | 3s循环 | ease-in-out |
| 涟漪 | JS 依次添加 `.ripple` class | 每环100ms间隔 | ease-out |
| 扫描线 | CSS `@keyframes scan` (opacity+position) | 2s循环 | linear |
| 抬升 | CSS `transition: transform 200ms, box-shadow 200ms` | 200ms | ease-out |
| 汇聚 | JS requestAnimationFrame 粒子动画 | 600ms | ease-in-out |
| 断裂闪烁 | CSS `@keyframes break-pulse` (opacity) | 1.5s循环 | ease-in-out |

所有动画包裹在 `.motion-safe` 下:
```css
.motion-safe .breath { animation: breathe 3s ease-in-out; }
.motion-reduce .breath { /* 静态 */ }
```

### 3.2 水印控制（Esc 快捷键 + UI 开关）

**文件**: `static/js/modules/trace-chain.js` (修改)

- `data-watermark-visible` 属性控制
- 按 `Esc`: 切换 `data-watermark-visible="false"` (隐藏)
- 再按 `Esc`: 恢复 `data-watermark-visible="true"`
- **水印 UI 开关**: 页面底部状态栏（与 beacon 隐私声明同行）增加微小的眼睛图标按钮:
  - `font-size: 11px`, 颜色 `var(--ink-muted)`
  - 点击切换水印显示/隐藏
  - hover 时显示 tooltip "隐藏/显示追溯链水印"
  - Esc 键快捷方式保留
- 页面加载默认可见

### 3.3 data-track 事件委托

**文件**: `static/js/modules/eval-ui.js` (修改)

- 在父容器 (`.eval-container`) 上监听 click
- 根据 `data-track` 属性值自动调用 `EvalAPI.sendBeacon()`
- 替换所有手动 `sendBeacon()` 调用
- 新增可追踪元素只需加 `data-track="action_name"` 属性

### 3.4 统一导航交互

- L1 切换: 整页加载 + 骨架屏 (Flask 多页面模式)
- L2 切换: 同功能区内子页面切换, 骨架屏
- L3: 页面内 Tab/折叠/锚点, 无整页刷新
- 键盘: Tab/Enter/Escape 完整支持

### 3.5 验证

```bash
# 动画验证
# - 所有动画在 .motion-safe 下正常
# - prefers-reduced-motion: reduce 全部降级

# 追踪覆盖验证
python -c "from services.eval.eval_engine import _compute_data_completeness; print(_compute_data_completeness())"
# 确认事件量不下降 >30%

# 水印开关验证
# - 浏览器中按 Esc → 水印隐藏 → 再按恢复

python -m pytest tests/ -x
bash scripts/perf_check.sh
```

**验收门禁:**
- [ ] 6种动画全部可触发 (`.motion-safe`)
- [ ] 6种动画全部可降级 (`.motion-reduce`)
- [ ] 水印控制: Esc 快捷键 + 眼睛图标 UI 开关均可工作
- [ ] `data-track` 事件委托覆盖所有追踪点
- [ ] 追踪事件量不下降 >30% (对比 Phase 0 baseline `coverage_baseline.txt`)
- [ ] 键盘导航 Tab/Enter/Escape 完整
- [ ] 移动端 (<768px) 动画自动降级, 无卡顿
- [ ] 安全回归测试通过
- [ ] `perf_check.sh` 通过 (对比 Phase 0 baseline)

**提交 checkpoint:**
```
git add -A && git commit -m "feat(P2): micro-animations + watermark toggle + data-track delegation"
```

---

## Phase 4 (P3): 3D 实验 — 粒子背景 + Spline (可选)

> **目标**: 增强视觉深度——但完全可选, 不影响核心功能
> **时间估计**: 3-4小时
> **验收**: WebGL 不可用时自动降级

### 4.1 WebGL 检测 + 降级

```javascript
function supportsWebGL() {
  try {
    const canvas = document.createElement('canvas');
    return !!(canvas.getContext('webgl') || canvas.getContext('experimental-webgl'));
  } catch (e) {
    return false;
  }
}
```

WebGL 不可用 → 纯 CSS 渐变背景 (已在 P0 定义)。

### 4.2 Three.js 背景粒子

**文件**: `static/js/modules/particles.js` (新建, 独立文件)

- Three.js CDN 引用 (固定版本 + integrity 哈希)
- <50 粒子, 缓慢浮动
- 初始化 ≤300ms
- 运行时帧率 ≥30fps
- 独立性能预算: 不影响 FCP
- 仅在 Landing 页面加载
- CSP 头显式允许 Three.js CDN 来源

### 4.3 Spline 3D (可选试验)

- 独立组件, 不影响核心 Dashboard
- Spline runtime 固定版本 + integrity 哈希
- 场景文件审查: Network 面板确认无外部请求
- 外部纹理/字体 → 本地化托管
- 任一条件不满足 → 降级为静态 SVG

### 4.4 验证

```bash
# WebGL 检测
# - 正常浏览器: 粒子背景渲染
# - 无 WebGL 浏览器 (或 DevTools 禁用): CSS 渐变降级

# 性能
# - FCP 仍 ≤ 1.5s
# - 粒子初始化 ≤300ms (performance.now() 测量)
# - 帧率 ≥30fps (DevTools FPS meter)

python -m pytest tests/ -x
bash scripts/perf_check.sh
```

**验收门禁:**
- [ ] WebGL 检测自动降级
- [ ] 粒子初始化 ≤300ms
- [ ] FCP 仍 ≤ 1.5s (全局) + Landing ≤ 1.2s
- [ ] 所有核心功能不受 3D 影响
- [ ] CSP 从报告模式切换到强制模式, 无违规
- [ ] 安全回归测试通过
- [ ] `perf_check.sh` 通过 (对比 Phase 0 baseline)

**提交 checkpoint:**
```
git add -A && git commit -m "feat(P3): 3D particle background + WebGL fallback"
```

---

## 回滚策略

每个 Phase 完成后创建独立 commit。任一 Phase 失败:

```bash
# 回滚到上一 Phase
git revert <failed-phase-commit>

# 或完全回滚整个分支
git checkout main
git branch -D feat/design-constructivism
git worktree remove ../portfolio-constructivism
```

worktree 隔离确保 main 分支始终可用。

---

## 执行速查表

| Phase | 内容 | 预估 | 关键门禁 | Commit |
|-------|------|------|----------|--------|
| **0** | 结构合并 (旧样式) | 3-5h | 173 tests + cv-lab不退化 + perf基线 + Landing数据条 + 骨架屏预埋 | `phase0` |
| **P0** | CSS变量+字体+深色基底 | 4-6h | FCP≤1.5s + 玻璃态仅3处 + CSP报告模式 | `P0` |
| **P1** | 追溯链SVG+轨道网络+导航 | 6-8h | JSON非空+≤500ms + 覆盖≥70% + Landing FCP≤1.2s + 移动端 | `P1` |
| **P2** | 微动效+水印UI+data-track | 4-5h | 6动画可降级+追踪不降>30% + 移动端 | `P2` |
| **P3** | 3D粒子+WebGL降级 | 3-4h | FCP≤1.5s + WebGL检测 + CSP强制模式 | `P3` |
| **总计** | | **20-28h** | | |

---

## 文件变更预估

| Phase | 新建 | 修改 | 删除 |
|-------|------|------|------|
| 0 | 8 (blueprints/cvlab/* + landing/* + import_graph skeleton) | 3 (server.py→app.py, base.html, .gitignore) | 0 |
| P0 | 3 (variables.css, fonts/, theme-toggle.js) | 5 (global.css, components.css, base.html, 12页面模板) | 0 |
| P1 | 4 (orbit_network.svg, trace-chain.js, import_graph.py, landing重构) | 6 (base.html, landing, cvlab×3模板, eval-ui.js) | 0 |
| P2 | 1 (动画CSS模块) | 4 (eval-ui.js, trace-chain.js, base.html, global.css) | 0 |
| P3 | 2 (particles.js, spline-loader.js) | 2 (landing/index.html, app.py CSP配置) | 0 |

---

> **约束重申**: 本计划基于 design-brief v2。craft 阶段遇到 brief 未覆盖的决策点必须停下来问。每阶段完成后提交验证报告，不跳跃执行。

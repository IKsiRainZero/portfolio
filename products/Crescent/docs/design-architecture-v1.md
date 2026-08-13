# 前端重构 & 三合一融合 — 架构设计 (v4)

> 状态: **决策稿 (工程稳健性)**。v1→v2→v3→v4。总工程师 + 交互设计顾问联合审查。
> 新增: 合并两步策略(先挂载后迁移)、轨道网络SVG实现决策、后台任务启动顺序、三级导航结构、motion-safe/motion-reduce CSS系统、融合后性能基线保持。
> 已决议全部 Q1-Q6。下一步: PRODUCT.md → 设计 spec → 计划 → 隔离分支执行。

---

## 一、当前系统地图

```
portfolio/                          ← git monorepo 根
├── portfolio-site/                 ← 大门/大厅 (独立 Flask, 493行 index.html, 视频背景)
│   ├── server.py                   ← 独立启动, 端口? 
│   ├── index.html                  ← 单页, 展示作品集
│   └── static/                     ← 视频 + 图片
├── portfolio-app/                  ← 主应用 (Flask, localhost:5000)
│   ├── server.py                   ← 入口, daemon 循环, Blueprint 注册
│   ├── routes/                     ← API 路由 (api_eval, api_ai, api_agent, api_config)
│   ├── services/                   ← 业务逻辑 (eval/, agent_service, rag_service, ...)
│   ├── templates/
│   │   ├── base.html               ← Jinja2 布局 (sidebar + content)
│   │   └── pages/                  ← 12 个页面 (home, eval, knowledge, agent_build, ...)
│   ├── static/
│   │   ├── css/                    ← global.css (80行), components.css (200+行), print.css
│   │   └── js/modules/             ← eval-main, eval-ui, eval-api, eval-slideout, ...
│   └── data/eval/                  ← 评估数据 (traces.jsonl, events.jsonl, scores.json, ...)
├── cv-lab/                          ← CV 教学实验室
│   ├── cv-lab-v3.3/cv-lab/
│   │   ├── app.py                  ← 独立 Flask (localhost:5001)
│   │   ├── templates/              ← 3 个页面 (index, cnn, convolution)
│   │   ├── static/                 ← background.png + css/
│   │   └── algorithms/             ← harris.py, sift.py
│   └── 演示.mp4                     ← 342MB 演示视频
├── electron/                        ← Electron 桌面应用 (独立 package.json)
├── docs/                            ← 文档中心
│   ├── 反馈/                        ← 用户反馈 & 前端设计意见
│   ├── 交付/                        ← agent-design-doc, dataset-doc 等
│   ├── checkpoints/                 ← 阶段 checkpoint
│   └── superpowers/specs/           ← 设计 spec 归档
├── 知识库/                          ← 结构化知识 + 灵感记录
└── CLAUDE.md                       ← 项目指令
```

**关键事实：**
- 3 个独立 Flask 进程（portfolio-app:5000, cv-lab:5001, portfolio-site:?）
- 1 个 Electron 壳（可独立启动，可能包裹某个端口）
- 12 个 Jinja2 模板页面，全部在 `portfolio-app/templates/pages/`
- CSS 设计系统: 浅色主题 "quiet confidence"，`--bg: #f5f3f0`（暖奶油色）
- 评估模块: M1-M6 完整交付，175 tests pass，审计 11 项全部清零

---

## 二、前端设计反馈核心摘要

来源: `docs/反馈/前端设计意见.txt`（"大师兄"的设计哲学 + "徒弟"的技术落地补充）

### 核心诊断

> "建造了一座宏伟的引擎，却把它藏在一个朴素的机箱里。"
> 
> 当前 Dashboard 是"能用的工具"，不是"在叙事中揭示数据的作品"。
> 需要的是**视觉叙事**，不是美化。

### 设计哲学

| 概念 | 含义 | 视觉翻译 |
|------|------|----------|
| **层积岩** (Stratigraphy) | Phase 1→5 层层建造，每层可见 | 色阶区分功能层级，深层=深色，上层=明亮 |
| **透明性** (Radical Transparency) | 每个决策可追溯到原始数据 | 追溯链半透明水印，hover 浮现完整链路 |
| **轨道网络** ("徒弟"补充) | 系统模块间的联通关系 | 三色"轨道"连接链1→链3，非割裂的区域 |

### 三套方案

| 方案 | 色板 | 气质 | 风险 |
|------|------|------|------|
| A. 地质剖面 | 暖沙 `#f5f0e8` + 铜绿 | 古典学术手稿 | 与"建AI系统"定位有代际差 |
| B. 构造主义 ★推荐 | 深灰蓝 `#1a1a2e` + 钢蓝/锈红/铜绿 | 暴露结构、精致克制 | 深色主题需全站重写 |
| C. 有机数字 | 深空 `#0a0a0f` + 算法渐变色 | 生成艺术、生命力 | 性能和维护负担大 |

**推荐: B 为主，辅以 C 的微动画（扫描线、呼吸感、粒子汇聚）。**

### 实施四阶段

| 阶段 | 内容 | 优先级 |
|------|------|--------|
| P0 | CSS 变量替换 + 玻璃态引入 + 性能基线 (FCP ≤1.5s) | 🔴 基础 |
| P1 | 追溯链可视化升级 + 弱 Three.js 背景层 | 🟡 增强 |
| P2 | 微动效融合 + C.U.R.E. 审核 + prefers-reduced-motion | 🟡 增强 |
| P3 | Spline 3D 试验性引入 (隔离组件) | 🟢 未来 |

### 新 CSS 变量框架（构造主义色板）

```css
:root {
  --bg-deep: #0f0f1a;        --bg-layer-1: #1a1a2e;
  --bg-layer-2: #222240;     --bg-layer-3: #2a2a4a;
  --steel-blue: #3b82f6;     --rust-red: #c44536;
  --copper-green: #00b4d8;   --amber: #f59e0b;
  --glass-bg: rgba(255,255,255,0.03);   --glass-border: rgba(255,255,255,0.06);
  --shadow-1/2/3: ...;       --shadow-glow-blue/red: ...;
}
```

### 用户反馈要点（来自总调查官）

1. 指标太泛化，看不到具体模块 → 需要模块级下钻
2. 建议不可点击，无探索空间 → 需要结构化元数据 + 可点击链接
3. 元评估信息量严重不足 → 需要完整展示 + 中文映射
4. 评分没有基线和对比 → 需要参照系（系统均值/历史/基线）
5. 评估与其它模块对接不可见 → 需要跨模块联动可视化

---

## 三、三合一融合构想

### 核心隐喻

```
知识库 (理论层)  →  cv-lab (实践层)  →  eval (反思层)
     ↑                                      │
     └────────── 反馈循环 ←─────────────────┘
```

### 角色重新定义

| 组件 | 当前 | 融合后 |
|------|------|--------|
| **portfolio-site** | 独立 Flask, 单页视频背景 | 整个平台的大门/大厅。展示做了什么，导航到各子模块 |
| **cv-lab** | 独立 Flask :5001 | 知识库的"实践操作层"。知识 → 可视化 → 交互验证 |
| **portfolio-app** (eval) | 内嵌在 portfolio-app | 后台评估引擎。评估所有模块健康度，产出改进建议 |
| **知识库** | 文件系统 JSON | 内容不变。cv-lab 成为其可视化实践的前端 |

### 目标目录结构 (草案)

```
portfolio-main/                     ← 重命名自 portfolio-app/
├── app.py                          ← 单入口 Flask 应用
├── blueprints/
│   ├── eval/                       ← 评估模块 (现 routes/api_eval.py)
│   ├── cvlab/                      ← cv-lab 迁移 (现 cv-lab/cv-lab-v3.3/cv-lab/app.py)
│   ├── agent/                      ← agent 模块
│   ├── knowledge/                  ← 知识库浏览
│   └── landing/                    ← 大门/大厅 (现 portfolio-site/)
├── templates/
│   ├── base.html                   ← 统一布局 (暗色主题? 导航系统?)
│   ├── landing/                    ← 大门页面
│   ├── cvlab/                      ← CV 实验页面 (cnn, convolution, ...)
│   ├── eval/                       ← 评估 Dashboard
│   └── pages/                      ← 其余页面
├── static/
│   ├── css/                        ← 统一设计系统
│   ├── js/                         ← 统一 JS
│   └── assets/                     ← 视频、图片
├── services/                       ← 后端服务层 (不变)
├── data/                           ← 评估 + 知识库数据
└── docs/                           ← 文档
```

### 端口统一

- 融合后: **单端口 localhost:5000**（所有 Blueprint 注册到一个 Flask app）
- Electron 外壳指向 `localhost:5000`
- 启动命令: `python app.py`（一个命令启动一切）

---

## 四、关键决策问题（待讨论）

### Q1: 浅色 → 深色 ✅ 已决议

**决议: 方案B改良版 — 默认深色构造主义 + `prefers-color-scheme` 自动切换 + 手动切换按钮。**

理由:
- 深色默认契合"深夜自审"的核心使用场景和"构造主义"的视觉哲学
- CSS 变量体系让双模式切换成本极低
- 保留浅色备选——有些人在白天更喜欢浅色，不影响核心设计系统的完整性
- 物理场景句: "一个工程师在凌晨1点打开 Dashboard，审视自己昨天搭建的系统是否在健康运行。房间只有屏幕的光。他需要快速理解数据，而不是被亮色闪到眼睛。"

### Q2: 回滚策略

前端改动高风险。建议:
- 用 `git worktree` 在隔离分支 `feat/design-constructivism` 上做所有前端工作
- 原 `main` 分支完全不动
- 每个 P 阶段完成后 merge 回 main
- 每个 checkpoint 都保证 `python app.py` 可正常启动

### Q3: 先合还是先美？ ✅ 已决议

**决议: 方案A（先合再美）+ 一个硬性条件。**

条件: 合并时必须同步引入新的 CSS 变量框架。不是"先合并成旧样式再美化"，而是"合并时就用新变量框架，只是先不发挥其全部潜力"。这确保合并后的代码直接兼容后续美化。

理由: cv-lab 只有 3 个模板 + 少量 JS，迁移为 Blueprint 的工作量可控。结构稳定了再化妆，否则对着要变的结构做设计会返工。

### Q4: impeccable 技能的角色 ✅ 已决议

**决议: 以本文档 v2（含视觉设计规范）作为 impeccable `init` 的输入。**

流程:
1. `init` 阶段 — 用本文档建 PRODUCT.md（产品身份定义）
2. `shape` 阶段 — 验证设计哲学和视觉规则是否自洽（不要过度反复——已有清晰方向和详细规则）
3. `craft` 阶段 — 严格按 spec 执行
4. `audit`/`polish` — 质量门禁

### Q5: 命名

- `portfolio-app` → `portfolio-main`？
- `cv-lab` → 保留原名作为 Blueprint 名称
- `portfolio-site` → 融合后消除，其功能由 `landing/` Blueprint 替代

### Q6: Electron 的位置

当前 Electron 在 monorepo 根。融合后它应该是"指向 `localhost:5000` 的桌面壳"——不需要改，只需要确认端口统一后它正常连接。

---

## 五、建议的后续流程

```
本文档 (v1 讨论稿)
    ↓ 讨论 → 达成共识
design-architecture-v2.md           ← 决策记录
    ↓
[impeccable init] → PRODUCT.md     ← 产品身份定义
    ↓
docs/superpowers/specs/             ← 设计 spec (合并反馈文档内容)
    ↓
docs/superpowers/plans/             ← 实施计划 (分阶段)
    ↓
git worktree → feat/design-xxx      ← 隔离执行
    ↓
Phase-by-phase merge → main
```

---

## 六、视觉设计规范

> 以下内容来自美术与设计前端大师的补充。将"层积岩""构造主义""透明性"翻译为可执行的视觉规则。

### 6.1 设计系统的物理场景

设计系统不是从色板开始的，是从**谁在什么情况下使用**开始的。三个核心场景：

**场景A：深夜自审。** 工程师在凌晨1点打开Dashboard，房间只有屏幕的光。他需要快速判断系统健康状态。→ 深色主题为默认，减少眼部疲劳。关键告警（P0）必须在黑暗中清晰可见。柔和微光替代刺眼高亮。

**场景B：白天演示。** 向客户或合作者展示项目成果。对方不关心技术细节，需要在30秒内感受到"这个系统是活的、可信的"。→ 视觉叙事优先：从大门进入，看到系统总览（活的），点击下钻看到追溯链（透明的）。微动画创造"系统在呼吸"的感觉。

**场景C：开发调试。** 开发者追踪一个具体的告警，需要从事件到效果的完整链路。→ 信息密度优先。追溯链清晰、数据可复制、时间戳精确。装饰性元素此时退居背景。

**设计原则**：一个设计系统同时服务于三个场景。默认深色（场景A），演示时展示动画（场景B），调试时动画自动减弱（场景C，通过 `prefers-reduced-motion` 检测）。

### 6.2 层积岩的视觉规则

"层积岩"是这个项目最核心的视觉隐喻——Phase 1到5层层建造，每一层都可见，每一层都不同。CSS 翻译：

**规则1：功能层级决定颜色深度。**
- 最底层（基础设施：trace_logger, eval_store）：最深色 `--bg-deep: #0f0f1a`
- 中间层（评估引擎：eval_engine, meta_evaluator）：中间色 `--bg-layer-1: #1a1a2e`
- 上层（元评估：L2自检, probe cards）：更亮 `--bg-layer-2: #222240`
- 最上层（Dashboard展示层）：最亮 `--bg-layer-3: #2a2a4a`

**规则2：层与层之间用"地质分界线"分隔。**
- 不是生硬的 `border: 1px solid`，而是微妙的渐变阴影：`box-shadow: 0 4px 16px rgba(0,0,0,0.5)` 在下方层产生"沉积"感。
- 每条分界线底部有一条极细的强调线（1px），颜色是该层数据所属的"结构色"（钢蓝=数据流，铜绿=成功状态，锈红=告警）。

**规则3：追溯链像"地质剖面"般展开。**
- 六环水平排列，环与环之间用细线连接（1px，钢蓝色）。
- hover一个环时，该环微微上浮（`translateY(-2px)`），下方出现阴影（像岩层被抬升）。
- 环的"深度"（z-index + box-shadow层级）对应其所属的Phase——事件环在最底层，效果环在最上层。

### 6.3 轨道网络的视觉设计

"徒弟"提出的"轨道网络"概念具象化为三种轨道对应三链闭环：

| 轨道 | 颜色 | 功能 | Dashboard 表现 |
|------|------|------|----------------|
| 链1（数据采集） | 铜绿 | 连接模块到数据存储 | 从左侧"数据源"区域发出的细线 |
| 链2（评估引擎） | 钢蓝 | 连接数据到评分 | 中央汇聚的环形 |
| 链3（元评估） | 琥珀 | 连接评估到自省 | 从中央向外辐射的虚线 |

**轨道不是装饰**——它们是数据流的视觉化。当某个模块被评估时，对应轨道短暂高亮（`opacity: 0.15 → 0.4 → 0.15`，持续2秒），让用户感知"系统正在工作"。

**轨道在Dashboard上的物理位置：**
- 在页面背景中，使用 **SVG `<path>`** 绘制极细的线条（`opacity: 0.12`，正常状态下几乎不可见）。不用 Three.js/canvas——轨道是低频更新的，SVG+CSS transition 性能开销几乎为零。
- 路径使用二次贝塞尔曲线（`<path d="M... Q... T..."/>`）确保平滑。
- 当用户hover一个模块或指标时，关联的轨道高亮（`opacity: 0.4`，CSS `transition: opacity 300ms ease-out`），显示数据流向。
- 轨道路径基于 `_build_import_graph()` 产出的 JSON 驱动——不是装饰，是真实架构的可视化。节点坐标自动布局（层级布局算法）

### 6.4 色彩系统的心理学映射

构造主义色板不是随意选择的。每种颜色的语义绑定：

| 颜色 | CSS变量 | 语义 | 触发条件 |
|------|---------|------|----------|
| 深灰蓝黑 | `--bg-deep` | 可信、稳定、专业 | 全局背景 |
| 钢蓝 | `--steel-blue` `#3b82f6` | 数据、连接、逻辑 | 链接、活跃态、数据线 |
| 锈红 | `--rust-red` `#c44536` | 危险、紧急、断裂 | P0告警、评分<0.5、追溯链断裂 |
| 铜绿 | `--copper-green` `#00b4d8` | 成功、完整、活力 | 评分>0.9、追溯链完整、系统正常 |
| 琥珀 | `--amber` `#f59e0b` | 警告、过渡、待定 | P1告警、评分0.5-0.7、探测卡未决 |

**色彩强度规则**：
- 正常状态下，强调色仅以1-2px的细线或微小图标出现——克制。
- 告警状态下，对应颜色扩大到卡片边框或背景微光——有节制的醒目。
- 演示模式下，色彩饱和度整体提升10%——为投影仪优化。

### 6.5 微动画词典

所有动画必须有明确的触发条件和持续时间。以下是动画词汇表：

| 动画名 | 触发 | 效果 | 时长 | 缓动 |
|--------|------|------|------|------|
| **呼吸** | 关键指标数值更新 | `scale(1.0 → 1.02 → 1.0)` | 3s循环 | `ease-in-out` |
| **涟漪** | hover追溯环 | 从第一环到最后一环依次短暂高亮 | 每环100ms间隔 | `ease-out` |
| **扫描线** | 元评估运行中 | 页面边缘1px蓝色线，`opacity 0→0.3→0` | 2s循环 | `linear` |
| **抬升** | hover评分卡 | `translateY(-2px)` + `box-shadow`加深 | 200ms | `ease-out` |
| **汇聚** | hover趋势标注点 | 周围粒子（微小的半透明圆点）向该点汇聚 | 600ms | `ease-in-out` |
| **断裂闪烁** | 追溯链断裂 | 断裂处红色虚线，`opacity`脉冲 | 1.5s循环 | `ease-in-out` |

**工程实现**：不依赖 JS 检测。在 `global.css` 中定义 `.motion-safe`（仅在 `prefers-reduced-motion: no-preference` 时生效）和 `.motion-reduce`（在 `prefers-reduced-motion: reduce` 时生效）。所有动画规则包裹在 `.motion-safe` 下。

**降级规则**（包裹在 `.motion-reduce` 下）：
- 呼吸 → 取消动画，静态显示
- 涟漪 → 直接高亮所有环，无依次动画
- 扫描线 → 取消
- 汇聚 → 取消，仅显示tooltip
- 抬升 → 取消 transform，保留 shadow
- 断裂闪烁 → 静态红色虚线，不闪烁

### 6.6 三套方案的视觉对比（更新）

| 方案 | 首屏印象 | 数据呈现 | 追溯链 | 适用场景 |
|------|----------|----------|--------|----------|
| A. 地质剖面 | 像翻开19世纪科学手稿。温暖、可信、有学术深度。 | 数据卡片像手绘标本标签。 | 像地层剖面图，环间用细铜线连接。 | 技术审稿、学术展示 |
| B. 构造主义 ★ | 像走进精致的工业博物馆。深邃、克制、结构暴露。 | 数据卡片像磨砂玻璃下的精密仪器。 | 像管道系统，环间用钢蓝管道连接。 | 技术同侪、工程演示 |
| C. 有机数字 | 像发现活的数字生命体。前沿、有机、不可预测。 | 数据随微光波动，评分像心跳。 | 像神经网络突触，环间用微光粒子连接。 | 发布演示、第一印象 |

**最终推荐: B为主，辅以C的微动画。** 核心理由: B的"结构暴露"与项目核心宣言完全一致——"一个人+AI+正确方法论，可以连续建造复杂系统而不陷入混乱。"构造主义正是这一宣言的视觉证据：结构就在这里，每一层都可以追溯。

### 6.7 响应式与性能的视觉约束

- **首次内容绘制（FCP）≤ 1.5秒。** 限制了背景动画复杂度。Three.js粒子系统在低端设备上必须降级为纯CSS渐变。
- **磨砂玻璃降级**：`@supports (backdrop-filter: blur())`检测。不支持的浏览器使用 `background: rgba(26,26,46,0.95)` 纯色替代。同级模糊元素 ≤ 8个。
- **移动端（<768px）**：追溯链从水平六环改为垂直列表。轨道网络隐藏。评分卡从三列改为单列堆叠。Tab导航改为下拉选择。
- **打印**：保留 `print.css`。打印时移除所有背景色、动画、玻璃态，仅保留黑色文字和边框。

---

## 七、视觉参考线框

> 让读者能"看到"未来。不是最终设计稿，是讨论的视觉锚点。

### 7.1 大门页面视觉叙事

大门页面是用户的第一印象。需要在3秒内传达三层信息：
1. 这是一个关于"建造系统"的项目（不是普通的作品集）
2. 系统是活的、在运行的（不是静态展示）
3. 可以深入探索（有清晰的导航）

**具体视觉构想**：
- **背景**：深空蓝黑（`#0f0f1a`），中央有一个微弱的"轨道网络"动画——三条极细的线（铜绿、钢蓝、琥珀）缓慢旋转，模拟系统正在运行。
- **前景**：中央大字："PORTFOLIO"（Inter Bold, 4rem, `letter-spacing: -0.03em`）。下方一行小字："一个人+AI+正确方法论，可以连续建造复杂系统而不陷入混乱。"（`font-size: 1rem, opacity: 0.7`）
- **导航**：不是传统的菜单栏，而是三个悬浮的"节点"——评估系统、知识库、CV实验室——每个节点是一个磨砂玻璃圆角矩形，hover时微微上浮并显示简介。
- **底部**：一行极小的实时数据："系统当前健康度: 0.85 | 上次评估: 2小时前 | 活跃模块: 22"——让用户在第一眼就感知到"这是活的"。

### 7.2 评估Dashboard视觉重构

当前Dashboard是4个Tab面板。重构后的视觉结构：

```
┌──────────────────────────────────────────────┐
│  顶部横幅: 系统总评分(大数字) + 评估体系自指状态  │
│  ┌─────────────────────────────────────────┐ │
│  │ 总览面板                                │ │
│  │  [雷达图]  [趋势线带标注点]  [P0告警横幅] │ │
│  │  背景: 极细的轨道网络线 (opacity:0.15)    │ │
│  └─────────────────────────────────────────┘ │
│  模块详情 / Agent追踪 / 元评估 (Tab切换)       │
│  ┌─────────────────────────────────────────┐ │
│  │ [评分卡 L1] [评分卡 L2折叠] [追溯面板]     │ │
│  │ hover时对应轨道高亮                      │ │
│  └─────────────────────────────────────────┘ │
│  底部: 数据新鲜度 + beacon隐私声明             │
└──────────────────────────────────────────────┘
```

**关键视觉变化**：
- 背景不再是单一纯色，而是有极细轨道线的深色基底
- 面板之间不再是生硬边框，而是磨砂玻璃+阴影的层叠关系
- 告警横幅不再是静态红色条，而是有微弱脉冲动画（`box-shadow`的`opacity`在0.2-0.5之间波动）

### 7.3 追溯链的视觉重构

当前追溯面板是侧边栏滑出，显示JSON数据。重构后：

- 追溯链在页面背景中持续存在，以极淡的水印形式（`opacity: 0.08`）显示当前选中指标的完整六环链路。
- 用户hover指标时，水印追溯链变为半透明（`opacity: 0.6`），六环依次高亮。
- 点击后，追溯链从背景"提取"到前景，以磨砂玻璃卡片形式展示完整信息。
- 每个环显示关键数据摘要（如"data_completeness: 0.72"），点击该环跳转到对应面板。

**这是"透明性"设计哲学的落地**——追溯链不是"需要时才打开的弹窗"，而是"始终存在、等待被揭示的故事"。

---

## 八、安全与架构加固

> 审计AI + 安全审计师联合审查。以下六项加固不削弱视觉设计的任何魅力，只是确保"内脏和皮肤同样健康"。

### 8.1 轨道网络数据源：必须基于真实导入关系

**风险**：美术大师的"轨道网络"需基于模块导入关系渲染。但当前系统中不存在结构化的模块依赖图。如果轨道用静态坐标手动定义，它会退化为"看起来像数据流，实际上不反映任何真实数据"的装饰——这是**看起来是活的，其实是死的**的陷阱。

**要求**：
1. 重构计划中新增任务：编写 `_build_import_graph()` 函数，扫描 `services/` 和 `routes/` 下所有 `.py` 文件的 `import` 语句，生成模块依赖图 JSON（格式：`{"nodes": [...], "edges": [{"from": ..., "to": ...}]}`）。
2. 前端轨道网络基于此 JSON 渲染 SVG/canvas 连线，节点坐标自动布局（力导向或层级布局）。
3. **如果 JSON 不存在或为空，轨道网络降级为隐藏状态，不渲染虚假连接线。** 这是硬性约束。

### 8.2 3D 依赖安全基线

**风险**：Three.js 和 Spline 需要 GPU 访问、可能加载外部纹理、可能收集设备信息。CDN 被劫持可导致脚本注入。Spline 场景文件可能向第三方服务器发送请求——**数据渗出**风险。

**要求**：
1. 任何第三方 CDN 库（Three.js、Spline runtime）必须**固定版本号 + `integrity` 哈希**。与 Chart.js 安全实践一致。
2. Spline 场景文件必须审查网络请求行为——在浏览器 DevTools Network 面板确认不向外部域名发送请求。
3. Spline 如需加载外部纹理/字体，必须**本地化托管**，不依赖第三方 CDN。
4. 如当前有 CSP 配置，显式允许新库来源。如无 CSP，重构时添加最低限度 CSP。
5. 3D 背景层独立性能预算：
   - Three.js 初始化 ≤300ms
   - 运行时帧率 ≥30fps
   - WebGL 不可用时（`canvas.getContext('webgl')` 返回 null），自动降级为纯 CSS 渐变背景
6. P3 阶段的 Spline 3D 为**可选试验性功能**，不影响核心 Dashboard 可用性。

### 8.3 追溯链水印隐私控制

**风险**：追溯链水印（`opacity: 0.08`）在截屏或投屏时可能被提取放大，意外暴露内部系统信息（事件ID、指标值、commit SHA）。虽非用户隐私数据，但"Radical Transparency"需要给用户对透明程度的控制权。

**要求**：
1. 追溯链水印组件预留 `data-watermark-visible` 属性，方便后续实现开关。
2. 计划 P2 阶段实现：按 `Esc` 键临时隐藏水印，再按恢复。
3. 水印中**不显示完整 commit SHA**（只显示前7位），**不显示完整事件ID**（只显示事件类型）。此约束在视觉设计层面已经降低信息暴露风险。

### 8.4 前端行为追踪覆盖保护

**风险**：前端重构涉及大量 DOM 结构变更。当前追踪是手动埋点（`EvalAPI.sendBeacon('tab_switch', 'overview')`），重构后大量交互点变化会导致追踪覆盖系统性下降。`data_completeness` 指标会在重构后静默退化——因为它检测到的用户交互事件减少，但它会报告为"数据采集正常"（因为缺少事件本身是静默的）。

**要求**：
1. 重构验收标准增加：重构完成后运行 `_compute_data_completeness()`，对比重构前后24h的前端行为事件数量。**如事件量下降 >30%，阻塞合并。**
2. 优先使用**事件委托**（在父容器监听点击，根据 `data-track` 属性自动发射追踪事件），而非在每个按钮手动调用 `sendBeacon`。降低重构时追踪丢失风险。
3. 新增 `data-track` 属性规范：所有可追踪交互元素必须有此属性，值为 `"action:context"` 格式（如 `data-track="tab_switch:overview"`）。

### 8.5 字体与CSS本地化托管

**风险**：Inter 和 JetBrains Mono 若通过 Google Fonts CDN 加载，CDN 被劫持可导致 CSS 注入——攻击者可隐藏告警横幅、修改评分颜色。这不是理论风险。

**要求**：
1. Inter 和 JetBrains Mono 字体文件必须**本地化托管**在 `static/fonts/` 下。
2. 使用 `@font-face` 引用本地文件，不通过任何外部 CDN。
3. 字体文件入 Git 版本控制（非 `.gitignore`）。单文件 ≤5MB。
4. 未来如需引入外部 CSS/字体 CDN，必须使用 `integrity` 哈希校验。

### 8.6 cv-lab Blueprint 迁移安全扫描

**风险**：cv-lab 原为独立 Flask 应用（独立端口、独立安全上下文）。迁移到 `portfolio-main` 后共享 `SECRET_KEY`、session、CORS 配置。cv-lab 的任何未修复 XSS 漏洞（用户上传图片处理、CV 算法参数回显）将影响同一域名下的评估 Dashboard。

**要求**：
1. 迁移 cv-lab 前，对其路由进行快速安全扫描：
   - 检查所有 `request.args` / `request.form` 输入是否经过转义
   - 检查是否有 `send_file` / `send_from_directory` 的不安全使用
2. 迁移后确认 `SESSION_COOKIE_HTTPONLY=True` 和 `SESSION_COOKIE_SAMESITE='Lax'` 配置仍然生效。
3. 安全扫描结果记录到迁移 commit message 或 checkpoint 文档中。

---

## 九、工程稳健性与用户体验路径

> 总工程师 + 交互设计顾问联合审查。确保重构不破坏已有系统完整性的必要约束。

### 9.1 融合顺序的工程策略：两步迁移

**风险**：cv-lab 的 3 个模板（index, cnn, convolution）没有继承 `base.html`，有自己的 `<head>`、独立CSS、特定DOM结构的JS逻辑（CNN可视化、卷积演示）。直接适配新CSS变量体系可能破坏交互功能。

**决议：两步走，不做 iframe（iframe 无法共享 session 和 CSS 变量）。**

1. **第一步（合并期）**：cv-lab 以独立 Blueprint 挂载，路由前缀 `/cvlab/`。模板暂时保持独立 `<head>` 和独立 CSS 文件，不强制继承 `base.html`。确保交互功能（CNN可视化、Harris角点检测、SIFT特征匹配）不退化。
2. **第二步（设计重构期）**：逐模板迁移到新CSS变量体系 + 统一 `base.html` 布局。每次迁移一个模板（index → cnn → convolution），验证功能完整后继续下一个。

### 9.2 轨道网络的实现决策：SVG，不是 Three.js

**决策**：轨道网络用 SVG 实现，不用 Three.js。

理由：轨道是静态或低频更新的（仅在 hover 时高亮），不需要 GPU 渲染。SVG + CSS transition 性能开销几乎为零。Three.js 留给 P1/P3 的"背景粒子"等真正需要 GPU 的场景。

**具体约束**：
- 轨道线路径使用 SVG `<path d="M... Q... T..."/>`（二次贝塞尔曲线），确保平滑。
- 正常状态 `opacity: 0.12`，hover 关联模块时 `opacity: 0.4`，CSS `transition: opacity 300ms ease-out`。
- 节点坐标由 `_build_import_graph()` 产出的 JSON 驱动，前端自动布局（Dagre 或简单的层级布局算法）。
- 不引入额外 JS 库——轨道渲染函数约 60 行纯 JS + SVG DOM 操作。

### 9.3 融合后的后台任务协调

**风险**：当前 `server.py` 启动多个后台线程（评估循环 1h、L2 独立 Timer、LLM Judge 消费者）。cv-lab 的算法（`harris.py`、`sift.py`）是同步阻塞的 CPU 密集型任务。

**要求**：
1. cv-lab 的算法函数**不得在 Flask 请求线程中直接调用**。使用 `concurrent.futures.ThreadPoolExecutor`（max_workers=2）异步执行，或预计算并缓存结果为静态 JSON。
2. 融合后的 `app.py` 需定义**启动顺序**：
   ```
   1. Flask app 创建 + config 加载
   2. Blueprint 注册 (eval, cvlab, landing, agent, knowledge)
   3. 后台线程启动 (评估循环, L2 Timer, LLM Judge 消费者)
   4. app.run() 监听端口
   ```
3. 启动顺序文档化——在 `app.py` 顶部注释中明确标注。

### 9.4 统一导航：三级结构

**问题**：当前 `base.html` 侧边栏已承载 12 个页面链接。加入 cv-lab + 知识库浏览后导航臃肿。

**决议：三级导航结构**：

| 级别 | 位置 | 内容 | 示例 |
|------|------|------|------|
| **一级** | 侧边栏顶部 / 顶栏 | 四大功能区入口 | 大门、评估系统、知识库、CV实验室 |
| **二级** | 侧边栏下方 / Tab | 每个功能区内部的子页面 | 评估: 总览/模块详情/Agent追踪/元评估 |
| **三级** | 页面内 | 深度内容锚点/折叠区 | 追溯链、评分卡 L2/L3 折叠、建议滑出面板 |

评估 Dashboard 的 Tab 系统（总览/模块详情/Agent追踪/元评估）已经实现了三级导航的部分模式，需推广到全局。

### 9.5 微动画的工程实现：CSS 媒体查询自动降级

**决策**：不依赖 JavaScript 检测 `prefers-reduced-motion`，用 CSS 媒体查询自动处理。

**实现**：在 `global.css` 中定义两个全局类：

```css
@media (prefers-reduced-motion: no-preference) {
  .motion-safe {
    /* 所有动画在此生效 */
  }
}
@media (prefers-reduced-motion: reduce) {
  .motion-reduce {
    /* 降级规则：取消动画、简化过渡 */
  }
}
```

- 所有 6 种微动画的 CSS 规则包裹在 `.motion-safe` 下
- 降级规则包裹在 `.motion-reduce` 下（呼吸→静态、涟漪→全亮、扫描线→隐藏、汇聚→tooltip、抬升→保留阴影无位移、断裂闪烁→静态红色虚线）
- 不需要 JS 检测——CSS 媒体查询本身就能响应系统设置变化

### 9.6 融合后性能基线保持

**硬性要求**：
1. 融合后 `bash scripts/perf_check.sh` 必须通过（`/api/eval/summary` p95 < 500ms，后台循环 < 60s）。
2. cv-lab `background.png` 压缩至 500KB 以内。
3. `演示.mp4` (342MB) 不入 Git，用 `.gitignore` 排除。
4. cv-lab 算法计算如需异步执行，用 `ThreadPoolExecutor` + 结果缓存。

---

## 附录A: 技术要点备忘

**合并相关:**
- Flask Blueprint 迁移: `cv-lab/app.py` 的 3 个路由可转为 `cvlab_bp`
- 模板继承: cv-lab 当前无 base.html，需要适配统一布局
- 静态资源: `cv-lab/static/background.png` (6MB) 需压缩
- `演示.mp4` (342MB) 不应入 git，用 `.gitignore` 排除
- cv-lab 算法文件 (`harris.py`, `sift.py`) 直接放 `services/cvlab/` 或保持 `algorithms/`
- 端口: 确保 Electron `main.js` 指向统一端口

**安全相关 (v3 新增):**
- 字体本地化: Inter + JetBrains Mono → `static/fonts/`，`@font-face` 引用，入 Git
- CDN 完整性: 所有外部库固定版本 + `integrity` 哈希
- CSP: 重构时添加最低限度 Content-Security-Policy 头
- 追踪保护: 前端使用 `data-track` 属性 + 事件委托，减少手动埋点
- 验收门禁: 重构后追踪事件量下降 >30% → 阻塞合并
- 追溯链水印: 组件预留 `data-watermark-visible`，commit SHA 仅显示前7位，事件ID仅显示类型
- 3D 降级: WebGL 不可用时纯 CSS 渐变替代
- cv-lab 安全扫描: 迁移前检查 XSS + `send_file` 不安全使用 + session cookie 配置

**工程相关 (v4 新增):**
- 融合策略: 两步走——先 Blueprint 挂载(保持独立样式) → 逐模板迁移到新CSS变量
- 启动顺序: 1.Config→2.Blueprint注册→3.后台线程→4.app.run()
- 轨道网络: SVG `<path>` + 二次贝塞尔曲线，opacity 0.12→0.4，300ms transition
- cv-lab算法: ThreadPoolExecutor(max_workers=2) 异步执行或预计算缓存
- 导航: 三级结构(一级4功能区 / 二级子页面 / 三级页面内)
- 微动画降级: `.motion-safe` / `.motion-reduce` CSS类，媒体查询自动切换
- 性能基线: `perf_check.sh` 必须通过，background.png ≤500KB

## 附录B: 设计资产清单

实施时需要的设计资产：

| 类别 | 内容 | 来源 | 优先级 |
|------|------|------|--------|
| 字体 | Inter (标题+正文) + JetBrains Mono (数据/代码) | **本地托管** `static/fonts/`, 不依赖 Google Fonts CDN | P0 |
| 图标 | 六环追溯链SVG (事件/指标/告警/建议/决策/效果) | 内联SVG, 1.5px线宽, 圆角连接 | P0 |
| 图标 | 三轨道状态指示器 (铜绿/钢蓝/琥珀) | 纯CSS实现, 2px环 + 微光 | P1 |
| 纹理 | 微噪点纹理 (叠加层, `opacity: 0.03`) | CSS `background-image` data URI | P1 |
| 3D | 背景粒子系统 (可选, WebGL检测 + 降级) | Three.js, <50 particles, <100KB, `integrity`哈希, 独立性能预算 | P3 |
| 音效 | 无。此项目不使用音效反馈 | — | — |

---

## 更新后的后续流程

```
本文档 v4 (决策稿 + 视觉规范 + 安全加固 + 工程稳健性)
    ↓
[impeccable init] → PRODUCT.md          ← 以本文档为输入
    ↓
[impeccable shape] → 验证设计自洽        ← 不过度反复
    ↓
docs/superpowers/specs/                  ← 设计 spec (合并反馈文档+本文档内容)
    ↓
docs/superpowers/plans/                  ← 实施计划
    │                                       ├── Phase Merge: cv-lab Blueprint(两步迁移) + 安全扫描 + 启动顺序
    │                                       ├── P0: CSS变量替换 + 字体本地化 + 玻璃态 + motion-safe系统
    │                                       ├── P1: 追溯链SVG + _build_import_graph + 轨道网络SVG
    │                                       ├── P2: 微动效 + 水印开关 + data-track事件委托 + 三级导航
    │                                       └── P3: 3D试验 (WebGL检测 + 降级)
    ↓
git worktree → feat/design-constructivism ← 隔离执行
    ↓
Phase-by-phase merge → main
验收门禁: FCP≤1.5s + 追踪覆盖≥70% + perf_check.sh通过 + 安全扫描通过 + cv-lab交互不退化
```

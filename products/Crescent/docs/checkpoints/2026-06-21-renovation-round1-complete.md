# Checkpoint: 首轮页面翻新完成 — 9 页统一设计语言

> 日期: 2026-06-21 | 分支: `feat/construction-renovation` | 提交: 48 个 (本轮累计)

## 背景

6 月 19-20 日完成了页面独立化基础设施（Router 导航引擎、`App.ready()` 生命周期、CSS 过渡系统、page-wrapper `height:100%` 继承链）。6 月 21 日启动"页面逐页翻新"——把每个功能页面从一个纯功能性 layout 变成有场景感的沉浸式体验，统一设计语言但各有独立隐喻。

## 完成清单

| # | 页面 | 路由 | 隐喻 | 提交 | 核心资产 |
|---|------|------|------|------|----------|
| 1 | 同桌 | `/` | 3D 木桌面 + Q版同桌 | 12 | SVG mascot, 拖拽桌面物品, 仪表盘 widget, 3D perspective |
| 2 | 教室 | `/classroom` | 下午教室 + 浮空黑板 | 10 | Canvas 粉笔尘粒子, 黑板+粉笔槽+粉笔, 暖光光晕, 半透明面板 |
| 3 | 面试 | `/interview` | 冷灰蓝会议室 + 荧光灯 | 7 | 可见台灯(可开关/拖拽/调强度), 浮尘粒子, 玻璃隔断, 简历高亮联动 |
| 4 | 训练器 | `/trainer` | 木桌 + 纸本练习册 | 7 | 纸面卡片系统(hard shadow), 笔记本格线, 按钮按下物理, 进度闪光 |
| 5 | 课本 | `/textbook` | 打开的大开本课本 | 5 | 书脊渐变, 书页叠加曲线, 角书签循环导航, 工作日志 Chart.js 图表 |
| 6 | 学习计划 | `/study-plan` | 便利贴 + 纸屑 | 2 | 图钉 ::before, 卡片微旋转, Canvas 50 纸屑粒子, 彩色任务便签网格 |
| 7 | 施工现场 | `/construction` | 警示条纹 | 3 | 黄黑斜条纹(repeating-linear-gradient), 状态指示灯, 蓝图网格面板 |
| 8 | 印象 | `/impressions` | 宝丽来照片墙 | 1 | 拍立得白框(宽下边距), 显影动画(sepia→clear), 胶片条 timeline, 纸片笔记 |
| 9 | 设置 | `/settings` | 工具台 | 1 | 暖色表单控件, 琥珀色 focus ring, 模板按钮按下态, 白卡片+微阴影 |

## 确立的设计模式

### 1. 背景实现 — `::before { position: fixed }` 🔴 强制规范

```css
.page-xxx { position: relative; }
.page-xxx::before {
  content: '';
  position: fixed;
  inset: 0;
  pointer-events: none;
  z-index: 0;
  background: /* ... */;
}
```

**原因:** `min-height: 100%` 依赖父级高度链（html→body→.app→.main→#mainContent），任一环节断裂就漏白。`position: fixed` 直接覆盖视口，不受 DOM 层级影响。

### 2. 内容层 z-index

```css
.xxx-wrap { position: relative; z-index: 1; }
```

所有内容包裹器必须 `z-index: 1` 以上，位于背景伪元素之上。

### 3. Canvas 粒子系统

多页面使用 Canvas 做环境粒子（浮尘/粉笔灰/纸屑/光尘）。模式：
- Canvas 元素 `position: fixed; inset: 0; pointer-events: none; z-index: 0`
- IIFE 初始化，监听 resize，requestAnimationFrame 循环
- 暂停时检查 `document.hidden` 避免后台消耗
- 粒子数 35-60 颗，速度极慢 (0.08-0.3 px/frame)，透明度极低 (0.02-0.09)

### 4. 卡片物理感

- 微旋转 (-0.3deg ~ +0.8deg) 模拟物理世界的不完美
- `box-shadow` 分层（近距离淡影 + 远距离中影）
- hover 时旋转归零 + 上浮 (scale 1.02 + shadow 加深)
- `prefers-reduced-motion` 下关闭旋转和动画

### 5. CSS 材质模拟

| 材质 | 技术 |
|------|------|
| 书脊 | `linear-gradient` 中缝高光 |
| 图钉 | `radial-gradient` 高光偏移模拟金属光泽 |
| 警示条纹 | `repeating-linear-gradient(45deg, ...)` |
| 书页叠加 | 多层 `box-shadow` + 椭圆 `border-radius` |
| 指示灯 | `radial-gradient` 偏离中心模拟白炽灯泡 |
| 蓝图网格 | `background-image` 两层 `linear-gradient` 画网格线 |

## 本轮 Bug 模式

### B1: 多 Flask 进程抢端口
**现象:** 页面打不开/间歇性 404  
**原因:** 多次启动 `python3 server.py` 未杀旧进程，4 个进程同时 LISTEN :5000  
**修复:** `taskkill` 全部杀掉，只保留一个  
**预防:** 启动前检查 `netstat -ano | grep :5000`

### B2: Flask 模板缓存不刷新
**现象:** 磁盘文件已更新，浏览器看到旧 CSS  
**原因:** 非 debug 模式下 Jinja2 可能缓存编译后的模板；旧进程未重启  
**修复:** 杀进程 + 重启 server  
**预防:** 改模板后重启 Flask（或在 debug 模式开发）

### B3: 背景 `min-height: 100%` 漏白
**现象:** 页面下方大面积白色  
**原因:** `min-height: 100%` 依赖完整的 `height: 100%` 父级链  
**修复:** 改为 `::before { position: fixed; inset: 0 }` 模式  
**预防:** 新页面一律使用 fixed 伪元素背景

### B4: 子 agent 改对文件但服务器没重启
**现象:** 印象页子 agent 提交正确，用户看不到变化  
**原因:** 与 B2 相同——旧 Flask 进程缓存了模板  
**修复:** 重启服务器  
**预防:** 文档化"改模板后必须重启"

## 文件变更统计

```
portfolio-app/templates/pages/home.html          (12 commits)
portfolio-app/templates/pages/classroom.html     (10 commits)
portfolio-app/templates/pages/mock_interview.html (7 commits)
portfolio-app/templates/pages/trainer.html       (7 commits)
portfolio-app/templates/pages/textbook.html      (5 commits)
portfolio-app/templates/pages/study_plan.html    (2 commits)
portfolio-app/templates/pages/construction.html  (3 commits)
portfolio-app/templates/pages/impressions.html   (1 commit)
portfolio-app/templates/pages/settings.html      (1 commit)
portfolio-app/services/progress_tracker.py       (daily activity 扩展)
portfolio-app/config.py                          (.api_key 双路径修复)
```

## 下一步：深化阶段

进入第二轮，对每个页面做细节打磨：

1. **学习计划** — 用户提到"还有待修复"
2. **面试** — Commit 4 简历高亮联动 (已是 in_progress)
3. **页面过渡动画** — Task #385 pending
4. **各页面微交互** — hover/active 状态统一, 动效一致性审查
5. **移动端适配** — 所有页面 640px 以下表现审查
6. **`prefers-reduced-motion`** — 逐页检查动效降级
7. **JS 语法验证自动化** — P1 规则：每次编辑后 `node --check`

# Checkpoint — 设计阶段完成，实施计划批准 (2026-06-13)

## 当前状态

四轮设计反馈 + 七轮计划审查全部处理完毕。设计 brief v2 + 实施计划 v2 定稿，总裁批准执行。

## 🔴 Compact 恢复后必须先读的文件（按顺序）

1. `PRODUCT.md` — 产品身份定义 v2（git根目录，97行）
2. `docs/design-architecture-v1.md` — 架构设计 v4（651行）
3. `docs/superpowers/specs/2026-06-13-design-brief.md` — 设计宪法 v2（324行）
4. `docs/superpowers/plans/2026-06-13-design-constructivism-plan.md` — 实施计划 v2（740行）
5. `docs/反馈/计划文档修改反馈(合订版).txt` — 四轮审查14项修正

## 文档链路

```
PRODUCT.md v2 → design-architecture-v1.md v4 → design-brief v2 → implementation-plan v2
                                                                        ↓
                                                              Phase 0 执行中/待执行
```

## 关键已决议事项

| 决策 | 结论 |
|------|------|
| 主题 | 深色构造主义默认 + prefers-color-scheme 自动切换 + 手动按钮 |
| 合并顺序 | 先合再美：结构合并(旧样式验证)→P0→P1→P2→P3 |
| 轨道网络 | SVG `<path>` + 贝塞尔曲线 + 文字标签 + 120s/圈 |
| 字体 | 本地化 `static/fonts/` |
| 回滚 | git worktree 隔离 `feat/design-constructivism` |
| 磨砂玻璃 | 仅3处：追溯面板/评分卡hover/Landing入口hover |
| 品牌标记 | Landing铜绿圆环24px+"P"字，首次访问动画(sessionStorage) |
| Landing数据 | Jinja2服务端渲染，两步检查(heartbeat+scores) |
| 追溯链脱敏 | SHA仅7位/事件仅类型标签/时间仅相对时间 |
| import_graph | 启动时执行一次+缓存JSON，≤500ms，P1门禁 |
| CSP | P0报告模式→P3强制模式 |
| 骨架屏 | Phase 0预埋, P2统一优化 |
| Landing FCP | ≤1.2s (单独预算) |
| 移动端 | P1/P2验收必须过iPhone14+iPad模拟器 |

## 实施阶段速览

| Phase | 内容 | 预估 | 关键门禁 |
|-------|------|------|----------|
| **0** | 结构合并 (旧样式) | 3-5h | 173 tests + perf基线 + Landing数据条 + 骨架屏 |
| **P0** | CSS变量+字体+深色基底 | 4-6h | FCP≤1.5s + 玻璃态仅3处 + CSP报告模式 |
| **P1** | 追溯链SVG+轨道网络+导航 | 6-8h | JSON非空+≤500ms + Landing FCP≤1.2s + 移动端 |
| **P2** | 微动效+水印UI+data-track | 4-5h | 6动画可降级+追踪不降>30% + 移动端 |
| **P3** | 3D粒子+WebGL降级 | 3-4h | FCP≤1.5s + CSP强制模式 |

## 下一步

1. `git worktree add -b feat/design-constructivism` 创建隔离分支
2. 执行 Phase 0：结构合并（3应用→单端口5000）
3. 每阶段完成后提交验证报告

## 最近 commits

```
9c3e035 docs: implementation plan v2 — 四轮审查14项加固 (终版, 批准执行)
0056f87 docs: implementation plan — 前端重构+三合一 (Phase 0→P3, 18-25h estimated)
d90e28a docs: design-brief v2 — 六人团队审查 (9项加固)
3372869 docs: PRODUCT.md v2 — 美术大师7项补充
7636250 docs: checkpoint — 设计讨论阶段 防compact记忆丢失
```

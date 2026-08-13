# Charts 图表组件规范

所有图表为手写 SVG，不依赖图表库。位于 `frontend/src/components/charts/`。

## 组件清单

| 组件 | 文件 | 功能 | 关键 Props |
|------|------|------|-----------|
| RadarChart | `RadarChart.tsx` | 双层雷达图（baseline + current） | `baseline`, `profile`, `size` |
| SkillTree | `SkillTree.tsx` | 递归技能分解树 | `skills`, `onSkillClick` |
| FilterTree | `FilterTree.tsx` | 方向筛选树（checkbox + 展开） | `directions`, `onFilter` |
| KnowledgeGraph | `KnowledgeGraph.tsx` | 知识图谱力导向布局 | `nodes`, `edges` |
| MatchPipeline | `MatchPipeline.tsx` | 匹配流程管道图 | `pipeline`, `result` |

## 样式规范
- CSS Modules (`.module.css`)
- 颜色只用 `var(--cr-surface1)` `--cr-surface2` `--cr-text1~4`
- 禁止手写颜色值（`#xxx` 除外），禁止 `--cr-bg1` `--cr-bg2`（不存在）
- SVG `fill` / `stroke` 使用 `currentColor` 或 CSS 变量
- `overflow: visible` 需显式说明原因

## 可访问性
- 每个 SVG 图表包含 `<title>` 和 `<desc>`
- 可交互元素加 `role` + `aria-label`
- 键盘导航：`tabIndex` + `onKeyDown`

## 性能
- 大数据集（>100 节点）考虑 requestAnimationFrame 分批渲染
- mockContent.ts 提供开发数据

## 新增图表 Checklist
1. 创建 `<Name>.tsx` + `<Name>.module.css`
2. 在 `mockContent.ts` 添加 mock 数据
3. 添加到 charts/ 目录
4. 更新本文件

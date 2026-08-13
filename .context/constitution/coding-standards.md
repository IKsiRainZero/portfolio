# 编码规范

## 通用

1. **编码前思考** — 不假设，不隐藏困惑。呈现权衡。不确定时询问而非猜测。困惑时停下来。
2. **简洁优先** — 用最少代码解决问题。不为一次性代码创建抽象。不为不可能场景做错误处理。如果 200 行可以写成 50 行，重写。
3. **精准修改** — 只碰必须碰的。不"改进"相邻代码。匹配现有风格。删除因自己改动而变成孤儿的导入/变量。
4. **目标驱动执行** — 定义成功标准 → 循环验证。"添加验证" → "为无效输入编写测试，然后让它们通过"。

## 文件规范

- **不写注释**（除非 WHY 不显而易见）：不解释 WHAT（命名已经说了），不写多行 docstring
- **不创建文档文件**：除非用户明确要求
- **不改动超过任务范围的代码**：三行相似不改抽象，单一操作用不到 helper

## 安全

- 新增 `/api/eval/*` 端点必须满足：路由层鉴权 + 数据层鉴权 + 403 测试 + 影子模式 403 测试
- `EVAL_ADMIN_SECRET` 独立于 `SECRET_KEY`，禁止 fallback
- `.api_key` / `.env` / 含 key 的 .txt → 绝不 commit

## Crescent 前端

- CSS Modules + CSS 变量（`--cr-*`），不写 inline style
- 有效变量：`--cr-surface1` `--cr-surface2` `--cr-text1` ~ `--cr-text4`
- 不存在：`--cr-bg1` `--cr-bg2`
- 图表组件手写 SVG，不引入图表库
- React 条件渲染避免 `{} &&`（空对象 truthy 陷阱），用 `'key' in obj` 或 `?.length ?`

## 文档版本铁律

修改 > 200 行的已有文档前必须：
1. 先 `git add + git commit` 当前版本，或 `cp doc.md doc-vN.md`
2. 优先用 Edit，只在新建或完全重写已备份文件时用 Write
3. Write 后立即 commit

关键文档列表：phase*-plan.md、phase*-execution-report.md、错误与修正与优化/*.md、CLAUDE.md

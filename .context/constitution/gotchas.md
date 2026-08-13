# 已知坑点

## Crescent

### PyInstaller 打包后 .exe 运行时挂起
- **原因**：Python print 在 PyInstaller 打包后 stdout 缓冲不 flush，SSE heartbeat 不生效
- **修复**：所有 print 加 `flush=True`，文件顶部加 `from __future__ import annotations`
- **相关**：commit 8b44985

### SSE Heartbeat 超时
- **原因**：反向代理（nginx/Caddy）默认 60s 超时断开 SSE 连接
- **修复**：每 30s 发送 heartbeat comment `: heartbeat\n\n`

### --cr-bg1/--cr-bg2 不存在
- **原因**：variables.css 中定义的是 `--cr-surface1`/`--cr-surface2`，不是 `--cr-bg1`/`--cr-bg2`
- **后果**：`var(--cr-bg1)` 解析为空，SVG fill 默认黑色，背景透明导致内容穿透
- **修复**：全局替换为 `--cr-surface1`/`--cr-surface2`

### panelPayloads.profile 空对象检测
- **原因**：SSE 返回的 `panelPayloads.profile` 可能是 `{}`（truthy），但没有 `skills` 属性
- **后果**：`undefined.forEach()` → TypeError → React 白屏
- **修复**：用 `'skills' in profilePayload` 检测而非 truthy check

### EVAL_ADMIN_SECRET 安全域分离
- `EVAL_ADMIN_SECRET` 独立于 `SECRET_KEY`，禁止 fallback
- 新增 `/api/eval/*` 端点必须同时满足：路由层鉴权 + 数据层鉴权 + 403 测试覆盖 + 影子模式 403 测试

## 工作空间

### Windows bash 路径编码
- `cp -r` 含中文路径时可能因字符编码失败
- 替代方案：`find -exec cp` 或 `rsync`

### `cp -r` 在 Windows bash 会替换目录而非合并
- 目标目录已存在时，`cp -r source/ target/` 会**替换**而非合并
- 合并前必须先检查内容差异

### Git worktree 在目录移动后断裂
- `.git` 文件指向绝对路径的 worktree，移动父目录后路径失效
- 修复：`git worktree prune` 清理失效引用

# Crescent 已知坑点

## PyInstaller 打包后 .exe 挂起
- **现象**: .exe 启动后网页能打开但 SSE 无响应
- **原因**: Python print 在 PyInstaller 打包后 stdout 缓冲不 flush
- **修复**: 所有 print 加 `flush=True`，文件顶部加 `from __future__ import annotations`
- **commit**: 8b44985

## SSE Heartbeat 超时
- **现象**: Workbench 流程跑到一半断开
- **原因**: 反向代理默认 60s 超时断开长连接
- **修复**: 每 30s 发送 `: heartbeat\n\n` comment 保活

## --cr-bg1/--cr-bg2 不存在
- **现象**: SVG 图表黑色填充、背景透明、内容穿透
- **原因**: variables.css 中定义的是 `--cr-surface1` `--cr-surface2`，不是 `--cr-bg1` `--cr-bg2`
- **有效变量**: `--cr-surface1: #F2EDE5` `--cr-surface2: #EAE4DA` `--cr-text1~4`
- **修复**: 全局替换所有引用

## panelPayloads.profile 空对象
- **现象**: DiscoverPage 点击"开始"后白屏
- **原因**: SSE 返回 `panelPayloads.profile = {}`（truthy），无 `skills` 属性，`SkillTree.buildTree(undefined)` → `undefined.forEach()` → TypeError
- **修复**: 用 `'skills' in payload` 检测，加 `?.length ?` 守卫

## EVAL_ADMIN_SECRET 安全域分离 🔴
- `EVAL_ADMIN_SECRET` 独立于 `SECRET_KEY`，禁止 fallback
- 新增 `/api/eval/*` 端点必须：路由层鉴权 + 数据层鉴权 + 403 测试 + 影子模式 403 测试

## Windows bash 路径问题
- `cp -r` 含中文路径时编码失败
- 目标目录已存在时 `cp -r` 会**替换**而非合并
- 替代：`find -exec cp` 或手动合并

## frontend/ 与 static/ 的构建产物
- 开发时 Vite dev server 在 :5173，生产用 `static/dist/` 的构建产物
- 改完前端必须重新 `npm run build` 并部署到 static/dist/
- 提交前检查 static/dist/ 是否已更新

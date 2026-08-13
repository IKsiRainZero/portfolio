# Electron MVP — Design Spec

> 2026-06-07 | 基于 Phase 1 Spec 阶段 3

## 目标

Electron 最小可用版本：能启动、能用（Flask 全功能）、能分发。

## 架构

```
portfolio/
├── electron/          # 新建 Electron 封装
│   ├── main.js        # 主进程
│   ├── preload.js     # 安全桥接（可选）
│   └── package.json   # Electron + electron-builder
├── portfolio-app/     # 现有 Flask 应用（不修改）
```

**启动流程：**
1. `npm start` 或 `electron .`
2. 主进程 `spawn("python", ["server.py"])` 启动 Flask
3. 轮询 `http://localhost:5000` 直到就绪
4. 打开 `BrowserWindow` 加载 `http://localhost:5000`
5. 窗口关闭 → kill Flask → 退出

## 决策

| 决策 | 选择 | 原因 |
|------|------|------|
| Python 环境 | 不打包，用系统 Python | 先跑通原型 |
| Flask 端口 | 默认 5000 | 保持兼容 |
| 窗口关闭 | 关闭→杀子进程→退出 | 简单干净 |
| 前端 | 不迁移 Jinja2，直接加载 localhost | MVP 不拆 |
| 分发 | electron-builder 配好暂不打 | 未来一键打包 |

## 不做

- 托盘图标、开机自启、自动更新
- Python 环境打包
- Jinja2→纯HTML 迁移
- Installer/.exe 生成
- 多窗口管理

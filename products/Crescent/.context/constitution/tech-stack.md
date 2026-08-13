# Crescent 技术栈

## 后端
- **框架**: FastAPI (Python 3.11+)
- **AI**: DeepSeek API (deepseek-chat / deepseek-reasoner)
- **实时通信**: Server-Sent Events (SSE)，非 WebSocket
- **模板**: Jinja2（部分旧页面）
- **打包**: PyInstaller → 单文件 .exe (Crescent.spec)
- **端口**: 5000 (生产) / 5173 (Vite dev proxy)

## 前端
- **框架**: React 19 + TypeScript
- **构建**: Vite 5
- **动画**: framer-motion 11
- **样式**: CSS Modules + CSS 变量设计系统 (variables.css)
- **图表**: 手写 SVG，不依赖图表库
- **路由**: React Router (react-router-dom)

## 数据存储
- **文件系统**: JSONL (eval snapshots/events), JSON (configs), Markdown (knowledge)
- **无数据库**: 无 PostgreSQL/MySQL/SQLite，全部文件系统存储

## 关键依赖
- `httpx` — 外部 API 调用
- `python-multipart` — 文件上传
- `pydantic` — 数据校验

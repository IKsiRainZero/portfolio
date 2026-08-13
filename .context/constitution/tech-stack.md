# 技术栈

## 工作空间
- 多项目工作空间，项目按状态分三级：products/ experiments/ archive/
- 版本控制：Git（单仓库，`.git` 在 workspace 根目录）
- 知识管理：`.context/` 三层架构（constitution / reference+sessions / records）

## Crescent (products/Crescent/)
- 后端：FastAPI + DeepSeek API
- 前端：React 19 + TypeScript + Vite (SPA)
- 动画：framer-motion
- 样式：CSS Modules + CSS 变量设计系统 (variables.css)
- 图表：手写 SVG 组件（RadarChart, SkillTree, FilterTree, KnowledgeGraph, MatchPipeline）
- SSE：Server-Sent Events (workbench pipeline)
- 打包：PyInstaller (dist/ 3.2GB)
- 端口：localhost:5000 (FastAPI)，localhost:5173 (Vite dev)

## cv-lab (products/cv-lab/)
- 后端：FastAPI
- 前端：原生 HTML/CSS/JS (Jinja2 模板)
- 样式：CSS 变量设计系统 (components.css + global.css)
- 端口：localhost:5001

## 旧项目
- archive/portfolio-app：FastAPI + Bing API + Jinja2
- archive/electron：Electron + vanilla JS
- archive/portfolio-site：静态 HTML + 视频背景
- experiments/：classwork (课程作业)、Facetest (面部识别)、cortex、quant-trading

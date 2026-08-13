# may-i-help-u 技术栈

## 语言与分发
- **Python 3.12+** — 与 Crescent 同版本，可复用模型配置
- **pip install may-i-help-u** — setup.py / pyproject.toml，标准 PyPI 分发
- 零系统依赖（不要求 CUDA、不要求 Docker）

## LLM 集成
- **DeepSeek API** (OpenAI 兼容) — 驱分解器、分析器、解决器的推理
- **模型配置复用** — 复用 Crescent 的 `model_config.py` 模式：
  - 每个 organ 可以配置不同模型/参数
  - 支持 fallback（DeepSeek → 本地模型 → 规则引擎）
- **Prompt 模板** — 每个器官有独立 prompt 文件（Jinja2 模板）

## 向量检索 (Coordinator)
- **ChromaDB** — 轻量嵌入式向量库，纯 Python 运行，无需外部服务
- **sentence-transformers** (`all-MiniLM-L6-v2`) — 本地 embedding，384 维，无 API 调用
- **余弦相似度** — ChromaDB 内置，匹配问题描述 ↔ 技术资源

## 网络搜索 (Coordinator)
- **Scrapling** — 反反爬虫 HTTP 客户端（已在工具清单），绕过 Cloudflare
- **LLM 结果提取** — 爬取的网页内容 → LLM 提取结构化摘要 → 存入向量库

## Function Calling (Solver)
- **OpenAI function call schema** — 工具注册统一用 JSON Schema
- **工具注册表** — Python callable + JSON Schema → 自动转为 DeepSeek function call
- **内置工具** — subprocess shell、文件读写、HTTP 请求
- **可扩展** — 调用者注册自定义工具进 registry

## 编排层 (Orchestrator / C 层)
- **LLM 调度** — 提示词工程，让 LLM 决定下一步调用哪个器官
- **循环终止条件** — 最大迭代次数 + LLM 自判断 "done"
- **Trace 日志** — 记录每一步 organ 调用（输入/输出/token），可回溯

## 测试
- **pytest** — 与 Crescent 统一
- **器官独立测试** — 每个 organ 可 mock LLM 调用，纯逻辑测试
- **集成测试** — 端到端 pipeline（paper problem → decompose → analyze → gather → solve）

## 不引入
- 不使用 LangChain/LlamaIndex（过度抽象，直接调 API 即可）
- 不使用 PostgreSQL/pgvector（ChromaDB 即可满足本地场景，零运维）
- 不引入 MCP SDK（MCP 层是后续包装，不在核心库内）

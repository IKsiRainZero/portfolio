# Config 修改手册

> Crescent `config.py` 被 47 个文件引用。每次修改都可能波及全项目。

## 五条纪律

### 1. 只追加，不重命名
- 新增配置 → 追加到对应区块末尾
- 禁止重命名已有变量。`API_KEY` → `DEEPSEEK_API_KEY` 会导致所有 `from config import API_KEY` 崩溃
- 如需重命名：先 grep 全项目统计引用点 → 全量替换 → 全量测试

### 2. 新增键必须带默认值
- 环境变量 > 文件 > 硬编码默认值（三级优先级）
- 默认值保证下游模块不因缺配置而崩溃
- 参照已有模式：`_KEY = os.environ.get("KEY", "")` → `if not _KEY: read from file` → 最后用默认值

### 3. 修改前 grep 全项目
```bash
cd Crescent && grep -rn "变量名" --include="*.py" .
```
不确定影响范围的改动 → 先讨论再动手

### 4. 敏感信息分层
- API Key 类：环境变量 > `data/user_data/.xxx_key` > 无默认值(启动报错)
- 模型参数类：可以有硬编码默认值
- 路径类：基于 `BASE_DIR` 派生，不写死绝对路径

### 5. 修改后跑全量测试
```bash
cd Crescent && python -m pytest tests/ -x --tb=short
```
如果有测试失败，在 commit message 中说明原因和修复。

## 当前变量地图

| 变量 | 类型 | 被引用次数 | 修改风险 |
|------|------|-----------|---------|
| `API_KEY` | str | ~18 | 高 — 影响所有 LLM 调用 |
| `BASE_DIR` | Path | ~12 | 高 — 影响所有路径 |
| `MODEL` | str | ~8 | 中 — 改名需同步 prompt 模板 |
| `LLM_PROVIDER` | str | ~5 | 中 — 切换 local/deepseek |
| `BRAVE_API_KEY` | str | 1 (search.py) | 低 |
| `SERPAPI_KEY` | str | 1 (search.py) | 低 |
| `EVAL_ADMIN_SECRET` | str | ~5 | 中 — 独立安全域 |
| `CHROMA_PATH` | Path | ~6 | 中 — 修改会丢失向量索引 |
| `EMBEDDING_MODEL` | str | ~4 | 中 — 修改后需重建索引 |

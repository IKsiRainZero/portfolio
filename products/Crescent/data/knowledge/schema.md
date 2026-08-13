# 知识库 JSON Schema

每个知识库是一个 JSON 文件，存放在 `data/knowledge/` 目录下。

## 顶层结构

```json
{
  "meta": {
    "domain": "python-basics",
    "display_name": "Python 基础",
    "description": "Python 编程语言核心概念，面向量化金融场景",
    "version": 1,
    "created": "2026-05-27"
  },
  "sections": [
    {
      "id": "data-structures",
      "title": "数据结构",
      "items": [...]
    }
  ]
}
```

## Item 类型

每个 item 必须有一个 `type` 字段，决定前端如何渲染：

### `qa` — 问答卡
```json
{
  "id": "ds-1",
  "type": "qa",
  "question": "list 和 tuple 的区别是什么？",
  "answer": "list 可变，tuple 不可变...",
  "tags": ["list", "tuple"],
  "difficulty": 1
}
```
渲染：可展开的 details/summary 组件，带「问AI」按钮。

### `table` — 对比表格
```json
{
  "id": "ref-1",
  "type": "table",
  "title": "数据结构选择指南",
  "headers": ["类型", "场景", "示例"],
  "rows": [["list", "有序集合", "g.choice(...)"], ["dict", "键值映射", "g.wendu = {}"]],
  "tags": ["reference"]
}
```
渲染：HTML 表格。

### `code` — 代码块
```json
{
  "id": "ex-1",
  "type": "code",
  "title": "列表推导式示例",
  "code": "squares = [x**2 for x in range(10)]",
  "language": "python",
  "explanation": "生成 0-9 的平方数列表"
}
```
渲染：深色背景的代码块 + 说明文字。

### `concept` — 概念卡
```json
{
  "id": "c-1",
  "type": "concept",
  "title": "PE（市盈率）",
  "content": "PE = 股价 / 每股收益...",
  "tags": ["valuation"]
}
```
渲染：蓝色背景的概念卡片。

## 添加新领域

1. 在 `data/knowledge/` 下创建新的 `.json` 文件
2. 按上述 schema 填写 meta 和 sections
3. 刷新页面，知识库浏览器自动发现新领域

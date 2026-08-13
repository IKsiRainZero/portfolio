# Stage 2: 信息免疫系统原型 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现 L1 来源追溯（Source Trace）完整链路——用户粘贴内容 → 6 步管道分析 → SSE 流式展示 → 所有来源可点击验证，加上仪表盘主动提醒。

**Architecture:** Flask SSE 端点驱动结构化 6 步管道（固定步骤，不用 Agent 自由发挥），前端 `/source-trace` 页面用 6 张可展开卡片逐步点亮。Scrapling Fetcher 抓取网页，markitdown 提取正文，本地 LLM 做关键词提取和差异对比。

**Tech Stack:** Flask SSE, Scrapling (requests Fetcher), markitdown, Ollama local LLM, 原生 JS

---

## 前置：安装依赖

### Task 1: 安装 Scrapling + markitdown

- [ ] **Step 1: pip install scrapling from local source**

```bash
pip install "C:/Users/16008/Desktop/personal/Write/portfolio/Scrapling-main/Scrapling-main/"
```

- [ ] **Step 2: pip install markitdown from local source**

```bash
pip install "C:/Users/16008/Desktop/personal/Write/portfolio/markitdown-main/markitdown-main/packages/markitdown/"
```

- [ ] **Step 3: Install duckduckgo_search (free web search, no API key)**

```bash
pip install duckduckgo_search
```

- [ ] **Step 4: Verify imports**

```bash
python -c "from scrapling.fetchers import Fetcher; print('scrapling OK')"
python -c "from markitdown import MarkItDown; print('markitdown OK')"
python -c "from duckduckgo_search import DDGS; print('ddgs OK')"
```

---

## 后端

### Task 2: 创建 `services/source_tracer.py` — 6 步管道

**Files:**
- Create: `portfolio-app/services/source_tracer.py`

- [ ] **Step 1: Write the module with all 6 step functions**

```python
"""来源追溯 — 6 步结构化管道，固定步骤保证行为可预测"""
import json
import re
from typing import Generator, Dict, Any, List


def _llm(prompt: str, system: str = "") -> str:
    """调用本地 LLM（轻量任务，用 qwen3:8b）"""
    from services.llm_service import get_llm
    from langchain_core.messages import HumanMessage, SystemMessage

    llm = get_llm()
    msgs = []
    if system:
        msgs.append(SystemMessage(content=system))
    msgs.append(HumanMessage(content=prompt))
    resp = llm.invoke(msgs)
    return resp.content.strip()


def step1_extract_keywords(content: str) -> Dict[str, Any]:
    """提取关键词和核心声明"""
    system = "你是一个信息溯源助手。从用户提供的内容中提取：1) 关键词（5-10个）2) 核心事实声明 3) 如果有URL，提取出来。用JSON格式回复。"
    prompt = f"内容：\n{content}\n\n请提取关键词、核心声明和URL。回复JSON：{{\"keywords\": [...], \"claims\": [...], \"urls\": [...]}}"
    raw = _llm(prompt, system)
    try:
        result = json.loads(raw)
    except json.JSONDecodeError:
        # 尝试从文本中提取JSON
        m = re.search(r'\{.*\}', raw, re.DOTALL)
        if m:
            result = json.loads(m.group())
        else:
            result = {"keywords": [], "claims": [content[:200]], "urls": []}
    return result


def step2_multi_search(keywords: List[str], urls: List[str]) -> Dict[str, Any]:
    """Scrapling 多源搜索（公开网页）"""
    from scrapling.fetchers import Fetcher

    sources = []
    search_urls = urls.copy() if urls else []

    # 如果有 URL 直接抓取
    for url in search_urls:
        try:
            resp = Fetcher.fetch(url, timeout=15)
            sources.append({
                "url": url,
                "title": resp.css('title::text').get() or url,
                "status": "fetched",
                "html": resp.body[:50000]  # 限制大小
            })
        except Exception as e:
            sources.append({"url": url, "status": "failed", "error": str(e)})

    # 用搜索引擎搜关键词（DuckDuckGo 免费，无需 API Key）
    try:
        from duckduckgo_search import DDGS
        query = " ".join(keywords[:5])
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=5):
                if r["href"] not in {s["url"] for s in sources}:
                    sources.append({
                        "url": r["href"],
                        "title": r.get("title", r["href"]),
                        "snippet": r.get("body", ""),
                        "status": "search_result"
                    })
    except Exception as e:
        sources.append({"status": "search_failed", "error": str(e), "note": "搜索引擎不可用，仅抓取了用户提供的URL"})

    return {"sources": sources, "total": len(sources)}


def step3_extract_content(sources: List[Dict]) -> Dict[str, Any]:
    """markitdown 提取正文"""
    from markitdown import MarkItDown
    from scrapling.fetchers import Fetcher

    md = MarkItDown()
    extracted = []

    for src in sources:
        if src.get("status") not in ("fetched", "search_result"):
            extracted.append({**src, "text": ""})
            continue

        try:
            if src.get("html"):
                # 直接用 HTML 转换
                text = md.convert_string(src["html"])
            else:
                # 抓取后转换
                resp = Fetcher.fetch(src["url"], timeout=15)
                text = md.convert_string(resp.body)
            # 截断到合理长度
            text_clean = text[:5000] if text else ""
            extracted.append({**src, "text": text_clean, "status": "extracted"})
        except Exception as e:
            extracted.append({**src, "status": "extract_failed", "error": str(e), "text": src.get("snippet", "")})

    return {"items": extracted}


def step4_timeline_backtrack(items: List[Dict]) -> Dict[str, Any]:
    """时间线回溯 — 尝试找更早的出处"""
    # Phase 1 简化版：按 URL 和内容分析时间线索
    earliest = None
    timeline = []

    for item in items:
        if item.get("status") in ("fetched", "extracted"):
            entry = {
                "url": item.get("url", ""),
                "title": item.get("title", ""),
            }
            timeline.append(entry)
            if earliest is None:
                earliest = entry

    return {
        "timeline": timeline,
        "earliest_known": earliest,
        "note": "时间线基于当前搜索结果的发布时间排序。搜索范围仅限于公开网页，私密群聊/朋友圈/已删除内容无法访问。"
    }


def step5_diff_annotate(original_text: str, user_content: str) -> Dict[str, Any]:
    """LLM 逐句对比差异"""
    if not original_text or not user_content:
        return {"diffs": [], "note": "缺少对比内容，跳过差异分析"}

    system = "你是一个信息溯源助手。对比"原文"和"用户看到的版本"，逐句标注差异。重点关注：语义变化、情绪词汇增减、关键事实变更。"
    prompt = f"原文：\n{original_text[:3000]}\n\n用户看到的版本：\n{user_content[:3000]}\n\n逐句对比，标注差异。"
    raw = _llm(prompt, system)

    return {"diffs_raw": raw, "note": "差异标注来自模型分析，不是客观事实，用户可以自行判断。"}


def step6_final_conclusion(chain: Dict[str, Any]) -> Dict[str, Any]:
    """阶段性结论 + 明确不确定性边界"""
    keywords = chain.get("keywords", {})
    sources = chain.get("sources", {})
    timeline = chain.get("timeline", {})
    diffs = chain.get("diffs", {})

    total_sources = sources.get("total", 0)
    failed = sum(1 for s in sources.get("sources", []) if "failed" in s.get("status", ""))

    determined = []
    uncertain = []

    if timeline.get("earliest_known"):
        determined.append(f"最早可查来源: {timeline['earliest_known'].get('url', '未知')}")
    if total_sources > 0:
        determined.append(f"共检索到 {total_sources} 个相关来源，其中 {failed} 个获取失败")
    if diffs.get("diffs_raw"):
        determined.append("已完成原文与用户版本差异对比")

    uncertain.append("无法确定是否还有其他更早来源（搜索范围仅限于公开网页）")
    uncertain.append("无法访问私密群聊、朋友圈、已删除内容")
    uncertain.append("差异标注来自模型分析，不是客观事实")
    if total_sources == 0:
        uncertain.append("未找到任何相关来源，该信息暂无公开可查记录")

    return {
        "determined": determined,
        "uncertain": uncertain,
        "source_links": timeline.get("timeline", []),
        "timestamp": chain.get("timestamp", ""),
    }


def trace_source(content: str) -> Generator[Dict[str, Any], None, Dict[str, Any]]:
    """主入口：执行完整 6 步管道，yield 每步的进度和结果。
    
    用法（Flask SSE）:
        for event in trace_source(user_content):
            yield f"data: {json.dumps(event, ensure_ascii=False)}\\n\\n"
    """
    import time

    chain = {"timestamp": time.strftime("%Y-%m-%d %H:%M:%S")}

    # Step 1: 提取关键词
    yield {"step": 1, "name": "提取关键词", "status": "running", "content": "正在分析你提供的内容..."}
    kw = step1_extract_keywords(content)
    chain["keywords"] = kw
    yield {
        "step": 1, "name": "提取关键词", "status": "done",
        "content": f"提取到关键词：{', '.join(kw.get('keywords', []))}",
        "detail": kw
    }

    # Step 2: 多平台搜索
    yield {"step": 2, "name": "多平台搜索", "status": "running", "content": "用 Scrapling 搜索公开网页..."}
    sources = step2_multi_search(kw.get("keywords", []), kw.get("urls", []))
    chain["sources"] = sources
    yield {
        "step": 2, "name": "多平台搜索", "status": "done",
        "content": f"找到 {sources['total']} 个相关来源",
        "detail": sources
    }

    # Step 3: 内容提取
    yield {"step": 3, "name": "内容提取", "status": "running", "content": "用 markitdown 提取正文..."}
    extracted = step3_extract_content(sources.get("sources", []))
    chain["extracted"] = extracted
    yield {
        "step": 3, "name": "内容提取", "status": "done",
        "content": f"成功提取 {sum(1 for i in extracted['items'] if i.get('status') == 'extracted')} 篇正文",
        "detail": extracted
    }

    # Step 4: 时间线回溯
    yield {"step": 4, "name": "时间线回溯", "status": "running", "content": "回溯时间线，找最早出处..."}
    timeline = step4_timeline_backtrack(extracted.get("items", []))
    chain["timeline"] = timeline
    yield {
        "step": 4, "name": "时间线回溯", "status": "done",
        "content": f"最早可查来源: {timeline.get('earliest_known', {}).get('url', '待定')}",
        "detail": timeline
    }

    # Step 5: 差异标注
    yield {"step": 5, "name": "差异标注", "status": "running", "content": "对比原文与用户版本..."}
    # 用第一个提取成功的正文作为"原文"
    first_text = ""
    for item in extracted.get("items", []):
        if item.get("text"):
            first_text = item["text"]
            break
    diffs = step5_diff_annotate(first_text, content)
    chain["diffs"] = diffs
    yield {
        "step": 5, "name": "差异标注", "status": "done",
        "content": "差异对比完成",
        "detail": diffs
    }

    # Step 6: 阶段性结论
    yield {"step": 6, "name": "阶段性结论", "status": "running", "content": "生成结论..."}
    conclusion = step6_final_conclusion(chain)
    chain["conclusion"] = conclusion
    yield {
        "step": 6, "name": "阶段性结论", "status": "done",
        "content": "分析完成",
        "detail": conclusion
    }

    return chain
```

- [ ] **Step 2: Verify module imports**

```bash
cd portfolio-app && python -c "from services.source_tracer import trace_source; print('OK')"
```

Expected: `OK`

---

### Task 3: 创建 API 路由 + 注册蓝图

**Files:**
- Create: `portfolio-app/routes/api_source_trace.py`
- Modify: `portfolio-app/server.py`

- [ ] **Step 1: Write the SSE API endpoint**

```python
"""来源追溯 API — SSE 流式推送 6 步管道进度"""
import json as _json
from flask import Blueprint, request, jsonify, Response

st_bp = Blueprint("source_trace", __name__, url_prefix="/api")


@st_bp.route("/source-trace", methods=["POST"])
def source_trace():
    """SSE 流式来源追溯"""
    data = request.json
    content = (data.get("content") or "").strip()
    if not content:
        return jsonify({"error": "请输入要追溯的内容或链接"}), 400

    from services.source_tracer import trace_source

    def generate():
        try:
            for event in trace_source(content):
                yield f"data: {_json.dumps(event, ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"data: {_json.dumps({'type': 'error', 'content': f'追溯过程出错: {str(e)}'}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
```

- [ ] **Step 2: Register blueprint in server.py**

In `server.py`, in `create_app()`:
```python
from routes.api_source_trace import st_bp
```
And add `st_bp` to the blueprint list:
```python
for bp in [pages_bp, config_bp, code_bp, knowledge_bp, progress_bp, ai_bp, exercises_bp, resume_bp, agent_bp, interview_bp, import_bp, sync_bp, st_bp]:
    app.register_blueprint(bp)
```

- [ ] **Step 3: Verify server starts clean**

```bash
cd portfolio-app && timeout 5 python server.py 2>&1 || true
```

Expected: No import errors.

---

## 前端

### Task 4: 创建页面模板 + JS 模块 + 路由

**Files:**
- Create: `portfolio-app/templates/pages/source_trace.html`
- Create: `portfolio-app/static/js/modules/source-trace.js`
- Modify: `portfolio-app/routes/pages.py`
- Modify: `portfolio-app/templates/base.html`

- [ ] **Step 1: Write the page template**

```html
{% extends "base.html" %}
{% block title %}来源追溯{% endblock %}
{% block page_title %}来源追溯{% endblock %}

{% block head %}
<script src="/static/js/modules/source-trace.js"></script>
{% endblock %}

{% block content %}
<section class="source-trace-page">
  <!-- 输入区 -->
  <div class="card" style="margin-bottom: 20px;">
    <h3>粘贴内容或链接，追溯信息来源</h3>
    <p class="subtitle" style="color:var(--text2);margin-bottom:12px;">
      支持：网页链接、截图文字、转发消息。所有搜索过程实时展示，来源链接可点击验证。
    </p>
    <textarea id="stInput" class="form-input" rows="4"
      placeholder="例如：粘贴一段微信聊天记录，或一个微博链接…"
      style="width:100%;resize:vertical;"></textarea>
    <div style="margin-top:12px;display:flex;align-items:center;gap:12px;">
      <button id="stStartBtn" class="btn btn-primary" onclick="SourceTrace.start()">
        开始追溯
      </button>
      <span id="stStatus" style="color:var(--text2);font-size:13px;"></span>
    </div>
  </div>

  <!-- 结果区 — 6 张卡片 -->
  <div id="stResults" style="display:none;">
    <div id="stCards"></div>
  </div>
</section>
{% endblock %}
```

- [ ] **Step 2: Write the JS module**

```javascript
/**
 * 来源追溯 — 6 步管道 SSE 流式展示
 */
const SourceTrace = {
  _es: null,

  start() {
    const input = document.getElementById('stInput').value.trim();
    if (!input) return;

    // 重置 UI
    document.getElementById('stResults').style.display = 'block';
    document.getElementById('stCards').innerHTML = '';
    document.getElementById('stStartBtn').disabled = true;
    document.getElementById('stStatus').textContent = '追溯中...';

    // 建 6 张空卡片
    const steps = [
      { id: 1, name: '提取关键词'},
      { id: 2, name: '多平台搜索'},
      { id: 3, name: '内容提取'},
      { id: 4, name: '时间线回溯'},
      { id: 5, name: '差异标注'},
      { id: 6, name: '阶段性结论'},
    ];
    const container = document.getElementById('stCards');
    steps.forEach(s => {
      const card = document.createElement('div');
      card.id = `stCard${s.id}`;
      card.className = 'card st-card';
      card.innerHTML = `
        <div class="st-card-header" onclick="SourceTrace.toggleCard(${s.id})">
          <span class="st-step-num">${s.id}</span>
          <span class="st-step-name">${s.name}</span>
          <span class="st-step-status" id="stStatus${s.id}"></span>
          <span class="st-caret">▸</span>
        </div>
        <div class="st-card-body" id="stBody${s.id}" style="display:none;"></div>`;
      container.appendChild(card);
    });

    this._connect(input);
  },

  _connect(content) {
    if (this._es) this._es.close();

    this._es = new EventSource('/api/source-trace', {
      // POST via fetch+ReadableStream is more standard for SSE POST,
      // but EventSource doesn't support POST natively.
      // Use fetch + manual SSE parsing instead:
    });

    // Actually use fetch for POST-SSE
    this._es.close();
    this._fetchSSE(content);
  },

  async _fetchSSE(content) {
    try {
      const resp = await fetch('/api/source-trace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buf = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });

        const lines = buf.split('\n');
        buf = lines.pop(); // incomplete line

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const data = JSON.parse(line.slice(6));
            this._handleEvent(data);
          }
        }
      }
    } catch (e) {
      document.getElementById('stStatus').textContent = '连接失败: ' + e.message;
    } finally {
      document.getElementById('stStartBtn').disabled = false;
      document.getElementById('stStatus').textContent = '追溯完成';
    }
  },

  _handleEvent(event) {
    if (event.type === 'error') {
      document.getElementById('stStatus').textContent = event.content;
      return;
    }

    const { step, status, content, detail } = event;

    // 更新卡片状态
    const statusEl = document.getElementById(`stStatus${step}`);
    if (statusEl) {
      statusEl.textContent = status === 'running' ? '⏳' : '✅';
      statusEl.style.color = status === 'running' ? 'var(--accent)' : 'var(--ok, #22c55e)';
    }

    // 更新卡片内容
    const bodyEl = document.getElementById(`stBody${step}`);
    if (bodyEl && content) {
      bodyEl.style.display = 'block';
      bodyEl.innerHTML = this._renderDetail(step, detail || {}, content);
      // 旋转小三角
      const card = document.getElementById(`stCard${step}`);
      const caret = card.querySelector('.st-caret');
      if (caret) caret.style.transform = 'rotate(90deg)';
    }

    // 高亮当前卡片
    if (status === 'running') {
      const card = document.getElementById(`stCard${step}`);
      if (card) card.style.boxShadow = '0 0 0 2px var(--accent)';
    } else if (status === 'done') {
      const card = document.getElementById(`stCard${step}`);
      if (card) card.style.boxShadow = '';
    }
  },

  _renderDetail(step, detail, summary) {
    let html = `<p style="margin-bottom:8px;">${summary}</p>`;

    if (step === 1 && detail.keywords) {
      html += '<div class="tags">' + detail.keywords.map(k =>
        `<span class="badge" style="margin:2px;">${App.escapeHtml(k)}</span>`
      ).join('') + '</div>';
    }

    if (step === 2 && detail.sources) {
      html += '<ul style="font-size:13px;">';
      detail.sources.forEach(s => {
        if (s.url) {
          html += `<li><a href="${App.escapeHtml(s.url)}" target="_blank" rel="noopener">${App.escapeHtml(s.title || s.url)}</a>`;
          if (s.snippet) html += `<br><small style="color:var(--text2)">${App.escapeHtml(s.snippet.substring(0, 150))}</small>`;
          if (s.status === 'failed') html += ` <span class="badge" style="background:#ef4444;">抓取失败</span>`;
          html += '</li>';
        }
      });
      html += '</ul>';
    }

    if (step === 4 && detail.timeline) {
      html += '<ol style="font-size:13px;">';
      detail.timeline.forEach(t => {
        html += `<li><a href="${App.escapeHtml(t.url)}" target="_blank" rel="noopener">${App.escapeHtml(t.title || t.url)}</a></li>`;
      });
      html += '</ol>';
      if (detail.note) html += `<p style="color:var(--text2);font-size:12px;margin-top:4px;">${App.escapeHtml(detail.note)}</p>`;
    }

    if (step === 5 && detail.diffs_raw) {
      html += `<div style="white-space:pre-wrap;font-size:13px;background:var(--bg2);padding:8px;border-radius:6px;">${App.escapeHtml(detail.diffs_raw)}</div>`;
      if (detail.note) html += `<p style="color:var(--text2);font-size:12px;margin-top:4px;">${App.escapeHtml(detail.note)}</p>`;
    }

    if (step === 6 && detail.determined) {
      html += '<h4 style="margin-bottom:4px;">确定的部分</h4><ul style="font-size:13px;">';
      detail.determined.forEach(d => html += `<li>${App.escapeHtml(d)}</li>`);
      html += '</ul>';
      html += '<h4 style="margin-bottom:4px;margin-top:12px;">不确定的部分</h4><ul style="font-size:13px;">';
      detail.uncertain.forEach(u => html += `<li style="color:var(--text2)">${App.escapeHtml(u)}</li>`);
      html += '</ul>';
      if (detail.source_links && detail.source_links.length) {
        html += '<h4 style="margin-bottom:4px;margin-top:12px;">所有来源链接</h4><ul style="font-size:13px;">';
        detail.source_links.forEach(s => {
          html += `<li><a href="${App.escapeHtml(s.url)}" target="_blank" rel="noopener">${App.escapeHtml(s.title || s.url)}</a></li>`;
        });
        html += '</ul>';
      }
    }

    return html;
  },

  toggleCard(id) {
    const body = document.getElementById(`stBody${id}`);
    const card = document.getElementById(`stCard${id}`);
    const caret = card.querySelector('.st-caret');
    if (body.style.display === 'none') {
      body.style.display = 'block';
      caret.style.transform = 'rotate(90deg)';
    } else {
      body.style.display = 'none';
      caret.style.transform = 'rotate(0deg)';
    }
  },
};
```

- [ ] **Step 3: Add page route**

In `routes/pages.py`, add:
```python
@pages_bp.route("/source-trace")
def source_trace():
    from flask import render_template
    return render_template("pages/source_trace.html")
```

- [ ] **Step 4: Add nav link in base.html**

In `templates/base.html`, add after the agent-build nav item:
```html
<a class="nav-item" href="/source-trace" data-page="source-trace">
  <span class="nav-icon">&#9740;</span><span>来源追溯</span>
</a>
```

---

### Task 5: 仪表盘主动提醒

**Files:**
- Modify: `portfolio-app/static/js/modules/dashboard.js`

- [ ] **Step 1: Add reminder logic**

In `dashboard.js`, add a function called during dashboard initialization:

```javascript
function checkSourceTraceReminder() {
  const key = 'source_trace_last_visit';
  const now = Date.now();
  const last = parseInt(localStorage.getItem(key) || '0', 10);
  const daysSince = (now - last) / (1000 * 60 * 60 * 24);

  // Show reminder if never used or > 7 days since last visit
  if (!last || daysSince > 7) {
    const reminderEl = document.getElementById('stReminder');
    if (reminderEl) {
      reminderEl.style.display = 'block';
      reminderEl.innerHTML = `
        <div class="card" style="border-left:3px solid var(--accent);padding:12px 16px;">
          <span style="font-size:14px;">最近有没有看到让你不确定的信息？</span>
          <a href="/source-trace" class="btn btn-sm" style="margin-left:12px;">追溯来源</a>
        </div>`;
    }
  }
}

// Update last visit when navigating to source-trace
document.addEventListener('click', function(e) {
  if (e.target.closest('a[href="/source-trace"]')) {
    localStorage.setItem('source_trace_last_visit', Date.now().toString());
  }
});
```

- [ ] **Step 2: Add reminder placeholder in home.html**

In `templates/pages/home.html`, add in a suitable position (e.g., below the quick-actions or at the top of the main content):
```html
<div id="stReminder" style="display:none;"></div>
```

And call `checkSourceTraceReminder()` in the dashboard init function.

---

### Task 6: CSS 样式

**Files:**
- Modify: `portfolio-app/static/css/global.css`

- [ ] **Step 1: Add source-trace specific styles**

Add at the end of `global.css`:
```css
/* Source Trace */
.st-card { margin-bottom: 8px; padding: 0; overflow: hidden; }
.st-card-header { display: flex; align-items: center; gap: 10px; padding: 12px 16px; cursor: pointer; user-select: none; }
.st-card-header:hover { background: var(--bg2); }
.st-step-num { width: 24px; height: 24px; border-radius: 50%; background: var(--accent); color: #fff; display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: 600; flex-shrink: 0; }
.st-step-name { flex: 1; font-weight: 600; font-size: 14px; }
.st-step-status { font-size: 16px; }
.st-caret { font-size: 12px; color: var(--text2); transition: transform 0.2s; }
.st-card-body { padding: 0 16px 16px 50px; font-size: 13px; }
```

---

## 验证

### Task 7: 端到端验证

- [ ] **Step 1: Start server**

```bash
cd portfolio-app && python server.py
```

- [ ] **Step 2: Verify page loads**

```bash
curl -s http://localhost:5000/source-trace | head -5
```
Expected: HTML with "来源追溯" in the output.

- [ ] **Step 3: Test API with a simple content**

```bash
curl -s -X POST http://localhost:5000/api/source-trace \
  -H "Content-Type: application/json" \
  -d '{"content":"https://example.com 有篇文章说AI会统治人类"}' \
  | head -20
```
Expected: SSE events flowing, starting with `data: {"step":1,...}`.

- [ ] **Step 4: Verify dashboard reminder**

Open http://localhost:5000/ in browser. First visit should show the reminder card. Click the "追溯来源" link → should navigate to /source-trace. Return to dashboard → reminder should be hidden (last visit < 7 days).

---

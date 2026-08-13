/**
 * Portfolio App — Core Application Shell
 * 全局状态、导航、AI 面板、设置
 */
const App = {
  // ---- State ----
  serverUrl: localStorage.getItem('serverUrl') || window.location.origin,
  serverOnline: false,
  apiConfigured: false,
  useStreaming: true,
  _activeEventSource: null,
  _pageReady: false,
  _readyCallbacks: [],

  // App.ready(fn) — replaces document.addEventListener('DOMContentLoaded', fn).
  // Works on initial SSR load AND after every Router navigation.
  ready(fn) {
    if (this._pageReady) { fn(); return; }
    this._readyCallbacks.push(fn);
  },

  _firePageReady() {
    this._pageReady = true;
    this._trackPageView();
    var cbs = this._readyCallbacks;
    this._readyCallbacks = [];
    cbs.forEach(function(fn) { try { fn(); } catch(e) { console.error(e); } });
  },

  _resetPageReady() {
    this._pageReady = false;
    this._readyCallbacks = [];
  },

  // ---- Init ----
  init() {
    this.restoreSidebar();
    this.highlightNav();
    this.checkServer();
    this.loadModelConfig();
    this.loadDeepThinking();
    this.loadImpressionSnippet();
    // Click outside to close model dropdown
    document.addEventListener('click', (e) => {
      const dd = document.getElementById('modelDropdown');
      const btn = document.getElementById('modelSwitchBtn');
      if (dd && btn && !dd.classList.contains('hidden') && !dd.contains(e.target) && !btn.contains(e.target)) {
        dd.classList.add('hidden');
      }
    });
    // Click modal overlay to close
    document.querySelectorAll('.modal-overlay').forEach(ov => {
      ov.addEventListener('click', (e) => { if (e.target === ov) ov.classList.add('hidden'); });
    });
    // Provider toggle in add-model modal
    const providerSel = document.getElementById('newModelProvider');
    if (providerSel) providerSel.addEventListener('change', () => this._toggleModelFormFields());
    // Init hybrid router (after nav highlight)
    Router.init();
    // Fire page-ready for initial SSR load. setTimeout(0) ensures all
    // page-level inline script blocks have executed and called App.ready().
    setTimeout(function() { App._firePageReady(); }, 0);
    // Restore session history messages if switching sessions
    setTimeout(function() { App.loadSessionHistory(); }, 100);
  },

  highlightNav() {
    const path = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(el => {
      el.classList.toggle('active', el.getAttribute('href') === path ||
        (path === '/' && el.getAttribute('href') === '/'));
    });
  },

  // ---- Server Status ----
  async checkServer() {
    try {
      const resp = await fetch(`${this.serverUrl}/api/config`);
      const data = await resp.json();
      this.serverOnline = true;
      this.apiConfigured = data.api_configured;
      const el = document.getElementById('sidebarStatus');
      if (el) el.innerHTML = `<span class="dot ${this.apiConfigured ? 'dot-on' : 'dot-off'}"></span> ${this.apiConfigured ? 'AI就绪' : 'Key未设'}`;
      // 同时更新设置页的状态
      const el2 = document.getElementById('serverStatus');
      if (el2) { el2.textContent = '在线'; el2.style.color = 'var(--green)'; }
      this.setOfflineBanner(false);
    } catch (e) {
      this.serverOnline = false;
      const el = document.getElementById('sidebarStatus');
      if (el) el.innerHTML = '<span class="dot dot-off"></span> 离线';
      // 同时更新设置页的状态
      const el2 = document.getElementById('serverStatus');
      if (el2) { el2.textContent = '离线'; el2.style.color = 'var(--red)'; }
      this.setOfflineBanner(true);
    }

    // Re-check every 30s
    if (!this._healthInterval) {
      this._healthInterval = setInterval(() => this.checkServer(), 30000);
    }
  },

  setOfflineBanner(show) {
    const banner = document.getElementById('offlineBanner');
    if (banner) banner.style.display = show ? 'block' : 'none';
  },

  loadImpressionSnippet() {
    try {
      const cached = JSON.parse(localStorage.getItem('impression_snapshot') || 'null');
      const el = document.getElementById('impressionSnippet');
      if (el && cached && cached.text) {
        el.textContent = cached.text.slice(0, 60) + '...';
      } else if (el) {
        el.textContent = '让系统更了解你...';
      }
    } catch(e) {}
  },

  // ---- Model Switching ----
  modelConfig: { active_provider: 'local', active_model: '', providers: [] },

  async loadModelConfig() {
    try {
      const resp = await fetch(`${this.serverUrl}/api/config/models`);
      this.modelConfig = await resp.json();
      this.renderModelDropdown();
      this.updateModelIndicator();
    } catch (e) { /* server offline, keep defaults */ }
  },

  updateModelIndicator() {
    const label = document.getElementById('modelSwitchLabel');
    const dot = document.getElementById('modelIndicator');
    if (!label || !dot) return;
    const m = this.modelConfig.active_model || 'unknown';
    label.textContent = m.length > 22 ? m.slice(0, 20) + '...' : m;
    label.title = m;
    dot.className = 'model-indicator ' + this.modelConfig.active_provider;
  },

  renderModelDropdown() {
    const list = document.getElementById('modelList');
    if (!list) return;
    const providers = this.modelConfig.providers || [];
    if (providers.length === 0) {
      list.innerHTML = '<div class="model-list-empty">暂无模型，点击下方按钮添加</div>';
      return;
    }
    const active = this.modelConfig.active_model;
    list.innerHTML = providers.map(p => {
      const isActive = p.name === active;
      const canDelete = !isActive && providers.length > 1;
      return `<div class="model-list-item${isActive ? ' active' : ''}" onclick="App.switchModel('${App.escapeHtml(p.provider)}', '${App.escapeHtml(p.name)}')">
        <span class="model-indicator ${App.escapeHtml(p.provider)}"></span>
        <span class="model-item-name" title="${App.escapeHtml(p.name)}">${App.escapeHtml(p.name)}</span>
        <span class="model-item-tag ${App.escapeHtml(p.provider)}">${p.provider === 'local' ? '本地' : 'API'}</span>
        ${canDelete ? '<span class="model-item-delete" onclick="event.stopPropagation();App.deleteModel(\'' + App.escapeHtml(p.name) + '\')" title="删除">×</span>' : ''}
      </div>`;
    }).join('');
  },

  deepThinking: false,

  loadDeepThinking() {
    var self = this;
    fetch('/api/config/settings')
      .then(function(r) { return r.json(); })
      .then(function(d) {
        self.deepThinking = d.settings.deep_thinking === true;
        self._updateDeepThinkUI();
      })
      .catch(function() { self.deepThinking = false; });
  },

  toggleDeepThinking() {
    var self = this;
    var turningOn = !this.deepThinking;
    if (turningOn) {
      if (!confirm(
        '⚡ 开启深度思考模式\n\n' +
        'Agent 将执行多步推理（最多 ' + (this._agentMaxIterations || 6) + ' 步），' +
        '调用知识库搜索、联网查询、代码执行等工具。\n\n' +
        '⚠️ 这会显著增加 Token 消耗（每次对话可能多用 5-10 倍 Token）。\n\n' +
        '确定开启吗？'
      )) return;
    }
    this.deepThinking = turningOn;
    this._updateDeepThinkUI();
    fetch('/api/config/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({deep_thinking: this.deepThinking})
    }).catch(function(){});
  },

  // ── Impressions tracking ──
  _impressionBuffer: [],
  _impressionTimer: null,

  trackImpression(type, data) {
    this._impressionBuffer.push({
      type: type,
      data: data || {},
      timestamp: new Date().toISOString()
    });
    if (!this._impressionTimer) {
      var self = this;
      this._impressionTimer = setTimeout(function() {
        self._flushImpressions();
      }, 2000);
    }
  },

  _flushImpressions() {
    var self = this;
    var batch = this._impressionBuffer.splice(0, this._impressionBuffer.length);
    this._impressionTimer = null;
    if (batch.length === 0) return;
    // Send one by one (simple, low volume)
    batch.forEach(function(ev) {
      fetch(self.serverUrl + '/api/impressions/event', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify(ev)
      }).catch(function() {});
    });
  },

  _trackPageView() {
    var page = window.location.pathname || '/';
    // Normalize: remove trailing slash
    if (page !== '/' && page.endsWith('/')) page = page.slice(0, -1);
    this.trackImpression('page_view', { page: page, title: document.title || '' });
  },

  _updateDeepThinkUI() {
    var btn = document.getElementById('deepThinkToggle');
    var dot = document.getElementById('dtDot');
    if (!btn) return;
    if (this.deepThinking) {
      btn.classList.add('on');
      btn.title = '深度思考：开启（多步Agent，消耗更多Token）';
      if (dot) dot.style.background = '#f59e0b';
    } else {
      btn.classList.remove('on');
      btn.title = '深度思考：关闭（单轮对话，省Token）';
      if (dot) dot.style.background = '#d1d5db';
    }
  },

  toggleModelDropdown() {
    const dd = document.getElementById('modelDropdown');
    if (!dd) return;
    dd.classList.toggle('hidden');
    if (!dd.classList.contains('hidden')) this.renderModelDropdown();
  },

  async switchModel(provider, model) {
    try {
      const resp = await fetch(`${this.serverUrl}/api/config/models/active`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider, model })
      });
      const data = await resp.json();
      if (data.ok) {
        this.modelConfig.active_provider = provider;
        this.modelConfig.active_model = model;
        this.updateModelIndicator();
        this.renderModelDropdown();
        document.getElementById('modelDropdown').classList.add('hidden');
        this.checkServer(); // refresh sidebar status
      } else {
        alert('切换失败: ' + (data.message || '未知错误'));
      }
    } catch (e) {
      alert('切换失败: ' + e.message);
    }
  },

  async deleteModel(name) {
    if (!confirm('确定删除模型「' + name + '」？')) return;
    try {
      const resp = await fetch(`${this.serverUrl}/api/config/models/${encodeURIComponent(name)}`, { method: 'DELETE' });
      const data = await resp.json();
      if (data.ok) {
        this.modelConfig.providers = data.providers;
        this.renderModelDropdown();
      } else {
        alert('删除失败: ' + (data.message || '未知错误'));
      }
    } catch (e) {
      alert('删除失败: ' + e.message);
    }
  },

  openModelModal() {
    document.getElementById('modelDropdown').classList.add('hidden');
    const modal = document.getElementById('modelModal');
    if (modal) modal.classList.remove('hidden');
    document.getElementById('newModelProvider').value = 'local';
    this._toggleModelFormFields();
  },

  closeModelModal() {
    const modal = document.getElementById('modelModal');
    if (modal) modal.classList.add('hidden');
  },

  _toggleModelFormFields() {
    const provider = document.getElementById('newModelProvider').value;
    document.getElementById('newModelApiKeyRow').style.display = provider === 'deepseek' ? 'block' : 'none';
    document.getElementById('newModelBaseUrlRow').style.display = provider === 'deepseek' ? 'block' : 'none';
    document.getElementById('newModelHint').textContent = provider === 'local' ? '本地模型需先 ollama pull 下载到本地' : 'API Key 留空则使用服务器已配置的 Key';
  },

  async addModel() {
    const name = document.getElementById('newModelName').value.trim();
    const provider = document.getElementById('newModelProvider').value;
    const apiKey = document.getElementById('newModelApiKey').value.trim();
    const baseUrl = document.getElementById('newModelBaseUrl').value.trim();
    if (!name) { alert('请输入模型名称'); return; }
    try {
      const resp = await fetch(`${this.serverUrl}/api/config/models`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, provider, api_key: apiKey, base_url: baseUrl })
      });
      const data = await resp.json();
      if (data.ok) {
        this.modelConfig.providers = data.providers;
        this.closeModelModal();
        this.renderModelDropdown();
        document.getElementById('newModelName').value = '';
        document.getElementById('newModelApiKey').value = '';
        document.getElementById('newModelBaseUrl').value = '';
      } else {
        alert('添加失败: ' + (data.message || '未知错误'));
      }
    } catch (e) {
      alert('添加失败: ' + e.message);
    }
  },

  // ---- AI Panel ----
  aiSessionId: null,

  getSessionId() {
    if (!this.aiSessionId) {
      // Check for user-selected session (from session history)
      try {
        var stored = localStorage.getItem('agent_session_id');
        if (stored) {
          this.aiSessionId = stored;
          localStorage.removeItem('agent_session_id');
          return this.aiSessionId;
        }
      } catch(e) {}
      const path = window.location.pathname;
      const page = path === '/' ? 'home' : path.replace(/\//g, '_').slice(1);
      this.aiSessionId = `ui_${page}`;
    }
    return this.aiSessionId;
  },

  toggleAIPanel() {
    const panel = document.getElementById('aiPanel');
    if (!panel) return;
    panel.classList.toggle('collapsed');
  },

  toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (!sidebar) return;
    sidebar.classList.toggle('collapsed');
    const isCollapsed = sidebar.classList.contains('collapsed');
    // Update toggle button text
    const btn = sidebar.querySelector('.sidebar-footer button');
    if (btn) { btn.innerHTML = isCollapsed ? '»' : '«'; btn.title = isCollapsed ? '展开侧边栏' : '收起侧边栏'; }
    try { localStorage.setItem('sidebar_collapsed', isCollapsed ? '1' : '0'); } catch(e) {}
  },

  // Restore sidebar state on init
  restoreSidebar() {
    try {
      if (localStorage.getItem('sidebar_collapsed') === '1') {
        const sidebar = document.getElementById('sidebar');
        if (sidebar) {
          sidebar.classList.add('collapsed');
          const btn = sidebar.querySelector('.sidebar-footer button');
          if (btn) { btn.innerHTML = '»'; btn.title = '展开侧边栏'; }
        }
      }
    } catch(e) {}
  },

  openAIPanel() {
    const panel = document.getElementById('aiPanel');
    if (panel && panel.classList.contains('collapsed')) this.toggleAIPanel();
  },

  async sendAIMsg() {
    const input = document.getElementById('aiInput');
    if (!input) return;
    const msg = input.value.trim();
    if (!msg) return;
    if (!this.serverOnline) {
      this.addAIMsg('ai', '服务器未连接。请先启动服务器。');
      return;
    }
    if (!this.apiConfigured) {
      this.addAIMsg('ai', '请先在设置中配置 DeepSeek API Key。');
      return;
    }

    input.value = '';
    this.openAIPanel();
    this.addAIMsg('user', msg);

    if (this.useStreaming && typeof EventSource !== 'undefined') {
      this._sendStreaming(msg);
    } else {
      this._sendNonStreaming(msg);
    }
  },

  _handleStreamEvent(event, thinkingEl, msgs) {
    let data;
    try { data = JSON.parse(event.data); } catch(e) { return; }

    const LABELS = {
      search_knowledge: '翻知识库', generate_question: '出题中', analyze_progress: '看进度',
      diagnose_weakness: '诊断薄弱点', evaluate_answer: '批改中', feynman_check: '费曼检查',
      create_study_plan: '制定学习计划', deep_question: '举一反三',
    };

    switch (data.type) {
      case 'token':
        // Live streaming token — build up text progressively
        if (!this._streamingEl) {
          if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; }
          this._streamingEl = document.createElement('div');
          this._streamingEl.className = 'tutor-msg ai streaming';
          msgs.appendChild(this._streamingEl);
          this._streamingBuf = '';
        }
        this._streamingBuf += data.content;
        this._streamingEl.innerHTML = App.renderMarkdown(this._streamingBuf);
        break;
      case 'thought':
        // Discard any partial streaming (thought is pre-tool, not final)
        if (this._streamingEl) { this._streamingEl.remove(); this._streamingEl = null; this._streamingBuf = ''; }
        if (thinkingEl) {
          thinkingEl.className = 'tutor-msg thinking-live';
          thinkingEl.innerHTML =
            '<div class="thinking-status">' +
              '<span class="thinking-dot"></span>' +
              '<span class="thinking-label">思考中</span>' +
            '</div>' +
            '<div class="thinking-body">' + App.escapeHtml(data.content || '').slice(0, 280) + '</div>';
        }
        break;
      case 'action':
        if (this._streamingEl) { this._streamingEl.remove(); this._streamingEl = null; this._streamingBuf = ''; }
        if (thinkingEl) {
          var label = LABELS[data.tool] || data.tool || '处理中';
          thinkingEl.className = 'tutor-msg thinking-live thinking-action';
          thinkingEl.innerHTML =
            '<div class="thinking-status">' +
              '<span class="thinking-dot"></span>' +
              '<span class="thinking-label">' + App.escapeHtml(label) + '</span>' +
            '</div>';
        }
        break;
      case 'observation':
        if (thinkingEl) {
          thinkingEl.className = 'tutor-msg thinking-live thinking-done';
          thinkingEl.innerHTML =
            '<div class="thinking-status">' +
              '<span class="thinking-check">&#10003;</span>' +
              '<span class="thinking-label">资料就绪</span>' +
            '</div>';
        }
        break;
      case 'final':
        if (this._streamingEl) {
          // Streaming completed — replace with fully decorated agent message
          this._streamingEl.remove();
          this._streamingEl = null;
          this._streamingBuf = '';
        }
        if (thinkingEl) thinkingEl.remove();
        this.addAgentMsg(data.reply, data.steps || [], data.session_id);
        // Update mascot plan/tool panel
        var _mascotNames = ['_deskmateMascot', '_teacherMascot', '_interviewerMascot', '_officeMascot', '_resumeMascot'];
        for (var _i = 0; _i < _mascotNames.length; _i++) {
          var _m = window[_mascotNames[_i]];
          if (_m && typeof _m.updateFromFinal === 'function') {
            _m.updateFromFinal(data);
          }
        }
        this._activeEventSource = null;
        break;
      case 'error':
        if (this._streamingEl) { this._streamingEl.remove(); this._streamingEl = null; this._streamingBuf = ''; }
        if (thinkingEl) thinkingEl.remove();
        this.addAIMsg('ai', data.content);
        this._activeEventSource = null;
        break;
      case 'cancelled':
        if (this._streamingEl) { this._streamingEl.remove(); this._streamingEl = null; this._streamingBuf = ''; }
        if (thinkingEl) {
          thinkingEl.className = 'tutor-msg thinking-live';
          thinkingEl.innerHTML = '<div class="thinking-status" style="opacity:0.7"><span style="font-size:14px">&#9888;</span><span class="thinking-label">已中断</span></div>';
          setTimeout(function() { if (thinkingEl && thinkingEl.parentNode) thinkingEl.remove(); }, 2000);
        }
        this._activeEventSource = null;
        break;
    }
    if (msgs) msgs.scrollTop = msgs.scrollHeight;
  },

  stopStream() {
    // 先发 cancel 信号，等待后端确认或超时后再关 SSE
    if (this._activeEventSource) {
      var sid = this.getSessionId();
      var es = this._activeEventSource;
      this._activeEventSource = null;
      var self = this;
      fetch(this.serverUrl + '/api/agent/chat/cancel', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ session_id: sid })
      }).catch(function() {});
      // 等待 cancel 信号传播（后端处理 + SSE 回传），超时 500ms 后强制关闭
      setTimeout(function() {
        try { es.close(); } catch(e) {}
      }, 3000);
    }
    this._streamingActive = false;
  },

  _sendStreaming(msg) {
    // Clean up existing stream + any partial streaming UI
    if (this._activeEventSource) {
      this._activeEventSource.close();
      this._activeEventSource = null;
    }
    if (this._streamingEl) {
      this._streamingEl.remove();
      this._streamingEl = null;
      this._streamingBuf = '';
    }

    const msgs = document.getElementById('aiMessages');
    const thinkingEl = document.createElement('div');
    thinkingEl.className = 'tutor-msg thinking-live';
    thinkingEl.innerHTML = '<div class="thinking-status"><span class="thinking-dot"></span><span class="thinking-label">准备中...</span></div>';
    msgs.appendChild(thinkingEl);
    msgs.scrollTop = msgs.scrollHeight;

    const url = `${this.serverUrl}/api/agent/chat/stream?` +
      `session_id=${encodeURIComponent(this.getSessionId())}` +
      `&message=${encodeURIComponent(msg)}`;

    const es = new EventSource(url);
    this._activeEventSource = es;

    es.onmessage = (event) => this._handleStreamEvent(event, thinkingEl, msgs);
    es.onerror = () => {
      if (this._activeEventSource === es) {
        es.close();
        this._activeEventSource = null;
        if (thinkingEl && thinkingEl.parentNode) {
          thinkingEl.remove();
          this.addAIMsg('ai', '连接中断，请重试。');
        }
      }
    };
  },

  async _sendNonStreaming(msg) {
    const msgs = document.getElementById('aiMessages');
    const thinkingEl = document.createElement('div');
    thinkingEl.className = 'tutor-msg thinking-live';
    thinkingEl.innerHTML = '<div class="thinking-status"><span class="thinking-dot"></span><span class="thinking-label">准备中...</span></div>';
    msgs.appendChild(thinkingEl);
    msgs.scrollTop = msgs.scrollHeight;

    try {
      const resp = await fetch(`${this.serverUrl}/api/agent/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: msg, session_id: this.getSessionId() })
      });
      const data = await resp.json();
      thinkingEl.remove();

      if (data.error) {
        this.addAIMsg('ai', `错误: ${data.error}`);
      } else {
        this.addAgentMsg(data.reply, data.steps || [], data.session_id);
      }
    } catch (e) {
      thinkingEl.remove();
      this.addAIMsg('ai', `请求失败: ${e.message}`);
    }
    msgs.scrollTop = msgs.scrollHeight;
  },

  addAgentMsg(reply, steps, sessionId) {
    const msgs = document.getElementById('aiMessages');
    if (!msgs) return;
    const el = document.createElement('div');
    el.className = 'tutor-msg ai';

    // Strip JSON block from display and extract for save button
    let displayReply = reply;
    let questionJson = null;
    const jsonMatch = reply.match(/```json\s*\n?([\s\S]*?)\n?```/);
    if (jsonMatch) {
      try {
        questionJson = JSON.parse(jsonMatch[1]);
        displayReply = reply.replace(/```json[\s\S]*?```/, '').trim();
      } catch(e) { /* not valid JSON, show full reply */ }
    }

    let html = '';

    // Show tool badges
    const toolNames = [...new Set((steps || []).filter(s => s.phase === 'action').map(s => s.tool))];
    if (toolNames.length > 0) {
      const TOOL_LABELS = {
        search_knowledge: '搜索知识库',
        generate_question: '生成题目',
        analyze_progress: '分析进度',
        diagnose_weakness: '诊断薄弱点',
        evaluate_answer: '批改评估',
        feynman_check: '费曼检查',
        create_study_plan: '学习计划',
        deep_question: '深度提问',
      };
      html += '<div class="tool-badges" style="margin-bottom:6px">';
      toolNames.forEach(t => {
        const label = TOOL_LABELS[t] || t;
        html += `<span class="tool-badge" style="display:inline-block;font-size:11px;padding:2px 8px;margin:2px 4px 2px 0;border-radius:12px;background:var(--bg);color:var(--text2);border:1px solid var(--border)">${App.escapeHtml(label)}</span>`;
      });
      html += '</div>';
    }

    // Render main reply with markdown
    html += App.renderMarkdown(displayReply);

    // Convert [来源: ...] to clickable links that open source sidebar
    html = html.replace(/\[来源[：:]\s*(.+?)\]/g, function(match, sources) {
      var items = sources.split(/[,，]\s*/);
      return '<span class="source-ref">[来源: ' + items.map(function(s) {
        var name = s.trim();
        return '<a href="#" class="source-link" onclick="SourceSidebar.show(\'' +
               App.escapeHtml(name).replace(/'/g, '\\\'') + '\');return false">' +
               App.escapeHtml(name) + '</a>';
      }).join(', ') + ']</span>';
    });

    // Show thinking steps if any
    if (steps && steps.length > 0) {
      html += '<details class="thinking-steps" style="margin-top:8px;font-size:11px">';
      html += '<summary style="cursor:pointer;color:var(--text2)">查看思考过程 (' + steps.length + ' 步)</summary>';
      steps.forEach((s, i) => {
        if (s.phase === 'thought') {
          html += '<div style="margin:4px 0;padding:4px 8px;background:#eef2ff;border-radius:4px">';
          html += '<strong>&#128161; 思考: </strong>';
          html += '<span style="color:var(--text);font-size:11px">' + App.escapeHtml(s.content || '').slice(0, 500) + '</span>';
          html += '</div>';
          return;
        }
        const icon = s.phase === 'action' ? '🔧' : '📋';
        const label = s.phase === 'action' ? '调用工具' : '观察结果';
        html += '<div style="margin:4px 0;padding:4px 8px;background:var(--bg);border-radius:4px">';
        html += '<strong>' + icon + ' ' + label + ': ' + App.escapeHtml(s.tool || '') + '</strong>';
        if (s.phase === 'action' && s.input) {
          html += '<div style="color:var(--text2);font-size:10px">输入: ' + App.escapeHtml(JSON.stringify(s.input)).slice(0, 200) + '</div>';
        }
        if (s.phase === 'observation' && s.output) {
          html += '<div style="color:var(--text2);font-size:10px;max-height:80px;overflow-y:auto">' + App.escapeHtml(s.output).slice(0, 400) + '</div>';
        }
        html += '</div>';
      });
      html += '</details>';
    }

    // Save to trainer button
    const hasGenQuestion = steps && steps.some(s => s.tool === 'generate_question');
    if ((hasGenQuestion || questionJson) && displayReply.length > 10) {
      const saveData = questionJson || { type: 'flashcards', question: displayReply.slice(0, 200), answer: displayReply.slice(0, 500), topic: 'AI生成' };
      const saveJson = App.escapeHtml(JSON.stringify(saveData));
      html += '<button class="btn btn-sm btn-primary" style="margin-top:8px;font-size:11px" onclick="App.saveQuestionToTrainer(\'' + saveJson + '\', this)">保存到题库</button>';
    }

    // Session info
    if (sessionId) {
      html += '<div class="meta" style="margin-top:4px">session: ' + App.escapeHtml(sessionId) + '</div>';
    }

    el.innerHTML = html;
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
  },

  askAI(topic, context) {
    this.openAIPanel();
    const input = document.getElementById('aiInput');
    let q = `关于「${topic}」`;
    if (context) q += `\n\n已知信息: ${context}`;
    q += '\n\n请帮我理解这个概念。';
    input.value = q;
    this.sendAIMsg();
  },

  addAIMsg(role, text) {
    const msgs = document.getElementById('aiMessages');
    if (!msgs) return;
    const el = document.createElement('div');
    el.className = `tutor-msg ${role}`;
    if (role === 'ai') {
      el.innerHTML = App.renderMarkdown(text);
    } else {
      el.textContent = text;
    }
    msgs.appendChild(el);
    msgs.scrollTop = msgs.scrollHeight;
  },

  // ── Markdown renderer ──
  renderMarkdown(text) {
    if (!text) return '';
    // 1. Extract and protect fenced code blocks
    var codeBlocks = [];
    var t = text.replace(/```(\w*)\n?([\s\S]*?)```/g, function(_, lang, code) {
      codeBlocks.push('<pre><code class="' + App.escapeHtml(lang || '') + '">' + App.escapeHtml(code.trimEnd()) + '</code></pre>');
      return '\x00CODE' + (codeBlocks.length - 1) + '\x00';
    });
    // 2. Inline code (protect before other rules)
    t = t.replace(/`([^`\n]+)`/g, function(_, code) {
      return '<code>' + App.escapeHtml(code) + '</code>';
    });
    // 3. Escape HTML in remaining text
    t = App.escapeHtml(t);
    // 4. Bold + italic (order matters: ** then *)
    t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // 5. Headers (line-start)
    t = t.replace(/^### (.+)$/gm, '<h4>$1</h4>');
    t = t.replace(/^## (.+)$/gm, '<h3>$1</h3>');
    t = t.replace(/^# (.+)$/gm, '<h2>$1</h2>');
    // 6. Blockquote
    t = t.replace(/^&gt; (.+)$/gm, '<blockquote>$1</blockquote>');
    // 7. Inline links [text](url) — already escaped, need to reverse entities in URL
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    // 8. Horizontal rule
    t = t.replace(/^---$/gm, '<hr>');
    // 9. Line breaks
    t = t.replace(/\n\n/g, '</p><p>');
    t = t.replace(/\n/g, '<br>');
    t = '<p>' + t + '</p>';
    // 10. Restore code blocks
    t = t.replace(/\x00CODE(\d+)\x00/g, function(_, i) { return codeBlocks[parseInt(i)]; });
    // 11. Clean empty paragraphs
    t = t.replace(/<p><\/p>/g, '');
    // 12. Nav links — route internal paths
    t = t.replace(/href="\/([^"]+)"/g, 'href="/$1"');
    return t;
  },

  saveQuestionToTrainer(itemJson, btn) {
    let item;
    try {
      item = JSON.parse(itemJson);
    } catch(e) {
      alert('题目数据格式错误');
      return;
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = '保存中...';
    }
    fetch(`${this.serverUrl}/api/exercises/save-generated`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ item })
    })
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        if (btn) { btn.textContent = '已保存'; btn.classList.add('saved'); }
      } else {
        if (btn) { btn.disabled = false; btn.textContent = '保存失败'; }
        alert('保存失败: ' + (data.error || '未知错误'));
      }
    })
    .catch(e => {
      if (btn) { btn.disabled = false; btn.textContent = '重试'; }
    });
  },

  // ---- Settings Modal ----
  openSettings() {
    const modal = document.getElementById('settingsModal');
    if (modal) modal.classList.remove('hidden');
    const input = document.getElementById('apiKeyInput');
    if (input) input.value = '';
    // Show current key status
    const status = document.getElementById('apiKeyStatus');
    if (status) {
      status.innerHTML = this.apiConfigured
        ? '<span style="color:var(--green)">已配置</span> — 输入新 Key 可更换'
        : '<span style="color:var(--red)">未配置</span> — 请输入 DeepSeek API Key';
    }
  },

  closeSettings() {
    const modal = document.getElementById('settingsModal');
    if (modal) modal.classList.add('hidden');
  },

  async saveSettings() {
    const key = document.getElementById('apiKeyInput').value.trim();
    this.closeSettings();
    if (key) {
      try {
        const ctrl = new AbortController();
        const timer = setTimeout(() => ctrl.abort(), 5000);
        await fetch(`${this.serverUrl}/api/config`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ api_key: key }),
          signal: ctrl.signal
        });
        clearTimeout(timer);
        this.checkServer();
      } catch (e) { /* ignore */ }
    }
  },

  // ---- Quick Actions ----
  quickAction(type) {
    this.openAIPanel();
    const input = document.getElementById('aiInput');
    if (!input) return;
    const prompts = {
      deep: '请对我刚才讨论的知识点使用 deep_question 工具，生成一道场景迁移/举一反三题。',
      deep_chain: '请开始深度提问模式，按以下流程进行：\n1. 先用 deep_question 对我最近讨论的概念出一道场景迁移题\n2. 等我回答后，用 evaluate_answer 评估我的回答\n3. 基于我发现的问题，再出一道更深入或换角度的题\n4. 重复2-3轮后，总结我的理解深度、盲区和改进建议\n现在请开始第1步。',
      exercise: '请根据刚才讨论的知识点，用 generate_question 生成一道练习题（选择题）。',
      diagnose: '请先调用 diagnose_weakness 诊断我的薄弱点，然后调用 create_study_plan 生成学习计划。'
    };
    input.value = prompts[type] || '';
    this.sendAIMsg();
  },

  // ---- History Recording ----
  async recordProgress(entry) {
    try {
      await fetch(`${this.serverUrl}/api/progress/record`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(entry)
      });
    } catch (e) { /* non-critical */ }
  },

  // ---- Utils ----
  escapeHtml(s) {
    if (typeof s !== 'string') return s;
    return s
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  },

  /** Shared UI: empty state placeholder */
  renderEmpty(title, msg) {
    return `<div class="empty-state"><h3>${this.escapeHtml(title||'')}</h3>${msg ? '<p>'+this.escapeHtml(msg)+'</p>' : ''}</div>`;
  },

  /** Shared UI: feedback box (type: correct/wrong/info/warn) */
  renderFeedback(type, html) {
    return `<div class="feedback-box feedback-${type}">${html}</div>`;
  },

  /** Shared UI: animated thinking indicator */
  renderThinking() {
    return '<span class="thinking-dots">思考中<span>.</span><span>.</span><span>.</span></span>';
  },

  // ── Session History ──
  openSessionHistory() {
    const modal = document.getElementById('sessionHistoryModal');
    if (modal) { modal.classList.remove('hidden'); }
    this.loadSessionList();
  },

  closeSessionHistory() {
    const modal = document.getElementById('sessionHistoryModal');
    if (modal) { modal.classList.add('hidden'); }
  },

  loadSessionList() {
    const list = document.getElementById('sessionHistoryList');
    if (!list) return;
    list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text3)">加载中...</div>';
    fetch('/api/session-history')
      .then(r => r.json())
      .then(sessions => {
        if (!sessions.length) {
          list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text3)">暂无会话历史</div>';
          return;
        }
        const personaLabels = { deskmate: '同桌', teacher: '老师', interviewer: '面试官' };
        list.innerHTML = sessions.map(s => {
          const label = personaLabels[s.persona] || s.persona || '未知';
          const date = s.last_accessed ? new Date(s.last_accessed * 1000).toLocaleString('zh-CN') : '';
          return '<div class="session-history-item" style="display:flex;align-items:center;justify-content:space-between;padding:10px 14px;border-bottom:1px solid var(--border);cursor:pointer;transition:background .12s" onclick="App.switchSession(\'' + App.escapeHtml(s.session_id) + '\', \'' + App.escapeHtml(s.persona || '') + '\')">' +
            '<div style="flex:1;min-width:0">' +
              '<div style="font-size:13px;font-weight:500">' + App.escapeHtml(label) + ' · ' + (s.message_count || 0) + ' 条消息</div>' +
              '<div style="font-size:11px;color:var(--text2);overflow:hidden;text-overflow:ellipsis;white-space:nowrap;margin-top:2px">' + App.escapeHtml(s.snippet || '(空)') + '</div>' +
              '<div style="font-size:10px;color:var(--text3);margin-top:1px">' + date + '</div>' +
            '</div>' +
            '<button class="btn btn-sm" style="font-size:10px;margin-left:12px;flex-shrink:0" onclick="event.stopPropagation();App.deleteSession(\'' + App.escapeHtml(s.session_id) + '\')" title="删除">✕</button>' +
          '</div>';
        }).join('');
      })
      .catch(() => {
        list.innerHTML = '<div style="padding:20px;text-align:center;color:var(--red)">加载失败</div>';
      });
  },

  switchSession(sessionId, persona) {
    try { localStorage.setItem('agent_session_id', sessionId); } catch(e) {}
    try { localStorage.setItem('agent_session_persona', persona || ''); } catch(e) {}
    this.closeSessionHistory();
    var routes = { deskmate: '/', teacher: '/classroom', interviewer: '/interview' };
    var url = routes[persona] || '/';
    if (typeof Router !== 'undefined' && Router.navigate) {
      Router.navigate(url);
    } else {
      location.href = url;
    }
  },

  loadSessionHistory() {
    var self = this;
    var sid = this.getSessionId();
    if (!sid || sid.indexOf('ui_') === 0) return;
    var persona = '';
    try { persona = localStorage.getItem('agent_session_persona') || ''; } catch(e) {}
    fetch('/api/session-history/' + encodeURIComponent(sid))
      .then(function(r) { if (!r.ok) throw new Error('not found'); return r.json(); })
      .then(function(data) {
        var msgs = data.messages || [];
        if (!msgs.length) return;
        var p = data.persona || persona;
        var containers = { teacher: 'teacherChat', deskmate: 'deskChat', interviewer: 'ivChat' };
        var containerId = containers[p] || 'aiMessages';
        var container = document.getElementById(containerId);
        if (!container) return;
        var classes = { teacher: 'teacher-msg', deskmate: 'desk-msg', interviewer: 'interview-msg' };
        var msgClass = classes[p] || 'tutor-msg';
        container.innerHTML = '';
        msgs.forEach(function(m) {
          if (m.role === 'user') {
            var el = document.createElement('div');
            el.className = msgClass + ' user';
            el.textContent = m.content || '';
            container.appendChild(el);
          } else if (m.role === 'assistant' || m.role === 'ai') {
            var el = document.createElement('div');
            el.className = msgClass + ' ' + p;
            el.innerHTML = App.renderMarkdown ? App.renderMarkdown(m.content || '') : (m.content || '').replace(/\n/g, '<br>');
            container.appendChild(el);
          }
        });
        container.scrollTop = container.scrollHeight;
      })
      .catch(function() {});
  },

  deleteSession(sessionId) {
    if (!confirm('删除这个会话？')) return;
    fetch('/api/session-history/' + encodeURIComponent(sessionId), { method: 'DELETE' })
      .then(() => this.loadSessionList())
      .catch(() => alert('删除失败'));
  }
};

// ═══════════════════════════════════════════
// Router — Hybrid navigation with transitions
// ═══════════════════════════════════════════
var Router = {
  _transitioning: false,
  _pageBodyClass: null,   // body class for background transition
  _allowedPaths: [        // whitelist: only navigate internal pages
    '/', '/classroom', '/interview', '/trainer', '/textbook',
    '/study-plan', '/construction', '/impressions', '/settings',
    '/feynman', '/agent-build', '/changelog',
    '/source-trace', '/knowledge', '/resume', '/architecture'
  ],

  init: function() {
    var self = this;
    // Intercept sidebar nav-item clicks
    document.querySelectorAll('.nav-item').forEach(function(el) {
      el.addEventListener('click', function(e) {
        var href = el.getAttribute('href');
        if (!href || href === '#') return;
        // Workbench is a separate app shell — full page navigation
        if (href === '/workbench') return;
        // Only intercept internal page links
        if (self._allowedPaths.indexOf(href) === -1) return;
        if (href === window.location.pathname) return;
        if (e.metaKey || e.ctrlKey || e.button === 1) return;
        e.preventDefault();
        if (self._transitioning) return;
        var currentPath = window.location.pathname;
        var direction = self._getDirection(currentPath, href);
        self.navigate(href, direction);
      });
    });
    // Browser back/forward
    window.addEventListener('popstate', function(e) {
      if (self._transitioning) return;
      // popstate direction is always 'back' (back button)
      self.navigate(window.location.pathname, 'back', true);
    });
    // Extract body class from current page
    var bc = document.body.className.match(/page-\S+/);
    if (bc) this._pageBodyClass = bc[0];
  },

  _getDirection: function(from, to) {
    // Simple heuristic: deeper paths get 'forward', root gets 'back'
    // Root is always the shallowest — navigating away is forward, coming back is backward
    if (from === '/' && to !== '/') return 'forward';
    if (to === '/' && from !== '/') return 'back';
    if (to === '/construction' || to === '/eval') return 'forward';
    if (from === '/construction' || from === '/eval') return 'back';
    return 'forward';
  },

  _getTransitionType: function(from, to) {
    // Room: classroom & interview keep their atmospheric enter/exit
    if (from === '/classroom' || from === '/interview' || to === '/classroom' || to === '/interview') return 'room';
    // Fade: utility/config pages (subtle, no movement)
    if (['/settings','/eval','/construction','/impressions','/changelog','/architecture','/source-trace'].indexOf(to) !== -1) return 'fade';
    if (['/settings','/eval','/construction','/impressions','/changelog','/architecture','/source-trace'].indexOf(from) !== -1) return 'fade';
    // Zoom: focused work pages (pull focus)
    if (['/trainer','/study-plan','/feynman','/agent-build'].indexOf(to) !== -1) return 'zoom';
    if (['/trainer','/study-plan','/feynman','/agent-build'].indexOf(from) !== -1) return 'zoom';
    // Slide: default (book-like lateral movement)
    return 'slide';
  },

  navigate: function(url, direction, replaceState) {
    var self = this;
    this._transitioning = true;
    // 关闭所有活跃的 EventSource，防止旧页面 SSE 事件写入已销毁的 DOM
    if (typeof App !== 'undefined') App.stopStream();
    var main = document.getElementById('mainContent');
    var overlay = document.getElementById('transition-overlay');
    if (overlay) overlay.classList.add('active');
    if (!main) { window.location.href = url; return; }

    // Step 1: Trigger exit animation on current content
    var exitPane = document.createElement('div');
    var transType = self._getTransitionType(window.location.pathname, url.split('?')[0]);
    var exitClass;
    if (transType === 'room') exitClass = 'room-exit';
    else if (transType === 'fade') exitClass = 'fade-exit';
    else if (transType === 'zoom') exitClass = 'zoom-exit';
    else exitClass = (direction === 'forward' ? 'exit-left' : 'exit-right');
    exitPane.className = 'transition-pane outgoing ' + exitClass;
    while (main.firstChild) exitPane.appendChild(main.firstChild);
    main.appendChild(exitPane);

    var exitDone = false;
    var fetchDone = false;
    var newHtml = null;

    // Step 2: Force reflow then start exit animation
    exitPane.offsetHeight;
    exitPane.classList.add('active');

    exitPane.addEventListener('animationend', function() {
      if (exitDone) return;
      exitDone = true;
      if (exitPane.parentNode) exitPane.parentNode.removeChild(exitPane);
      if (fetchDone) self._doEnter(main, newHtml, direction, replaceState, url);
    });

    // Step 3: Fetch new page in parallel
    fetch(url)
      .then(function(r) { return r.text(); })
      .then(function(html) {
        newHtml = html;
        fetchDone = true;
        if (exitDone) self._doEnter(main, newHtml, direction, replaceState, url);
      })
      .catch(function() {
        // Fetch failed — fallback to full navigation
        window.location.href = url;
      });
  },

  _doEnter: function(main, fullHtml, direction, replaceState, url) {
    var self = this;

    // Extract body class from new page HTML
    var bodyMatch = fullHtml.match(/<body[^>]*class="([^"]*)"/);
    var bodyContentMatch = fullHtml.match(/<body[^>]*>([\s\S]*?)<\/body>/);
    var headMatch = fullHtml.match(/<head>([\s\S]*?)<\/head>/);

    // Update body class for background transition
    if (bodyMatch) {
      var classes = bodyMatch[1].split(/\s+/);
      var pageClass = null;
      for (var i = 0; i < classes.length; i++) {
        if (classes[i].indexOf('page-') === 0) { pageClass = classes[i]; break; }
      }
      if (pageClass && pageClass !== this._pageBodyClass) {
        document.body.className = document.body.className.replace(/page-\S+/g, '');
        document.body.className += ' ' + pageClass;
        this._pageBodyClass = pageClass;
      }
    }

    // Update <head> — inject style blocks from new page
    if (headMatch) {
      var tempDiv = document.createElement('div');
      tempDiv.innerHTML = headMatch[1];
      // Remove old page-specific styles
      document.querySelectorAll('head style.page-style').forEach(function(s) { s.remove(); });
      // Copy ALL <style> blocks from new page (not just ones with id/data-page)
      tempDiv.querySelectorAll('style').forEach(function(s) {
        var clone = document.createElement('style');
        clone.className = 'page-style';
        clone.textContent = s.textContent;
        document.head.appendChild(clone);
      });
      // Update title
      var titleEl = tempDiv.querySelector('title');
      if (titleEl) document.title = titleEl.textContent;
    }

    // Extract #mainContent from new HTML (DOM-based, no regex fragile on tag mismatch)
    var newContent = '';
    if (bodyContentMatch) {
      var bodyHtml = bodyContentMatch[1];
      var tempDiv = document.createElement('div');
      tempDiv.innerHTML = bodyHtml;
      var mainEl = tempDiv.querySelector('#mainContent');
      if (mainEl) { newContent = mainEl.innerHTML; }
    }

    if (!newContent) {
      window.location.href = url;
      return;
    }

    // Step 4: Inject new content with enter animation
    var enterPane = document.createElement('div');
    var enterTransType = self._getTransitionType(window.location.pathname, url.split('?')[0]);
    var enterClass;
    if (enterTransType === 'room') enterClass = 'room-enter';
    else if (enterTransType === 'fade') enterClass = 'fade-enter';
    else if (enterTransType === 'zoom') enterClass = 'zoom-enter';
    else enterClass = (direction === 'forward' ? 'enter-right' : 'enter-left');
    enterPane.className = 'transition-pane incoming ' + enterClass;
    enterPane.innerHTML = newContent;
    main.appendChild(enterPane);

    enterPane.offsetHeight;
    enterPane.classList.add('active');

    var entered = false;
    function finishEnter() {
      if (entered) return;
      entered = true;
      // Unwrap — move children to main, remove pane
      while (enterPane.firstChild) main.appendChild(enterPane.firstChild);
      if (enterPane.parentNode) enterPane.parentNode.removeChild(enterPane);
      self._transitioning = false;
      var overlay = document.getElementById('transition-overlay');
      if (overlay) overlay.classList.remove('active');
      if (typeof App !== 'undefined' && App.highlightNav) App.highlightNav();

      // Reset ready state BEFORE re-executing scripts (they call App.ready())
      App._resetPageReady();

      // Re-execute inline page scripts
      self._execPageScripts(main, bodyHtml);

      // Fire page-ready — drains callbacks registered by re-executed scripts
      setTimeout(function() { App._firePageReady(); }, 0);

      // Load session history after SPA navigation
      App.aiSessionId = null;
      try { App.aiSessionPersona = localStorage.getItem("agent_session_persona") || ""; } catch(e) {}
      setTimeout(function() { App.loadSessionHistory(); }, 200);
    }
    enterPane.addEventListener('animationend', finishEnter);
    // Fallback: if animation doesn't fire (e.g., prefers-reduced-motion), execute after timeout
    setTimeout(finishEnter, 800);

    // Update history
    if (replaceState) {
      history.replaceState({ url: url }, '', url);
    } else {
      history.pushState({ url: url }, '', url);
    }
  },

  _execPageScripts: function(container, fullBodyHtml) {
    // Remove old page scripts before adding new ones
    document.querySelectorAll('script.page-script').forEach(function(s) { s.remove(); });
    // Search the FULL body HTML for scripts, not just #mainContent
    var tempDiv = document.createElement('div');
    tempDiv.innerHTML = fullBodyHtml;
    var scripts = tempDiv.querySelectorAll('script:not([src])');
    scripts.forEach(function(oldScript) {
      var newScript = document.createElement('script');
      newScript.className = 'page-script';
      newScript.textContent = oldScript.textContent;
      document.body.appendChild(newScript);
    });
  }
};

// Boot
document.addEventListener('DOMContentLoaded', () => App.init());

// ═══════════════════════════════════════════
// SourceSidebar — Opens knowledge source trace
// ═══════════════════════════════════════════
window.SourceSidebar = {
  show: function(sourceName) {
    var sidebar = document.getElementById('sourceSidebar');
    var body = document.getElementById('sourceSidebarBody');
    if (!sidebar || !body) return;
    sidebar.style.display = 'flex';
    body.innerHTML = '<div class="pipeline-loading">加载中...</div>';

    fetch('/api/knowledge/source/' + encodeURIComponent(sourceName))
      .then(function(r) { return r.json(); })
      .then(function(data) {
        body.innerHTML =
          '<h4 style="margin:0 0 4px;font-size:16px">' + App.escapeHtml(data.title || sourceName) + '</h4>' +
          '<p style="color:#888;font-size:12px;margin:0 0 12px">' + App.escapeHtml(data.type || '') + ' · ' + (data.chunks || 0) + ' chunks</p>' +
          '<blockquote style="margin:0;padding:12px 16px;background:#f8f5ee;border-left:3px solid #c9b99a;font-size:13px;line-height:1.7;white-space:pre-wrap">' + App.escapeHtml((data.text || '').slice(0, 800)) + '</blockquote>' +
          '<p style="margin-top:16px"><a href="/knowledge-pipeline" style="color:#6b4c2a">在知识管道中查看 →</a></p>';
      })
      .catch(function() {
        body.innerHTML = '<p style="color:#c44">加载失败，请重试</p>';
      });
  },
  hide: function() {
    var sidebar = document.getElementById('sourceSidebar');
    if (sidebar) sidebar.style.display = 'none';
  }
};

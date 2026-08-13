/**
 * Settings Page Module — API key, usage controls, templates, data export/import, cache
 * Depends on: App (app.js)
 */
const SettingsPage = {
  _currentTemplate: 'moderate',

  async init() {
    this.refreshStatus();
    this.loadStorageInfo();
    await this.loadSettings();
    this._bindTemplates();
    this.renderNewsCategories();
  },

  // ── Load / Save Settings ──

  async loadSettings() {
    try {
      var resp = await fetch('/api/config/settings');
      var data = await resp.json();
      var s = data.settings || {};
      this._currentTemplate = s.template || 'moderate';
      this._applyToForm(s);
      this._updateTemplateUI();
      document.getElementById('dailyCallCount').textContent = data.daily_call_count || 0;
      document.getElementById('currentProvider').textContent =
        App.modelConfig.active_provider || '-';
      document.getElementById('currentModel').textContent =
        App.modelConfig.active_model || '-';
    } catch(e) {
      // settings unavailable, use defaults
      document.getElementById('dailyCallCount').textContent = '-';
    }
  },

  _applyToForm(s) {
    setVal('cfg_agent_max_iterations', s.agent_max_iterations);
    setCheck('cfg_agent_max_iterations_unlimited', s.agent_max_iterations_unlimited);
    setVal('cfg_rate_limit_per_minute', s.rate_limit_per_minute);
    setCheck('cfg_rate_limit_unlimited', s.rate_limit_unlimited);
    setVal('cfg_max_conversation_rounds', s.max_conversation_rounds);
    setCheck('cfg_max_conversation_rounds_unlimited', s.max_conversation_rounds_unlimited);
    setVal('cfg_session_token_limit', s.session_token_limit);
    setCheck('cfg_session_token_limit_unlimited', s.session_token_limit_unlimited);
    setVal('cfg_daily_token_limit', s.daily_token_limit);
    setCheck('cfg_daily_token_limit_unlimited', s.daily_token_limit_unlimited);
    setVal('cfg_streaming_enabled', s.streaming_enabled ? 'true' : 'false');
    setVal('cfg_news_enabled', s.news_enabled !== false ? 'true' : 'false');
    setVal('cfg_news_count', s.news_count || 5);
    this._newsCategories = s.news_categories || ['technology', 'science'];
    // Data source API keys
    var newsKey = s.news_api_key || '';
    setVal('cfg_news_api_key', newsKey);
    var statusEl = document.getElementById('newsApiKeyStatus');
    if (statusEl) { statusEl.textContent = newsKey ? '已配置' : '未配置'; }

    // update disabled state and warnings
    toggleUI('agent_max_iterations', s.agent_max_iterations_unlimited);
    toggleUI('rate_limit', s.rate_limit_unlimited);
    toggleUI('max_conversation_rounds', s.max_conversation_rounds_unlimited);
    toggleUI('session_token_limit', s.session_token_limit_unlimited);
    toggleUI('daily_token_limit', s.daily_token_limit_unlimited);
  },

  _collectSettings() {
    return {
      agent_max_iterations: parseInt(getVal('cfg_agent_max_iterations')) || 6,
      agent_max_iterations_unlimited: getCheck('cfg_agent_max_iterations_unlimited'),
      rate_limit_per_minute: parseInt(getVal('cfg_rate_limit_per_minute')) || 15,
      rate_limit_unlimited: getCheck('cfg_rate_limit_unlimited'),
      max_conversation_rounds: parseInt(getVal('cfg_max_conversation_rounds')) || 15,
      max_conversation_rounds_unlimited: getCheck('cfg_max_conversation_rounds_unlimited'),
      session_token_limit: parseInt(getVal('cfg_session_token_limit')) || 30000,
      session_token_limit_unlimited: getCheck('cfg_session_token_limit_unlimited'),
      daily_token_limit: parseInt(getVal('cfg_daily_token_limit')) || 200000,
      daily_token_limit_unlimited: getCheck('cfg_daily_token_limit_unlimited'),
      streaming_enabled: getVal('cfg_streaming_enabled') === 'true',
      news_enabled: getVal('cfg_news_enabled') === 'true',
      news_categories: this._newsCategories || ['technology', 'science'],
      news_count: parseInt(getVal('cfg_news_count')) || 5,
      news_api_key: getVal('cfg_news_api_key') || '',
    };
  },

  async saveCurrent() {
    var settings = this._collectSettings();
    settings.template = this._currentTemplate;
    try {
      var resp = await fetch('/api/config/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      var data = await resp.json();
      if (data.ok) {
        App.checkServer();
        this.showMsg('设置已保存', 'ok');
      }
    } catch(e) {
      this.showMsg('保存失败: ' + e.message, 'err');
    }
  },

  // ── Templates ──

  _bindTemplates() {
    var self = this;
    document.querySelectorAll('.template-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        var tpl = this.dataset.template;
        if (tpl === 'custom') {
          self._currentTemplate = 'custom';
          self._updateTemplateUI();
          return;
        }
        self.applyTemplate(tpl);
      });
    });

    // When any control changes manually, switch to custom
    var selects = ['cfg_agent_max_iterations', 'cfg_rate_limit_per_minute',
      'cfg_max_conversation_rounds', 'cfg_session_token_limit', 'cfg_daily_token_limit',
      'cfg_streaming_enabled'];
    selects.forEach(function(id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener('change', function() { self._markCustom(); });
    });
  },

  async applyTemplate(name) {
    try {
      var resp = await fetch('/api/config/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ template: name })
      });
      var data = await resp.json();
      if (data.ok) {
        this._currentTemplate = name;
        this._applyToForm(data.settings);
        this.renderNewsCategories();
        this._updateTemplateUI();
        this.showMsg('已应用「' + this._templateLabel(name) + '」模板', 'ok');
      }
    } catch(e) {
      this.showMsg('模板应用失败', 'err');
    }
  },

  _markCustom() {
    if (this._currentTemplate === 'custom') return;
    this._currentTemplate = 'custom';
    this._updateTemplateUI();
  },

  _updateTemplateUI() {
    document.querySelectorAll('.template-btn').forEach(function(btn) {
      btn.classList.toggle('active', btn.dataset.template === SettingsPage._currentTemplate);
    });
  },

  _templateLabel(name) {
    return { light: '轻量', moderate: '中度', heavy: '重度', custom: '自定义' }[name] || name;
  },

  // ── News Category Preferences ──

  newsCategories: ["technology", "science", "business", "general", "health", "entertainment"],

  newsCategoryLabels: {
    technology: "科技", science: "科学", business: "财经",
    general: "时事", health: "健康", entertainment: "娱乐"
  },

  renderNewsCategories: function() {
    var container = document.getElementById("newsCategoryTags");
    if (!container) return;
    var selected = SettingsPage._newsCategories || ['technology', 'science'];
    container.innerHTML = "";
    SettingsPage.newsCategories.forEach(function(cat) {
      var tag = document.createElement("span");
      tag.className = "template-btn";
      tag.style.cssText = "flex:0 0 auto;padding:6px 14px;font-size:12px;";
      tag.textContent = SettingsPage.newsCategoryLabels[cat] || cat;
      if (selected.indexOf(cat) >= 0) tag.classList.add("active");
      tag.onclick = function() {
        tag.classList.toggle("active");
        SettingsPage.saveNewsCategories();
      };
      container.appendChild(tag);
    });
  },

  async saveNewsCategories() {
    var tags = document.querySelectorAll("#newsCategoryTags .template-btn.active");
    var selected = [];
    var self = this;
    tags.forEach(function(t) {
      for (var i = 0; i < self.newsCategories.length; i++) {
        if (t.textContent === (self.newsCategoryLabels[self.newsCategories[i]] || self.newsCategories[i])) {
          selected.push(self.newsCategories[i]);
          break;
        }
      }
    });
    this._newsCategories = selected;
    var settings = this._collectSettings();
    settings.template = this._currentTemplate;
    try {
      var resp = await fetch('/api/config/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(settings)
      });
      var data = await resp.json();
      if (data.ok) this.showMsg('新闻类别已保存', 'ok');
    } catch(e) {
      this.showMsg('保存失败: ' + e.message, 'err');
    }
  },

  // ── Unlimited toggle ──

  toggleUnlimited(key) {
    var checked = getCheck('cfg_' + key + '_unlimited');
    toggleUI(key, checked);
    this._markCustom();
  },

  // ── Status ──

  refreshStatus() {
    document.getElementById('apiStatus').textContent = App.apiConfigured ? 'AI就绪' : 'Key未设';
    document.getElementById('apiStatus').style.color = App.apiConfigured ? 'var(--green)' : 'var(--red)';
    document.getElementById('serverStatus').textContent = App.serverOnline ? '在线' : '离线';
    document.getElementById('serverStatus').style.color = App.serverOnline ? 'var(--green)' : 'var(--red)';
    document.getElementById('serverUrl').textContent = App.serverUrl;
    document.getElementById('activeModel').textContent =
      (App.modelConfig.active_model || '-') + ' (' + (App.modelConfig.active_provider || '-') + ')';
  },

  // ── API Key ──

  async saveKey() {
    var key = document.getElementById('apiKeyInput').value.trim();
    if (!key) { this.showMsg('请输入 API Key', 'warn'); return; }
    try {
      var resp = await fetch('/api/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: key })
      });
      var data = await resp.json();
      if (data.ok) {
        this.showMsg('API Key 已保存', 'ok');
        App.apiConfigured = true;
        this.refreshStatus();
      } else {
        this.showMsg('保存失败: ' + (data.error || '未知错误'), 'err');
      }
    } catch(e) {
      this.showMsg('服务器离线，无法保存', 'err');
    }
  },

  // ── Data Export ──

  async exportAll() {
    var exportData = {};
    try {
      var resp = await fetch('/api/progress/dashboard');
      exportData.progress = await resp.json();
    } catch(e) { exportData.progress = { error: '不可用' }; }

    try { exportData.trainer_cache = JSON.parse(localStorage.getItem('trainer_data') || 'null'); } catch(e) { exportData.trainer_cache = null; }
    try { exportData.interview_history = JSON.parse(localStorage.getItem('interview_history') || '[]'); } catch(e) { exportData.interview_history = []; }
    try { exportData.error_notebook = JSON.parse(localStorage.getItem('error_notebook') || '[]'); } catch(e) { exportData.error_notebook = []; }

    var blob = new Blob([JSON.stringify(exportData, null, 2)], { type: 'application/json' });
    var url = URL.createObjectURL(blob);
    var a = document.createElement('a');
    a.href = url; a.download = 'portfolio-backup-' + new Date().toISOString().slice(0, 10) + '.json';
    a.click();
    URL.revokeObjectURL(url);
    this.showMsg('数据已导出', 'ok');
  },

  // ── Data Import ──

  importData() {
    var input = document.createElement('input');
    input.type = 'file'; input.accept = '.json';
    input.onchange = function(e) {
      var file = e.target.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function(ev) {
        try {
          var imported = JSON.parse(ev.target.result);
          var count = 0;
          if (imported.trainer_cache) { localStorage.setItem('trainer_data', JSON.stringify(imported.trainer_cache)); count++; }
          if (imported.interview_history) { localStorage.setItem('interview_history', JSON.stringify(imported.interview_history)); count++; }
          if (imported.error_notebook) { localStorage.setItem('error_notebook', JSON.stringify(imported.error_notebook)); count++; }
          SettingsPage.showMsg('已恢复 ' + count + ' 项数据到本地缓存', 'ok');
          SettingsPage.loadStorageInfo();
        } catch(err) {
          SettingsPage.showMsg('导入失败: 文件格式错误', 'err');
        }
      };
      reader.readAsText(file);
    };
    input.click();
  },

  // ── Cache Management ──

  clearCache() {
    if (!confirm('确定清除所有本地缓存？这不会影响服务器端的进度数据。')) return;
    ['trainer_data', 'error_notebook', 'interview_history', 'knowledge_read'].forEach(function(k) {
      localStorage.removeItem(k);
    });
    this.loadStorageInfo();
    this.showMsg('缓存已清除', 'ok');
  },

  loadStorageInfo() {
    var total = 0;
    var items = [];
    try {
      ['trainer_data', 'error_notebook', 'interview_history', 'knowledge_read'].forEach(function(k) {
        var val = localStorage.getItem(k);
        if (val) {
          var size = new Blob([val]).size;
          total += size;
          var parsed = JSON.parse(val);
          var count = Array.isArray(parsed) ? parsed.length : (parsed && typeof parsed === 'object' ? Object.keys(parsed).length : 1);
          items.push({ key: k, count: count, size: (size / 1024).toFixed(1) });
        }
      });
    } catch(e) { /* ignore */ }
    document.getElementById('cacheSize').textContent = (total / 1024).toFixed(1) + ' KB';
    var html = items.map(function(it) {
      return '<div style="font-size:11px;padding:2px 0;color:var(--text2)">' +
        '<span style="color:var(--text)">' + it.key + '</span> — ' + it.count + ' 项, ' + it.size + ' KB</div>';
    }).join('');
    document.getElementById('cacheDetails').innerHTML = html || '<div style="font-size:11px;color:var(--text2)">无缓存数据</div>';
  },

  // ── Feedback ──

  showMsg(msg, type) {
    var el = document.getElementById('settingsMsg');
    var colors = { ok: 'var(--green)', warn: '#d97706', err: 'var(--red)' };
    el.innerHTML = '<span style="color:' + (colors[type] || colors.ok) + '">' + App.escapeHtml(msg) + '</span>';
    setTimeout(function() { el.innerHTML = ''; }, 4000);
  }
};

// ── Helpers ──

function getVal(id) {
  var el = document.getElementById(id);
  return el ? el.value : '';
}

function setVal(id, val) {
  var el = document.getElementById(id);
  if (el) el.value = val;
}

function getCheck(id) {
  var el = document.getElementById(id);
  return el ? el.checked : false;
}

function setCheck(id, val) {
  var el = document.getElementById(id);
  if (el) el.checked = !!val;
}

function toggleUI(key, unlimited) {
  var select = document.getElementById('cfg_' + key);
  var warn = document.getElementById('warn_' + key);
  if (select) select.disabled = unlimited;
  if (warn) warn.classList.toggle('show', unlimited);
}

App.ready(function() { SettingsPage.init(); });

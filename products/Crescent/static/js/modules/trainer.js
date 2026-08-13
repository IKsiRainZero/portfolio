/**
 * Trainer Module — Shared core: state, init, data loading, tabs, import modal
 * Tab-specific logic in trainer-mcq.js / trainer-code.js / trainer-flash.js / trainer-review.js
 */
const Trainer = {
  // ---- State ----
  tab: 'mcq',
  data: { mcq: [], coding: [], flashcards: [] },
  tempData: { mcq: [], coding: [], flashcards: [] },
  loaded: false,
  topicFilter: { mcq: 'all', code: 'all', flash: 'all' },

  // MCQ state
  mcqIdx: 0, mcqScore: 0, mcqWrong: [], mcqDone: false, mcqAnswered: false,

  // Code state
  codeIdx: 0,

  // Flash state
  flashIdx: 0, flashRatings: [], flashAnswers: {}, flashFlipped: false, flashAiResult: '',

  // Feynman state
  feynmanInited: false,

  // ---- Init ----
  async init() {
    await this.loadData();
    this.setupTabs();
    this.render();
  },

  async loadData() {
    const cached = localStorage.getItem('trainer_data');
    if (cached) {
      try { this.data = JSON.parse(cached); this.loaded = true; } catch(e) { /* stale */ }
    }
    const types = ['mcq', 'coding', 'flashcards'];
    let updated = false;
    for (const t of types) {
      try {
        const resp = await fetch(`/api/exercises/${t}`);
        const json = await resp.json();
        if (json.data && json.data.length) { this.data[t] = json.data; updated = true; }
      } catch(e) { /* use cached */ }
    }
    if (updated) { localStorage.setItem('trainer_data', JSON.stringify(this.data)); this.loaded = true; }
    await this.loadTempData();
  },

  async loadTempData() {
    try {
      const resp = await fetch('/api/exercises/temp');
      const json = await resp.json();
      this.tempData = { mcq: json.mcq || [], coding: json.coding || [], flashcards: json.flashcards || [] };
    } catch(e) { this.tempData = { mcq: [], coding: [], flashcards: [] }; }
  },

  // ---- Topic helpers ----
  getTopics(type) {
    const items = this.data[type] || [];
    const key = type === 'flashcards' ? 'category' : (type === 'coding' ? 'scenario' : 'topic');
    return [...new Set(items.map(i => i[key]).filter(Boolean))].sort();
  },

  getFiltered(type) {
    const filterKey = type === 'flashcards' ? 'flash' : (type === 'coding' ? 'code' : 'mcq');
    const filter = this.topicFilter[filterKey] || 'all';
    const items = this.data[type] || [];
    const tempItems = this.tempData[type] || [];
    if (filter === 'temp') return tempItems;
    if (!filter || filter === 'all') return items;
    const key = type === 'flashcards' ? 'category' : (type === 'coding' ? 'scenario' : 'topic');
    return items.filter(i => i[key] === filter);
  },

  hasTempItems() {
    return ['mcq', 'coding', 'flashcards'].some(t => (this.tempData[t] || []).length > 0);
  },

  totalTempCount() {
    return ['mcq', 'coding', 'flashcards'].reduce((sum, t) => sum + (this.tempData[t] || []).length, 0);
  },

  renderTopicFilter(type) {
    const topics = this.getTopics(type);
    const filterKey = type === 'flashcards' ? 'flash' : (type === 'coding' ? 'code' : 'mcq');
    const current = this.topicFilter[filterKey] || 'all';
    const tempCount = (this.tempData[type] || []).length;
    let opts = `<option value="all" ${current==='all'?'selected':''}>全部 (${this.data[type].length})</option>`;
    if (tempCount > 0) opts += `<option value="temp" ${current==='temp'?'selected':''}>临时训练 (${tempCount})</option>`;
    opts += topics.map(t => {
      const count = this.data[type].filter(i => (i.topic||i.scenario||i.category) === t).length;
      return `<option value="${App.escapeHtml(t)}" ${current===t?'selected':''}>${App.escapeHtml(t)} (${count})</option>`;
    }).join('');
    if (topics.length <= 1 && tempCount === 0) return '';
    return `<div style="margin-bottom:12px;display:flex;align-items:center;gap:8px">
      <label style="font-size:11px;color:var(--text2);white-space:nowrap">知识点筛选:</label>
      <select onchange="Trainer.setTopicFilter('${filterKey}',this.value)" style="font-size:11px;padding:4px 8px;border:1px solid var(--border);border-radius:6px;background:white;max-width:200px">${opts}</select>
    </div>`;
  },

  setTopicFilter(key, value) {
    this.topicFilter[key] = value;
    if (key === 'mcq') { this.mcqIdx = 0; this.mcqScore = 0; this.mcqWrong = []; this.mcqDone = false; this.mcqAnswered = false; }
    if (key === 'code') this.codeIdx = 0;
    if (key === 'flash') { this.flashIdx = 0; this.flashRatings = []; this.flashAnswers = {}; this.flashFlipped = false; this.flashAiResult = ''; }
    this.render();
  },

  // ---- Import Modal ----
  showImportModal() {
    document.getElementById('importModal').style.display = 'flex';
    document.getElementById('importText').value = '';
    document.getElementById('importFeedback').innerHTML = '';
    document.getElementById('btnImportSubmit').disabled = false;
  },

  closeImportModal() { document.getElementById('importModal').style.display = 'none'; },

  async submitImport() {
    const textarea = document.getElementById('importText');
    const fb = document.getElementById('importFeedback');
    const btn = document.getElementById('btnImportSubmit');
    const text = textarea.value.trim();
    if (text.length < 20) { fb.innerHTML = '<span style="color:var(--red)">文本太短，请至少输入20个字符</span>'; return; }
    btn.disabled = true; btn.textContent = 'AI 生成中...';
    fb.innerHTML = '<span style="color:var(--text2)">正在调用 AI 提取知识点并生成题目，可能需要 30-60 秒...</span>';
    try {
      const resp = await fetch('/api/ai/import-knowledge', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text })
      });
      const data = await resp.json();
      if (data.error) { fb.innerHTML = `<span style="color:var(--red)">导入失败: ${App.escapeHtml(data.error)}</span>`; btn.disabled = false; btn.textContent = 'AI 生成题目'; return; }
      if (data.ok) {
        fb.innerHTML = `<span style="color:var(--green)">生成成功！知识点 ${data.knowledge_count} 个，选择题 ${data.exercises_count.mcq} 道，编程题 ${data.exercises_count.coding} 道，闪卡 ${data.exercises_count.flashcards} 张。临时训练区共 ${data.total_temp} 道题。</span>`;
        await this.loadTempData(); this.updateTabLabels(); this.render();
      }
    } catch (e) { fb.innerHTML = `<span style="color:var(--red)">请求失败: ${e.message}</span>`; }
    btn.disabled = false; btn.textContent = 'AI 生成题目';
  },

  // ---- Temp Classification ----
  renderTempActions() {
    if (!this.hasTempItems()) return '';
    const filterKey = this.tab === 'flash' ? 'flash' : (this.tab === 'code' ? 'code' : 'mcq');
    if (this.topicFilter[filterKey] !== 'temp') return '';
    return `<div class="card" style="margin-bottom:12px;background:#fffbeb;border:1px solid #fcd34d">
      <div style="display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px">
        <span style="font-size:12px;color:#92400e">临时训练区 — AI 生成的题目，请在练习后确认保留或清除</span>
        <div style="display:flex;gap:6px">
          <button class="btn btn-sm btn-primary" onclick="Trainer.classifyTemp()">分类入库</button>
          <button class="btn btn-sm" onclick="Trainer.clearTemp()" style="background:#fee2e2;color:#991b1b">全部清除</button>
        </div>
      </div>
    </div>`;
  },

  async classifyTemp() {
    if (!confirm('将临时训练区的所有题目分类写入正式题库？此操作不可撤销。')) return;
    try {
      const resp = await fetch('/api/exercises/temp/classify', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ keep_ids: {} }) });
      const data = await resp.json();
      if (data.ok) {
        alert(`分类完成！已入库: 选择题${data.moved.mcq}道, 编程题${data.moved.coding}道, 闪卡${data.moved.flashcards}张`);
        this.tempData = { mcq: [], coding: [], flashcards: [] };
        this.topicFilter = { mcq: 'all', code: 'all', flash: 'all' };
        await this.loadData(); this.updateTabLabels(); this.render();
      }
    } catch (e) { alert('分类失败: ' + e.message); }
  },

  async clearTemp() {
    if (!confirm('确定清空所有临时训练题目？此操作不可撤销。')) return;
    try {
      await fetch('/api/exercises/temp/clear', { method: 'POST' });
      this.tempData = { mcq: [], coding: [], flashcards: [] };
      this.topicFilter = { mcq: 'all', code: 'all', flash: 'all' };
      this.updateTabLabels(); this.render();
    } catch (e) { alert('清除失败: ' + e.message); }
  },

  // ---- Tabs ----
  setupTabs() {
    document.querySelectorAll('#trainerTabs .tab-btn').forEach(btn => {
      btn.addEventListener('click', () => this.switchTab(btn.dataset.tab));
    });
  },

  switchTab(tab) {
    this.tab = tab;
    document.querySelectorAll('#trainerTabs .tab-btn').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
    if (tab === 'mcq') { this.mcqIdx = 0; this.mcqScore = 0; this.mcqWrong = []; this.mcqDone = false; this.mcqAnswered = false; }
    if (tab === 'code') this.codeIdx = 0;
    if (tab === 'flash') { this.flashIdx = 0; this.flashRatings = []; this.flashAnswers = {}; this.flashFlipped = false; this.flashAiResult = ''; }
    if (tab === 'short') { this.shortIdx = 0; this.shortAnswers = {}; this.shortResults = []; }
    if (tab === 'feynman') {
      document.getElementById('trainerContent').style.display = 'none';
      document.getElementById('trainerFeynman').style.display = '';
      if (!this.feynmanInited) { FeynmanCoach.init(); this.feynmanInited = true; }
    } else {
      document.getElementById('trainerContent').style.display = '';
      document.getElementById('trainerFeynman').style.display = 'none';
    }
    this.updateTabLabels(); this.render();
  },

  updateTabLabels() {
    const tempM = (this.tempData.mcq || []).length;
    const tempC = (this.tempData.coding || []).length;
    const tempF = (this.tempData.flashcards || []).length;
    const labels = {
      mcq: `选择题 (${this.data.mcq.length}${tempM ? '+' + tempM : ''})`,
      code: `编程实战 (${this.data.coding.length}${tempC ? '+' + tempC : ''})`,
      flash: `闪卡 (${this.data.flashcards.length}${tempF ? '+' + tempF : ''})`,
      short: '简答题',
      review: '复习清单',
      feynman: '费曼教练'
    };
    document.querySelectorAll('#trainerTabs .tab-btn').forEach(btn => {
      const t = btn.dataset.tab;
      btn.textContent = labels[t] || btn.textContent;
    });
  },

  render() {
    const c = document.getElementById('trainerContent');
    if (!c) return;
    switch(this.tab) {
      case 'mcq': this.renderMCQ(c); break;
      case 'code': this.renderCode(c); break;
      case 'flash': this.renderFlash(c); break;
      case 'short': this.renderShort(c); break;
      case 'review': this.renderReview(c); break;
      case 'feynman': break; // feynman has its own container, no-op
    }
  }
};

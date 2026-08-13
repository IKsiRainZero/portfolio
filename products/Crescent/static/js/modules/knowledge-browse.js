/**
 * Knowledge Browser — domain loading, filtering, rendering
 * + Reading progress, fable stories, related concepts
 * Depends on: App (app.js)
 */
var currentItems = [];
var currentSetId = '';

// ── Reading progress ──

function getReadItems() {
  try { return JSON.parse(localStorage.getItem('knowledge_read') || '[]'); }
  catch(e) { return []; }
}

function markAsRead(itemId) {
  var read = getReadItems();
  if (read.indexOf(itemId) === -1) {
    read.push(itemId);
    localStorage.setItem('knowledge_read', JSON.stringify(read));
    updateReadingProgress();
  }
}

function updateReadingProgress() {
  var read = getReadItems();
  var total = currentItems.length;
  if (!total) { document.getElementById('readingProgress').style.display = 'none'; return; }
  var readInSet = currentItems.filter(function(it) {
    return read.indexOf(it.id || it.question || it.title) !== -1;
  }).length;
  document.getElementById('readingProgress').style.display = 'block';
  document.getElementById('readingProgressText').textContent = readInSet + '/' + total;
  document.getElementById('readingProgressFill').style.width = (readInSet / total * 100) + '%';
}

// ── Domain loading ──

async function loadDomains() {
  try {
    var resp = await fetch('/api/knowledge/sets');
    var data = await resp.json();
    var sel = document.getElementById('domainSelect');
    if (!sel) return;
    data.sets.forEach(function(s) {
      var opt = document.createElement('option');
      opt.value = s.id;
      opt.textContent = s.display_name || s.id;
      sel.appendChild(opt);
    });
  } catch(e) { /* API not available yet */ }
}

async function loadKnowledgeSet(id) {
  if (!id) return;
  currentSetId = id;
  try {
    var resp = await fetch('/api/knowledge/' + id);
    var data = await resp.json();
    currentItems = data.items || [];
    // Ensure each item has an id for tracking
    currentItems.forEach(function(it, i) {
      if (!it.id) it.id = id + '-' + i;
    });
    renderItems(currentItems);
    updateReadingProgress();
  } catch(e) {
    document.getElementById('knowledgeContent').innerHTML = '<div class="empty-state"><h3>加载失败</h3><p>'+App.escapeHtml(e.message)+'</p></div>';
  }
}

// ── Search history ──

function getSearchHistory() {
  try { return JSON.parse(localStorage.getItem('knowledge_search_history') || '[]'); }
  catch(e) { return []; }
}

function addSearchRecord(query, domain) {
  if (!query || !query.trim()) return;
  var history = getSearchHistory();
  history.unshift({ query: query.trim(), timestamp: Date.now(), domain: domain || currentSetId || '' });
  if (history.length > 100) history = history.slice(0, 100);
  localStorage.setItem('knowledge_search_history', JSON.stringify(history));
}

function getHotSearches(limit) {
  limit = limit || 10;
  var history = getSearchHistory();
  var freq = {};
  history.forEach(function(h) {
    var k = h.query.toLowerCase();
    freq[k] = (freq[k] || 0) + 1;
  });
  return Object.entries(freq)
    .sort(function(a, b) { return b[1] - a[1]; })
    .slice(0, limit)
    .map(function(e) { return { query: e[0], count: e[1] }; });
}

function getRecentDomains(limit) {
  limit = limit || 5;
  var history = getSearchHistory();
  var seen = [];
  var domains = [];
  history.forEach(function(h) {
    if (h.domain && seen.indexOf(h.domain) === -1) {
      seen.push(h.domain);
      domains.push(h.domain);
    }
  });
  return domains.slice(0, limit);
}

function filterKnowledge() {
  var q = document.getElementById('knowledgeSearch').value.toLowerCase();
  if (q) addSearchRecord(q);
  var filtered = q ? currentItems.filter(function(item) {
    return (item.title||'').toLowerCase().indexOf(q) !== -1 ||
      (item.question||'').toLowerCase().indexOf(q) !== -1 ||
      (item.answer||'').toLowerCase().indexOf(q) !== -1 ||
      (item.content||'').toLowerCase().indexOf(q) !== -1;
  }) : currentItems;
  renderItems(filtered);
}

// ── Rendering ──

function renderItems(items) {
  var c = document.getElementById('knowledgeContent');
  if (!items.length) { c.innerHTML = '<div class="empty-state"><h3>无匹配结果</h3></div>'; return; }
  var sections = {};
  items.forEach(function(item) {
    var sec = item.section || '其他';
    if (!sections[sec]) sections[sec] = [];
    sections[sec].push(item);
  });
  c.innerHTML = Object.keys(sections).map(function(sec) {
    var secItems = sections[sec];
    return '<div class="card">' +
      '<div class="card-header">' + App.escapeHtml(sec) + ' <span class="badge badge-topic">' + secItems.length + ' 项</span></div>' +
      secItems.map(function(item) { return renderItem(item); }).join('') +
    '</div>';
  }).join('');

  // Attach expand listeners for reading progress
  document.querySelectorAll('details.read-track').forEach(function(el) {
    el.addEventListener('toggle', function() {
      if (el.open) markAsRead(el.dataset.itemId);
    });
  });
}

function renderItem(item) {
  var itemId = App.escapeHtml(item.id || item.question || item.title || '');
  var fableBtn = '<button class="btn btn-sm" style="font-size:10px;padding:2px 6px;margin-left:4px" onclick="tellFable(\'' + itemId + '\', this)" title="用寓言故事解释这个概念">听故事</button>';

  // Find related items (same section or shared keywords)
  var relatedHtml = renderRelated(item);

  switch(item.type) {
    case 'qa':
      return '<details class="read-track" data-item-id="' + itemId + '" style="margin:6px 0;padding:8px 12px;background:var(--bg);border-radius:6px">' +
        '<summary style="cursor:pointer;font-size:13px;font-weight:500">Q: ' + App.escapeHtml(item.question||'') + '</summary>' +
        '<p style="margin-top:8px;font-size:12px;color:var(--text2);white-space:pre-line">' + App.escapeHtml(item.answer||'') + '</p>' +
        '<div style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap">' +
          '<button class="btn btn-sm" onclick="expandKnowledge(event,\'' + itemId + '\')">展开</button>' +
          '<button class="btn btn-sm" onclick="App.askAI('" + App.escapeHtml((item.question||'').slice(0,60)) + "','" + App.escapeHtml((item.answer||'').slice(0,150)) + "')">问AI</button>' +
          fableBtn +
        '</div>' +
        '<div class="fable-result" id="fable-' + itemId + '" style="margin-top:8px"></div>' +
        relatedHtml +
      '</details>';

    case 'concept':
      return '<div class="read-track" data-item-id="' + itemId + '" style="margin:6px 0;padding:10px 14px;background:var(--accent-subtle);border-radius:6px" data-observe="true">' +
        '<strong style="font-size:13px">' + App.escapeHtml(item.title||'') + '</strong>' +
        '<p style="font-size:12px;color:var(--text2);margin-top:4px;white-space:pre-line">' + App.escapeHtml(item.content||'') + '</p>' +
        '<div style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap">' +
          '<button class="btn btn-sm" onclick="expandKnowledge(event,\'' + itemId + '\')">展开</button>' +
          '<button class="btn btn-sm" onclick="App.askAI(\'' + App.escapeHtml((item.title||'').slice(0,60)) + '\',\'' + App.escapeHtml((item.content||'').slice(0,150)) + '\')">问AI</button>' +
          fableBtn +
        '</div>' +
        '<div class="fable-result" id="fable-' + itemId + '" style="margin-top:8px"></div>' +
        relatedHtml +
      '</div>';

    case 'table':
      return '<table style="width:100%;font-size:12px;border-collapse:collapse;margin:8px 0">' +
        (item.headers ? '<tr>' + item.headers.map(function(h) { return '<th style="text-align:left;padding:6px 8px;border-bottom:2px solid var(--border)">' + App.escapeHtml(h) + '</th>'; }).join('') + '</tr>' : '') +
        (item.rows||[]).map(function(row) { return '<tr>' + row.map(function(c) { return '<td style="padding:6px 8px;border-bottom:1px solid var(--border)">' + App.escapeHtml(String(c)) + '</td>'; }).join('') + '</tr>'; }).join('') +
      '</table>';

    case 'code':
      return '<pre style="background:#1e293b;color:#e2e8f0;padding:12px;border-radius:6px;font-size:12px;overflow-x:auto;margin:8px 0">' + App.escapeHtml(item.code||'') + '</pre>' +
        (item.explanation ? '<p style="font-size:11px;color:var(--text2)">' + App.escapeHtml(item.explanation) + '</p>' : '');

    default:
      return '';
  }
}

// ── Expand knowledge item ──

function expandKnowledge(event, itemId) {
  if (event) event.stopPropagation();
  var item = currentItems.find(function(it) {
    return (it.id || it.question || it.title) === itemId;
  });
  if (!item) return;
  var title = App.escapeHtml(item.question || item.title || '');
  var body = App.escapeHtml(item.answer || item.content || '');
  var overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = '<div class="modal" style="max-width:600px;max-height:80vh;overflow-y:auto">' +
    '<h2>' + title + '</h2>' +
    '<div style="font-size:13px;line-height:1.7;white-space:pre-line">' + body + '</div>' +
    '<button class="btn btn-sm" style="margin-top:12px" onclick="this.closest(\'.modal-overlay\').remove()">关闭</button>' +
  '</div>';
  overlay.addEventListener('click', function(e) { if (e.target === overlay) overlay.remove(); });
  document.body.appendChild(overlay);
}

// ── Fable/story generation ──

async function tellFable(itemId, btn) {
  var item = currentItems.find(function(it) {
    return (it.id || it.question || it.title) === itemId;
  });
  if (!item) return;
  var concept = item.question || item.title || item.concept || '';
  var context = item.answer || item.content || '';
  var fbDiv = document.getElementById('fable-' + itemId);
  if (!fbDiv) return;
  if (fbDiv.innerHTML) { fbDiv.innerHTML = ''; return; } // toggle off

  fbDiv.innerHTML = '<span class="thinking-dots">生成故事中<span>.</span><span>.</span><span>.</span></span>';
  if (btn) btn.textContent = '生成中...';

  var prompt = '请用寓言/童话/生活故事的形式解释概念：「' + concept + '」。\n' +
    '背景: ' + context.slice(0, 300) + '\n\n' +
    '要求:\n1. 用200字以内的小故事或日常类比\n' +
    '2. 故事要自然有趣，不要直接说教\n' +
    '3. 故事结束后用一句话点明与概念的联系\n' +
    '4. 用中文';

  try {
    var resp = await fetch(App.serverUrl + '/api/agent/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: prompt, session_id: 'knowledge_fable' })
    });
    var data = await resp.json();
    if (data.error) {
      fbDiv.innerHTML = '<div class="feedback-box feedback-wrong" style="font-size:11px">' + App.escapeHtml(data.error) + '</div>';
    } else {
      fbDiv.innerHTML = '<div class="feedback-box feedback-info" style="font-size:11px;white-space:pre-line;margin-top:6px">' +
        App.escapeHtml(data.reply || '').replace(/\n/g, '<br>') + '</div>';
    }
  } catch(e) {
    fbDiv.innerHTML = '<div class="feedback-box feedback-wrong" style="font-size:11px">请求失败</div>';
  }
  if (btn) btn.textContent = '听故事';
}

// ── Related concepts ──

function renderRelated(item) {
  if (currentItems.length < 2) return '';
  var concept = item.question || item.title || '';
  if (!concept || concept.length < 3) return '';

  // Find items with overlapping keywords in the same set
  var keywords = concept.toLowerCase().split(/[\s,，、。？?！!：:]+/).filter(function(w) { return w.length >= 2; });
  if (!keywords.length) return '';

  var related = currentItems.filter(function(other) {
    if (other === item) return false;
    var otherText = (other.question || other.title || '').toLowerCase();
    return keywords.some(function(kw) { return otherText.indexOf(kw) !== -1; });
  }).slice(0, 3);

  if (!related.length) return '';

  return '<div style="margin-top:8px;font-size:10px;color:var(--text2)">' +
    '<span>相关: </span>' +
    related.map(function(r) {
      var name = (r.question || r.title || '').slice(0, 30);
      return '<a href="#" style="color:var(--accent);margin-right:8px;text-decoration:none" onclick="App.askAI(\'' +
        App.escapeHtml(name) + '\',\'\');return false">' + App.escapeHtml(name) + '</a>';
    }).join('') +
  '</div>';
}

// ── Intersection Observer for reading progress ──
if (typeof IntersectionObserver !== 'undefined') {
  var readObserver = new IntersectionObserver(function(entries) {
    entries.forEach(function(entry) {
      if (entry.isIntersecting) {
        var id = entry.target.dataset.itemId;
        if (id) markAsRead(id);
      }
    });
  }, { threshold: 0.5 });

  // Observe concept cards after render (done in renderItems for details)
  setTimeout(function() {
    document.querySelectorAll('[data-observe="true"]').forEach(function(el) {
      readObserver.observe(el);
    });
  }, 200);
}

// ── Agent 智能检索 ──

async function knowledgeAgentSearch() {
  var input = document.getElementById('agentSearchInput');
  var result = document.getElementById('agentSearchResult');
  var btn = document.getElementById('btnAgentSearch');
  var query = input.value.trim();
  if (!query) return;

  if (!App.serverOnline) { result.innerHTML = '<div class="feedback-box feedback-wrong">服务器未连接</div>'; return; }
  if (!App.apiConfigured) { result.innerHTML = '<div class="feedback-box feedback-wrong">请先配置 API Key</div>'; return; }

  btn.disabled = true; btn.textContent = '搜索中...';
  result.innerHTML = '<span class="thinking-dots">搜索中<span>.</span><span>.</span><span>.</span></span>';

  try {
    var resp = await fetch(App.serverUrl + '/api/agent/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: query, session_id: 'knowledge' })
    });
    var data = await resp.json();
    if (data.error) {
      result.innerHTML = '<div class="feedback-box feedback-wrong">' + App.escapeHtml(data.error) + '</div>';
    } else {
      var html = '<div style="white-space:pre-line;margin-bottom:8px">' + App.escapeHtml(data.reply).replace(/\n/g, '<br>') + '</div>';
      if (data.steps && data.steps.length > 0) {
        html += '<details style="font-size:11px;margin-top:6px"><summary style="cursor:pointer;color:var(--text2)">查看检索过程</summary>';
        data.steps.forEach(function(s) {
          html += '<div style="margin:2px 0;padding:2px 6px;background:var(--bg);border-radius:3px;font-size:10px;color:var(--text2)">' + (s.phase==='action'?'调用':'结果') + ': ' + App.escapeHtml(s.tool||'') + '</div>';
        });
        html += '</details>';
      }
      result.innerHTML = html;
    }
  } catch(e) {
    result.innerHTML = '<div class="feedback-box feedback-wrong">请求失败: ' + App.escapeHtml(e.message) + '</div>';
  }
  btn.disabled = false; btn.textContent = '搜索';
}

App.ready(loadDomains);

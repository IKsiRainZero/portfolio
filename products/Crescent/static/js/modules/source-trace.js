/**
 * 来源追溯 — 6 步管道 SSE 流式展示
 */
const SourceTrace = {
  _es: null,

  start() {
    const input = document.getElementById('stInput').value.trim();
    if (!input) return;

    document.getElementById('stResults').style.display = 'block';
    document.getElementById('stCards').innerHTML = '';
    document.getElementById('stStartBtn').disabled = true;
    document.getElementById('stStatus').textContent = '追溯中...';

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
      card.innerHTML =
        `<div class="st-card-header" onclick="SourceTrace.toggleCard(${s.id})">
          <span class="st-step-num">${s.id}</span>
          <span class="st-step-name">${s.name}</span>
          <span class="st-step-status" id="stStatus${s.id}"></span>
          <span class="st-caret">&#9656;</span>
        </div>
        <div class="st-card-body" id="stBody${s.id}" style="display:none;"></div>`;
      container.appendChild(card);
    });

    this._fetchSSE(input);
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
        buf = lines.pop();

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));
              this._handleEvent(data);
            } catch (e) { /* skip malformed */ }
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
    if (!step) return;

    const statusEl = document.getElementById(`stStatus${step}`);
    if (statusEl) {
      statusEl.textContent = status === 'running' ? '⏳' : '✅';
      statusEl.style.color = status === 'running' ? 'var(--accent)' : '#22c55e';
    }

    const bodyEl = document.getElementById(`stBody${step}`);
    if (bodyEl && content) {
      bodyEl.style.display = 'block';
      bodyEl.innerHTML = this._renderDetail(step, detail || {}, content);
      const card = document.getElementById(`stCard${step}`);
      const caret = card ? card.querySelector('.st-caret') : null;
      if (caret) caret.style.transform = 'rotate(90deg)';
    }

    const card = document.getElementById(`stCard${step}`);
    if (card) {
      if (status === 'running') {
        card.style.boxShadow = '0 0 0 2px var(--accent)';
      } else if (status === 'done') {
        card.style.boxShadow = '';
      }
    }
  },

  _renderDetail(step, detail, summary) {
    let html = '<p style="margin-bottom:8px;">' + App.escapeHtml(summary) + '</p>';

    if (step === 1 && detail.keywords) {
      html += '<div class="tags">' + detail.keywords.map(function(k) {
        return '<span class="badge" style="margin:2px;">' + App.escapeHtml(k) + '</span>';
      }).join('') + '</div>';
    }

    if (step === 2 && detail.sources) {
      html += '<ul style="font-size:13px;">';
      detail.sources.forEach(function(s) {
        if (s.url) {
          html += '<li><a href="' + App.escapeHtml(s.url) + '" target="_blank" rel="noopener">' + App.escapeHtml(s.title || s.url) + '</a>';
          if (s.snippet) html += '<br><small style="color:var(--text2)">' + App.escapeHtml(s.snippet.substring(0, 150)) + '</small>';
          if (s.status === 'failed') html += ' <span class="badge" style="background:#ef4444;">抓取失败</span>';
          html += '</li>';
        }
      });
      html += '</ul>';
    }

    if (step === 4 && detail.timeline) {
      html += '<ol style="font-size:13px;">';
      detail.timeline.forEach(function(t) {
        html += '<li><a href="' + App.escapeHtml(t.url) + '" target="_blank" rel="noopener">' + App.escapeHtml(t.title || t.url) + '</a></li>';
      });
      html += '</ol>';
      if (detail.note) html += '<p style="color:var(--text2);font-size:12px;margin-top:4px;">' + App.escapeHtml(detail.note) + '</p>';
    }

    if (step === 5 && detail.diffs_raw) {
      html += '<div style="white-space:pre-wrap;font-size:13px;background:var(--bg2);padding:8px;border-radius:6px;">' + App.escapeHtml(detail.diffs_raw) + '</div>';
      if (detail.note) html += '<p style="color:var(--text2);font-size:12px;margin-top:4px;">' + App.escapeHtml(detail.note) + '</p>';
    }

    if (step === 6 && detail.determined) {
      html += '<h4 style="margin-bottom:4px;">确定的部分</h4><ul style="font-size:13px;">';
      detail.determined.forEach(function(d) { html += '<li>' + App.escapeHtml(d) + '</li>'; });
      html += '</ul>';
      html += '<h4 style="margin-bottom:4px;margin-top:12px;">不确定的部分</h4><ul style="font-size:13px;">';
      detail.uncertain.forEach(function(u) { html += '<li style="color:var(--text2)">' + App.escapeHtml(u) + '</li>'; });
      html += '</ul>';
      if (detail.source_links && detail.source_links.length) {
        html += '<h4 style="margin-bottom:4px;margin-top:12px;">所有来源链接</h4><ul style="font-size:13px;">';
        detail.source_links.forEach(function(s) {
          html += '<li><a href="' + App.escapeHtml(s.url) + '" target="_blank" rel="noopener">' + App.escapeHtml(s.title || s.url) + '</a></li>';
        });
        html += '</ul>';
      }
    }

    return html;
  },

  toggleCard(id) {
    const body = document.getElementById('stBody' + id);
    const card = document.getElementById('stCard' + id);
    if (!body || !card) return;
    const caret = card.querySelector('.st-caret');
    if (body.style.display === 'none') {
      body.style.display = 'block';
      if (caret) caret.style.transform = 'rotate(90deg)';
    } else {
      body.style.display = 'none';
      if (caret) caret.style.transform = 'rotate(0deg)';
    }
  },
};

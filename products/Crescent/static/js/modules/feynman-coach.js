/**
 * Feynman Coach Module — explain→evaluate→revise loop
 * Depends on: App (app.js)
 */
const FeynmanCoach = {
  state: {
    concept: '',
    sessionId: '',
    round: 0,
    history: []
  },

  async init() {
    try {
      const resp = await fetch('/api/knowledge/sets');
      const data = await resp.json();
      if (data.sets && data.sets.length) {
        const sel = document.getElementById('feynmanConcept');
        data.sets.forEach(function(s) {
          const opt = document.createElement('option');
          opt.value = s.id;
          opt.textContent = s.display_name || s.id;
          sel.appendChild(opt);
        });
      }
    } catch(e) { /* non-critical */ }
  },

  startCheck() {
    var domainEl = document.getElementById('feynmanConcept');
    var customEl = document.getElementById('feynmanCustomConcept');
    var concept = customEl.value.trim() || (domainEl.value || '');

    if (!concept) {
      alert('请选择一个概念或手动输入概念名称');
      return;
    }

    this.state = {
      concept: concept,
      sessionId: 'feynman_' + Date.now(),
      round: 0,
      history: []
    };

    document.getElementById('feynmanAttemptCount').textContent = '';
    document.getElementById('feynmanExplanation').value = '';
    document.getElementById('feynmanFeedback').innerHTML = '';
    document.getElementById('feynmanResult').style.display = 'none';
    document.getElementById('feynmanHistory').innerHTML = '';
    document.getElementById('btnSubmitFeynman').disabled = false;
    document.getElementById('btnStartFeynman').disabled = true;
    document.getElementById('feynmanExplanation').focus();
  },

  async submitExplanation() {
    var explanation = document.getElementById('feynmanExplanation').value.trim();
    if (explanation.length < 20) {
      document.getElementById('feynmanFeedback').innerHTML =
        App.renderFeedback('wrong', '解释太短，请至少输入20个字符');
      return;
    }

    this.state.round++;
    document.getElementById('feynmanAttemptCount').textContent =
      '第 ' + this.state.round + ' 轮';
    document.getElementById('btnSubmitFeynman').disabled = true;
    document.getElementById('feynmanFeedback').innerHTML =
      App.renderFeedback('info', App.renderThinking() + ' AI 正在检查你的解释...');

    var prompt = '请用 feynman_check 工具检查我对「' + this.state.concept + '」的解释:\n\n' + explanation +
      '\n\n请严格按照费曼标准评分（简单性、完整性、清晰度、具体性各1-5分），并给出术语检查、遗漏要点、亮点、改进方向和简化版示范。';

    await this.sendToAgent(prompt);
  },

  async submitRevision() {
    var revision = document.getElementById('feynmanRevision').value.trim();
    if (revision.length < 20) {
      document.getElementById('feynmanRevisionFeedback').innerHTML =
        App.renderFeedback('wrong', '修改内容太短，请至少输入20个字符');
      return;
    }

    this.state.round++;
    document.getElementById('feynmanAttemptCount').textContent =
      '第 ' + this.state.round + ' 轮';
    document.getElementById('feynmanRevisionFeedback').innerHTML =
      App.renderFeedback('info', App.renderThinking() + ' AI 正在重新检查...');

    var prompt = '上一轮你指出了问题，我修改了对「' + this.state.concept + '」的解释。请再次用 feynman_check 检查我的新解释:\n\n' + revision;

    await this.sendToAgent(prompt);
  },

  async sendToAgent(message) {
    if (!App.serverOnline || !App.apiConfigured) {
      this.showError('请先配置 API Key 并确保服务器在线');
      return;
    }

    try {
      var resp = await fetch(App.serverUrl + '/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, session_id: this.state.sessionId })
      });
      var data = await resp.json();
      if (data.error) { this.showError(data.error); return; }
      this.handleResult(data.reply || '');
    } catch(e) {
      this.showError('请求失败: ' + e.message);
    }
  },

  handleResult(reply) {
    var s = this.state;
    s.history.push({ round: s.round, reply: reply });

    // Parse score
    var scoreMatch = reply.match(/总分[：:]\s*(\d+)/);
    var score = scoreMatch ? parseInt(scoreMatch[1]) : null;

    document.getElementById('feynmanFeedback').innerHTML = '';

    // Show result panel
    document.getElementById('feynmanResult').style.display = 'block';
    var resultClass = score !== null ? (score >= 7 ? 'feedback-correct' : score >= 4 ? 'feedback-info' : 'feedback-wrong') : 'feedback-info';
    document.getElementById('feynmanResultBody').className = 'card ' + resultClass;
    document.getElementById('feynmanResultBody').style.cssText = 'margin-bottom:12px;white-space:pre-line;font-size:12px';

    var resultHtml = reply.replace(/\n/g, '<br>');

    // Highlight score
    if (score !== null) {
      var scoreLabel = score >= 7 ? '优秀！解释得很好' : score >= 4 ? '还行，还有改进空间' : '需要大幅改进';
      resultHtml = '<div style="font-size:18px;font-weight:700;margin-bottom:8px;color:' +
        (score >= 7 ? 'var(--green)' : score >= 4 ? '#d97706' : 'var(--red)') + '">' +
        score + '/10 — ' + scoreLabel + '</div>' + resultHtml;
    }

    document.getElementById('feynmanResultBody').innerHTML = resultHtml;

    // Reset revision area
    document.getElementById('feynmanRevision').value = '';
    document.getElementById('feynmanRevisionFeedback').innerHTML = '';

    // Re-enable
    document.getElementById('btnSubmitFeynman').disabled = false;

    // Update history display
    this.renderHistory();

    // Record progress
    App.recordProgress({
      type: 'feynman',
      item_id: 'feynman_' + s.concept,
      topic: s.concept,
      score: score,
      rounds: s.round
    });
  },

  renderHistory() {
    var s = this.state;
    if (s.history.length <= 1) return;
    var div = document.getElementById('feynmanHistory');
    div.innerHTML = '<div class="card" style="margin-top:12px"><div class="card-header">解释历史 (' +
      s.history.length + ' 轮)</div>' +
      s.history.map(function(h) {
        var scoreMatch = h.reply.match(/总分[：:]\s*(\d+)/);
        var score = scoreMatch ? parseInt(scoreMatch[1]) : null;
        var color = score !== null ? (score >= 7 ? 'var(--green)' : score >= 4 ? '#d97706' : 'var(--red)') : 'var(--text2)';
        return '<div style="margin-bottom:6px;font-size:11px">' +
          '<strong>第' + h.round + '轮</strong> ' +
          (score !== null ? '<span style="color:' + color + '">' + score + '/10</span>' : '') +
          '</div>';
      }).join('') + '</div>';
  },

  reset() {
    this.state = {
      concept: '',
      sessionId: '',
      round: 0,
      history: []
    };
    document.getElementById('feynmanExplanation').value = '';
    document.getElementById('feynmanFeedback').innerHTML = '';
    document.getElementById('feynmanResult').style.display = 'none';
    document.getElementById('feynmanHistory').innerHTML = '';
    document.getElementById('feynmanAttemptCount').textContent = '';
    document.getElementById('btnSubmitFeynman').disabled = false;
    document.getElementById('btnStartFeynman').disabled = false;
  },

  showError(msg) {
    document.getElementById('feynmanFeedback').innerHTML =
      App.renderFeedback('wrong', msg);
    document.getElementById('btnSubmitFeynman').disabled = false;
  }
};

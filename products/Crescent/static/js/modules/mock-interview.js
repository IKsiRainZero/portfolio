/**
 * Mock Interview Module — Agent-driven adaptive interview
 * Depends on: App (app.js)
 */
const MockInterview = {
  state: {
    qIndex: 0,
    total: 5,
    domains: '',
    jd: '',
    sessionId: '',
    history: [],
    currentQ: '',
    phase: 'setup'    // setup | waiting_q | waiting_fb | report | done
  },

  async init() {
    await this.loadDomains();
    this.loadHistory();
  },

  async loadDomains() {
    try {
      const resp = await fetch('/api/knowledge/sets');
      const data = await resp.json();
      if (data.sets && data.sets.length) {
        const sel = document.getElementById('interviewDomain');
        if (sel) {
          data.sets.forEach(s => {
            const opt = document.createElement('option');
            opt.value = s.id;
            opt.textContent = s.display_name || s.id;
            sel.appendChild(opt);
          });
        }
      }
    } catch(e) { /* domains not critical */ }
  },

  loadHistory() {
    try {
      const history = JSON.parse(localStorage.getItem('interview_history') || '[]');
      const div = document.getElementById('interviewHistory');
      if (!div) return;
      if (!history.length) { div.innerHTML = '<p>暂无记录</p>'; return; }
      div.innerHTML = history.slice(0, 5).map(function(h, i) {
        return '<div style="margin-bottom:4px;cursor:pointer" onclick="MockInterview.viewReport(' + i + ')">' +
          App.escapeHtml(h.date || '') + ' — ' + App.escapeHtml(h.domains || '综合') +
          ' — 得分 ' + (h.score || '-') + '/10</div>';
      }).join('');
    } catch(e) { /* non-critical */ }
  },

  start() {
    if (!App.serverOnline || !App.apiConfigured) {
      document.getElementById('interviewSetupFeedback').innerHTML =
        App.renderFeedback('wrong', '请先配置 API Key 并确保服务器在线');
      return;
    }

    var domain = document.getElementById('interviewDomain')?.value || '';
    var total = parseInt(document.getElementById('interviewCount')?.value || '5');
    var jd = document.getElementById('interviewJD')?.value.trim() || '';
    var position = document.getElementById('interviewPosition')?.value.trim() || '';
    var company = document.getElementById('interviewCompany')?.value.trim() || '';
    var round = document.getElementById('interviewRound')?.value || '';
    var style = document.getElementById('interviewStyle')?.value || '';

    this.state = {
      qIndex: 0, total: total,
      domains: domain, jd: jd,
      position: position, company: company,
      round: round, style: style,
      sessionId: 'iv_' + Date.now(),
      history: [], currentQ: '',
      phase: 'waiting_q'
    };

    document.getElementById('interviewSetup').style.display = 'none';
    document.getElementById('interviewQA').style.display = 'block';
    document.getElementById('interviewReport').style.display = 'none';
    document.getElementById('interviewFeedback').innerHTML = '';
    document.getElementById('interviewNextArea').style.display = 'none';
    document.getElementById('interviewQTotal').textContent = total;
    document.getElementById('interviewQNum').textContent = '1';
    document.getElementById('interviewProgressBar').style.width = '0%';

    this.showInfo('AI 面试官正在准备第一个问题...');
    this.sendToAgent(this._buildPrompt('start'));
  },

  _buildPrompt(type) {
    var s = this.state;
    if (type === 'start') {
      var p = '你是一位专业的技术面试官。请开始一场模拟面试。\n\n';
      if (s.domains) p += '知识领域: ' + s.domains + '\n';
      if (s.position) p += '目标岗位: ' + s.position + '\n';
      if (s.company) p += '目标公司: ' + s.company + '\n';
      if (s.round) p += '面试轮次: ' + s.round + '\n';
      if (s.style) p += '面试官风格: ' + s.style + '\n';
      if (s.jd) p += '岗位要求: ' + s.jd + '\n';
      p += '面试题数: ' + s.total + ' 题\n\n';
      p += '流程:\n';
      p += '1. 先调用 search_knowledge 了解相关领域\n';
      p += '2. 出一道开放式面试题（考察理解深度，不要选择题）\n';
      p += '3. 只出题，不要多说，等用户回答\n';
      if (s.style === '压力测试型') p += '4. 采用压力面试风格：适当质疑、追问细节、考察抗压能力\n';
      if (s.style === '技术深挖型') p += '4. 对每个回答进行技术深挖：追问实现细节、架构决策、trade-off 考量\n';
      if (s.round === '终面') p += '5. 终面轮次：侧重综合素质、项目经验深度、团队协作和文化匹配\n';
      p += '现在请出第1题。';
      return p;
    }
    if (type === 'evaluate') {
      var last = s.history[s.history.length - 1];
      var isLast = s.qIndex + 1 >= s.total;
      var p2 = '题目: ' + last.question + '\n\n我的回答: ' + last.answer + '\n\n';
      p2 += '请用 evaluate_answer 评估我的回答，然后:\n';
      if (isLast) {
        p2 += '- 这是最后一题。评估后请输出 "INTERVIEW_COMPLETE"，然后生成综合反馈报告（含总体评分1-10、各题简评、优势领域、需加强领域、学习建议）。';
      } else {
        p2 += '- 给1-2句简短反馈，然后直接出下一题（不要加额外说明）。';
      }
      return p2;
    }
    if (type === 'next') {
      return '请出下一道面试题（第' + (s.qIndex + 1) + '题，共' + s.total + '题）。不要重复之前的题目。';
    }
    if (type === 'report') {
      var p3 = '面试已结束。请生成综合反馈报告:\n';
      p3 += '1. 总体评分(1-10分)\n2. 各题简评\n3. 优势领域\n4. 需要加强的领域\n5. 具体学习建议\n\n';
      p3 += '面试记录:\n';
      s.history.forEach(function(h, i) {
        p3 += '第' + (i+1) + '题: ' + h.question + '\n回答: ' + h.answer + '\n\n';
      });
      return p3;
    }
    return '';
  },

  async sendToAgent(message) {
    var ctrl = new AbortController();
    var timer = setTimeout(function() { ctrl.abort(); }, 30000);
    try {
      var resp = await fetch(App.serverUrl + '/api/agent/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: message, session_id: this.state.sessionId }),
        signal: ctrl.signal
      });
      clearTimeout(timer);
      var data = await resp.json();
      if (data.error) { this.showError(data.error); return; }
      this.handleReply(data.reply || '');
    } catch(e) {
      clearTimeout(timer);
      this.showError(e.name === 'AbortError' ? '请求超时，请重试' : '请求失败: ' + e.message);
    }
  },

  handleReply(reply) {
    var s = this.state;
    var display = reply;

    // Strip JSON blocks
    var jsonMatch = reply.match(/```json\s*\n?([\s\S]*?)\n?```/);
    if (jsonMatch) {
      try {
        var parsed = JSON.parse(jsonMatch[1]);
        if (parsed.question) s.currentQ = parsed.question;
        display = reply.replace(/```json[\s\S]*?```/, '').trim();
      } catch(e) { /* ignore */ }
    }

    if (s.phase === 'waiting_q') {
      // Agent gave us a question
      s.currentQ = display;
      s.phase = 'answering';
      this._renderQuestion();
    } else if (s.phase === 'waiting_fb') {
      // Agent gave feedback + possibly next question or completion
      var isComplete = display.indexOf('INTERVIEW_COMPLETE') !== -1 ||
        s.qIndex + 1 >= s.total;

      if (isComplete) {
        s.phase = 'waiting_report';
        document.getElementById('interviewFeedback').innerHTML =
          '<div class="feedback-box feedback-info">' + App.escapeHtml(display).replace(/\n/g, '<br>') + '</div>';
        document.getElementById('interviewNextArea').style.display = 'none';
        document.getElementById('btnSubmitAnswer').disabled = true;
        this.showInfo('正在生成综合报告...');
        this.sendToAgent(this._buildPrompt('report'));
      } else {
        s.qIndex++;
        // The Agent's reply likely contains feedback + next question
        // Show it as feedback, then reveal next button
        document.getElementById('interviewFeedback').innerHTML =
          '<div class="feedback-box feedback-info" style="white-space:pre-line;font-size:12px">' +
          App.escapeHtml(display).replace(/\n/g, '<br>') + '</div>';
        document.getElementById('interviewNextArea').style.display = 'block';
        document.getElementById('btnSubmitAnswer').disabled = true;
        s.phase = 'waiting_next';
      }
    } else if (s.phase === 'waiting_next') {
      // Agent gave next question
      s.currentQ = display;
      s.phase = 'answering';
      this._renderQuestion();
    } else if (s.phase === 'waiting_report') {
      // Agent gave final report
      s.phase = 'done';
      this._renderReport(display);
    }
  },

  _renderQuestion() {
    var s = this.state;
    document.getElementById('interviewProgressBar').style.width =
      (s.qIndex / s.total * 100) + '%';
    document.getElementById('interviewQNum').textContent = s.qIndex + 1;
    document.getElementById('interviewQTotal').textContent = s.total;
    document.getElementById('interviewQuestion').textContent = s.currentQ;
    document.getElementById('interviewQTopic').textContent = s.domains || '面试题';

    var ta = document.getElementById('interviewAnswer');
    if (ta) ta.value = '';
    document.getElementById('interviewFeedback').innerHTML = '';
    document.getElementById('interviewNextArea').style.display = 'none';
    document.getElementById('btnSubmitAnswer').disabled = false;
  },

  submitAnswer() {
    var answer = document.getElementById('interviewAnswer')?.value.trim();
    if (!answer) return;
    if (answer.length < 10) {
      document.getElementById('interviewFeedback').innerHTML =
        App.renderFeedback('wrong', '回答太短，请至少输入10个字符');
      return;
    }

    var s = this.state;
    s.history.push({ question: s.currentQ, answer: answer });
    s.phase = 'waiting_fb';

    document.getElementById('btnSubmitAnswer').disabled = true;
    this.showInfo('AI 面试官正在评估你的回答...');
    this.sendToAgent(this._buildPrompt('evaluate'));
  },

  nextQuestion() {
    this.state.phase = 'waiting_next';
    document.getElementById('interviewFeedback').innerHTML = '';
    document.getElementById('interviewNextArea').style.display = 'none';
    this.showInfo('正在生成下一题...');
    this.sendToAgent(this._buildPrompt('next'));
  },

  skipQuestion() {
    var s = this.state;
    s.history.push({ question: s.currentQ, answer: '(跳过)' });
    s.qIndex++;

    if (s.qIndex >= s.total) {
      s.phase = 'waiting_report';
      document.getElementById('interviewFeedback').innerHTML = '';
      document.getElementById('interviewNextArea').style.display = 'none';
      document.getElementById('btnSubmitAnswer').disabled = true;
      this.showInfo('正在生成综合报告...');
      this.sendToAgent(this._buildPrompt('report'));
    } else {
      s.phase = 'waiting_next';
      document.getElementById('interviewFeedback').innerHTML = '';
      document.getElementById('interviewNextArea').style.display = 'none';
      this.showInfo('正在生成下一题...');
      this.sendToAgent(this._buildPrompt('next'));
    }
  },

  _renderReport(body) {
    var s = this.state;
    var scoreMatch = body.match(/(\d+(?:\.\d+)?)\s*(?:\/10|分)/);
    var score = scoreMatch ? parseFloat(scoreMatch[1]) : null;

    document.getElementById('interviewQA').style.display = 'none';
    document.getElementById('interviewReport').style.display = 'block';

    document.getElementById('interviewStats').innerHTML =
      '<div class="stat-card"><div class="stat-value">' + (score || '-') + '</div><div class="stat-label">综合评分/10</div></div>' +
      '<div class="stat-card"><div class="stat-value">' + s.history.filter(function(h) { return h.answer !== '(跳过)'; }).length + '</div><div class="stat-label">作答题目</div></div>' +
      '<div class="stat-card"><div class="stat-value">' + s.history.filter(function(h) { return h.answer === '(跳过)'; }).length + '</div><div class="stat-label">跳过</div></div>' +
      '<div class="stat-card"><div class="stat-value">' + (s.domains || '综合') + '</div><div class="stat-label">面试领域</div></div>';

    document.getElementById('interviewReportBody').innerHTML =
      body.replace(/\n/g, '<br>');

    document.getElementById('interviewQARecap').innerHTML = s.history.map(function(h, i) {
      return '<div style="margin-bottom:10px;padding:8px;background:var(--bg);border-radius:6px">' +
        '<strong style="font-size:11px;color:var(--text2)">第' + (i+1) + '题</strong>' +
        '<div style="font-size:12px;margin:4px 0">' + App.escapeHtml(h.question).slice(0, 150) + '...</div>' +
        '<div style="font-size:11px;color:' + (h.answer === '(跳过)' ? 'var(--red)' : 'var(--text2)') + '">' +
        (h.answer === '(跳过)' ? '已跳过' : '已作答 (' + h.answer.length + ' 字)') + '</div></div>';
    }).join('');

    this._saveHistory(score);
    App.recordProgress({
      type: 'mock_interview',
      item_id: 'interview_' + s.sessionId,
      topic: s.domains || '综合',
      score: score
    });
  },

  _saveHistory(score) {
    try {
      var history = JSON.parse(localStorage.getItem('interview_history') || '[]');
      history.unshift({
        date: new Date().toISOString().slice(0, 10),
        domains: this.state.domains || '综合',
        total: this.state.total,
        score: score,
        sessionId: this.state.sessionId
      });
      localStorage.setItem('interview_history', JSON.stringify(history.slice(0, 20)));
    } catch(e) { /* non-critical */ }
  },

  viewReport(index) {
    try {
      var history = JSON.parse(localStorage.getItem('interview_history') || '[]');
      var h = history[index];
      if (h) {
        alert('面试日期: ' + h.date + '\n领域: ' + h.domains + '\n题数: ' + h.total + '\n得分: ' + (h.score || '-') + '/10');
      }
    } catch(e) { /* ignore */ }
  },

  restart() {
    this.state = {
      qIndex: 0, total: 5,
      domains: '', jd: '', sessionId: '',
      history: [], currentQ: '',
      phase: 'setup'
    };
    document.getElementById('interviewSetup').style.display = 'block';
    document.getElementById('interviewQA').style.display = 'none';
    document.getElementById('interviewReport').style.display = 'none';
  },

  showInfo(msg) {
    document.getElementById('interviewFeedback').innerHTML =
      '<div class="feedback-box feedback-info">' + App.renderThinking() + ' ' + App.escapeHtml(msg) + '</div>';
  },

  showError(msg) {
    document.getElementById('interviewFeedback').innerHTML =
      App.renderFeedback('wrong', msg);
    document.getElementById('btnSubmitAnswer').disabled = false;
    this.state.phase = 'answering';
  }
};

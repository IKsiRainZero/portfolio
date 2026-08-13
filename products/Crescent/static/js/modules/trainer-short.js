/**
 * Trainer Short-Answer Tab — open-ended questions with Agent grading
 * Depends on: Trainer (trainer.js), App (app.js)
 */
Trainer.shortIdx = 0;
Trainer.shortAnswers = {};
Trainer.shortResults = [];

Trainer.renderShort = function(c) {
  const pool = this.getFiltered('flashcards');
  if (this.data.flashcards.length === 0 && (this.tempData.flashcards||[]).length === 0) {
    c.innerHTML = App.renderEmpty('题目数据加载中...', '请确认服务器正在运行');
    return;
  }
  if (this.shortIdx >= pool.length) {
    const graded = this.shortResults.filter(r => r.score !== null);
    const avgScore = graded.length ? (graded.reduce((a,b) => a+b.score, 0) / graded.length).toFixed(1) : '-';
    const excellent = graded.filter(r => r.score >= 8).length;
    c.innerHTML = `
      ${this.renderTempActions()}${this.renderTopicFilter('flashcards')}
      <div class="stat-grid">
        <div class="stat-card"><div class="stat-value">${graded.length}</div><div class="stat-label">已作答</div></div>
        <div class="stat-card"><div class="stat-value">${avgScore}</div><div class="stat-label">平均分/10</div></div>
        <div class="stat-card"><div class="stat-value">${excellent}</div><div class="stat-label">优秀(≥8分)</div></div>
        <div class="stat-card"><div class="stat-value">${pool.length - graded.length}</div><div class="stat-label">剩余</div></div>
      </div>
      ${this.shortResults.filter(r => r.score && r.score < 6).length ? `<h3>需加强的概念</h3><ul class="review-list">${this.shortResults.filter(r => r.score && r.score < 6).map(r => `<li onclick="App.askAI('${App.escapeHtml(r.concept||'')}','得分${r.score}/10')">${App.escapeHtml(r.concept)} — ${r.score}/10分</li>`).join('')}</ul>` : ''}
      <button class="btn btn-primary" onclick="Trainer.shortIdx=0;Trainer.shortResults=[];Trainer.render()" style="margin-top:16px">重新练习</button>`;
    return;
  }
  if (pool.length === 0) {
    c.innerHTML = `${this.renderTempActions()}${this.renderTopicFilter('flashcards')}<div class="empty-state"><h3>该分类暂无题目</h3></div>`;
    return;
  }
  const fc = pool[this.shortIdx];
  const cardId = `short-${this.shortIdx}`;
  const userAnswer = this.shortAnswers[cardId] || '';
  const existingResult = this.shortResults[this.shortIdx];

  c.innerHTML = `
    ${this.renderTempActions()}${this.renderTopicFilter('flashcards')}
    <div class="progress-bar"><div class="progress-fill" style="width:${this.shortIdx/pool.length*100}%"></div></div>
    <div class="card" style="margin-bottom:12px">
      <span class="badge badge-topic" style="margin-bottom:4px">${App.escapeHtml(fc.category||'简答题')}</span>
      <h3 style="margin:4px 0">${App.escapeHtml(fc.concept||'')}</h3>
      <p style="font-size:13px;color:var(--text2);white-space:pre-line">${App.escapeHtml(fc.question||'请用自己的话解释这个概念。')}</p>
    </div>
    ${existingResult ? `
    <div class="card" style="margin-bottom:12px">
      <div style="font-size:11px;color:var(--text2);margin-bottom:6px">你的回答</div>
      <div style="font-size:12px;white-space:pre-line;padding:10px;background:var(--bg);border-radius:6px;margin-bottom:8px">${App.escapeHtml(existingResult.answer||'')}</div>
      <div class="feedback-box ${existingResult.score >= 7 ? 'feedback-correct' : existingResult.score >= 5 ? 'feedback-info' : 'feedback-wrong'}" style="white-space:pre-line;font-size:12px">${App.escapeHtml(existingResult.feedback||'')}</div>
      <button class="btn btn-sm" style="margin-top:8px" onclick="Trainer.shortIdx++;Trainer.render()">下一题</button>
    </div>` : `
    <div class="card" style="margin-bottom:12px">
      <label style="font-size:11px;color:var(--text2);display:block;margin-bottom:4px">用你自己的话回答（不是复述定义，而是解释你理解到了什么）</label>
      <textarea id="shortAnswer" placeholder="写下你的理解..."
        style="width:100%;height:120px;font-size:13px;padding:10px;border:1px solid var(--border);border-radius:8px;resize:vertical;font-family:inherit"
        oninput="Trainer.shortAnswers['${cardId}']=this.value">${App.escapeHtml(userAnswer)}</textarea>
      <div style="display:flex;gap:8px;margin-top:8px">
        <button class="btn btn-primary" onclick="Trainer.submitShortAnswer('${cardId}')">提交评分</button>
        <button class="btn" onclick="Trainer.shortIdx++;Trainer.render()">跳过</button>
      </div>
      <div id="shortFeedback" style="margin-top:10px"></div>
    </div>`}
    <div class="card" style="text-align:center">
      <p style="font-size:11px;color:var(--text2)">第 ${this.shortIdx+1}/${pool.length} 题</p>
    </div>`;
};

Trainer.submitShortAnswer = async function(cardId) {
  const pool = this.getFiltered('flashcards');
  const fc = pool[this.shortIdx];
  const userAnswer = this.shortAnswers[cardId] || '';
  if (userAnswer.trim().length < 10) {
    document.getElementById('shortFeedback').innerHTML = App.renderFeedback('wrong', '回答太短，请至少输入10个字符。');
    return;
  }

  const fb = document.getElementById('shortFeedback');
  fb.innerHTML = App.renderFeedback('info', App.renderThinking());

  if (!App.serverOnline) {
    fb.innerHTML = App.renderFeedback('warn', '服务器未连接');
    return;
  }

  try {
    const resp = await fetch(`${App.serverUrl}/api/agent/chat`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: `评估以下回答:\n题目: ${fc.question || fc.concept}\n用户回答: ${userAnswer}\n参考答案: ${fc.answer || ''}`,
        session_id: 'trainer_short'
      })
    });
    const data = await resp.json();

    if (data.error) {
      fb.innerHTML = App.renderFeedback('wrong', data.error);
      return;
    }

    // Parse score from reply
    let score = null;
    const scoreMatch = (data.reply || '').match(/总分[：:]\s*(\d+)/);
    if (scoreMatch) score = parseInt(scoreMatch[1]);

    this.shortResults[this.shortIdx] = {
      concept: fc.concept, answer: userAnswer,
      feedback: data.reply, score, category: fc.category
    };

    App.recordProgress({
      type: 'short_answer', item_id: `short-${fc.concept}`,
      topic: fc.category || 'short_answer', score
    });

    // Show result
    fb.innerHTML = `<div class="feedback-box ${score >= 7 ? 'feedback-correct' : score >= 5 ? 'feedback-info' : 'feedback-wrong'}" style="white-space:pre-line;font-size:12px">${App.escapeHtml(data.reply)}</div>
    <button class="btn btn-sm btn-primary" style="margin-top:6px" onclick="Trainer.shortIdx++;Trainer.render()">下一题</button>`;
  } catch(e) {
    fb.innerHTML = App.renderFeedback('wrong', `请求失败: ${e.message}`);
  }
};

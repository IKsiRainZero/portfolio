/**
 * Trainer MCQ Tab — multiple-choice question rendering & answering
 * Depends on: Trainer (trainer.js), App (app.js)
 */
Trainer.renderMCQ = function(c) {
  const pool = this.getFiltered('mcq');
  if (this.data.mcq.length === 0 && (this.tempData.mcq||[]).length === 0) {
    c.innerHTML = '<div class="empty-state"><h3>题目数据加载中...</h3><p>请确认服务器正在运行</p></div>';
    return;
  }
  if (this.mcqDone) {
    const pct = this.mcqScore / pool.length * 100;
    c.innerHTML = `${this.renderTempActions()}${this.renderTopicFilter('mcq')}
    <div class="stat-grid">
      <div class="stat-card"><div class="stat-value">${this.mcqScore}/${pool.length}</div><div class="stat-label">正确</div></div>
      <div class="stat-card"><div class="stat-value">${pct.toFixed(0)}%</div><div class="stat-label">正确率</div></div>
      <div class="stat-card"><div class="stat-value">${this.mcqWrong.length}</div><div class="stat-label">需复习</div></div>
      <div class="stat-card"><div class="stat-value">${pct>=80?'PASS':'MORE'}</div><div class="stat-label">${pct>=80?'达标':'继续练'}</div></div>
    </div>
    <h3 style="margin-bottom:12px">需复习的题目</h3>
    <ul class="review-list">${this.mcqWrong.map(w=>`<li onclick="App.askAI('${App.escapeHtml(w.question||'').slice(0,60)}','${App.escapeHtml(w.explanation||'')}')">[${App.escapeHtml(w.topic)}] ${App.escapeHtml((w.question||'').slice(0,50))}...</li>`).join('')}</ul>
    <button class="btn btn-primary" onclick="Trainer.switchTab('mcq')" style="margin-top:16px">重新练习</button>`;
    return;
  }
  if (pool.length === 0) {
    c.innerHTML = `${this.renderTempActions()}${this.renderTopicFilter('mcq')}<div class="empty-state"><h3>该分类暂无题目</h3></div>`;
    return;
  }
  const q = pool[this.mcqIdx];
  if (!q) { c.innerHTML = '<div class="empty-state"><h3>题目加载出错</h3></div>'; return; }
  const pct = this.mcqIdx / pool.length * 100;
  const diffLabels = {1:'*',2:'**',3:'***'};
  c.innerHTML = `
    ${this.renderTempActions()}${this.renderTopicFilter('mcq')}
    <div class="progress-bar"><div class="progress-fill" style="width:${pct}%"></div></div>
    <div class="card">
      <div class="card-header">
        <span>第 ${this.mcqIdx+1}/${pool.length} 题</span>
        <span><span class="badge badge-topic">${App.escapeHtml(q.topic||'')}</span> <span class="badge badge-diff">${diffLabels[q.difficulty]||'*'}</span></span>
      </div>
      <p style="font-size:13px;white-space:pre-line;margin-bottom:12px">${App.escapeHtml(q.question||'')}</p>
      <div id="optionsContainer">${(q.options||[]).map((o,i)=>`<button class="option-btn" onclick="Trainer.answerMCQ(${i},this)">${App.escapeHtml(o)}</button>`).join('')}</div>
      <div id="mcqFeedback"></div>
    </div>`;
  this.mcqAnswered = false;
};

Trainer.mcqStreak = 0;

Trainer.answerMCQ = function(idx, btn) {
  if (this.mcqAnswered) return;
  this.mcqAnswered = true;
  const pool = this.getFiltered('mcq');
  const q = pool[this.mcqIdx];
  const correctIdx = typeof q.correct === 'number' ? q.correct : (q.answer ? q.answer.charCodeAt(0)-65 : -1);
  const correct = idx === correctIdx;
  const correctLetter = String.fromCharCode(65 + correctIdx);
  if (correct) { this.mcqScore++; this.mcqStreak = Math.max(0, this.mcqStreak) + 1; }
  else { this.mcqWrong.push(q); this.mcqStreak = Math.min(0, this.mcqStreak) - 1; }

  // Save wrong answers to error notebook (localStorage)
  if (!correct) {
    const notebook = JSON.parse(localStorage.getItem('error_notebook') || '[]');
    notebook.push({ topic: q.topic, question: q.question, answer: q.options ? q.options[correctIdx] : '', explanation: q.explanation, difficulty: q.difficulty, time: new Date().toISOString() });
    localStorage.setItem('error_notebook', JSON.stringify(notebook.slice(-50))); // keep last 50
  }

  document.querySelectorAll('.option-btn').forEach((b, i) => {
    b.disabled = true;
    if (i === correctIdx) b.classList.add('correct');
    if (i === idx && !correct) b.classList.add('wrong');
  });

  let difficultyHint = '';
  if (this.mcqStreak >= 3) difficultyHint = '<p style="font-size:11px;color:var(--green);margin-top:4px">连续答对' + this.mcqStreak + '题！建议尝试更高难度的题目。</p>';
  else if (this.mcqStreak <= -2) difficultyHint = '<p style="font-size:11px;color:var(--red);margin-top:4px">连续答错，建议回到基础知识巩固一下。</p>';

  let mistakeReason = null;

  const fb = document.getElementById('mcqFeedback');
  const qId = 'mcq_' + (q.id || this.mcqIdx);
  fb.innerHTML = `<div class="feedback-box ${correct?'feedback-correct':'feedback-wrong'}">
    <strong>${correct?'正确！':'错误。正确答案: '+correctLetter}</strong><br>
    ${App.escapeHtml(q.explanation||'')}
    ${difficultyHint}<br>
    <button class="btn btn-sm" style="margin-top:6px" onclick="App.askAI('${App.escapeHtml((q.question||'').slice(0,80))}','${App.escapeHtml(q.explanation||'').slice(0,100)}')">问AI教练</button>
    <button class="btn btn-sm" style="margin-top:6px;margin-left:4px" onclick="Trainer.inlineAIExplain('${qId}')">AI 解析本题</button>
    <div id="mcqAIExplain_${qId}" style="margin-top:8px"></div>
  </div>`;

  // 错题原因追问
  if (!correct) {
    const reasonRow = document.createElement('div');
    reasonRow.className = 'mistake-reason-row';
    reasonRow.innerHTML = `
      <span style="font-size:12px;color:var(--text2);margin-right:4px;">这题做错是因为：</span>
      <button class="mistake-btn" data-reason="guess">🤔 猜的</button>
      <button class="mistake-btn" data-reason="knowledge_gap">📚 不会</button>
      <button class="mistake-btn" data-reason="careless">😅 粗心</button>
    `;
    fb.appendChild(reasonRow);

    reasonRow.querySelectorAll('.mistake-btn').forEach(btn => {
      btn.onclick = () => {
        reasonRow.querySelectorAll('.mistake-btn').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        mistakeReason = btn.dataset.reason;
        // 更新 error_notebook
        const notebook = JSON.parse(localStorage.getItem('error_notebook') || '[]');
        if (notebook.length > 0) {
          notebook[notebook.length - 1].mistake_reason = mistakeReason;
          localStorage.setItem('error_notebook', JSON.stringify(notebook));
        }
        // 补充记录错因
        App.recordProgress({
          type: 'mcq_mistake_reason', item_id: `mcq-${q.id}`, topic: q.topic,
          mistake_reason: mistakeReason
        });
      };
    });
  } else {
    App.recordProgress({
      type: 'mcq', item_id: `mcq-${q.id}`, topic: q.topic,
      correct: true, user_answer: String.fromCharCode(65+idx), correct_answer: correctLetter
    });
  }

  // 手动"下一题"按钮
  const nextBtn = document.createElement('button');
  nextBtn.className = 'btn btn-primary';
  nextBtn.textContent = '下一题 →';
  nextBtn.style.marginTop = '12px';
  nextBtn.onclick = () => {
    this.mcqIdx++;
    if (this.mcqIdx >= pool.length) this.mcqDone = true;
    this.render();
  };
  // 插入到反馈区下方
  const feedbackEl = document.getElementById('mcqFeedback');
  if (feedbackEl) {
    feedbackEl.appendChild(nextBtn);
  }
};

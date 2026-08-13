/**
 * Trainer Flash Tab — flashcard rendering, flip, AI compare, rating
 * Depends on: Trainer (trainer.js), App (app.js)
 */
Trainer.renderFlash = function(c) {
  const pool = this.getFiltered('flashcards');
  if (this.data.flashcards.length === 0 && (this.tempData.flashcards||[]).length === 0) {
    c.innerHTML = '<div class="empty-state"><h3>闪卡数据加载中...</h3></div>';
    return;
  }
  if (this.flashIdx >= pool.length) {
    const avg = this.flashRatings.length ? (this.flashRatings.reduce((a,b)=>a+b,0)/this.flashRatings.length).toFixed(1) : '-';
    const weak = pool.filter((_,i)=> (this.flashRatings[i]||0) <= 2);
    c.innerHTML = `
      ${this.renderTempActions()}${this.renderTopicFilter('flashcards')}
      <div class="stat-grid">
        <div class="stat-card"><div class="stat-value">${this.flashRatings.length}</div><div class="stat-label">已复习</div></div>
        <div class="stat-card"><div class="stat-value">${avg}</div><div class="stat-label">平均掌握度/5</div></div>
        <div class="stat-card"><div class="stat-value">${weak.length}</div><div class="stat-label">薄弱项(<3分)</div></div>
      </div>
      ${weak.length ? `<h3>需重点复习</h3><ul class="review-list">${weak.map(w=>`<li onclick="App.askAI('${App.escapeHtml(w.concept||'')}','${App.escapeHtml((w.answer||'').slice(0,100))}')">${App.escapeHtml(w.concept)} [${App.escapeHtml(w.category||'')}]</li>`).join('')}</ul>` : ''}
      <button class="btn btn-primary" onclick="Trainer.switchTab('flash')" style="margin-top:16px">重新练习</button>`;
    return;
  }
  if (pool.length === 0) {
    c.innerHTML = `${this.renderTempActions()}${this.renderTopicFilter('flashcards')}<div class="empty-state"><h3>该分类暂无闪卡</h3></div>`;
    return;
  }
  const fc = pool[this.flashIdx];
  const cardId = `flash-${this.flashIdx}`;
  const userAnswer = this.flashAnswers[cardId] || '';
  this.flashFlipped = false; this.flashAiResult = '';
  c.innerHTML = `
    ${this.renderTempActions()}${this.renderTopicFilter('flashcards')}
    <div class="card" style="margin-bottom:12px">
      <span class="badge badge-topic" style="margin-bottom:4px">${App.escapeHtml(fc.category||'')}</span>
      <h3 style="margin:4px 0">${App.escapeHtml(fc.concept||'')}</h3>
      <p style="font-size:13px;color:var(--text2)">${App.escapeHtml(fc.question||'')}</p>
    </div>
    <div class="card" style="margin-bottom:12px">
      <label style="font-size:11px;color:var(--text2);display:block;margin-bottom:4px">你的回答（尝试用自己的话解释，再翻转对比）</label>
      <textarea id="flashUserAnswer" placeholder="在这里写下你对这个概念的理解..."
        style="width:100%;height:80px;font-size:13px;padding:10px;border:1px solid var(--border);border-radius:8px;resize:vertical;font-family:inherit"
        oninput="Trainer.saveFlashAnswer('${cardId}',this.value)">${App.escapeHtml(userAnswer)}</textarea>
      <div style="display:flex;gap:8px;margin-top:8px">
        <button class="btn btn-primary" onclick="Trainer.flipFlashCard()">翻转查看答案</button>
        <button class="btn btn-sm" onclick="App.askAI('${App.escapeHtml(fc.concept||'')}','${App.escapeHtml((fc.answer||'').slice(0,100))}')">问AI教练</button>
      </div>
    </div>
    <div class="card" id="flashCompareArea" style="display:none;margin-bottom:12px">
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div style="background:#f0f9ff;border:1px solid #bae6fd;border-radius:8px;padding:12px">
          <div style="font-size:11px;color:#0369a1;font-weight:700;margin-bottom:6px">你的回答</div>
          <div id="flashUserAnswerDisplay" style="font-size:12px;white-space:pre-line;color:#334155"></div>
        </div>
        <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:12px">
          <div style="font-size:11px;color:#15803d;font-weight:700;margin-bottom:6px">标准答案</div>
          <div style="font-size:12px;white-space:pre-line;color:#334155">${App.escapeHtml(fc.answer||'')}</div>
        </div>
      </div>
      <div style="text-align:center;margin-top:12px">
        <button class="btn btn-primary" onclick="Trainer.compareWithAI('${cardId}')">AI 对比分析</button>
        <div id="flashAiFeedback" style="margin-top:10px;font-size:12px;text-align:left"></div>
      </div>
    </div>
    <div class="card" style="text-align:center">
      <p style="font-size:12px;margin-bottom:8px">掌握程度自评 (1=不会, 3=说得清, 5=流利)</p>
      <div class="rating-btns">${[1,2,3,4,5].map(n=>`<button class="rating-btn" onclick="Trainer.rateFlash(${n})">${n}</button>`).join('')}</div>
      <div id="flashDetail"></div>
    </div>`;
};

Trainer.saveFlashAnswer = function(cardId, value) { this.flashAnswers[cardId] = value; };

Trainer.flipFlashCard = function() {
  const userAnswer = document.getElementById('flashUserAnswer')?.value || '';
  document.getElementById('flashUserAnswerDisplay').textContent = userAnswer || '(未填写)';
  document.getElementById('flashCompareArea').style.display = 'block';
  this.flashFlipped = true;
  document.getElementById('flashCompareArea').scrollIntoView({behavior:'smooth'});
};

Trainer.compareWithAI = async function(cardId) {
  const pool = this.getFiltered('flashcards');
  const fc = pool[this.flashIdx];
  const userAnswer = this.flashAnswers[cardId] || '';
  const fb = document.getElementById('flashAiFeedback');
  fb.innerHTML = '<div class="feedback-box feedback-info">AI 分析中...</div>';
  if (!App.serverOnline) { fb.innerHTML = '<div class="feedback-box feedback-warn">服务器未连接，无法调用AI</div>'; return; }
  try {
    const resp = await fetch(`${App.serverUrl}/api/agent/chat`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        message: `请对比分析用户对"${fc.concept}"的理解与标准答案的差异。\n\n概念: ${fc.concept}\n问题: ${fc.question||''}\n\n用户回答:\n${userAnswer}\n\n标准答案:\n${fc.answer||''}\n\n请从以下角度分析:\n1. 用户理解了哪些关键点？\n2. 用户遗漏或表述不准的地方\n3. 相比标准答案，用户有哪些独特见解或额外补充？\n4. 给出改进建议(如有)`,
        session_id: 'trainer_flash'
      })
    });
    const data = await resp.json();
    if (data.error) { fb.innerHTML = `<div class="feedback-box feedback-wrong">${App.escapeHtml(data.error)}</div>`; }
    else { this.flashAiResult = data.reply || ''; fb.innerHTML = `<div class="feedback-box feedback-info" style="white-space:pre-line;font-size:12px">${App.escapeHtml(this.flashAiResult)}</div>`; }
  } catch(e) { fb.innerHTML = `<div class="feedback-box feedback-wrong">请求失败: ${e.message}</div>`; }
};

Trainer.rateFlash = function(n) {
  const pool = this.getFiltered('flashcards');
  const fc = pool[this.flashIdx];
  this.flashRatings.push(n);
  this.flashAnswers = {}; this.flashFlipped = false; this.flashAiResult = '';
  App.recordProgress({ type: 'flashcard', item_id: `flash-${fc.concept}`, topic: fc.category || 'flashcard', rating: n });
  fetch('/api/srs/review', {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ card_id: fc.concept, concept: fc.concept, category: fc.category || 'general', rating: n })
  }).catch(() => {});
  this.flashIdx++;
  // 显示"下一张"按钮，不自动跳转
  const nextBtn = document.createElement('button');
  nextBtn.className = 'btn btn-primary';
  nextBtn.textContent = '下一张 →';
  nextBtn.style.marginTop = '12px';
  const feedDiv = document.getElementById('flashDetail');
  if (feedDiv) {
    feedDiv.appendChild(nextBtn);
    nextBtn.onclick = () => this.render();
  } else {
    setTimeout(() => this.render(), 100);
  }
};

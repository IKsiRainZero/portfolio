/**
 * Trainer Review Tab — SRS plan + progress summary + error notebook
 * Depends on: Trainer (trainer.js), App (app.js)
 */
Trainer.renderReview = function(c) {
  Promise.all([
    fetch('/api/srs/plan').then(r => r.json()).catch(() => ({})),
    fetch('/api/progress/summary').then(r => r.json()).catch(() => ({}))
  ]).then(([plan, data]) => {
    const dueCount = plan.review_due || 0;
    const newCount = (plan.new_today || []).length;
    c.innerHTML = `
      ${dueCount > 0 ? `<div class="card feedback-info" style="margin-bottom:12px">
        <div class="card-header">今日学习计划 — ${plan.date}</div>
        <p style="margin:0;font-size:13px">待复习闪卡 <b>${dueCount}</b> 张 · 新卡推荐 <b>${newCount}</b> 张</p>
        ${plan.review_today && plan.review_today.length ? `
          <ul class="review-list" style="margin-top:8px">
            ${plan.review_today.slice(0,8).map(d => `<li onclick="Trainer.switchTab('flash');Trainer.topicFilter.flash='${App.escapeHtml(d.category||'')}'" style="cursor:pointer">
              [${d.avg_rating||0}/5] ${App.escapeHtml(d.concept||'')} — ${App.escapeHtml(d.category||'')}
            </li>`).join('')}
          </ul>` : ''}
        ${newCount > 0 ? `
          <p style="margin:8px 0 0;font-size:12px;color:var(--text2)">新卡推荐：${plan.new_today.map(c => App.escapeHtml(c.concept||'')).join('、')}</p>` : ''}
      </div>` : `<div class="card feedback-info" style="margin-bottom:12px">
        <p style="margin:0;font-size:13px">今日暂无待复习闪卡 · 已复习 <b>${plan.reviewed_cards||0}</b>/${plan.total_cards||0} 张</p>
      </div>`}
      <div class="stat-grid">
        <div class="stat-card"><div class="stat-value">${data.mcq_total||0}</div><div class="stat-label">MCQ练习次数</div></div>
        <div class="stat-card"><div class="stat-value">${data.code_total||0}</div><div class="stat-label">编程提交</div></div>
        <div class="stat-card"><div class="stat-value">${data.flash_total||0}</div><div class="stat-label">闪卡评分</div></div>
        <div class="stat-card"><div class="stat-value">${data.interview_total||0}</div><div class="stat-label">模拟面试</div></div>
      </div>
      ${data.weak_areas && data.weak_areas.length ? `
        <div class="card feedback-warn">
          <div class="card-header">薄弱环节（正确率 < 70%）</div>
          <ul class="review-list">
            ${data.weak_areas.map(w => `<li onclick="App.askAI('${w.topic}','正确率${w.accuracy}%，请帮我补习')">${App.escapeHtml(w.topic)} — 正确率 ${w.accuracy}% (${w.attempts}次)</li>`).join('')}
          </ul>
        </div>` : ''}
      ${data.weak_flashcards && data.weak_flashcards.length ? `
        <div class="card feedback-warn" style="margin-top:12px">
          <div class="card-header">闪卡薄弱项（评分 < 3）</div>
          <ul class="review-list">
            ${data.weak_flashcards.map(w => `<li onclick="App.askAI('${w.concept}','')">${App.escapeHtml(w.concept)} — 均分 ${w.rating}/5</li>`).join('')}
          </ul>
        </div>` : ''}
      ${Trainer._renderErrorNotebook()}
      ${!data.weak_areas?.length && !data.weak_flashcards?.length ? '<div class="empty-state"><h3>暂无薄弱项数据</h3><p>完成一些练习后这里会显示薄弱项分析</p></div>' : ''}`;
  }).catch(() => {
    c.innerHTML = '<div class="empty-state"><h3>进度数据不可用</h3><p>请确认服务器在线</p></div>';
  });
};

/** Render error notebook from localStorage — MCQ wrong answers grouped by topic */
Trainer._renderErrorNotebook = function() {
  try {
    const notebook = JSON.parse(localStorage.getItem('error_notebook') || '[]');
    if (!notebook.length) return '';
    const byTopic = {};
    notebook.forEach(e => {
      const t = e.topic || '其他';
      if (!byTopic[t]) byTopic[t] = [];
      byTopic[t].push(e);
    });
    const topics = Object.keys(byTopic);
    return '<div class="card" style="margin-top:12px;background:#fff7ed;border:1px solid #fdba74">' +
      '<div class="card-header" style="display:flex;justify-content:space-between;align-items:center">' +
        '<span>错题本 (' + notebook.length + ' 道)</span>' +
        '<button class="btn btn-sm" style="font-size:10px;padding:2px 8px" onclick="localStorage.removeItem(\'error_notebook\');Trainer.render()">清空</button>' +
      '</div>' +
      topics.map(function(t) {
        return '<div style="margin-bottom:8px">' +
        '<strong style="font-size:11px;color:#c2410c">' + App.escapeHtml(t) + ' (' + byTopic[t].length + '题)</strong>' +
        '<ul class="review-list" style="margin-top:4px">' +
          byTopic[t].slice(0, 10).map(function(e) {
            return '<li onclick="App.askAI(\'' + App.escapeHtml((e.question||'').slice(0,60)) + '\',\'' + App.escapeHtml('正确答案: ' + (e.answer||'')) + '\')" title="' + App.escapeHtml(e.explanation||'') + '">' + App.escapeHtml((e.question||'').slice(0, 60)) + '...</li>';
          }).join('') +
          (byTopic[t].length > 10 ? '<li style="color:var(--text2);font-size:11px">...及其他 ' + (byTopic[t].length - 10) + ' 道</li>' : '') +
        '</ul></div>';
      }).join('') +
      '<button class="btn btn-sm btn-primary" style="margin-top:8px" onclick="Trainer.switchTab(\'mcq\');Trainer.mcqDone=false;Trainer.mcqIdx=0;Trainer.mcqScore=0;Trainer.mcqWrong=[];Trainer.render()">重新练习错题</button>' +
    '</div>';
  } catch(e) { return ''; }
};

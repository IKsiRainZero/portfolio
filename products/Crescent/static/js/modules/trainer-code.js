/**
 * Trainer Code Tab — coding problem rendering & execution
 * Depends on: Trainer (trainer.js), App (app.js)
 */
Trainer.renderCode = function(c) {
  const pool = this.getFiltered('coding');
  if (this.data.coding.length === 0 && (this.tempData.coding||[]).length === 0) {
    c.innerHTML = '<div class="empty-state"><h3>题目数据加载中...</h3></div>';
    return;
  }
  if (this.codeIdx >= pool.length) {
    c.innerHTML = `${this.renderTempActions()}${this.renderTopicFilter('coding')}<div class="empty-state"><h3>编程题全部完成！</h3>
      <button class="btn btn-primary" onclick="Trainer.codeIdx=0;Trainer.render()" style="margin-top:12px">重新练习</button></div>`;
    return;
  }
  const p = pool[this.codeIdx];
  const historyCode = localStorage.getItem(`trainer_code_${p.id}`) || p.starter_code;
  const diffLabels = {1:'*',2:'**',3:'***'};
  c.innerHTML = `
    ${this.renderTempActions()}${this.renderTopicFilter('coding')}
    <div class="card">
      <div class="card-header"><span>第${p.id}题: ${App.escapeHtml(p.title)} [${diffLabels[p.difficulty]||'*'}]</span><span class="badge badge-topic">${App.escapeHtml(p.scenario||'')}</span></div>
      <p style="font-size:12px;white-space:pre-line;margin-bottom:8px;color:var(--text2)">${App.escapeHtml(p.description||'')}</p>
      <div style="margin-bottom:12px">
        <button class="btn btn-sm" onclick="document.getElementById('codeHint').innerHTML='提示: ${App.escapeHtml(p.hint||'')}'">提示</button>
        <button class="btn btn-sm" onclick="localStorage.removeItem('trainer_code_${p.id}');document.getElementById('codeEditor').value=Trainer.getFiltered('coding')[Trainer.codeIdx].starter_code">重置</button>
        <button class="btn btn-sm" onclick="App.askAI('编程题${p.id}:${App.escapeHtml(p.title)}','代码:\\n'+document.getElementById('codeEditor').value.slice(0,300))">问AI</button>
      </div>
      <textarea class="code-editor" id="codeEditor" spellcheck="false">${App.escapeHtml(historyCode)}</textarea>
      <div id="codeHint" style="margin-top:8px;font-size:11px;color:var(--text2)"></div>
      <div id="codeResults" style="margin-top:12px"></div>
      <div style="margin-top:12px;display:flex;gap:8px">
        <button class="btn btn-primary" onclick="Trainer.runCode()">运行测试</button>
        <button class="btn" onclick="Trainer.codeIdx++;Trainer.render()">跳过</button>
      </div>
    </div>`;
  document.getElementById('codeEditor').addEventListener('input', function() {
    localStorage.setItem(`trainer_code_${p.id}`, this.value);
  });
};

Trainer.runCode = async function() {
  const pool = this.getFiltered('coding');
  const p = pool[this.codeIdx];
  const code = document.getElementById('codeEditor').value;
  const resDiv = document.getElementById('codeResults');

  if (!App.serverOnline) { resDiv.innerHTML = '<div class="feedback-box feedback-wrong">服务器未连接</div>'; return; }

  resDiv.innerHTML = '<div class="feedback-box feedback-info">运行中...</div>';
  try {
    const resp = await fetch(`${App.serverUrl}/api/code/run`, {
      method:'POST', headers:{'Content-Type':'application/json'},
      body: JSON.stringify({code, function_name: p.function_name, test_cases: p.test_cases})
    });
    const data = await resp.json();
    if (data.error) {
      resDiv.innerHTML = `<div class="feedback-box feedback-wrong"><strong>执行出错:</strong><br><pre style="font-size:11px;overflow-x:auto">${App.escapeHtml(data.stderr||data.error)}</pre></div>`;
      return;
    }
    const allPass = data.results.every(r=>r.passed);
    App.recordProgress({ type: 'code', item_id: `code-${p.id}`, topic: p.scenario || 'coding', passed: allPass, total_tests: data.results.length });
    resDiv.innerHTML = `
      <div class="feedback-box ${allPass?'feedback-correct':'feedback-wrong'}"><strong>${allPass?'全部通过！':'部分测试未通过'}</strong></div>
      ${data.results.map((r,i)=>`<div class="feedback-box ${r.passed?'feedback-correct':'feedback-wrong'}" style="margin-top:4px">
        用例${i+1}: ${r.passed?'通过':'失败'} | 输入:${JSON.stringify((p.test_cases[i]||{}).input)} | 期望:${JSON.stringify(r.expected)} | ${r.error?'错误:'+r.error:'得到:'+JSON.stringify(r.actual)}
      </div>`).join('')}
      ${allPass ? `<button class="btn btn-primary" style="margin-top:8px" onclick="Trainer.codeIdx++;Trainer.render()">下一题</button>` :
        `<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">
          <button class="btn btn-sm" onclick="Trainer.inlineCodeReview('${p.id}')">AI 代码审查</button>
          <button class="btn btn-sm" onclick="Trainer.codeIdx++;Trainer.render()">跳过</button>
          <div id="codeAIReview_${p.id}" style="margin-top:6px;width:100%"></div>
        </div>`}`;
  } catch(e) {
    resDiv.innerHTML = `<div class="feedback-box feedback-wrong">请求失败: ${e.message}</div>`;
  }
};

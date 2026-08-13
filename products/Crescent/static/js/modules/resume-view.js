/**
 * Resume View — render from structured JSON data
 */
const ResumeView = {
  async init() {
    try {
      const resp = await fetch('/api/resume/data');
      const data = await resp.json();
      if (data.personal) this.render(data);
      else throw new Error('No resume data');
    } catch(e) {
      document.getElementById('resumeContainer').innerHTML =
        '<div class="empty-state"><h3>简历数据未就绪</h3><p>数据文件在 data/resume/ 目录下</p></div>';
    }
  },

  render(data) {
    const p = data.personal || {};
    const edu = data.education || {};
    const skills = data.skills || {};
    const projects = data.projects || [];
    const experience = data.experience || [];

    document.getElementById('resumeContainer').innerHTML = `
    <style>
      .resume-page {
        max-width: 794px; margin: 0 auto; background: #fff;
        padding: 30px 36px; font-size: 11.5px; line-height: 1.5;
        box-shadow: 0 2px 12px rgba(0,0,0,.08);
      }
      .r-header { display: flex; align-items: center; gap: 24px; margin-bottom: 12px; }
      .r-photo { width: 100px; height: 132px; object-fit: cover; border-radius: 4px; flex-shrink: 0; background: #f1f5f9; }
      .r-name { font-size: 24px; font-weight: 700; margin-bottom: 2px; }
      .r-subtitle { font-size: 12px; color: #64748b; }
      .r-contact { font-size: 11px; color: #64748b; margin-top: 6px; display: flex; gap: 16px; flex-wrap: wrap; }
      .r-section { margin-bottom: 10px; }
      .r-section-title {
        font-size: 13px; font-weight: 700; padding-bottom: 4px; margin-bottom: 8px;
        border-bottom: 1px solid #e2e8f0; position: relative;
      }
      .r-section-title::before { content: ''; position: absolute; left: 0; bottom: -1px; width: 40px; height: 3px; background: #2563eb; border-radius: 2px; }
      .r-entry { margin-bottom: 8px; }
      .r-entry-header { display: flex; justify-content: space-between; align-items: baseline; }
      .r-entry-title { font-weight: 600; font-size: 12px; }
      .r-entry-date { font-size: 10px; color: #94a3b8; white-space: nowrap; }
      .r-entry-sub { font-size: 11px; color: #64748b; margin-bottom: 2px; }
      .r-bullets { list-style: none; padding: 0; }
      .r-bullets li { position: relative; padding-left: 14px; margin: 2px 0; font-size: 11px; }
      .r-bullets li::before { content: '—'; position: absolute; left: 0; color: #94a3b8; }
      .r-skills-row { display: flex; margin: 2px 0; font-size: 11px; }
      .r-skills-label { min-width: 80px; text-align: right; font-weight: 600; margin-right: 12px; color: #64748b; flex-shrink: 0; }
      .r-self { font-size: 11px; line-height: 1.55; color: #475569; }
      @media print {
        .resume-page { box-shadow: none; padding: 0; max-width: 100%; }
        .no-print { display: none !important; }
      }
    </style>
    <div class="resume-page">
      <div class="r-header">
        <img class="r-photo" src="${p.photo || ''}" alt="photo" onerror="this.style.display='none'">
        <div>
          <div class="r-name">${App.escapeHtml(p.name || '')}</div>
          <div class="r-subtitle">${App.escapeHtml(p.subtitle || '')}</div>
          <div class="r-contact">
            <span>${App.escapeHtml(p.email || '')}</span>
            <span>${App.escapeHtml(p.phone || '')}</span>
          </div>
        </div>
      </div>

      <div class="r-section">
        <div class="r-section-title">教育背景</div>
        <div class="r-entry">
          <div class="r-entry-header">
            <span class="r-entry-title">${App.escapeHtml(edu.school || '')} — ${App.escapeHtml(edu.degree || '')}</span>
            <span class="r-entry-date">${App.escapeHtml(edu.years || '')}</span>
          </div>
          <ul class="r-bullets">${(edu.details||[]).map(d=>`<li>${App.escapeHtml(d)}</li>`).join('')}</ul>
        </div>
      </div>

      <div class="r-section">
        <div class="r-section-title">技术能力</div>
        ${Object.entries(skills).map(([k,v]) => `<div class="r-skills-row"><span class="r-skills-label">${App.escapeHtml(k)}</span><span>${App.escapeHtml(v)}</span></div>`).join('')}
      </div>

      <div class="r-section">
        <div class="r-section-title">项目经历</div>
        ${projects.map(proj => `
          <div class="r-entry">
            <div class="r-entry-header">
              <span class="r-entry-title">${App.escapeHtml(proj.name)}</span>
              <span class="r-entry-date">${App.escapeHtml(proj.date)}</span>
            </div>
            <div class="r-entry-sub">${App.escapeHtml(proj.subtitle)}</div>
            <ul class="r-bullets">${(proj.points||[]).map(pt=>`<li>${App.escapeHtml(pt)}</li>`).join('')}</ul>
          </div>
        `).join('')}
      </div>

      <div class="r-section">
        <div class="r-section-title">经历</div>
        ${experience.map(exp => `
          <div class="r-entry">
            <div class="r-entry-header">
              <span class="r-entry-title">${App.escapeHtml(exp.title)} — ${App.escapeHtml(exp.company)}</span>
              <span class="r-entry-date">${App.escapeHtml(exp.date)}</span>
            </div>
            <ul class="r-bullets">${(exp.points||[]).map(pt=>`<li>${App.escapeHtml(pt)}</li>`).join('')}</ul>
          </div>
        `).join('')}
      </div>

      <div class="r-section r-self no-print">
        <div class="r-section-title">自我评价</div>
        <p>知识面广、元认知能力强，能快速上手新技术并清晰传达复杂内容。聚焦 <strong>AI 应用落地</strong>，坚信 AI 的价值在于<strong>解决真实场景中的具体问题</strong>，从个人知识管理到企业级协作架构。关注工程 trade-off（如 ReAct vs CoT 的成本/精度权衡）、Agent 稳定性与反馈闭环设计。Cortex 项目体现了我在<span style="color:var(--accent);font-weight:500">AI Agent 架构设计、知识工程管线、MCP 协议生态</span>方向的持续实践。</p>
        <p style="margin-top:6px">深度使用 Claude Code 作为日常开发环境，历史 AI 对话 tokens 消耗十亿级以上。具备出色的中英文表达能力，纯原创小说、剧本创作超 30 万字。待人以诚，责任意识强，善于在团队协作中调和矛盾、推动共识达成。</p>
      </div>
    </div>`;
  }
};

/** Agent 构建可视化页 */
const AgentBuild = {
  data: null,
  pipelineStep: 0,
  pipelineTimer: null,

  async init() {
    try {
      const resp = await fetch('/data/agent_architecture.json');
      this.data = await resp.json();
    } catch (e) {
      this.data = null;
    }
    this._renderLadder();
    this._renderPipeline();
  },

  // ── 五层阶梯 ──

  _renderLadder() {
    const container = document.getElementById('ladderCards');
    const detail = document.getElementById('ladderDetail');
    if (!this.data) {
      container.innerHTML = '<div class="card" style="padding:24px;">无法加载架构数据</div>';
      return;
    }

    const colors = ['#6366f1','#8b5cf6','#a855f7','#d946ef','#ec4899'];
    this.data.layers.forEach((layer, i) => {
      const card = document.createElement('div');
      card.className = 'ladder-card card';
      card.style.borderLeft = `4px solid ${colors[i]}`;
      card.innerHTML = `
        <div class="ladder-num" style="background:${colors[i]}">${layer.level}</div>
        <div class="ladder-title">${layer.name}</div>
        <div class="ladder-brief">${layer.desc}</div>
      `;
      card.onclick = () => {
        document.querySelectorAll('.ladder-card').forEach(c => c.classList.remove('active'));
        card.classList.add('active');
        this._showLadderDetail(layer, colors[i]);
      };
      container.appendChild(card);
    });

    // Default: show first
    if (this.data.layers.length > 0) {
      container.children[0].classList.add('active');
      this._showLadderDetail(this.data.layers[0], colors[0]);
    }
  },

  _showLadderDetail(layer, color) {
    const detail = document.getElementById('ladderDetail');
    const items = layer.ours.map(s => `<li>${s}</li>`).join('');
    detail.innerHTML = `
      <h3 style="color:${color};margin-bottom:12px;">${layer.name} — 我们的实现</h3>
      <p style="color:var(--text-secondary);margin-bottom:16px;">${layer.desc}</p>
      <ul style="padding-left:20px;line-height:2;">${items}</ul>
    `;
  },

  // ── 管道动画 ──

  _renderPipeline() {
    const track = document.getElementById('pipelineTrack');
    if (!this.data) {
      track.innerHTML = '<div class="card" style="padding:24px;">无法加载管道数据</div>';
      return;
    }

    track.innerHTML = this.data.pipeline.map((p, i) => `
      <div class="pipe-node" id="pipeNode${i}">
        <div class="pipe-icon">${p.icon}</div>
        <div class="pipe-name">${p.name}</div>
        <div class="pipe-desc">${p.desc}</div>
      </div>
      ${i < this.data.pipeline.length - 1 ? '<div class="pipe-arrow" id="pipeArrow' + i + '">→</div>' : ''}
    `).join('');

    // 初始全部 dim
    document.querySelectorAll('.pipe-node').forEach(n => n.classList.add('dim'));

    document.getElementById('pipelinePlay').onclick = () => this._autoPlay();
    document.getElementById('pipelineStep').onclick = () => this._stepForward();
    document.getElementById('pipelineReset').onclick = () => this._resetPipeline();
  },

  _autoPlay() {
    this._resetPipeline();
    this.pipelineStep = 0;
    const total = this.data.pipeline.length;
    const playBtn = document.getElementById('pipelinePlay');
    playBtn.disabled = true;
    playBtn.textContent = '⏸ 播放中...';

    const highlight = () => {
      if (this.pipelineStep > 0) {
        // light previous arrow
        const prevArrow = document.getElementById('pipeArrow' + (this.pipelineStep - 1));
        if (prevArrow) prevArrow.classList.add('active');
      }
      const node = document.getElementById('pipeNode' + this.pipelineStep);
      if (node) node.classList.remove('dim');

      this.pipelineStep++;
      if (this.pipelineStep < total) {
        this.pipelineTimer = setTimeout(highlight, 800);
      } else {
        playBtn.textContent = '▶ 自动演示';
        playBtn.disabled = false;
      }
    };
    highlight();
  },

  _stepForward() {
    if (this.pipelineTimer) { clearTimeout(this.pipelineTimer); this.pipelineTimer = null; }
    document.getElementById('pipelinePlay').textContent = '▶ 自动演示';
    document.getElementById('pipelinePlay').disabled = false;

    const total = this.data.pipeline.length;
    if (this.pipelineStep >= total) return;

    if (this.pipelineStep > 0) {
      const prevArrow = document.getElementById('pipeArrow' + (this.pipelineStep - 1));
      if (prevArrow) prevArrow.classList.add('active');
    }
    const node = document.getElementById('pipeNode' + this.pipelineStep);
    if (node) node.classList.remove('dim');
    this.pipelineStep++;
  },

  _resetPipeline() {
    if (this.pipelineTimer) { clearTimeout(this.pipelineTimer); this.pipelineTimer = null; }
    this.pipelineStep = 0;
    document.getElementById('pipelinePlay').textContent = '▶ 自动演示';
    document.getElementById('pipelinePlay').disabled = false;
    document.querySelectorAll('.pipe-node').forEach(n => n.classList.add('dim'));
    document.querySelectorAll('.pipe-arrow').forEach(a => a.classList.remove('active'));
  }
};

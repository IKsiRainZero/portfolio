/**
 * Dashboard Module — stats cards, weak areas, study plan, continue-last
 * Depends on: App (app.js)
 */
const Dashboard = {
  _currentSnapshot: null,

  async init() {
    await Promise.all([
      this.loadSRSStats(),
      this.loadDashboardData(),
      this.loadStudyPlan(),
      this.loadTokenStats()
    ]);
    await this.loadInsight();
    this.checkSourceTraceReminder();
    this.setupSourceTraceListeners();
  },

  async loadInsight() {
    // Collect current snapshot from already-loaded data
    var mcq = parseInt(document.getElementById('statMcq')?.textContent || '0');
    var code = parseInt(document.getElementById('statCode')?.textContent || '0');
    var flash = parseInt(document.getElementById('statFlash')?.textContent || '0');
    var interview = parseInt(document.getElementById('statInterview')?.textContent || '0');
    var total = parseInt(document.getElementById('statTotal')?.textContent || '0');
    var streak = parseInt(document.getElementById('statStreak')?.textContent || '0');
    var due = parseInt(document.getElementById('srsDue')?.textContent || '0');

    var weakEl = document.getElementById('weakAreas');
    var weakTopics = [];
    if (weakEl) {
      var lis = weakEl.querySelectorAll('li span:first-child');
      lis.forEach(function(s) { weakTopics.push(s.textContent.trim()); });
    }

    this._currentSnapshot = {
      total_exercises: total,
      mcq_total: mcq, code_total: code,
      flash_total: flash, interview_total: interview,
      streak_days: streak, due_today: due,
      weak_count: weakTopics.length,
      weak_areas: weakTopics.slice(0, 5),
    };

    // Try to get insight from server
    var lastSnapshot = {};
    try {
      lastSnapshot = JSON.parse(localStorage.getItem('dashboard_snapshot') || '{}');
    } catch(e) { lastSnapshot = {}; }

    try {
      var resp = await fetch('/api/agent/dashboard-insight', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ last_snapshot: lastSnapshot })
      });
      var data = await resp.json();
      if (data.insight) {
        this.renderInsight(data.insight);
        document.getElementById('dashboardInsight').style.display = 'block';
        localStorage.setItem('dashboard_snapshot', JSON.stringify(data.snapshot || this._currentSnapshot));
      }
    } catch(e) {
      // Server offline — try cached insight or hide
      var cached = localStorage.getItem('dashboard_insight_cached');
      if (cached) {
        this.renderInsight(cached);
        document.getElementById('dashboardInsight').style.display = 'block';
      }
    }
  },

  renderInsight(text) {
    // Cache the raw text for offline reuse
    try { localStorage.setItem('dashboard_insight_cached', text); } catch(e) {}

    // Parse [text](url) markdown links
    var html = App.escapeHtml(text)
      .replace(/\[([^\]]+)\]\(\/([^)]+)\)/g, '<a href="/$2" style="color:var(--accent);font-weight:500;text-decoration:underline;white-space:nowrap">$1</a>')
      .replace(/\n/g, '<br>');
    document.getElementById('insightText').innerHTML = html;
  },

  async loadSRSStats() {
    try {
      const resp = await fetch('/api/srs/stats');
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const s = await resp.json();
      document.getElementById('srsDue').textContent = s.due_today ?? 0;
      document.getElementById('srsTracked').textContent = s.total_cards_tracked ?? 0;
      document.getElementById('srsReviews').textContent = s.total_reviews ?? 0;
      document.getElementById('srsAvg').textContent = s.avg_rating ? s.avg_rating.toFixed(1) : '-';
    } catch(e) {
      document.getElementById('srsAvg').textContent = '--';
    }
  },

  async loadDashboardData() {
    try {
      const resp = await fetch('/api/progress/dashboard');
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const d = await resp.json();

      // Stats
      document.getElementById('statMcq').textContent = d.mcq_total ?? 0;
      document.getElementById('statCode').textContent = d.code_total ?? 0;
      document.getElementById('statFlash').textContent = d.flash_total ?? 0;
      document.getElementById('statInterview').textContent = d.interview_total ?? 0;
      document.getElementById('statStreak').textContent = (d.streak_days || 0) + ' 天';
      document.getElementById('statTotal').textContent = d.total_exercises ?? 0;

      // Weak areas
      this.renderWeakAreas(d.weak_areas || []);

      // Continue last
      this.renderContinueLast(d.last_active);

      // Recent activity
      this.renderRecent(d.recent || []);
    } catch(e) {
      document.getElementById('weakAreas').innerHTML =
        '<p style="font-size:12px;color:var(--text2);text-align:center;padding:20px">数据加载中...</p>';
    }
  },

  renderWeakAreas(weak) {
    const el = document.getElementById('weakAreas');
    if (!el) return;
    if (!weak.length) {
      el.innerHTML = '<p style="font-size:12px;color:var(--text2);text-align:center;padding:20px">暂无薄弱环节，继续加油！</p>';
      return;
    }
    el.innerHTML = '<ul class="review-list">' + weak.slice(0, 6).map(function(w) {
      const pct = parseInt(w.accuracy) || 0;
      const color = pct >= 70 ? 'var(--green)' : pct >= 40 ? '#d97706' : 'var(--red)';
      return '<li onclick="App.askAI(\'' + App.escapeHtml(w.topic) + '\',\'正确率' + w.accuracy + '%，帮我针对性练习\')" style="cursor:pointer">' +
        '<span>' + App.escapeHtml(w.topic) + '</span>' +
        '<span style="color:' + color + ';font-size:11px">' + w.accuracy + '%</span>' +
        '<div class="progress-bar" style="margin-top:4px"><div class="progress-fill" style="width:' + pct + '%;background:' + color + '"></div></div>' +
      '</li>';
    }).join('') + '</ul>';
  },

  renderContinueLast(last) {
    const el = document.getElementById('continueLast');
    if (!el) return;
    if (!last) {
      el.style.display = 'none';
      return;
    }
    el.style.display = 'block';
    el.innerHTML = '<a href="' + last.page + '" class="quick-card" style="display:block">' +
      '<h4>继续上次</h4>' +
      '<p>' + App.escapeHtml(last.label) + ' — ' + App.escapeHtml(last.topic || '未分类') + '</p>' +
      '<span style="font-size:10px;color:var(--text2)">' + (last.timestamp ? last.timestamp.slice(0, 16) : '') + '</span>' +
    '</a>';
  },

  renderRecent(recent) {
    const el = document.getElementById('recentActivity');
    if (!el) return;
    if (!recent.length) {
      el.innerHTML = '<p style="font-size:11px;color:var(--text2);padding:8px">暂无活动记录</p>';
      return;
    }
    const typeLabels = { mcq: '选择题', code: '编程', flashcard: '闪卡', short_answer: '简答', mock_interview: '面试', feynman: '费曼' };
    el.innerHTML = recent.slice(0, 5).map(function(r) {
      const label = typeLabels[r.type] || r.type || '练习';
      const date = (r.timestamp || '').slice(0, 16);
      const correct = r.correct !== undefined ? (r.correct ? ' ✓' : ' ✗') : '';
      const score = r.score !== undefined ? ' ' + r.score + '/10' : '';
      return '<li style="font-size:11px;padding:4px 0;border-bottom:1px solid var(--border);color:var(--text2)">' +
        '<span style="color:var(--accent)">' + label + '</span>' +
        (r.topic ? ' — ' + App.escapeHtml(r.topic) : '') + correct + score +
        '<span style="float:right;font-size:10px">' + date + '</span></li>';
    }).join('');
  },

  async loadStudyPlan() {
    try {
      const resp = await fetch('/api/srs/plan');
      if (!resp.ok) throw new Error('HTTP ' + resp.status);
      const plan = await resp.json();
      let html = '';
      if (plan.review_due > 0 && plan.review_today && plan.review_today.length > 0) {
        html += '<p style="font-size:12px;color:var(--text2);margin-bottom:8px">待复习 ' + plan.review_due + ' 张 · 已学 ' + (plan.reviewed_cards || 0) + '/' + (plan.total_cards || 0) + '</p>';
        html += '<ul class="review-list">';
        plan.review_today.slice(0, 5).forEach(function(c) {
          html += '<li onclick="location.href=\'/trainer\'" style="cursor:pointer">' +
            App.escapeHtml(c.concept || '') +
            ' <span style="font-weight:400;color:var(--text2);font-size:10px">评分 ' + (c.avg_rating || '-') + '/5</span></li>';
        });
        html += '</ul>';
      } else if (plan.review_due > 0) {
        html += '<p style="font-size:12px;color:var(--text2);text-align:center;padding:20px">有 ' + plan.review_due + ' 张待复习卡片</p>';
      } else {
        html += '<p style="font-size:12px;color:var(--text2);text-align:center;padding:20px">今天没有待复习卡片</p>';
      }
      if (plan.new_today && plan.new_today.length > 0) {
        html += '<p style="font-size:11px;color:var(--text2);margin:12px 0 4px">推荐新卡:</p>';
        plan.new_today.slice(0, 3).forEach(function(c) {
          html += '<span class="badge badge-topic" style="margin:2px;cursor:pointer" onclick="location.href=\'/trainer\'">' + App.escapeHtml(c.concept || '') + '</span>';
        });
      }
      document.getElementById('studyPlan').innerHTML = html;
    } catch(e) {
      document.getElementById('studyPlan').innerHTML =
        '<p style="font-size:11px;color:var(--text2);text-align:center;padding:20px">计划加载失败</p>';
    }
  },

  async loadTokenStats() {
    try {
        const cfgResp = await fetch('/api/tokens/config');
        const cfg = await cfgResp.json();
        if (!cfg.available) {
            document.getElementById('tokenUnavailable').style.display = 'block';
            document.getElementById('tokenStats').style.display = 'none';
            return;
        }

        const resp = await fetch('/api/tokens/dashboard?days=30');
        if (!resp.ok) throw new Error('HTTP ' + resp.status);
        const d = await resp.json();

        const fmtNum = (n) => {
            if (n === null || n === undefined) return '-';
            if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
            if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
            return n.toString();
        };

        document.getElementById('tokenToday').textContent = fmtNum(d.today_tokens);
        document.getElementById('tokenMonth').textContent = fmtNum(d.month_tokens);
        document.getElementById('tokenCost').textContent =
            d.month_cost_usd != null ? '$' + d.month_cost_usd.toFixed(2) : '-';
        document.getElementById('tokenCalls').textContent = d.agent_calls || 0;
    } catch(e) {
        document.getElementById('tokenUnavailable').style.display = 'block';
        document.getElementById('tokenStats').style.display = 'none';
    }
  },

  checkSourceTraceReminder() {
    const key = 'source_trace_last_visit';
    const now = Date.now();
    const last = parseInt(localStorage.getItem(key) || '0', 10);
    const daysSince = last ? (now - last) / (1000 * 60 * 60 * 24) : 999;

    if (!last || daysSince > 7) {
      const el = document.getElementById('stReminder');
      if (el) el.style.display = 'block';
    }
  },

  setupSourceTraceListeners() {
    document.addEventListener('click', function(e) {
      if (e.target.closest('a[href="/source-trace"]')) {
        localStorage.setItem('source_trace_last_visit', Date.now().toString());
      }
    });
  },
};

document.addEventListener('DOMContentLoaded', function() { Dashboard.init(); });

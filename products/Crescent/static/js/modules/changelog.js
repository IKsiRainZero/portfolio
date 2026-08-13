/**
 * Changelog Page Module — version history from /data/changelog.json
 * Depends on: App (app.js)
 */
const ChangelogPage = {
  async init() {
    const root = document.getElementById('changelogRoot');
    if (!root) return;

    try {
      const resp = await fetch('/data/changelog.json');
      const data = await resp.json();
      this.render(root, data);
    } catch (e) {
      root.innerHTML = App.renderEmpty('加载失败', '请确认服务器正在运行');
    }
  },

  render(root, data) {
    const versions = data.versions || [];
    if (!versions.length) {
      root.innerHTML = App.renderEmpty('暂无更新记录', '');
      return;
    }

    let html = '';
    versions.forEach((v, vi) => {
      const isLatest = vi === 0;

      html += '<div class="card" style="margin-bottom:16px">';
      html += '<div class="card-header" style="display:flex;align-items:center;gap:8px">';
      html += '<span class="badge" style="background:var(--accent);color:#fff;font-size:12px">v' + App.escapeHtml(v.version) + '</span>';
      html += '<span style="font-weight:600">' + App.escapeHtml(v.title) + '</span>';
      if (isLatest) {
        html += '<span class="badge" style="background:var(--green);color:#fff;font-size:10px">最新</span>';
      }
      html += '</div>';

      html += '<div style="padding:12px 16px">';
      html += '<div style="font-size:12px;color:var(--text2);margin-bottom:10px">' + App.escapeHtml(v.date) + '</div>';
      html += '<p style="font-size:13px;color:var(--text);margin-bottom:12px">' + App.escapeHtml(v.summary) + '</p>';

      (v.sections || []).forEach(function(sec) {
        html += '<div style="margin-bottom:10px">';
        html += '<div style="font-size:13px;font-weight:600;margin-bottom:4px;display:flex;align-items:center;gap:4px">';
        html += '<span>' + ChangelogPage._icon(sec.icon) + '</span>';
        html += '<span>' + App.escapeHtml(sec.title) + '</span>';
        html += '</div>';

        (sec.items || []).forEach(function(item) {
          const tagColors = {
            'new': 'background:#dcfce7;color:#166534',
            'improved': 'background:#dbeafe;color:#1e40af',
            'fixed': 'background:#fef3c7;color:#92400e'
          };
          const tagStyle = tagColors[item.tag] || 'background:var(--bg);color:var(--text2)';
          const tagLabel = { 'new': '新增', 'improved': '优化', 'fixed': '修复' }[item.tag] || item.tag;

          html += '<div style="font-size:12px;padding:3px 0 3px 20px;display:flex;align-items:baseline;gap:6px">';
          html += '<span style="' + tagStyle + ';font-size:10px;padding:0 5px;border-radius:3px;white-space:nowrap">' + tagLabel + '</span>';
          html += '<span style="color:var(--text)">' + App.escapeHtml(item.text) + '</span>';
          html += '</div>';
        });

        html += '</div>';
      });

      html += '</div>';
      html += '</div>';
    });

    html += '<div style="text-align:center;font-size:11px;color:var(--text2);padding:8px">';
    html += '更新日志基于 <code>data/changelog.json</code>，离线也可查看。';
    html += '</div>';

    root.innerHTML = html;
  },

  _icon(name) {
    const icons = {
      'zap': '⚡',
      'search': '🔍',
      'book-open': '📖',
      'layout': '🎨',
      'database': '🖾',
      'trending-up': '📈',
      'rocket': '🚀'
    };
    return icons[name] || '•';
  }
};

App.ready(function() { ChangelogPage.init(); });

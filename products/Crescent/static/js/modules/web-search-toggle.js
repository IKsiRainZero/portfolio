// Shared web search toggle — used by home, classroom, interview pages
window.WebSearchToggle = {
  _enabled: true,

  init: function(opts) {
    opts = opts || {};
    this._btnId = opts.btnId || 'wsToggleBtn';
    this._onChange = opts.onChange || null;
    this._loadState();
  },

  _loadState: function() {
    var self = this;
    fetch('/api/config/settings')
      .then(function(r) { return r.json(); })
      .then(function(d) {
        self._enabled = d.settings.web_search_enabled !== false;
        self._updateBtn();
      })
      .catch(function() { self._enabled = true; });
  },

  toggle: function() {
    this._enabled = !this._enabled;
    this._updateBtn();
    fetch('/api/config/settings', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({web_search_enabled: this._enabled})
    }).catch(function(){});
    if (typeof App !== 'undefined') App.trackImpression('feature_use', {feature: 'web_search_toggle', enabled: this._enabled});
    if (this._onChange) this._onChange(this._enabled);
  },

  isEnabled: function() { return this._enabled; },

  _updateBtn: function() {
    var btn = document.getElementById(this._btnId);
    if (!btn) return;
    if (this._enabled) {
      btn.className = 'ws-toggle on';
      btn.title = '联网搜索: 开 — 点击关闭';
    } else {
      btn.className = 'ws-toggle off';
      btn.title = '联网搜索: 关 — 点击开启';
    }
  }
};

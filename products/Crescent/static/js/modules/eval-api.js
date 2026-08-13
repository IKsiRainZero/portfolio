/**
 * eval-api.js — 评估 API 请求层
 * 唯一允许调用 fetch 的模块。所有函数返回 Promise。
 * 命名空间: window.EvalAPI
 */
window.EvalAPI = (function() {
  const ADMIN_TOKEN = document.querySelector('meta[name="admin-token"]')
    ? document.querySelector('meta[name="admin-token"]').content
    : '';

  async function _fetch(path, options) {
    const opts = Object.assign({}, options || {}, {
      headers: Object.assign({}, (options || {}).headers || {}, {
        'X-Admin-Token': ADMIN_TOKEN,
      }),
    });
    const res = await fetch(path, opts);
    if (!res.ok) {
      const body = await res.json().catch(function() { return {}; });
      throw new Error(body.error || 'API error ' + res.status);
    }
    return res.json();
  }

  function fetchWithTimeout(path, options, timeoutMs) {
    return new Promise(function(resolve, reject) {
      const timer = setTimeout(function() {
        reject(new Error('timeout'));
      }, timeoutMs || 10000);
      _fetch(path, options).then(function(data) {
        clearTimeout(timer);
        resolve(data);
      }).catch(function(err) {
        clearTimeout(timer);
        reject(err);
      });
    });
  }

  function fetchSummary() {
    return fetchWithTimeout('/api/eval/summary', null, 3000).catch(function(err) {
      if (err.message === 'timeout') {
        console.warn('[Eval] /api/eval/summary 响应超过 3 秒 — 请检查数据量或后端性能');
      }
      throw err;
    });
  }
  function fetchConfigs()        { return _fetch('/api/eval/configs'); }
  function fetchTrend(configId, days) { return _fetch('/api/eval/trend/' + configId + '?days=' + (days || 30)); }
  function fetchTraces(limit, windowHours) { return _fetch('/api/eval/traces?limit=' + (limit || 50) + '&window_hours=' + (windowHours || 24)); }
  function fetchTrace(id)        { return _fetch('/api/eval/traces/' + id); }
  function fetchSuggestions(status, severity) {
    var qs = [];
    if (status) qs.push('status=' + status);
    if (severity) qs.push('severity=' + severity);
    return _fetch('/api/eval/suggestions' + (qs.length ? '?' + qs.join('&') : ''));
  }
  function fetchMetaResults()    { return _fetch('/api/eval/meta/results'); }
  function applySuggestion(id)   { return _fetch('/api/eval/suggestions/' + id + '/apply', { method: 'POST' }); }
  function rejectSuggestion(id)  { return _fetch('/api/eval/suggestions/' + id + '/reject', { method: 'POST' }); }
  function fetchTraceChain(id)   { return _fetch('/api/eval/trace-chain/' + id); }
  function fetchProbes()         { return _fetch('/api/eval/probes'); }

  // ── Beacon (前端行为追踪) ──
  function sendBeacon(eventType, panelId) {
    fetch('/api/eval/beacon', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-Admin-Token': ADMIN_TOKEN,
      },
      body: JSON.stringify({
        event_type: eventType,
        panel_id: panelId,
        timestamp: Date.now(),
      }),
      keepalive: false,
    }).catch(function() {});
  }

  function toggleShadow(enable) {
    return _fetch('/api/eval/shadow/toggle', {
      method: 'POST',
      body: JSON.stringify({ enable: enable }),
    });
  }

  function fetchShadowStatus() {
    return _fetch('/api/eval/shadow/status');
  }

  return {
    fetchSummary: fetchSummary,
    fetchConfigs: fetchConfigs,
    fetchTrend: fetchTrend,
    fetchTraces: fetchTraces,
    fetchTrace: fetchTrace,
    fetchSuggestions: fetchSuggestions,
    fetchMetaResults: fetchMetaResults,
    applySuggestion: applySuggestion,
    rejectSuggestion: rejectSuggestion,
    fetchTraceChain: fetchTraceChain,
    fetchProbes: fetchProbes,
    sendBeacon: sendBeacon,
    toggleShadow: toggleShadow,
    fetchShadowStatus: fetchShadowStatus,
  };
})();

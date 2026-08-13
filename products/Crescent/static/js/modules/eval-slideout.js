/**
 * eval-slideout — 建议滑出面板组件
 *
 * 职责: 滑出面板的打开、关闭、渲染（含历史事件、指标变化、元数据）
 * 依赖: EvalUI.escapeHtml(), EvalAPI.fetchSuggestions()
 * 接口: window.EvalSlideOut = { show(sug), close(), bindClicks() }
 */
(function() {
  'use strict';

  function show(sug) {
    var panel = document.getElementById('eval-slideout');
    var mask = document.getElementById('eval-slideout-mask');
    if (!panel || !mask) return;

    EvalAPI.sendBeacon('slideout_open', 'suggestion_detail');

    var attr = sug.attribution_status || 'pending';
    var attrLabels = { attributed: '✔ 效果可归因', unattributable: '⚡ 无法归因', likely_failed: '⚠ 可能失败', pending: '⌛ 待验证' };
    var attrColors = { attributed: 'var(--success)', unattributable: 'var(--warning)', likely_failed: 'var(--danger)', pending: 'var(--text2)' };

    var deltaStr = '';
    if (sug.effect_score_delta !== null && sug.effect_score_delta !== undefined) {
      var d = sug.effect_score_delta;
      deltaStr = '<span style="color:' + (d >= 0 ? 'var(--success)' : 'var(--danger)') + '">Δ' + (d >= 0 ? '+' : '') + d.toFixed(2) + '</span>';
    }

    var html = '<div style="padding:16px">' +
      '<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">' +
        '<h3 style="margin:0;font-size:16px">建议详情</h3>' +
        '<button style="border:none;background:none;font-size:20px;cursor:pointer;line-height:1" onclick="EvalSlideOut.close()">&times;</button>' +
      '</div>' +
      '<div style="font-size:14px;margin-bottom:12px"><strong>' + EvalUI.withConceptTooltips(sug.description || sug.title || '') + '</strong></div>' +
      '<div style="margin-bottom:8px"><span class="badge">' + EvalUI.escapeHtml(sug.severity || '') + '</span>' +
      ' <span class="badge">' + EvalUI.escapeHtml(sug.category || '') + '</span></div>' +
      '<div style="font-size:13px;color:' + (attrColors[attr] || 'var(--text2)') + ';margin-bottom:4px">' + (attrLabels[attr] || attr) + ' ' + deltaStr + '</div>';

    // Delta details
    if (sug.delta_details && Object.keys(sug.delta_details).length > 0) {
      html += '<div style="margin-top:12px;padding:8px;background:var(--bg);border-radius:6px;font-size:12px">';
      html += '<div style="font-weight:600;margin-bottom:4px">指标变化</div>';
      Object.keys(sug.delta_details).forEach(function(k) {
        var v = sug.delta_details[k];
        html += '<div>' + EvalUI.escapeHtml(k) + ': <span style="color:' + (v >= 0 ? 'var(--success)' : 'var(--danger)') + '">' + (v >= 0 ? '+' : '') + v.toFixed(2) + '</span></div>';
      });
      html += '</div>';
    }

    // Baseline
    if (sug.baseline_scores && Object.keys(sug.baseline_scores).length > 0) {
      html += '<div style="margin-top:8px;font-size:12px;color:var(--text2)">基线: ';
      Object.keys(sug.baseline_scores).forEach(function(k) {
        var b = sug.baseline_scores[k];
        html += EvalUI.escapeHtml(k) + '=' + (typeof b === 'object' ? (b.value || 0).toFixed(2) : b.toFixed(2)) + ' ';
      });
      html += '</div>';
    }

    // History similar events (IDC constraint 4)
    if (sug.category) {
      html += '<div style="margin-top:16px;padding:12px;border-top:1px solid var(--border)">' +
        '<div style="font-size:13px;font-weight:600;color:var(--text2);margin-bottom:8px">📚 历史相似事件</div>' +
        '<div style="font-size:12px;color:var(--text2)">该类别（' + EvalUI.escapeHtml(sug.category) + '）的相关错误记录可在<a href="/knowledge" target="_blank">知识库</a>中查阅。</div>' +
      '</div>';
    }

    // Meta
    html += '<div style="margin-top:12px;font-size:11px;color:var(--text3)">';
    if (sug.created_at) html += '创建: ' + EvalUI.escapeHtml(sug.created_at) + ' | ';
    if (sug.applied_at) html += '采纳: ' + EvalUI.escapeHtml(sug.applied_at) + ' | ';
    if (sug.applied_commit) html += 'commit: ' + EvalUI.escapeHtml(sug.applied_commit.substring(0, 7));
    html += '</div>';

    // M2: 追溯链容器
    html += '<div id="slideout-trace-chain" style="margin-top:16px;padding:12px;border-top:1px solid var(--border)"></div>';

    html += '</div>';
    panel.innerHTML = html;
    panel.style.display = '';
    mask.style.display = '';

    // 异步加载追溯链
    if (sug.suggestion_id) {
      EvalAPI.fetchTraceChain(sug.suggestion_id).then(function(chainData) {
        var tc = document.getElementById('slideout-trace-chain');
        if (tc) {
          tc.innerHTML = '';
          tc.appendChild(EvalUI.renderTraceChainNarrative(chainData));
        }
      }).catch(function() {
        // 追溯链加载失败静默降级
      });
    }
  }

  function close() {
    var panel = document.getElementById('eval-slideout');
    var mask = document.getElementById('eval-slideout-mask');
    if (panel) panel.style.display = 'none';
    if (mask) mask.style.display = 'none';
  }

  function bindClicks() {
    document.querySelectorAll('.suggestion-item').forEach(function(el) {
      el.style.cursor = 'pointer';
      el.addEventListener('click', function() {
        var sid = el.getAttribute('data-id');
        if (!sid) return;
        EvalAPI.fetchSuggestions(null, null).then(function(res) {
          var sug = (res.suggestions || []).find(function(s) { return s.suggestion_id === sid; });
          if (sug) show(sug);
        });
      });
    });
  }

  window.EvalSlideOut = {
    show: show,
    close: close,
    bindClicks: bindClicks,
  };
})();

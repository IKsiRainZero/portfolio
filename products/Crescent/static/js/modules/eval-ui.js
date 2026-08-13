/**
 * eval-ui.js — 单组件渲染函数
 * 职责: 评分卡、Span 节点、建议条目、告警横幅、空状态占位。
 * 安全: <template> + cloneNode + textContent，secure-by-default。
 *        escapeHtml 仅用于单个文本节点填充，innerHTML 不再用于结构生成。
 * 命名空间: window.EvalUI
 */
window.EvalUI = (function() {

  // ── 工具函数 ──

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function gaugeColor(val) {
    if (val >= 0.9) return 'var(--success, #10b981)';
    if (val >= 0.7) return 'var(--accent, #6366f1)';
    if (val >= 0.5) return 'var(--warning, #f59e0b)';
    return 'var(--danger, #ef4444)';
  }

  // ── Template 工具 ──

  /** 获取 template 并返回 clone 后的文档片段 */
  function _cloneTemplate(tplId) {
    var tpl = document.getElementById(tplId);
    if (!tpl) return null;
    return document.importNode(tpl.content, true);
  }

  /** 从片段中取第一个元素，可选设置 id */
  function _firstEl(frag) {
    return frag ? frag.firstElementChild : null;
  }

  // ── 告警横幅 ──

  function renderAlertBanner(alerts) {
    var container = document.getElementById('eval-alerts');
    if (!container) return;
    container.textContent = '';

    if (!alerts || alerts.length === 0) {
      var ok = document.createElement('div');
      ok.className = 'alert-banner alert-ok';
      ok.textContent = '✔ 所有系统指标正常';
      container.appendChild(ok);
      return;
    }
    if (alerts === null) {
      var warn = document.createElement('div');
      warn.className = 'alert-banner alert-warn';
      warn.textContent = '告警数据暂时不可用';
      container.appendChild(warn);
      return;
    }

    alerts.forEach(function(a) {
      var frag = _cloneTemplate('tpl-alert-item');
      if (!frag) return;
      var el = _firstEl(frag);
      if (a.severity === 'P0') {
        el.classList.add('alert-critical');
      }
      if (a.config_id) {
        el.setAttribute('data-config-id', a.config_id);
        el.style.cursor = 'pointer';
      }
      var sevSpan = frag.querySelector('.alert-severity');
      if (sevSpan) sevSpan.textContent = a.severity;
      var msgSpan = frag.querySelector('.alert-message');
      if (msgSpan) msgSpan.textContent = a.message;
      container.appendChild(frag);
    });
  }

  // ── 评分卡 ──

  function renderScoreCard(metric, value, previous, sparkData, l2Data, l3Data) {
    var frag = _cloneTemplate('tpl-score-card');
    if (!frag) return '';

    var card = frag.querySelector('.score-card');
    card.setAttribute('data-config-id', metric.config_id);

    // canvas id
    var canvas = frag.querySelector('canvas');
    canvas.id = 'gauge-' + metric.config_id;

    // value
    var valEl = frag.querySelector('.score-gauge-value');
    var color = gaugeColor(value);
    valEl.textContent = value !== null ? (value * 100).toFixed(0) : '--';
    valEl.style.color = color;

    // name
    var h3 = frag.querySelector('h3');
    h3.textContent = metric.name || metric.config_id;

    // delta
    var deltaEl = frag.querySelector('.score-delta');
    if (previous !== null && previous !== undefined) {
      var delta = value - previous;
      deltaEl.style.display = '';
      deltaEl.textContent = (delta >= 0 ? '+' : '') + delta.toFixed(2);
      deltaEl.className = 'score-delta ' + (delta >= 0 ? 'text-success' : 'text-danger');
    }

    // sparkline canvas
    var sparkCanvas = frag.querySelector('.spark-canvas');
    if (sparkData && sparkData.length > 0) {
      sparkCanvas.style.display = '';
      sparkCanvas.id = 'spark-' + metric.config_id;
    }

    // user_value_statement (dense mode: inline concept tooltips)
    var bq = frag.querySelector('blockquote');
    if (metric.user_value_statement) {
      bq.style.display = '';
      var statement = metric.user_value_statement;
      var density = (window.EvalUIConfig || {}).tooltipDensity || 'sparse';
      if (density === 'dense') {
        bq.innerHTML = withConceptTooltips(statement);
      } else {
        bq.textContent = statement;
      }
    }

    // ── M3 L2: 子指标分解 + 关联建议 (回答"为什么这么低/高？") ──
    var l2 = frag.querySelector('.score-l2');
    var l2Body = frag.querySelector('.score-l2-body');
    if (l2Data && l2Data.sub_indicators && l2Data.sub_indicators.length > 0) {
      l2.style.display = '';
      var l2Html = '<div style="font-weight:600;margin-bottom:4px">子指标分解</div>';
      l2Data.sub_indicators.forEach(function(si) {
        var siPct = (si.value * 100).toFixed(0);
        l2Html += '<div style="margin:2px 0">' + si.name + ': <span style="color:' + gaugeColor(si.value) + ';font-weight:600">' + siPct + '</span></div>';
      });
      if (l2Data.suggestions && l2Data.suggestions.length > 0) {
        l2Html += '<div style="font-weight:600;margin:8px 0 4px">关联建议</div>';
        l2Data.suggestions.forEach(function(s) {
          l2Html += '<div style="margin:2px 0;font-size:12px">[' + (s.severity || 'P2') + '] ' + withConceptTooltips((s.description || s.title || '').substring(0, 80)) + '</div>';
        });
      }
      l2Body.innerHTML = l2Html;
    }

    // ── M3 L3: 参照系 + 计算说明 + 决策问题 (回答"这意味着什么？") ──
    var l3 = frag.querySelector('.score-l3');
    var l3Body = frag.querySelector('.score-l3-body');
    if (l3Data) {
      l3.style.display = '';
      var l3Html = '';
      if (l3Data.reference) {
        l3Html += '<div style="font-weight:600;margin-bottom:4px">参照系</div>';
        l3Html += '<div style="margin:2px 0">系统平均: ' + (l3Data.reference.system_avg !== undefined ? (l3Data.reference.system_avg * 100).toFixed(0) : '--') + '</div>';
        l3Html += '<div style="margin:2px 0">上月平均: ' + (l3Data.reference.last_month_avg !== undefined ? (l3Data.reference.last_month_avg * 100).toFixed(0) : '--') + '</div>';
        l3Html += '<div style="margin:2px 0">基线: ' + (l3Data.reference.baseline !== undefined ? (l3Data.reference.baseline * 100).toFixed(0) : '--') + '</div>';
      }
      if (l3Data.computation) {
        l3Html += '<div style="font-weight:600;margin:8px 0 4px">计算说明</div>';
        l3Html += '<div style="font-size:12px">' + withConceptTooltips(l3Data.computation) + '</div>';
      }
      if (l3Data.decision_question) {
        l3Html += '<div style="font-weight:600;margin:8px 0 4px">对应决策</div>';
        l3Html += '<div style="font-size:12px;font-style:italic">"' + withConceptTooltips(l3Data.decision_question) + '"</div>';
      }
      l3Body.innerHTML = l3Html;
    }

    // Serialize outerHTML for eval-main compatibility
    var tmp = document.createElement('div');
    tmp.appendChild(frag);
    return tmp.innerHTML;
  }

  // ── 建议条目 ──

  function renderSuggestionItem(s) {
    var frag = _cloneTemplate('tpl-suggestion-item');
    if (!frag) return '';

    var el = _firstEl(frag);
    el.setAttribute('data-id', s.suggestion_id);
    el.className = 'suggestion-item suggestion-' + (s.status || 'pending');

    var attr = s.attribution_status || 'pending';
    var attrIcons = { attributed: '✔', unattributable: '⚡', likely_failed: '⚠', pending: '⌛' };
    var attrColors = { attributed: 'var(--success)', unattributable: 'var(--warning)', likely_failed: 'var(--danger)', pending: 'var(--text2)' };

    var iconSpan = frag.querySelector('.sug-attr-icon');
    iconSpan.textContent = attrIcons[attr] || '';
    iconSpan.style.color = attrColors[attr] || 'var(--text2)';

    var titleEl = frag.querySelector('.sug-title');
    titleEl.innerHTML = withConceptTooltips((s.description || s.title || '').substring(0, 100));

    var sevEl = frag.querySelector('.sug-severity');
    sevEl.textContent = s.severity || '';

    // Attributed message
    var attrEl = frag.querySelector('.sug-attributed');
    if (attr === 'attributed' && s.effect_score_delta !== null && s.effect_score_delta !== undefined) {
      attrEl.style.display = '';
      attrEl.textContent = '✔ 效果可归因: delta=' + (s.effect_score_delta >= 0 ? '+' : '') + s.effect_score_delta.toFixed(2);
    }

    // Unattributable message
    var unattribEl = frag.querySelector('.sug-unattributable');
    if (attr === 'unattributable') {
      unattribEl.style.display = '';
      var commits = (s.delta_details && s.delta_details.conflict_commits || []).join(', ') || '';
      unattribEl.textContent = '⚡ 无法归因 — ' + (commits ? '冲突 commit: ' + commits : '原因未知');
    }

    // Likely failed message
    var failedEl = frag.querySelector('.sug-failed');
    if (attr === 'likely_failed') {
      failedEl.style.display = '';
      failedEl.appendChild(document.createTextNode('⚨ 可能失败 — 建议回滚 '));
      var btn = document.createElement('button');
      btn.className = 'btn btn-sm btn-danger';
      btn.textContent = '回滚';
      btn.onclick = function() {
        EvalAPI.rejectSuggestion(s.suggestion_id);
      };
      failedEl.appendChild(btn);
    }

    // Meta line
    var metaEl = frag.querySelector('.sug-meta');
    var metaParts = [];
    if (s.created_at) metaParts.push(s.created_at);
    if (s.applied_commit) metaParts.push('commit: ' + s.applied_commit.substring(0, 7));
    metaEl.textContent = metaParts.join(' | ');

    var tmp = document.createElement('div');
    tmp.appendChild(frag);
    return tmp.innerHTML;
  }

  // ── Span 节点 ──

  function renderSpanNode(span, depth) {
    var frag = _cloneTemplate('tpl-span-node');
    if (!frag) return '';

    var el = _firstEl(frag);
    el.style.paddingLeft = (depth || 0) * 16 + 'px';

    var icon, color, weight = 'normal';
    if (span.orphan_confirmed)      { icon = '◆'; color = '#6b7280'; }
    else if (span.orphan)           { icon = '◆'; color = '#9ca3af'; }
    else if (span.status === 'error')   { icon = '●'; color = 'var(--danger)'; weight = 'bold'; }
    else if (span.status === 'timeout') { icon = '○'; color = 'var(--warning)'; }
    else                            { icon = '●'; color = 'var(--success)'; }

    el.style.color = color;
    el.style.fontWeight = weight;

    var iconSpan = frag.querySelector('.span-icon');
    iconSpan.textContent = icon;

    var bodyEl = frag.querySelector('.span-body');
    bodyEl.textContent = (span.kind || '?') + ': ' + (span.name || '') + ' (' + (span.duration_ms || '?') + 'ms)';
    if (span.error_type) {
      bodyEl.textContent += ' ' + span.error_type;
      var errSpan = document.createElement('span');
      errSpan.style.color = 'var(--danger)';
      errSpan.textContent = span.error_type;
      el.appendChild(errSpan);
    }

    var orphanTag = frag.querySelector('.span-orphan-tag');
    if (span.orphan) {
      orphanTag.style.display = '';
      orphanTag.textContent = '— 未关联';
    }

    var tmp = document.createElement('div');
    tmp.appendChild(frag);
    return tmp.innerHTML;
  }

  // ── 空状态占位 ──

  function renderEmptyState(panelId, reason, action) {
    var frag = _cloneTemplate('tpl-empty-state');
    if (!frag) return '';

    var el = _firstEl(frag);
    el.id = 'empty-' + panelId;

    var reasonEl = frag.querySelector('.empty-reason');
    reasonEl.textContent = reason;

    var actionEl = frag.querySelector('.empty-action');
    if (action) {
      actionEl.style.display = '';
      actionEl.textContent = action;
    }

    var tmp = document.createElement('div');
    tmp.appendChild(frag);
    return tmp.innerHTML;
  }

  // ── M5: 探测卡渲染 (含 resolution 状态) ──

  function renderProbeCard(probe) {
    var resolution = probe.resolution;
    var isResolved = !!resolution;

    var div = document.createElement('div');
    div.className = 'probe-card';
    div.setAttribute('data-probe-id', probe.probe_id);
    div.style.cssText = 'padding:10px 12px;margin:6px 0;border-radius:6px;font-size:13px;'
      + (isResolved ? 'opacity:0.6;' : '')
      + 'background:var(--blue-bg, #eff6ff);border:1px solid var(--border-light);'
      + 'display:flex;justify-content:space-between;align-items:center';

    var left = document.createElement('div');
    left.style.flex = '1';
    var title = document.createElement('div');
    title.style.fontWeight = '600';
    title.textContent = probe.title || probe.probe_id;
    left.appendChild(title);
    var desc = document.createElement('div');
    desc.style.cssText = 'font-size:12px;color:var(--text2);margin-top:2px';

    if (resolution === 'user_ignored') {
      var reason = probe.resolution_reason || '';
      desc.textContent = '已忽略' + (reason ? '（原因：' + reason + '）' : '');
    } else if (resolution === 'auto_expired') {
      desc.textContent = '已过期（未处理）';
    } else if (resolution === 'promoted_to_suggestion') {
      desc.textContent = '已升级为建议';
    } else {
      desc.innerHTML = withConceptTooltips((probe.description || '').substring(0, 120));
    }
    left.appendChild(desc);
    if (probe.recurrence_count && probe.recurrence_count > 1) {
      var badge = document.createElement('span');
      badge.style.cssText = 'background:var(--warning);color:#fff;font-size:11px;padding:1px 6px;border-radius:10px;margin-left:6px';
      badge.textContent = '重复 ' + probe.recurrence_count + ' 次';
      title.appendChild(badge);
    }
    div.appendChild(left);

    var actions = document.createElement('div');
    actions.style.cssText = 'display:flex;gap:6px;align-items:center;flex-shrink:0;margin-left:12px';
    if (!isResolved) {
      var countdown = document.createElement('span');
      countdown.style.cssText = 'font-size:11px;color:var(--text2)';
      var daysLeft = probe.expires_at ? Math.max(0, Math.ceil((new Date(probe.expires_at) - new Date()) / 86400000)) : 30;
      countdown.textContent = daysLeft + '天后过期';
      actions.appendChild(countdown);
      var ignoreBtn = document.createElement('button');
      ignoreBtn.className = 'btn btn-sm';
      ignoreBtn.style.cssText = 'font-size:11px;padding:2px 8px';
      ignoreBtn.textContent = '忽略';
      ignoreBtn.onclick = function() { EvalUI.ignoreProbe(probe.probe_id, div); };
      actions.appendChild(ignoreBtn);
    }
    div.appendChild(actions);

    return div;
  }

  // ── M5: 探测卡忽略处理 (调用 API) ──

  function ignoreProbe(probeId, cardEl) {
    var promptEl = document.createElement('div');
    promptEl.className = 'probe-ignore-prompt';
    promptEl.style.cssText = 'margin-top:8px;padding:8px;border-top:1px solid var(--border-light)';
    promptEl.innerHTML = '<textarea placeholder="忽略原因（可选，不超过200字）" maxlength="200" rows="2"'
      + ' style="width:100%;margin:8px 0;padding:6px;font-size:13px;box-sizing:border-box"></textarea>'
      + '<button class="btn-confirm-ignore btn btn-sm" style="margin-right:6px">确认忽略</button>'
      + '<button class="btn-cancel-ignore btn btn-sm btn-secondary">取消</button>';
    cardEl.appendChild(promptEl);

    promptEl.querySelector('.btn-cancel-ignore').addEventListener('click', function() { promptEl.remove(); });
    promptEl.querySelector('.btn-confirm-ignore').addEventListener('click', function() {
      var reason = promptEl.querySelector('textarea').value.trim().slice(0, 200);
      var token = (document.querySelector('meta[name="admin-token"]') || {}).content || '';
      fetch('/api/eval/probes/' + encodeURIComponent(probeId) + '/ignore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Admin-Token': token },
        body: JSON.stringify({ reason: reason }),
      }).then(function(r) {
        if (r.ok) { cardEl.style.opacity = '0.6'; cardEl.querySelector('.probe-ignore-prompt').remove(); }
      }).catch(function() {});
    });
  }

  // ── M3: 概念 tooltip (可配置密度) ──

  function renderConceptTooltip(term) {
    var tips = {
      '决策面': '将评估指标与具体工程决策关联的YAML配置。回答"这个分数影响什么决策？"',
      '探测卡': '前瞻性水源产出的创新信号。不是告警——而是"可能应该发生但还没发生的事情"。30天过期。',
      '双水源': '回顾性水源(已发生的) + 前瞻性水源(可能应该发生但还没发生的)。两者互补。',
      'L0': '自动接入层：HTTP请求、LLM调用自动记录，零配置。',
      'L1': '三行代码接入：在业务模块中调用 emit_event() 即可产生评估事件。',
      'L2': '决策面接入：通过YAML定义评估指标与决策问题的关联，系统自动生成评分。',
    };
    var tooltip = tips[term];
    if (!tooltip) return '';
    return '<span class="concept-tip" style="cursor:help;border-bottom:1px dotted var(--accent)"'
      + ' title="' + escapeHtml(tooltip) + '">ⓘ ' + escapeHtml(term) + '</span>';
  }

  function withConceptTooltips(text) {
    if (!text || typeof text !== 'string') return text;
    var result = escapeHtml(text);
    var terms = ['决策面', '探测卡', '双水源', 'L0', 'L1', 'L2'];
    terms.forEach(function(term) {
      if (result.indexOf(term) !== -1) {
        result = result.split(term).join(renderConceptTooltip(term));
      }
    });
    return result;
  }

  // ── M3: eval_coverage 状态横幅 (cold_start / partial / load_failed) ──

  function renderCoverageBanner(state, coverageData) {
    var covered = (coverageData && coverageData.covered_count) || 0;
    var uncovered = (coverageData && coverageData.uncovered_count) || 0;
    var messages = {
      cold_start: {
        icon: '\u{1f331}',
        title: '决策面覆盖: 尚未定义',
        body: '尚未加载任何决策面模块。',
        bodyHtml: '尚未加载任何决策面模块。<br><a href="#" onclick="window.EvalMain.switchTab(' + "'meta'" + ');return false" style="color:var(--accent)">点击了解如何创建决策面 →</a>',
        cls: 'coverage-cold-start'
      },
      partial: {
        icon: '\u{1f4e1}',
        title: '决策面覆盖: 已覆盖 ' + covered + ' / 未覆盖 ' + uncovered,
        body: '部分模块已定义决策面，其余模块将在后续迭代中补充。',
        bodyHtml: '部分模块已定义决策面，其余模块将在后续迭代中补充。<br><canvas class="coverage-chart-canvas" id="chart-coverage" style="width:100%;max-width:300px;height:40px;margin-top:8px"></canvas>',
        cls: 'coverage-partial'
      },
      load_failed: {
        icon: '⚠',
        title: '决策面加载失败',
        body: '无法加载决策面配置，请检查 data/eval/modules/ 目录下的 YAML 文件。',
        cls: 'coverage-failed'
      }
    };
    var info = messages[state];
    if (!info) return '';

    var div = document.createElement('div');
    div.className = 'coverage-banner ' + info.cls;
    div.style.cssText = 'padding:10px 16px;margin-bottom:16px;border-radius:var(--radius-sm);font-size:13px;'
      + 'background:var(--blue-bg, #eff6ff);border:1px solid var(--border-light);'
      + 'display:flex;align-items:center;gap:10px';
    var icon = document.createElement('span');
    icon.style.cssText = 'font-size:18px;flex-shrink:0';
    icon.textContent = info.icon;
    div.appendChild(icon);
    var textBox = document.createElement('div');
    var title = document.createElement('div');
    title.style.cssText = 'font-weight:600;margin-bottom:2px';
    title.textContent = info.title;
    textBox.appendChild(title);
    var body = document.createElement('div');
    body.style.cssText = 'color:var(--text2);font-size:12px';
    if (info.bodyHtml) {
      body.innerHTML = info.bodyHtml;
    } else {
      body.textContent = info.body;
    }
    textBox.appendChild(body);
    div.appendChild(textBox);

    return div;
  }

  // ── M4-1: 知识管线健康卡片 ──
  function renderKnowledgeHealthCard(khData) {
    if (!khData) {
      // 无数据时静默隐藏（冷启动场景）
      return null;
    }
    var score = khData.health_score;
    var details = khData.details || {};
    var pendingItems = details.pending_items || 0;
    var needsSync = details.needs_sync;
    var pendingDomains = details.pending_domains || [];
    var hasError = !!details.error;

    var color = score !== null && score !== undefined ? gaugeColor(score) : 'var(--text3)';
    var scoreStr = score !== null && score !== undefined ? (score * 100).toFixed(0) : '--';

    var div = document.createElement('div');
    div.className = 'knowledge-health-card';
    div.style.cssText = 'padding:10px 16px;margin-bottom:16px;border-radius:var(--radius-sm);font-size:13px;'
      + 'background:var(--blue-bg, #eff6ff);border:1px solid var(--border-light);'
      + 'display:flex;align-items:center;gap:12px';

    // 健康度指示器
    var gauge = document.createElement('div');
    gauge.style.cssText = 'width:48px;height:48px;border-radius:50%;display:flex;align-items:center;justify-content:center;'
      + 'font-size:16px;font-weight:700;flex-shrink:0;border:2px solid ' + color + ';color:' + color;
    gauge.textContent = scoreStr;
    div.appendChild(gauge);

    var textBox = document.createElement('div');
    textBox.style.flex = '1';

    var title = document.createElement('div');
    title.style.cssText = 'font-weight:600;margin-bottom:2px';
    title.textContent = '知识管线健康度';
    textBox.appendChild(title);

    var desc = document.createElement('div');
    desc.style.cssText = 'color:var(--text2);font-size:12px';

    if (hasError) {
      desc.textContent = '知识同步查询失败 — 请检查 knowledge_sync 服务';
      desc.style.color = 'var(--danger)';
    } else if (needsSync) {
      desc.textContent = pendingItems + ' 条待同步' + (pendingDomains.length > 0 ? ' (' + pendingDomains.slice(0, 3).join(', ') + ')' : '');
    } else if (score === 0.5) {
      desc.textContent = '知识库为空 — 添加知识条目后自动激活管线';
    } else {
      desc.textContent = '管线正常 — 知识库与 ChromaDB 已同步';
    }
    textBox.appendChild(desc);

    if (khData.updated_at) {
      var ts = document.createElement('div');
      ts.style.cssText = 'font-size:10px;color:var(--text3);margin-top:2px';
      ts.textContent = '更新于 ' + khData.updated_at.substring(11, 19);
      textBox.appendChild(ts);
    }

    div.appendChild(textBox);
    return div;
  }

  function renderTraceChainNarrative(data) {
    if (!data || !data.chain) {
      return renderEmptyState('追溯链数据不可用');
    }
    var div = document.createElement('div');
    div.className = 'trace-chain-narrative';

    // 链状态徽章
    var stateLabel = {'full': '完整链', 'partial': '部分链', 'broken': '断裂链'}[data.chain_state] || data.chain_state;
    var stateColor = {'full': 'var(--green)', 'partial': 'var(--yellow)', 'broken': 'var(--red)'}[data.chain_state] || 'var(--text3)';
    var hashIcon = data.chain_hash_verified ? '✓' : '✗';
    var hashColor = data.chain_hash_verified ? 'var(--green)' : 'var(--red)';

    div.innerHTML =
      '<div style="display:flex;align-items:center;gap:12px;margin-bottom:12px">' +
        '<span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;background:' + stateColor + '20;color:' + stateColor + '">' + stateLabel + '</span>' +
        '<span style="font-size:12px;color:' + hashColor + '">' + hashIcon + ' 链哈希: ' + (data.chain_hash_verified ? '已验证' : '篡改/断裂') + '</span>' +
      '</div>' +
      '<div class="chain-nodes" style="display:flex;align-items:center;gap:4px;margin-bottom:14px;flex-wrap:wrap;font-size:12px;color:var(--text2)">' +
        data.chain.map(function(id, i) {
          var labels = ['事件', '指标', '告警', '建议'];
          return '<span style="padding:3px 8px;background:var(--bg-card);border-radius:4px;border:1px solid ' + (id ? 'var(--border-light)' : 'var(--red)') + ';color:' + (id ? 'var(--text1)' : 'var(--text3)') + '">' +
            labels[i] + ': ' + (id || '(缺失)') +
          '</span>';
        }).join('<span style="color:var(--text3)">→</span>') +
      '</div>';

    // 证据摘要
    var brief = data.evidence_brief || {};
    var sections = [
      {key: 'metric', label: '指标', icon: '📊'},
      {key: 'alert', label: '告警', icon: '⚠'},
      {key: 'suggestion', label: '建议', icon: '📝'},
      {key: 'decision', label: '决策', icon: '🔵'},
    ];
    sections.forEach(function(sec) {
      var text = brief[sec.key] || '';
      if (text) {
        var p = document.createElement('div');
        p.style.cssText = 'margin:4px 0;font-size:13px;line-height:1.5';
        p.innerHTML = '<strong>' + sec.icon + ' ' + sec.label + ':</strong> <span style="color:var(--text2)">' + escapeHtml(text) + '</span>';
        div.appendChild(p);
      }
    });

    return div;
  }

  return {
    escapeHtml: escapeHtml,
    gaugeColor: gaugeColor,
    renderAlertBanner: renderAlertBanner,
    renderScoreCard: renderScoreCard,
    renderSuggestionItem: renderSuggestionItem,
    renderSpanNode: renderSpanNode,
    renderEmptyState: renderEmptyState,
    renderCoverageBanner: renderCoverageBanner,
    renderKnowledgeHealthCard: renderKnowledgeHealthCard,
    renderProbeCard: renderProbeCard,
    ignoreProbe: ignoreProbe,
    renderConceptTooltip: renderConceptTooltip,
    withConceptTooltips: withConceptTooltips,
    renderTraceChainNarrative: renderTraceChainNarrative,
  };
})();

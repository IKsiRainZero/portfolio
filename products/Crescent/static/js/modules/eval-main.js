/**
 * eval-main.js — 初始化入口 + 面板组装 + 事件调度
 * 命名空间: window.EvalMain
 */

// ── M3: Eval UI 可配置选项 ──
window.EvalUIConfig = {
  innovationSignalPlacement: 'tab',  // 'tab' | 'overview'
  tooltipDensity: 'sparse',          // 'sparse' | 'dense'
};

window.EvalMain = (function() {
  var currentTab = 'overview';
  var pollTimer = null;

  // ── Tab 切换 ──
  function switchTab(tab) {
    currentTab = tab;
    window.location.hash = tab;
    document.querySelectorAll('.eval-tab').forEach(function(el) {
      el.classList.toggle('active', el.dataset.tab === tab);
    });
    document.querySelectorAll('.eval-panel').forEach(function(el) {
      el.style.display = el.dataset.panel === tab ? '' : 'none';
    });
    EvalCharts.destroyAllCharts();
    EvalAPI.sendBeacon('tab_switch', tab);
    if (tab === 'overview') assembleOverview();
    else if (tab === 'details') assembleDetailPanel();
    else if (tab === 'agent') assembleAgentPanel();
    else if (tab === 'meta') assembleMetaPanel();
    else if (tab === 'innovation') assembleInnovationPanel();
  }

  function initTabs() {
    // M3: EvalUIConfig — 创新信号区放置策略
    var placement = (window.EvalUIConfig || {}).innovationSignalPlacement || 'tab';
    if (placement === 'tab') {
      // 动态注入"创新信号"Tab 按钮
      var tabsNav = document.querySelector('.eval-tabs');
      if (tabsNav && !tabsNav.querySelector('[data-tab="innovation"]')) {
        var btn = document.createElement('button');
        btn.className = 'eval-tab';
        btn.dataset.tab = 'innovation';
        btn.textContent = '创新信号';
        tabsNav.appendChild(btn);
      }
      // 动态注入 Panel 容器
      if (!document.getElementById('panel-innovation')) {
        var panel = document.createElement('div');
        panel.className = 'eval-panel';
        panel.dataset.panel = 'innovation';
        panel.id = 'panel-innovation';
        panel.style.display = 'none';
        panel.innerHTML = '<div id="eval-probes-tab"><div id="probe-cards-list-tab" style="padding:16px"></div></div>';
        document.querySelector('.eval-container').appendChild(panel);
      }
    } else {
      // overview 模式: 显示内嵌创新信号区
      var probesEl = document.getElementById('eval-probes');
      if (probesEl) probesEl.style.display = '';
    }

    document.querySelectorAll('.eval-tab').forEach(function(el) {
      el.addEventListener('click', function() {
        switchTab(el.dataset.tab);
      });
    });
    var hash = window.location.hash.replace('#', '') || 'overview';
    switchTab(hash);
  }

  // ── 滚动到指定卡片 (P2-13/P2-14) ──
  function scrollToCard(configId) {
    switchTab('details');
    setTimeout(function() {
      var card = document.querySelector('.score-card[data-config-id="' + configId + '"]');
      if (card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'center' });
        card.style.boxShadow = '0 0 0 3px var(--accent)';
        setTimeout(function() { card.style.boxShadow = ''; }, 2000);
      } else {
        // 卡片未渲染（可能在加载中），延长等待
        setTimeout(function() {
          var retry = document.querySelector('.score-card[data-config-id="' + configId + '"]');
          if (retry) {
            retry.scrollIntoView({ behavior: 'smooth', block: 'center' });
            retry.style.boxShadow = '0 0 0 3px var(--accent)';
            setTimeout(function() { retry.style.boxShadow = ''; }, 2000);
          }
        }, 600);
      }
    }, 100);
  }

  // ── 总览面板组装 ──
  function assembleOverview() {
    var container = document.getElementById('panel-overview');
    if (!container) return;
    // 清理旧的 error overlay（重试时）
    var oldErr = document.getElementById('overview-error-overlay');
    if (oldErr) oldErr.parentNode.removeChild(oldErr);
    // 使用 overlay 而非 innerHTML，保护固定 DOM 元素不被销毁
    var overlay = document.createElement('div');
    overlay.className = 'loading-skeleton';
    overlay.style.cssText = 'position:absolute;top:0;left:0;right:0;bottom:0;display:flex;align-items:center;justify-content:center;z-index:1';
    overlay.innerHTML = '<p>加载中...</p>';
    container.style.position = container.style.position || 'relative';
    container.appendChild(overlay);

    EvalAPI.fetchSummary().then(function(data) {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);

      // 告警
      EvalUI.renderAlertBanner(data.alerts);

      // 告警点击 → 滚动到对应卡片 (P2-13)
      var alertItems = document.querySelectorAll('#eval-alerts .alert-item');
      alertItems.forEach(function(item) {
        var configId = item.getAttribute('data-config-id');
        if (!configId) return;
        item.style.cursor = 'pointer';
        item.addEventListener('click', function() {
          scrollToCard(configId);
        });
      });

      // M3: 覆盖状态横幅 (非 healthy 时显示)
      var oldBanner = document.querySelector('.coverage-banner');
      if (oldBanner) oldBanner.parentNode.removeChild(oldBanner);
      var coverageBanner = EvalUI.renderCoverageBanner(data.coverage, data.coverage_data);
      if (coverageBanner) {
        var alertsEl = document.getElementById('eval-alerts');
        if (alertsEl && alertsEl.nextSibling) {
          alertsEl.parentNode.insertBefore(coverageBanner, alertsEl.nextSibling);
        } else if (alertsEl) {
          alertsEl.parentNode.appendChild(coverageBanner);
        }
        // M3: 覆盖图表 (在非 partial 状态下显示)
        if (data.coverage === 'partial' && data.coverage_data) {
          var covChartCanvas = coverageBanner.querySelector('.coverage-chart-canvas');
          if (covChartCanvas) {
            EvalCharts.createOrUpdateChart(covChartCanvas.id, EvalCharts.coverageConfig(
              data.coverage_data.covered_count,
              data.coverage_data.uncovered_count
            ));
          }
        }
      }

      // M4-1: 知识管线健康卡片
      var oldKH = document.querySelector('.knowledge-health-card');
      if (oldKH) oldKH.parentNode.removeChild(oldKH);
      var khCard = EvalUI.renderKnowledgeHealthCard(data.knowledge_health);
      if (khCard) {
        var covEl = document.querySelector('.coverage-banner');
        var refEl = covEl || document.getElementById('eval-alerts');
        if (refEl && refEl.nextSibling) {
          refEl.parentNode.insertBefore(khCard, refEl.nextSibling);
        } else if (refEl) {
          refEl.parentNode.appendChild(khCard);
        }
      }

      // 趋势线
      if (data.trend && data.trend.length > 0) {
        var emptyMsg = document.getElementById('trend-empty-msg');
        if (emptyMsg) emptyMsg.style.display = 'none';
        EvalCharts.createOrUpdateChart('chart-trend', EvalCharts.trendConfig(data.trend, data.annotations || []));
      }

      // 评分明细列表 — 替换雷达图
      var breakdownEl = document.getElementById('score-breakdown-list');
      if (breakdownEl && data.radar) {
        var radarLabels = data.radar_labels || {};
        var configIds = Object.keys(data.radar);
        var hasAnyData = configIds.some(function(k) { return data.radar[k] > 0; });
        if (configIds.length > 0 && hasAnyData) {
          var items = configIds.map(function(k) {
            var val = data.radar[k];
            var pct = (val * 100).toFixed(0);
            var color = EvalUI.gaugeColor(val);
            var name = radarLabels[k] || k;
            return '<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--border-light)">' +
              '<span style="flex:0 0 90px;font-size:12px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis" title="' + EvalUI.escapeHtml(name) + '">' + EvalUI.escapeHtml(name) + '</span>' +
              '<span style="flex:1;height:6px;background:var(--bg);border-radius:3px;overflow:hidden">' +
                '<span style="display:block;height:100%;width:' + pct + '%;background:' + color + ';border-radius:3px;min-width:2px"></span>' +
              '</span>' +
              '<span style="flex:0 0 32px;font-size:12px;font-weight:600;color:' + color + ';text-align:right">' + pct + '</span>' +
            '</div>';
          }).join('');
          breakdownEl.innerHTML = items;
        } else {
          // 无数据 → 加载配置列表展示指标体系
          breakdownEl.innerHTML = '<span style="color:var(--text2)">评分数据收集中...</span>';
          EvalAPI.fetchConfigs().then(function(cfgRes) {
            if (!document.getElementById('score-breakdown-list')) return;
            var cfgs = (cfgRes.configs || []).filter(function(c) { return c.weight > 0; });
            if (cfgs.length === 0) return;
            var rows = cfgs.map(function(c) {
              return '<div style="display:flex;align-items:center;gap:8px;padding:5px 0;border-bottom:1px solid var(--border-light)">' +
                '<span style="flex:1;font-size:12px;font-weight:500">' + EvalUI.escapeHtml(c.display_name || c.name || c.config_id) + '</span>' +
                '<span style="font-size:11px;color:var(--text3)">权' + (c.weight || 0).toFixed(2) + '</span>' +
                '<span style="font-size:11px;color:var(--text3)">阈' + (c.threshold !== undefined ? c.threshold : '--') + '</span>' +
              '</div>';
            }).join('');
            document.getElementById('score-breakdown-list').innerHTML = rows +
              '<div style="font-size:10px;color:var(--text3);margin-top:8px">评分数据将在 daemon 首次采集后更新</div>';
          }).catch(function() {});
        }
      }

      // 总评分
      var scoreEl = document.getElementById('total-score-value');
      if (scoreEl && data.total_score !== null) {
        scoreEl.textContent = (data.total_score * 100).toFixed(0);
        scoreEl.style.color = EvalUI.gaugeColor(data.total_score);
      }

      // 加权公式说明
      var formulaEl = document.getElementById('eval-formula');
      if (formulaEl) {
        formulaEl.textContent = 'Total = Σ(w_i × s_i) / Σ(w_i)';
        formulaEl.title = '加权平均: 各指标分数按权重加权求和后除以总权重';
      }

      // 数据新鲜度指示器 (P1-8)
      var freshEl = document.getElementById('eval-freshness');
      if (freshEl && data.updated_at) {
        var minutesAgo = Math.round((Date.now() - new Date(data.updated_at).getTime()) / 60000);
        if (minutesAgo > 60) {
          freshEl.style.color = 'var(--warning)';
          freshEl.textContent = '⚠ 数据更新于 ' + minutesAgo + ' 分钟前 — 可能已过时';
        } else {
          freshEl.style.color = 'var(--text2)';
          freshEl.textContent = minutesAgo <= 1 ? '刚刚更新' : '数据更新于 ' + minutesAgo + ' 分钟前';
        }
      }

      // 最近标注
      var annEl = document.getElementById('annotations-list');
      if (annEl && data.annotations && data.annotations.length > 0) {
        annEl.innerHTML = data.annotations.slice(0, 5).map(function(a) {
          var delta = (a.value_after !== null && a.value_before !== null)
            ? (a.value_after - a.value_before).toFixed(2)
            : (a.delta ? a.delta.toFixed(2) : '--');
          return '<div style="font-size:13px;padding:4px 0;border-bottom:1px solid var(--border)">' +
            '<strong>' + EvalUI.escapeHtml(a.title || '') + '</strong> ' +
            (a.value_before !== null ? '(' + a.value_before.toFixed(2) + ' → ' + (a.value_after !== null ? a.value_after.toFixed(2) : '?') + ')' : '') +
            ' <span style="color:var(--accent)">' + (delta >= 0 ? '+' : '') + delta + '</span>' +
          '</div>';
        }).join('');
      } else if (annEl) {
        annEl.innerHTML = '<span style="color:var(--text2)">暂无变更标注 — 采纳建议后自动记录效果</span>';
      }

      // 时间戳
      var timeEl = document.getElementById('eval-updated-at');
      if (timeEl && data.updated_at) {
        timeEl.textContent = '上次更新: ' + data.updated_at.substring(11, 19);
      }

      // 自指全局指示器 (Phase 4 约束 3)
      var selfRef = document.getElementById('eval-self-ref');
      if (selfRef) {
        selfRef.style.display = '';
        var healthEl = document.getElementById('self-ref-health');
        var pendingEl = document.getElementById('self-ref-pending');
        var freshEl2 = document.getElementById('self-ref-freshness');
        var pendingCount = (data.alerts || []).filter(function(a) { return a.type === 'suggestion'; }).length;
        if (healthEl) healthEl.textContent = '评估系统自身健康度: ' + (data.total_score !== null ? (data.total_score * 100).toFixed(0) : '--');
        if (pendingEl) pendingEl.textContent = pendingCount + ' 条待审核建议';
        if (freshEl2) {
          var minutesAgo2 = data.updated_at ? Math.round((Date.now() - new Date(data.updated_at).getTime()) / 60000) : null;
          freshEl2.textContent = minutesAgo2 !== null ? '数据更新于 ' + minutesAgo2 + ' 分钟前' : '';
        }
        // 健康度下降 → 橙色
        if (data.total_score !== null && data.total_score < 0.7 && healthEl) {
          healthEl.style.color = 'var(--warning)';
        }
        if (pendingCount >= 3 && pendingEl) {
          pendingEl.style.color = 'var(--warning)';
        }
      }

      // 错误降级
      if (data.errors && data.errors.length > 0) {
        var errEl = document.getElementById('eval-errors');
        if (errEl) {
          errEl.innerHTML = data.errors.map(function(e) {
            return '<div style="color:var(--warning);font-size:12px">&#9888; ' + EvalUI.escapeHtml(e) + '</div>';
          }).join('');
        }
      }
    }).catch(function(err) {
      if (overlay.parentNode) overlay.parentNode.removeChild(overlay);
      var errMsg = err.message === 'timeout'
        ? '数据加载超时 — 请稍后重试'
        : '数据暂时不可用: ' + EvalUI.escapeHtml(err.message);
      var errOverlay = document.createElement('div');
      errOverlay.id = 'overview-error-overlay';
      errOverlay.style.cssText = 'position:absolute;top:0;left:0;right:0;bottom:0;display:flex;flex-direction:column;align-items:center;justify-content:center;z-index:2;background:var(--surface)';
      errOverlay.innerHTML = '<p style="color:var(--danger)">' + errMsg + '</p>' +
        '<button class="btn" onclick="EvalMain.assembleOverview()">重试</button>';
      container.style.position = container.style.position || 'relative';
      container.appendChild(errOverlay);
    });
  }

  // ── 模块详情面板组装 ──
  function assembleDetailPanel() {
    var container = document.getElementById('panel-details');
    if (!container) return;
    container.innerHTML = '<div class="loading-skeleton"><p>加载中...</p></div>';

    Promise.all([
      EvalAPI.fetchConfigs(),
      EvalAPI.fetchSummary(),
      EvalAPI.fetchSuggestions(null, null),
    ]).then(function(results) {
      var configs = results[0].configs || [];
      var summary = results[1];
      var suggestions = results[2].suggestions || [];
      var radar = summary.radar || {};
      var sparklines = summary.sparklines || {};
      // 跟踪上次值用于计算 delta
      var prevScores = {};
      try { prevScores = JSON.parse(localStorage.getItem('eval_prev_scores') || '{}'); } catch(e) {}

      // 宪法指标（weight=0）单独分组，放在最前面
      var html = '';
      var constitutional = configs.filter(function(c) { return c.weight === 0; });
      var regular = configs.filter(function(c) { return c.weight !== 0; });
      if (constitutional.length > 0) {
        html += '<h3 style="margin-top:0;font-size:13px;font-weight:600;color:var(--danger)">🔒 宪法指标 (P0 — 红线)</h3>';
        html += '<div class="score-cards-grid">';
        constitutional.forEach(function(cfg) {
          var val = radar[cfg.config_id] || 0;
          html += EvalUI.renderScoreCard(cfg, val, null, null);
        });
        html += '</div>';
        html += '<hr style="border:none;border-top:2px solid var(--danger);opacity:.2;margin:20px 0">';
      }
      // 构建 L2/L3 数据索引
      var suggestionsByCategory = {};
      suggestions.forEach(function(s) {
        var cat = s.category || '';
        if (!suggestionsByCategory[cat]) suggestionsByCategory[cat] = [];
        suggestionsByCategory[cat].push(s);
      });
      // 计算系统平均作为参照系
      var allVals = Object.values(radar).filter(function(v) { return typeof v === 'number'; });
      var systemAvg = allVals.length > 0 ? allVals.reduce(function(a,b){return a+b;},0) / allVals.length : null;

      html += '<div class="score-cards-grid">';
      regular.forEach(function(cfg) {
        var val = radar[cfg.config_id] || 0;
        var prev = prevScores[cfg.config_id];
        var spark = sparklines[cfg.config_id] || null;

        // L2: 子指标分解 + 关联建议 (回答"为什么")
        var l2Data = null;
        var category = cfg.category || cfg.config_id;
        var relatedSuggestions = suggestionsByCategory[category] || suggestionsByCategory[cfg.config_id] || [];
        if (relatedSuggestions.length > 0 || cfg.sub_indicators) {
          l2Data = {
            sub_indicators: cfg.sub_indicators || [],
            suggestions: relatedSuggestions.slice(0, 3)
          };
        }

        // L3: 参照系 + 计算说明 + 决策问题 (回答"意味着什么")
        var l3Data = null;
        if (cfg.threshold !== undefined || cfg.user_value_statement) {
          l3Data = {
            reference: {
              system_avg: systemAvg,
              last_month_avg: null,
              baseline: cfg.threshold || null
            },
            computation: cfg.computation || (cfg.evaluator_type === 'CODE' ? '纯代码计算，基于埋点数据统计' : cfg.evaluator_type === 'LLM_JUDGE' ? 'LLM Judge 评分' : '混合评估 (CODE + LLM)'),
            decision_question: cfg.decision_question || null
          };
        }

        html += EvalUI.renderScoreCard(cfg, val, prev, spark, l2Data, l3Data);
      });
      html += '</div>';
      html += '<h3 style="margin-top:32px">建议列表</h3>';
      html += '<div class="suggestion-filters">' +
        '<select id="sug-filter-status"><option value="">全部状态</option><option value="pending">待处理</option><option value="applied">已采纳</option><option value="rejected">已拒绝</option></select>' +
        '<select id="sug-filter-severity"><option value="">全部严重度</option><option value="P0">P0</option><option value="P1">P1</option><option value="P2">P2</option></select>' +
      '</div>';
      html += '<div class="suggestions-list" id="suggestion-list">';
      if (suggestions.length === 0) {
        html += EvalUI.renderEmptyState('suggestions', '建议列表为空 — 评估引擎尚未生成建议', '后台任务每 1 小时运行一次，或手动触发审查生成建议');
      } else {
        suggestions.forEach(function(s) {
          html += EvalUI.renderSuggestionItem(s);
        });
      }
      html += '</div>';

      container.innerHTML = html;

      // 渲染仪表图 + sparkline
      configs.forEach(function(cfg) {
        var val = radar[cfg.config_id] || 0;
        var canvasId = 'gauge-' + cfg.config_id;
        if (document.getElementById(canvasId)) {
          EvalCharts.createOrUpdateChart(canvasId, EvalCharts.gaugeConfig(val));
        }
        if (cfg.weight === 0) return; // 宪法指标无 sparkline
        var sparkId = 'spark-' + cfg.config_id;
        var sparkData = sparklines[cfg.config_id];
        if (document.getElementById(sparkId) && sparkData && sparkData.length > 0) {
          EvalCharts.createOrUpdateChart(sparkId, EvalCharts.sparklineConfig(sparkData));
        }
      });

      // 保存当前评分供下次计算 delta
      try { localStorage.setItem('eval_prev_scores', JSON.stringify(radar)); } catch(e) {}

      // 筛选事件
      var statusFilter = document.getElementById('sug-filter-status');
      var sevFilter = document.getElementById('sug-filter-severity');
      if (statusFilter && sevFilter) {
        var reload = function() {
          EvalAPI.fetchSuggestions(statusFilter.value || null, sevFilter.value || null).then(function(res) {
            var list = document.getElementById('suggestion-list');
            if (list) {
              var items = res.suggestions || [];
              if (items.length === 0) {
                list.innerHTML = EvalUI.renderEmptyState('suggestions', '没有匹配的建议', '尝试选择其他严重度或状态筛选，或等待后台任务生成新建议');
              } else {
                list.innerHTML = items.map(function(s) { return EvalUI.renderSuggestionItem(s); }).join('');
              }
              if (window.EvalSlideOut) EvalSlideOut.bindClicks();
            }
          });
        };
        statusFilter.addEventListener('change', reload);
        sevFilter.addEventListener('change', reload);
      }

      // 建议点击 → 滑出面板 (P1-2)
      if (window.EvalSlideOut) EvalSlideOut.bindClicks();
    }).catch(function(err) {
      container.innerHTML = '<div style="padding:24px;text-align:center;color:var(--danger)">加载失败: ' + EvalUI.escapeHtml(err.message) + '</div>';
    });
  }

  // ── Agent 面板组装 ──
  function assembleAgentPanel() {
    var container = document.getElementById('panel-agent');
    if (!container) return;
    container.innerHTML = '<div class="loading-skeleton"><p>加载中...</p></div>';

    EvalAPI.fetchTraces(20, 24).then(function(data) {
      var traces = data.traces || [];

      // 聚合指标 (P2-12): 成功率、工具准确度、Token 效率
      var totalSpans = 0;
      var errorSpans = 0;
      var totalDuration = 0;
      var llmSpans = 0;
      var toolSpans = 0;
      traces.forEach(function(t) {
        totalSpans += (t.span_count || 0);
        if (t.error) errorSpans++;
        totalDuration += (t.duration_ms || 0);
      });

      // 从 spans 聚合
      var successRate = totalSpans > 0 ? ((totalSpans - errorSpans) / totalSpans * 100).toFixed(0) : '--';
      var avgDuration = traces.length > 0 ? (totalDuration / traces.length).toFixed(0) : '--';

      var html = '<div class="agent-metrics" style="display:flex;gap:16px;margin-bottom:24px">' +
        '<div class="agent-card" style="flex:1;padding:16px;border:1px solid var(--border);border-radius:8px;text-align:center">' +
          '<div style="font-size:24px;font-weight:700;color:var(--accent)">' + successRate + '<span style="font-size:14px">%</span></div>' +
          '<div style="font-size:12px;color:var(--text2);margin-top:4px">成功率 (Spans)</div>' +
        '</div>' +
        '<div class="agent-card" style="flex:1;padding:16px;border:1px solid var(--border);border-radius:8px;text-align:center">' +
          '<div style="font-size:24px;font-weight:700;color:var(--accent)">' + traces.length + '</div>' +
          '<div style="font-size:12px;color:var(--text2);margin-top:4px">Traces (24h)</div>' +
        '</div>' +
        '<div class="agent-card" style="flex:1;padding:16px;border:1px solid var(--border);border-radius:8px;text-align:center">' +
          '<div style="font-size:24px;font-weight:700;color:var(--accent)">' + avgDuration + '<span style="font-size:14px">ms</span></div>' +
          '<div style="font-size:12px;color:var(--text2);margin-top:4px">平均耗时</div>' +
        '</div>' +
      '</div>';

      html += '<p style="font-size:13px;color:var(--text2);margin-bottom:12px">每次 Agent 对话或 API 请求自动生成一条 Trace，包含完整的调用链追踪（LLM 调用、工具使用、耗时）。点击展开查看详情。</p>';
      html += '<h3>Trace 列表</h3>';
      if (traces.length === 0) {
        html += EvalUI.renderEmptyState('traces', '暂无 Agent 追踪数据', '评估系统通过 HTTP 请求自动采集 Trace — 完成几次对话交互后可在此查看');
      } else {
        html += '<div class="trace-list">';
        traces.forEach(function(t) {
          html += '<div class="trace-item" style="padding:8px;border:1px solid var(--border);border-radius:6px;margin-bottom:8px;cursor:pointer" data-trace-id="' + EvalUI.escapeHtml(t.trace_id) + '">' +
            '<span style="font-weight:600">' + EvalUI.escapeHtml(t.name || t.trace_id) + '</span> ' +
            '<span style="color:var(--text2);font-size:12px">' + (t.duration_ms || '?') + 'ms | ' + (t.span_count || 0) + ' spans</span>' +
            '<span style="float:right;font-size:12px;color:' + (t.error ? 'var(--danger)' : 'var(--success)') + '">' + (t.error ? '&#9888;' : '&#10004;') + '</span>' +
          '</div>';
        });
        html += '</div>';
      }

      container.innerHTML = html;

      // Trace 展开事件
      document.querySelectorAll('.trace-item').forEach(function(el) {
        el.addEventListener('click', function() {
          var tid = el.dataset.traceId;
          EvalAPI.fetchTrace(tid).then(function(trace) {
            var spans = trace.spans || [];
            var spanHtml = '<div style="padding:8px 16px;background:var(--bg2);border-radius:6px;margin-top:8px;font-family:monospace;font-size:13px">' +
              '<div>' + EvalUI.renderSpanNode({ kind: trace.kind || 'Trace', name: trace.name || tid, duration_ms: trace.duration_ms, status: trace.error ? 'error' : 'success' }, 0) + '</div>';
            spans.forEach(function(s) {
              spanHtml += EvalUI.renderSpanNode(s, 1);
            });
            spanHtml += '</div>';
            var existing = el.nextElementSibling;
            if (existing && existing.classList.contains('trace-detail')) {
              existing.remove();
            } else {
              el.insertAdjacentHTML('afterend', '<div class="trace-detail">' + spanHtml + '</div>');
            }
          });
        });
      });
    }).catch(function(err) {
      container.innerHTML = '<div style="padding:24px;text-align:center;color:var(--danger)">加载失败: ' + EvalUI.escapeHtml(err.message) + '</div>';
    });
  }

  // ── 元评估面板组装 ──
  function assembleMetaPanel() {
    var container = document.getElementById('panel-meta');
    if (!container) return;
    container.innerHTML = '<div class="loading-skeleton"><p>加载中...</p></div>';

    EvalAPI.fetchMetaResults().then(function(data) {
      var results = data.results || [];
      var metaScore = '--';
      // 计算综合元评估评分
      if (results.length > 0) {
        var sum = 0;
        results.forEach(function(r) { sum += (r.value || 0); });
        metaScore = (sum / results.length * 100).toFixed(0);
      }

      var html = '<div style="padding:16px;border:1px solid var(--border);border-radius:8px;margin-bottom:16px">' +
        '<strong>评估体系健康度</strong>: <span style="font-size:20px;font-weight:700;color:' + EvalUI.gaugeColor(results.length > 0 ? (parseInt(metaScore) || 0) / 100 : 0) + '">' + metaScore + '</span>' +
        (results.length > 0 ? '' : ' <span style="color:var(--text2);font-size:12px">(等待元评估运行)</span>') +
      '</div>';

      html += '<div style="padding:8px;margin-bottom:16px">' +
        '<span>&#128274; 宪法 Metric: data_completeness, eval_system_freshness, code_llm_consensus, score_drift</span>' +
      '</div>';

      html += '<h3>元评估指标</h3>';
      if (results.length === 0) {
        html += EvalUI.renderEmptyState('meta', '元评估尚未运行', '后台每 6 小时自动运行，或等待下次周期触发');
      } else {
        results.forEach(function(r) {
          var configName = r.config_id || '';
          var val = r.value !== null && r.value !== undefined ? r.value : -1;
          var color = EvalUI.gaugeColor(val);
          var details = r.details || {};
          var detailText = '';
          var detailItems = '';
          if (details.passes !== undefined) {
            detailText = ' (' + details.passes + '/' + details.total + ' 通过)';
            if (details.deviations && details.deviations.length > 0) {
              detailItems = '<div style="margin-top:6px;font-size:11px;color:var(--text2)">' +
                details.deviations.map(function(d) {
                  return '<div style="padding:2px 0">- [' + (d.severity || '') + '] ' + EvalUI.escapeHtml(d.check || '') + ': ' + EvalUI.escapeHtml(d.detail || '') + '</div>';
                }).join('') + '</div>';
            }
          } else if (details.stale !== undefined) {
            detailText = ' (' + details.stale + ' 项过时)';
            if (details.stale_details && details.stale_details.length > 0) {
              detailItems = '<div style="margin-top:6px;font-size:11px;color:var(--text2)">' +
                details.stale_details.map(function(d) {
                  var age = d.age_days !== null ? d.age_days + '天' : '?';
                  return '<div style="padding:2px 0">- <strong>' + EvalUI.escapeHtml(d.config_id || '') + '</strong>: ' + age + (d.severity ? ' [' + d.severity + ']' : '') + (d.reason ? ' (' + d.reason + ')' : '') + '</div>';
                }).join('') + '</div>';
            }
          } else if (details.compared !== undefined) {
            detailText = ' (' + details.compared + ' 条对比)';
          } else if (details.violations !== undefined) {
            detailText = ' (' + details.violations + ' 条违规)';
            if (details.violation_details && details.violation_details.length > 0) {
              detailItems = '<div style="margin-top:6px;font-size:11px;color:var(--text2)">' +
                details.violation_details.map(function(d) {
                  return '<div style="padding:2px 0">- ' + EvalUI.escapeHtml(d.file || '') + ': ' + EvalUI.escapeHtml(d.type || '') + (d.detail ? ' (' + EvalUI.escapeHtml(d.detail) + ')' : '') + '</div>';
                }).join('') + '</div>';
            }
          } else if (details.unprotected !== undefined) {
            detailText = ' (' + details.unprotected + ' 条未防护)';
            if (details.unprotected_details && details.unprotected_details.length > 0) {
              detailItems = '<div style="margin-top:6px;font-size:11px;color:var(--text2)">' +
                details.unprotected_details.map(function(d) {
                  return '<div style="padding:2px 0">- <strong>' + EvalUI.escapeHtml(d.file || '') + '</strong>' + (d.severity ? ' [' + d.severity + ']' : '') + '</div>';
                }).join('') + '</div>';
            }
          }

          html += '<div style="padding:10px 14px;border:1px solid var(--border);border-radius:6px;margin-bottom:8px;">' +
            '<div style="display:flex;justify-content:space-between;align-items:center">' +
              '<span style="font-size:13px">' + EvalUI.escapeHtml(configName) + detailText + '</span>' +
              '<span style="font-weight:700;color:' + color + '">' + (val >= 0 ? (val * 100).toFixed(0) : '--') + '</span>' +
            '</div>' +
            detailItems +
          '</div>';
        });
      }

      html += '<p style="font-size:11px;color:var(--text3);margin-top:12px">来源: META_EVAL · 更新于 ' + (data.updated_at || '--') + '</p>';

      container.innerHTML = html;
    }).catch(function(err) {
      container.innerHTML = '<div style="padding:24px;text-align:center;color:var(--danger)">加载失败: ' + EvalUI.escapeHtml(err.message) + '</div>';
    });
  }

  // ── M3: 创新信号面板 ──
  function assembleInnovationPanel() {
    var container = document.getElementById('panel-innovation');
    if (!container) return;
    var probesList = document.getElementById('probe-cards-list-tab');
    if (!probesList) return;
    probesList.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text2);font-size:14px">加载中...</div>';

    EvalAPI.fetchProbes().then(function(data) {
      var probes = data.probes || [];
      if (probes.length === 0) {
        probesList.innerHTML = '<div style="padding:16px;text-align:center;color:var(--text2);font-size:14px">暂无创新信号 — 探测卡将在前瞻性水源激活后展示</div>';
      } else {
        var html = '';
        var activeProbes = probes.filter(function(p) { return !p.resolution; });
        var resolvedProbes = probes.filter(function(p) { return p.resolution; });
        if (activeProbes.length > 0) {
          html += '<h3 style="margin-top:0;font-size:13px;font-weight:600">活跃探测卡 (' + activeProbes.length + ')</h3>';
          activeProbes.forEach(function(p) {
            html += '<div id="probe-' + EvalUI.escapeHtml(p.probe_id) + '"></div>';
          });
        }
        if (resolvedProbes.length > 0) {
          html += '<hr style="border:none;border-top:1px solid var(--border-light);margin:16px 0">';
          html += '<h3 style="font-size:13px;font-weight:600;color:var(--text2)">已处理 (' + resolvedProbes.length + ')</h3>';
          resolvedProbes.forEach(function(p) {
            html += '<div id="probe-' + EvalUI.escapeHtml(p.probe_id) + '"></div>';
          });
        }
        if (activeProbes.length === 0 && resolvedProbes.length === 0) {
          html = '<div style="padding:16px;text-align:center;color:var(--text2);font-size:14px">暂无创新信号 — 探测卡将在前瞻性水源激活后展示</div>';
        }
        probesList.innerHTML = html;

        // 渲染活跃探测卡
        activeProbes.forEach(function(p) {
          var el = document.getElementById('probe-' + p.probe_id);
          if (el) el.appendChild(EvalUI.renderProbeCard(p));
        });
        // 渲染已处理探测卡（淡化样式）
        resolvedProbes.forEach(function(p) {
          var el = document.getElementById('probe-' + p.probe_id);
          if (el) {
            var card = EvalUI.renderProbeCard(p);
            card.style.opacity = '0.6';
            el.appendChild(card);
          }
        });
      }
    }).catch(function() {
      probesList.innerHTML = '<div style="padding:16px;text-align:center;color:var(--warning)">探测卡加载失败</div>';
    });

    // 激活时自动发送 beacon
    EvalAPI.sendBeacon('panel_view', 'innovation');
  }

  // ── 轮询 ──
  function startPolling(intervalMs) {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(function() {
      if (currentTab === 'overview') {
        assembleOverview();
      }
    }, intervalMs || 60000);
  }

  // ── 影子模式运行时切换 (Slide 08 "我可以随时打开开关") ──
  function toggleShadowMode(enable) {
    var shadowBanner = document.getElementById('eval-shadow-banner');
    var activeBanner = document.getElementById('eval-active-banner');
    EvalAPI.toggleShadow(enable).then(function(res) {
      if (res.shadow_mode) {
        if (shadowBanner) shadowBanner.style.display = '';
        if (activeBanner) activeBanner.style.display = 'none';
      } else {
        if (shadowBanner) shadowBanner.style.display = 'none';
        if (activeBanner) activeBanner.style.display = '';
      }
    }).catch(function(err) {
      alert('切换失败: ' + (err.message || '未知错误'));
      // Revert checkbox
      var cb = document.getElementById('shadow-toggle-check');
      var cb2 = document.getElementById('shadow-toggle-check-active');
      if (cb) cb.checked = !enable;
      if (cb2) cb2.checked = enable;
    });
  }

  // ── 初始化 ──
  function init() {
    initTabs();
    startPolling(60000);
  }

  return {
    init: init,
    switchTab: switchTab,
    assembleOverview: assembleOverview,
    assembleDetailPanel: assembleDetailPanel,
    assembleAgentPanel: assembleAgentPanel,
    assembleMetaPanel: assembleMetaPanel,
    scrollToCard: scrollToCard,
    toggleShadowMode: toggleShadowMode,
  };
})();

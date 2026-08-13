/**
 * eval-charts.js — Chart.js 实例管理
 * createOrUpdateChart 是 new Chart() 的唯一入口。
 * 命名空间: window.EvalCharts
 */
window.EvalCharts = (function() {
  var instances = {};

  function createOrUpdateChart(canvasId, config) {
    if (instances[canvasId]) {
      instances[canvasId].destroy();
    }
    var ctx = document.getElementById(canvasId).getContext('2d');
    instances[canvasId] = new Chart(ctx, config);
    return instances[canvasId];
  }

  function destroyAllCharts() {
    Object.values(instances).forEach(function(c) { c.destroy(); });
    instances = {};
  }

  function radarConfig(labels, data, ids) {
    return {
      type: 'radar',
      data: {
        labels: labels,
        datasets: [{
          label: '评分',
          data: data,
          backgroundColor: 'rgba(99, 102, 241, 0.2)',
          borderColor: 'rgba(99, 102, 241, 0.8)',
          borderWidth: 2,
          pointBackgroundColor: 'rgba(99, 102, 241, 1)',
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { r: { min: 0, max: 1, ticks: { stepSize: 0.2 } } },
        onClick: function(e, elements) {
          if (elements.length > 0) {
            var idx = elements[0].index;
            var configId = (ids || labels)[idx];
            if (window.EvalMain && window.EvalMain.scrollToCard) {
              window.EvalMain.scrollToCard(configId);
            }
          }
        },
      },
    };
  }

  function trendConfig(points, annotations) {
    var annByDate = {};
    (annotations || []).forEach(function(a) {
      if (a.date) annByDate[a.date] = a;
    });

    var data = points.map(function(p) { return p.value; });
    var labels = points.map(function(p) { return p.date; });
    var bgColors = points.map(function(p) {
      var a = annByDate[p.date];
      if (a && a.type === 'suggestion_applied') return '#6366f1';
      if (a) return '#9ca3af';
      return 'rgba(99, 102, 241, 1)';
    });
    var radii = points.map(function(p) {
      return annByDate[p.date] ? 6 : 3;
    });

    return {
      type: 'line',
      data: {
        labels: labels,
        datasets: [{
          label: '趋势',
          data: data,
          borderColor: 'rgba(99, 102, 241, 1)',
          borderWidth: 2,
          pointRadius: radii,
          pointBackgroundColor: bgColors,
          pointBorderColor: bgColors,
          tension: 0.3,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: { y: { min: 0, max: 1 } },
        plugins: {
          tooltip: {
            callbacks: {
              label: function(ctx) {
                var date = ctx.label;
                var a = annByDate[date];
                if (a) {
                  var before = a.value_before !== null && a.value_before !== undefined ? a.value_before.toFixed(2) : '?';
                  var after = a.value_after !== null && a.value_after !== undefined ? a.value_after.toFixed(2) : '?';
                  var d = a.delta !== null && a.delta !== undefined ? (a.delta >= 0 ? '+' : '') + a.delta.toFixed(2) : '--';
                  return a.title + ': ' + before + ' → ' + after + ' (Δ' + d + ')';
                }
                return '评分: ' + ctx.raw.toFixed(2);
              },
            },
          },
        },
      },
    };
  }

  function sparklineConfig(data) {
    return {
      type: 'line',
      data: {
        labels: data.map(function(_, i) { return i; }),
        datasets: [{
          data: data,
          borderColor: 'rgba(99, 102, 241, 0.8)',
          borderWidth: 1.5,
          pointRadius: 0,
          tension: 0.3,
        }],
      },
      options: {
        responsive: false,
        maintainAspectRatio: true,
        plugins: { legend: { display: false } },
        scales: { x: { display: false }, y: { display: false, min: 0, max: 1 } },
      },
    };
  }

  function gaugeConfig(value) {
    return {
      type: 'doughnut',
      data: {
        datasets: [{
          data: [value, 1 - value],
          backgroundColor: [_gaugeColor(value), '#e5e7eb'],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: false,
        maintainAspectRatio: true,
        cutout: '75%',
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
      },
    };
  }

  function coverageConfig(covered, uncovered) {
    return {
      type: 'doughnut',
      data: {
        labels: ['已覆盖', '未覆盖'],
        datasets: [{
          data: [covered, uncovered],
          backgroundColor: ['#6366f1', '#e5e7eb'],
          borderWidth: 0,
        }],
      },
      options: {
        responsive: false,
        maintainAspectRatio: true,
        cutout: '65%',
        plugins: { legend: { position: 'bottom' } },
      },
    };
  }

  function _gaugeColor(val) {
    if (val >= 0.9) return '#10b981';
    if (val >= 0.7) return '#6366f1';
    if (val >= 0.5) return '#f59e0b';
    return '#ef4444';
  }

  return {
    createOrUpdateChart: createOrUpdateChart,
    destroyAllCharts: destroyAllCharts,
    radarConfig: radarConfig,
    trendConfig: trendConfig,
    sparklineConfig: sparklineConfig,
    gaugeConfig: gaugeConfig,
    coverageConfig: coverageConfig,
  };
})();

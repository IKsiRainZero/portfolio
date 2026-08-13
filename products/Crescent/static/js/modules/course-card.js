/* course-card.js — 结构化课程卡组件
 * 用法: CourseCard.render(course, container, { mode: 'compact'|'full' });
 * mode: 'compact' (教室聊天区, 默认折叠) | 'full' (办公室预览区, 全部展开)
 */

(function(global) {
  'use strict';

  var _katexLoaded = false;
  var _mermaidLoaded = false;

  function loadKaTeX(cb) {
    if (_katexLoaded) { cb(); return; }
    if (window.katex) { _katexLoaded = true; cb(); return; }
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css';
    document.head.appendChild(link);
    var script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js';
    script.onload = function() { _katexLoaded = true; cb(); };
    document.head.appendChild(script);
  }

  function loadMermaid(cb) {
    if (_mermaidLoaded) { cb(); return; }
    if (window.mermaid) { _mermaidLoaded = true; cb(); return; }
    var script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js';
    script.onload = function() {
      window.mermaid.initialize({ startOnLoad: false, theme: 'neutral' });
      _mermaidLoaded = true;
      cb();
    };
    document.head.appendChild(script);
  }

  function esc(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  function buildSectionHTML(section) {
    var html = '<div class="course-section">';
    html += '<div class="course-section-heading">' + esc(section.heading) + '</div>';

    var body = section.body || '';
    // Convert markdown-like formatting to HTML (simple subset)
    body = body.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    body = body.replace(/\*(.+?)\*/g, '<em>$1</em>');
    body = body.replace(/`(.+?)`/g, '<code>$1</code>');
    body = body.replace(/\n\n/g, '</p><p>');
    body = body.replace(/\n/g, '<br>');
    body = '<p>' + body + '</p>';

    html += '<div class="course-section-body">' + body + '</div>';

    // Chart
    if (section.chart) {
      html += '<div class="course-section-chart" data-chart-type="' + esc(section.chart.type) + '">';
      if (section.chart.type === 'formula') {
        html += '<span class="katex-placeholder" data-latex="' + esc(section.chart.code) + '">' + esc(section.chart.code) + '</span>';
      } else if (section.chart.type === 'mermaid') {
        html += '<pre class="mermaid-placeholder">' + esc(section.chart.code) + '</pre>';
      }
      html += '</div>';
    }

    // Examples
    if (section.examples && section.examples.length) {
      html += '<div class="course-section-examples">';
      section.examples.forEach(function(ex) {
        html += '<div class="course-example">';
        html += '<div class="example-q">Q: ' + esc(ex.q) + '</div>';
        html += '<div class="example-a">A: ' + esc(ex.a) + '</div>';
        html += '</div>';
      });
      html += '</div>';
    }

    html += '</div>';
    return html;
  }

  function renderChartElements(container) {
    // KaTeX
    var katexPlaceholders = container.querySelectorAll('.katex-placeholder');
    if (katexPlaceholders.length) {
      loadKaTeX(function() {
        katexPlaceholders.forEach(function(el) {
          try {
            window.katex.render(el.dataset.latex, el, { throwOnError: false, displayMode: true });
          } catch(e) {
            el.textContent = el.dataset.latex;
          }
        });
      });
    }
    // Mermaid
    var mermaidPlaceholders = container.querySelectorAll('.mermaid-placeholder');
    if (mermaidPlaceholders.length) {
      loadMermaid(function() {
        mermaidPlaceholders.forEach(function(el, i) {
          try {
            var id = 'mermaid-' + Date.now() + '-' + i;
            window.mermaid.render(id, el.textContent).then(function(result) {
              el.innerHTML = result.svg;
            });
          } catch(e) {
            el.innerHTML = '<em>(图表渲染失败)</em>';
          }
        });
      });
    }
  }

  function render(course, container, opts) {
    opts = opts || {};
    var mode = opts.mode || 'compact';

    if (typeof container === 'string') {
      container = document.querySelector(container);
    }
    if (!container) return;

    var isCompact = mode === 'compact';
    var html = '';

    html += '<div class="course-card' + (isCompact ? ' collapsed' : ' office-preview') + '" data-course-id="' + esc(course.id) + '">';

    // Header
    html += '<div class="course-card-header">';
    html += '<span class="course-icon">📋</span>';
    html += '<span class="course-title">' + esc(course.title) + '</span>';
    html += '</div>';

    // Body
    html += '<div class="course-card-body">';
    (course.sections || []).forEach(function(section) {
      html += buildSectionHTML(section);
    });
    html += '</div>';

    // Expand/collapse (compact mode only)
    if (isCompact && (course.sections || []).length > 2) {
      html += '<div class="course-card-expand">';
      html += '<button class="course-expand-btn" onclick="var c=this.closest(\'.course-card\');c.classList.toggle(\'collapsed\');this.textContent=c.classList.contains(\'collapsed\')?\'展开▼\':\'收起▲\'">展开▼</button>';
      html += '</div>';
    }

    // Quiz
    if (course.quiz && course.quiz.length) {
      html += '<div class="course-card-quiz">';
      html += '<div class="quiz-label">🧪 检验题</div>';
      course.quiz.forEach(function(q) {
        html += '<div class="quiz-item">';
        if (q.type === 'feynman') {
          html += '💬 ' + esc(q.prompt);
        } else {
          html += '📝 ' + esc(q.prompt);
          if (q.options) {
            html += '<div style="margin-top:4px;padding-left:12px">';
            q.options.forEach(function(opt, i) {
              html += '<div>' + String.fromCharCode(65+i) + '. ' + esc(opt) + '</div>';
            });
            html += '</div>';
          }
        }
        html += '</div>';
      });
      html += '</div>';
    }

    // Footer
    html += '<div class="course-card-footer">';
    if (course.sources && course.sources.length) {
      var refText = course.sources.map(function(s) { return s.name || s.title; }).join(', ');
      html += '<span class="course-refs">📎 ' + esc(refText) + '</span>';
    }
    html += '<button class="btn-save-kb" onclick="CourseCard._saveToKB(\'' + esc(course.id) + '\')">添加到课本</button>';
    if (isCompact) {
      html += '<button class="btn-open-office" onclick="CourseCard._openInOffice(\'' + esc(course.id) + '\')">在办公室中打开</button>';
    }
    html += '</div>';

    html += '</div>';

    container.innerHTML = html;

    // Render charts
    renderChartElements(container);
  }

  // ── 课程注册表（跨页面传递 course 对象）──
  var _courseCache = {};

  function registerCourse(course) {
    _courseCache[course.id] = course;
    return course;
  }

  function getCourse(id) {
    return _courseCache[id] || null;
  }

  // ── 按钮回调 ──
  function _openInOffice(courseId) {
    // Store course and navigate to office
    var course = _courseCache[courseId];
    if (course) {
      try { sessionStorage.setItem('office_course', JSON.stringify(course)); } catch(e) {}
    }
    if (window.Router) {
      Router.navigate('/classroom/office?course=' + encodeURIComponent(courseId));
    }
  }

  function _saveToKB(courseId) {
    var course = _courseCache[courseId];
    if (!course) {
      alert('课程数据暂不可用');
      return;
    }
    fetch('/api/knowledge/ingest/course', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ course: course, set_id: 'courses' })
    }).then(function(r) { return r.json(); })
      .then(function(d) {
        if (d.ok) { alert('已添加到课本'); }
        else { alert('保存失败: ' + (d.error || '未知错误')); }
      })
      .catch(function() { alert('网络错误'); });
  }

  global.CourseCard = {
    render: render,
    registerCourse: registerCourse,
    getCourse: getCourse,
    _openInOffice: _openInOffice,
    _saveToKB: _saveToKB
  };

})(window);

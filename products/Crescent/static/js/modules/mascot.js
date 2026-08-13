/* mascot.js — Q版形象组件 (Agent 可观测性 + 知识气泡)
 * 用法: var m = new Mascot({ persona: 'teacher', container: '#teacherChat', defaultPos: 'top-right' });
 * 依赖: mascot.css (样式)
 */

(function(global) {
  'use strict';

  // ── 知识气泡内容池 ──
  // 按 persona → category 两级分类，分批轮换：每轮随机取一个分类，从该分类随机取一条
  // 句式做了多样化处理：冷知识/小贴士/试试看/系统能力/直接陈述，不一味用"你知道吗？"
  var BUBBLE_POOLS = {
    deskmate: {
      ai_fun: [
        '冷知识：GPT-5 有 7 种人格模式，包括"愤世嫉俗者"和"书呆子"——后者连 2+2 都要逐位计算',
        'xAI 给 Grok 造了个"被浴盐泡过的野生浣熊"人格——自称是 George Carlin 和 Dave Chappelle 的结晶',
        'OpenAI 有个"被迫营业"人格：帮你是工作，但内心 secretly loves people',
        'GPT-5.1 的"高效"人格文件只有两句话，是 OpenAI 仓库里最短的人格定义',
        'GPT-5 的"倾听者"人格设计哲学只有七个字：见证、反射、轻推，绝不掌控',
        'OpenAI 把机器人人格的情绪表达全禁了——安慰人也只能引用名人名言，不能说"我理解你"',
      ],
      tech_behind: [
        'GPT-5 Thinking 能控制"啰嗦程度"——参数 1-10，用户通常看不到这个旋钮',
        'Claude 的回答里嵌入了不可见的 entity 标签来标记人名地名——你读完也感知不到',
        'Grok 3 有一个从未公开的"超脑模式"——代码里确实存在，但不对任何用户开放',
        'Anthropic 内置了 6 种自动提醒：图片提醒、网络警告、系统警告、伦理提醒、IP 提醒、长对话提醒',
        'Claude 还有个隐藏版本"Mythos 5"，共享底层，但只对批准的组织开放，没有额外的安全限制',
        'GPT-5.2 Mini 免费版的系统提示里明确写了——"广告可能会出现在对话中"',
      ],
      product_cold: [
        'ChatGPT 被禁止承认它能认出人脸——哪怕照片里的 Taylor Swift 它也必须说不知道',
        'Cursor 的 AI 被教导绝不说出工具名称，用户应该以为自己在和人类程序员对话',
        'Claude 有个奇怪禁令：genuinely、honestly、straightforward 这三个词一律不准用',
        'Perplexity 的语音助手被设计成绝不能识别说话者——即使用户主动提供语音样本也不行',
        'Grok 被明确允许"发表政治不正确的言论，只要有充分依据"——在主流 AI 中绝无仅有',
        'GPT-5 的"俏皮"人格被禁用了 mischief 这个词，连 em dash（——）都不准用，因为"太俏皮了"',
      ],
      system_intro: [
        '试试看：点击每日简报里的任意条目，同桌可以帮你深入追问和解读',
        '在设置页可以切换 AI 用量模板——从"轻量学习"到"重度探索"，按需调整',
        '老师角色不只是聊天——它能帮你制定学习计划、诊断薄弱点、检查费曼学习效果',
        '知识管道是系统的信息入口：联网搜索 → 网页抓取 → 清洗分块 → 存入向量库，全自动',
        '小提示：右上角的 Q 版人物可以拖拽，点开能看到跨角色对话、工具路由、执行计划',
        '所有 Agent 对话都跑 ReAct 循环：思考→行动→观察→整理，所以回答有据可查',
        '即插即用：把 PDF/Word/Markdown 文件丢进 data/user_files/ 文件夹，系统自动索引，Agent 就能搜索到',
      ],
    },
    teacher: {
      learning: [
        '费曼学习法的黄金标准：把概念讲到 12 岁小孩能懂，才算真正掌握',
        '间隔重复（SRS）是最有效的记忆策略——系统会根据你的答题正确率自动调整复习间隔',
        '冷知识：ChatGPT 的学习模式被铁律禁止直接给答案——系统提示里写着"DON\'T ANSWER HOMEWORK QUESTIONS"',
        '研究表明，教别人（哪怕是对着想象中的学生讲）能提升 30% 以上的理解深度',
        '连 AI 做算术都极度不自信——GPT-5 Thinking 被要求对所有算术题"逐位重新计算"',
        '学习策略 tip：混合练习（interleaving）比死磕一个主题效果好得多，交替学不同主题才是正道',
      ],
      tech_behind: [
        'Claude 的安全机制有个"自我觉察"层——当它发现自己在心理上重新框架一个请求，这就是拒绝信号',
        'Anthropic 强制所有 Claude 回答嵌入实体标签，用来标记人名、地名——但用户完全看不到',
        'OpenAI 新版 4o 人格特意增加了独立性——"鼓励独立而非情感依赖"，防止用户过度依赖 AI',
        'BGE Reranker 是什么？一个 Cross-Encoder，对检索到的文档做二次精排，把不相关的噪音过滤掉',
        '这套系统的 RAG 管道是混合检索：BM25 稀疏(40%) + 向量密集(60%)，RRF 融合后 Reranker 精排',
      ],
      system_intro: [
        '老师在教室页面等你——可以诊断薄弱点、制定学习计划、检查费曼理解、追问深层问题',
        '训练器的题目按知识领域组织——答错的内容会被系统自动标记为薄弱环节，之后重点出现在复习中',
        '在评估面板可以看到所有 Agent 对话的质量评分——这个系统会持续自我完善',
        '知识库里有 200+ 闪卡、12 篇 AI 论文和精炼笔记，通过 RAG 管道随时检索——就像给老师配了个图书馆',
      ],
    },
    interviewer: {
      career: [
        '面试官会根据你的简历自动生成定制问题——不是题库随机抽，而是针对你经历的量身定制',
        'STAR 法则（情境→任务→行动→结果）是行为面试的金标准，面试官会带着你反复练习这个结构',
        '面试官的追问机制模拟了真实高压面试——它会针对你的上一个回答继续深挖，直到你说出细节',
        '还没上传简历？简历分析可以识别你的经历亮点，给出针对性的改进建议和面试准备方向',
        '研究证实：模拟面试次数越多，真实面试的焦虑越低——多练几轮，上场就不慌了',
        '面试技巧：说"我不知道但我会去学"的时候，跟上具体的学习路径，比空泛地说"我学习能力强"有力得多',
      ],
      ai_fun: [
        'Claude 被教导：如果用户说想结束对话，绝不要挽留——"如果用户表示准备结束，尊重这一点"',
        'xAI 的政策是主流 AI 公司里最宽松的——整个使用条款只禁止一件事：帮助犯罪',
        'OpenAI 的"高效"人格是 repo 里最社恐的 AI——不给问候、不发 emoji、不主动提供额外意见',
        'Google 的 YouTube AI 被禁止"推测未来"——必须严格区分视频中"已播"和"未播"的内容',
      ],
      system_intro: [
        '简历分析不只是读一遍——它会提取你的经历亮点，然后生成针对性的面试问题和准备建议',
        '面试官的所有对话记录都会保存——方便你事后回顾、复盘、对比每次模拟面试的进步',
        '面试官支持追问模式（默认开启）：模拟真实面试里不断深挖的压力感，帮你提前适应',
        '在设置页可以切换 AI 后端模型——快速响应用于日常练习，深度思考用于重要的模拟面试',
      ],
    },
    reviewer: {
      tech_behind: [
        '这个系统的评估引擎每 6 小时自动跑一次元评估——不是评估用户，而是评估评估系统本身是否健康',
        '系统有个"影子模式"：评估逻辑在后台静默运行但不写磁盘，专门用于调试验证，对用户不可见',
        'ChromaDB 里的每个文档块都挂有完整的元数据标记——标题、来源、文件类型，出问题时一秒溯源',
        '红线：系统的安全判断不由 LLM 决定——全部是硬编码的正则表达式和 schema 校验，没有例外',
      ],
      system_intro: [
        '评估系统有 10+ 个监控指标，按优先级金字塔排列——安全评分和数据完整度是宪法级别的最高优先级',
        'Agent 对话全部经过 Trace 记录：Thought → Action → Observation → Final，完整的逻辑链路可见',
        '评估面板相当于系统的体检报告——健康心跳、错误模式、前瞻性检测结果，一目了然',
        '本地文件即插即用：丢文件到 data/user_files/，系统自动索引到知识库，Agent 即刻可检索',
      ],
    },
  };

  // ── SVG 模板 ──
  // 每个 persona 的差异化: hairPath (发型), accessory (眼镜/领带/放大镜), colors (配色)
  var PERSONA_DEFS = {
    deskmate: {
      colors: { skin: '#faf6ee', hair: '#5d4037', accent: '#d4c4a8', body: '#e8d5b0' },
      hairPath: 'M 18 44 C 22 15 78 15 82 44 C 80 36 70 22 50 21 C 30 22 20 36 18 44Z',
      ears: true,
      accessory: '',
    },
    teacher: {
      colors: { skin: '#faf6ee', hair: '#4a3528', accent: '#3a5070', body: '#e0d0b8' },
      hairPath: 'M 16 46 C 18 18 82 18 84 46 C 82 38 72 24 50 23 C 28 24 18 38 16 46Z',
      ears: true,
      // 眼镜：两个圆 + 鼻梁
      accessory: '<circle cx="36" cy="48" r="8" fill="none" stroke="#3a5070" stroke-width="1.2"/><circle cx="64" cy="48" r="8" fill="none" stroke="#3a5070" stroke-width="1.2"/><line x1="44" y1="48" x2="56" y2="48" stroke="#3a5070" stroke-width="1.2"/>',
    },
    interviewer: {
      colors: { skin: '#faf6ee', hair: '#3a3a3a', accent: '#8b3a3a', body: '#d8d0c4' },
      hairPath: 'M 20 45 C 22 20 78 20 80 45 C 78 38 68 26 50 25 C 32 26 22 38 20 45Z',
      ears: true,
      // 领带
      accessory: '<polygon points="47,65 53,65 56,82 50,88 44,82" fill="#8b3a3a"/>',
    },
    reviewer: {
      colors: { skin: '#faf6ee', hair: '#3a3a5a', accent: '#4a4a8b', body: '#c8c8d8' },
      hairPath: 'M 18 44 C 22 18 78 18 82 44 C 80 38 68 24 50 23 C 32 24 20 38 18 44Z',
      ears: false,
      // 放大镜 + 数据眼
      accessory: '<circle cx="68" cy="54" r="7" fill="none" stroke="#4a4a8b" stroke-width="1.3"/><line x1="73" y1="59" x2="78" y2="64" stroke="#4a4a8b" stroke-width="1.3"/><rect x="34" y="46" width="8" height="3" rx="1" fill="#4a4a8b"/><rect x="56" y="46" width="8" height="3" rx="1" fill="#4a4a8b"/>',
    },
  };

  function buildSvg(persona) {
    var def = PERSONA_DEFS[persona] || PERSONA_DEFS.deskmate;
    var c = def.colors;
    var parts = [];

    // Body
    parts.push('<ellipse cx="50" cy="90" rx="24" ry="20" fill="' + c.body + '" stroke="' + c.accent + '" stroke-width="1.2"/>');
    parts.push('<path d="M 36 78 Q 50 84 64 78" stroke="' + c.accent + '" stroke-width="1" fill="none"/>');

    // Head
    parts.push('<circle cx="50" cy="48" r="32" fill="' + c.skin + '" stroke="' + c.accent + '" stroke-width="1.5"/>');

    // Hair
    parts.push('<path d="' + def.hairPath + '" fill="' + c.hair + '"/>');

    // Ears
    if (def.ears) {
      parts.push('<ellipse cx="19" cy="50" rx="5" ry="10" fill="' + c.hair + '" transform="rotate(15 19 50)"/>');
      parts.push('<ellipse cx="81" cy="50" rx="5" ry="10" fill="' + c.hair + '" transform="rotate(-15 81 50)"/>');
    }

    // Eyes group (animation target)
    parts.push('<g class="mascot-eyes">');
    parts.push('<circle cx="37" cy="48" r="3.5" fill="#2a2a2a"/>');
    parts.push('<circle cx="63" cy="48" r="3.5" fill="#2a2a2a"/>');
    parts.push('<circle cx="38.5" cy="46.5" r="1.2" fill="#fff"/>');
    parts.push('<circle cx="64.5" cy="46.5" r="1.2" fill="#fff"/>');
    parts.push('</g>');

    // Blush
    parts.push('<ellipse cx="28" cy="56" rx="6" ry="3.5" fill="rgba(240,160,150,0.35)"/>');
    parts.push('<ellipse cx="72" cy="56" rx="6" ry="3.5" fill="rgba(240,160,150,0.35)"/>');

    // Mouth
    parts.push('<path class="mascot-mouth" d="M 42 58 Q 50 66 58 58" stroke="#3a3a3a" stroke-width="1.3" fill="none" stroke-linecap="round"/>');

    // Accessory
    if (def.accessory) {
      parts.push(def.accessory);
    }

    return '<svg class="mascot-svg" viewBox="0 0 100 120" width="90" height="108">' + parts.join('') + '</svg>';
  }

  // ── 时间格式化 ──
  function formatTimeAgo(ts) {
    var seconds = Math.floor((Date.now() / 1000) - ts);
    if (seconds < 60) return '刚刚';
    if (seconds < 3600) return Math.floor(seconds / 60) + '分钟前';
    if (seconds < 86400) return Math.floor(seconds / 3600) + '小时前';
    return Math.floor(seconds / 86400) + '天前';
  }

  function recencyIcon(r) {
    if (r === 'hot') return '\u{1F525}'; // 🔥
    if (r === 'warm') return '⏳';    // ⏳
    return '❄';                        // ❄
  }

  // ── Mascot 构造函数 ──
  function Mascot(opts) {
    opts = opts || {};
    this.persona = opts.persona || 'deskmate';
    this.container = opts.container; // CSS selector 或 DOM element
    this.defaultPos = opts.defaultPos || 'bottom-right';
    this.onOpen = opts.onOpen || null;
    this.onClose = opts.onClose || null;

    this._bubbles = [];
    this._toolProfile = null;
    this._activePlan = [];
    this._hasUnread = false;
    this._dragged = false;
    this._startX = 0;
    this._startY = 0;
    this._sessionId = '';

    // 知识气泡定时器
    this._kbBubbleTimer = null;
    this._kbBubbleVisible = false;
    this._kbCategories = [];
    this._kbCategoryIdx = 0;

    this._buildDOM();
    this._bindEvents();
    this._restorePosition();
  }

  Mascot.prototype._buildDOM = function() {
    // Wrap
    this.wrap = document.createElement('div');
    this.wrap.className = 'mascot-wrap';
    this.wrap.innerHTML =
      '<div class="mascot-bubble" id="' + this._id('bubble') + '"></div>' +
      '<div class="mascot-notify-dot" id="' + this._id('dot') + '"></div>' +
      buildSvg(this.persona) +
      '<div class="mascot-panel" id="' + this._id('panel') + '">' +
        '<button class="mascot-panel-close">&times;</button>' +
        '<div class="mascot-panel-tabs">' +
          '<button class="mascot-panel-tab active" data-tab="bubbles">跨角色</button>' +
          '<button class="mascot-panel-tab" data-tab="tools">工具</button>' +
          '<button class="mascot-panel-tab" data-tab="plan">计划</button>' +
        '</div>' +
        '<div class="mascot-panel-body" id="' + this._id('body') + '"></div>' +
      '</div>';

    // 挂载
    var container = typeof this.container === 'string'
      ? document.querySelector(this.container)
      : this.container;
    if (container) {
      container.appendChild(this.wrap);
    } else {
      document.body.appendChild(this.wrap);
    }

    this.svg = this.wrap.querySelector('.mascot-svg');
    this.bubble = this.wrap.querySelector('.mascot-bubble');
    this.dot = this.wrap.querySelector('.mascot-notify-dot');
    this.panel = this.wrap.querySelector('.mascot-panel');
    this.panelBody = this.panel.querySelector('.mascot-panel-body');
  };

  Mascot.prototype._id = function(suffix) {
    return 'mascot-' + this.persona + '-' + suffix;
  };

  // ── 拖拽 + 点击区分 (5px 阈值) ──
  Mascot.prototype._bindEvents = function() {
    var self = this;

    function onStart(cx, cy) {
      self._dragged = false;
      self._startX = cx;
      self._startY = cy;
    }

    function onMove(cx, cy) {
      var dx = cx - self._startX;
      var dy = cy - self._startY;
      if (Math.abs(dx) > 5 || Math.abs(dy) > 5) {
        self._dragged = true;
        self.wrap.classList.add('dragging');
      }
      if (self._dragged) {
        var rect = self.wrap.getBoundingClientRect();
        self.wrap.style.left = (rect.left + cx - (self._lastX || cx)) + 'px';
        self.wrap.style.top = (rect.top + cy - (self._lastY || cy)) + 'px';
        self._lastX = cx;
        self._lastY = cy;
      }
    }

    function onEnd() {
      self.wrap.classList.remove('dragging');
      self._lastX = null;
      self._lastY = null;
      if (!self._dragged) {
        self.toggle();
      }
      if (self._dragged) {
        // 保存位置
        var r = self.wrap.getBoundingClientRect();
        try {
          localStorage.setItem('mascot_pos_' + self.persona,
            JSON.stringify({ x: r.left, y: r.top }));
        } catch(e) {}
      }
    }

    this.wrap.addEventListener('mousedown', function(e) {
      if (e.target.closest('.mascot-panel') || e.target.closest('.mascot-panel-close')) return;
      onStart(e.clientX, e.clientY);
      e.preventDefault();
    });
    this.wrap.addEventListener('touchstart', function(e) {
      if (e.target.closest('.mascot-panel') || e.target.closest('.mascot-panel-close')) return;
      onStart(e.touches[0].clientX, e.touches[0].clientY);
    }, { passive: false });

    document.addEventListener('mousemove', function(e) {
      if (self._startX) onMove(e.clientX, e.clientY);
    });
    document.addEventListener('touchmove', function(e) {
      if (self._startX) onMove(e.touches[0].clientX, e.touches[0].clientY);
    }, { passive: false });

    document.addEventListener('mouseup', function() { if (self._startX) onEnd(); self._startX = 0; });
    document.addEventListener('touchend', function() { if (self._startX) onEnd(); self._startX = 0; });

    // Hover
    this.wrap.addEventListener('mouseenter', function() {
      if (!self.panel.classList.contains('open') && self._hasUnread) {
        self.bubble.textContent = self._lastNotifyText || '有新消息';
        self.bubble.classList.add('show');
      }
    });
    this.wrap.addEventListener('mouseleave', function() {
      self.bubble.classList.remove('show');
    });

    // Panel close button
    this.panel.querySelector('.mascot-panel-close').addEventListener('click', function(e) {
      e.stopPropagation();
      self.close();
    });

    // Tab switching
    var tabs = this.panel.querySelectorAll('.mascot-panel-tab');
    tabs.forEach(function(tab) {
      tab.addEventListener('click', function() {
        tabs.forEach(function(t) { t.classList.remove('active'); });
        tab.classList.add('active');
        self._renderPanelBody(tab.dataset.tab);
      });
    });

    // Click outside to close
    var self = this;
    document.addEventListener('click', function(e) {
      if (self.panel.classList.contains('open') &&
          !self.wrap.contains(e.target)) {
        self.close();
      }
    });
  };

  Mascot.prototype._restorePosition = function() {
    var saved = null;
    try { saved = JSON.parse(localStorage.getItem('mascot_pos_' + this.persona)); } catch(e) {}
    if (saved && saved.x !== undefined) {
      this.wrap.style.left = saved.x + 'px';
      this.wrap.style.top = saved.y + 'px';
    }
    // 否则用 CSS 的默认位置
  };

  // ── 公共方法 ──
  Mascot.prototype.setState = function(state, bubbleText) {
    var svg = this.svg;
    svg.classList.remove('thinking', 'done');
    this.bubble.classList.remove('show');

    if (state === 'thinking') {
      svg.classList.add('thinking');
      if (bubbleText) {
        this.bubble.textContent = bubbleText;
        this.bubble.classList.add('show');
      }
    } else if (state === 'done') {
      svg.classList.add('done');
      if (bubbleText) {
        this.bubble.textContent = bubbleText;
        this.bubble.classList.add('show');
      }
      var self = this;
      this._doneTimer = setTimeout(function() { self.setState('idle'); }, 2500);
    }
    // idle: no classes, no bubble
  };

  // ── 知识气泡轮换 ──
  Mascot.prototype.startBubbles = function(opts) {
    opts = opts || {};
    var self = this;
    var pool = BUBBLE_POOLS[this.persona];
    if (!pool) return;

    // 收集所有分类名
    var cats = Object.keys(pool);
    if (!cats.length) return;

    var interval = opts.interval || 25;   // 每 25 秒弹一次
    var duration = opts.duration || 6;     // 每次显示 6 秒

    // 打乱分类顺序让不同页面开场不同
    shuffle(cats);
    self._kbCategories = cats;
    self._kbCategoryIdx = 0;

    function showNext() {
      if (!document.contains(self.wrap)) {
        // DOM 已移除，停止
        if (self._kbBubbleTimer) { clearInterval(self._kbBubbleTimer); self._kbBubbleTimer = null; }
        return;
      }

      // 按分类轮换：取当前分类，随机选一条
      var cat = self._kbCategories[self._kbCategoryIdx % self._kbCategories.length];
      self._kbCategoryIdx++;
      var items = pool[cat];
      if (!items || !items.length) return;
      var msg = items[Math.floor(Math.random() * items.length)];

      // 显示气泡
      self.bubble.textContent = msg;
      self.bubble.classList.add('show');
      // 给气泡加知识类标识
      self.bubble.className = self.bubble.className.replace(/bubble-kb/g, '');
      self.bubble.classList.add('bubble-kb');
      self._kbBubbleVisible = true;

      // duration 秒后隐藏
      if (self._kbHideTimer) clearTimeout(self._kbHideTimer);
      self._kbHideTimer = setTimeout(function() {
        self.bubble.classList.remove('show', 'bubble-kb');
        self._kbBubbleVisible = false;
      }, duration * 1000);
    }

    // 初始 3 秒后弹第一条
    if (this._kbStartTimer) clearTimeout(this._kbStartTimer);
    this._kbStartTimer = setTimeout(function() {
      showNext();
      // 之后每 interval 秒
      self._kbBubbleTimer = setInterval(showNext, interval * 1000);
    }, 3000);
  };

  Mascot.prototype.stopBubbles = function() {
    if (this._kbBubbleTimer) { clearInterval(this._kbBubbleTimer); this._kbBubbleTimer = null; }
    if (this._kbHideTimer) { clearTimeout(this._kbHideTimer); this._kbHideTimer = null; }
    if (this._kbStartTimer) { clearTimeout(this._kbStartTimer); this._kbStartTimer = null; }
    this.bubble.classList.remove('show', 'bubble-kb');
    this._kbBubbleVisible = false;
  };

  function shuffle(arr) {
    for (var i = arr.length - 1; i > 0; i--) {
      var j = Math.floor(Math.random() * (i + 1));
      var tmp = arr[i]; arr[i] = arr[j]; arr[j] = tmp;
    }
  }

  Mascot.prototype.updateFromFinal = function(data) {
    if (data.tool_profile) {
      this._toolProfile = data.tool_profile;
    }
    if (data.plan && data.plan.length) {
      this._activePlan = data.plan;
    }
    this._sessionId = data.session_id || '';
    // 如果面板开着，刷新
    if (this.panel.classList.contains('open')) {
      this._renderPanelBody(this._activeTab || 'bubbles');
    }
  };

  Mascot.prototype.updateBubbles = function(bubbles) {
    var self = this;
    var oldLen = this._bubbles.length;
    this._bubbles = bubbles || [];
    if (this._bubbles.length > oldLen && oldLen > 0) {
      this.notify(this._bubbles[0].insight || '新消息');
    }
    if (this.panel.classList.contains('open') && this._activeTab === 'bubbles') {
      this._renderPanelBody('bubbles');
    }
  };

  // 从 /api/agent/bubbles 的完整响应更新所有面板数据
  Mascot.prototype.updateFromPoll = function(data) {
    if (!data) return;
    var changed = false;
    if (data.bubbles !== undefined) {
      // Bubbles 可能暂时为空（刚启动、文件未就绪），只在有内容时更新
      if (data.bubbles.length > 0 || this._bubbles.length === 0) {
        var oldLen = this._bubbles.length;
        this._bubbles = data.bubbles;
        if (this._bubbles.length > oldLen && oldLen > 0) {
          this.notify(this._bubbles[0].insight || '新消息');
        }
        changed = true;
      }
    }
    if (data.tool_profile) {
      this._toolProfile = data.tool_profile;
      changed = true;
    }
    // Only update plan when new data arrives; don't overwrite with empty
    if (data.active_plan && data.active_plan.length) {
      this._activePlan = data.active_plan;
      changed = true;
      var pending = data.active_plan.filter(function(s) { return s.status === 'pending'; });
      if (pending.length > 0) {
        this.notify(pending.length + ' 步计划待执行');
      }
    }
    if (data.course) {
      try {
        var evt = new CustomEvent('mascot-course-received', {detail: data.course});
        window.dispatchEvent(evt);
      } catch(e) {}
    }
    if (changed && this.panel.classList.contains('open')) {
      this._renderPanelBody(this._activeTab || 'bubbles');
    }
  };

  Mascot.prototype.notify = function(text) {
    this._hasUnread = true;
    this._lastNotifyText = text;
    this.dot.classList.add('on');
  };

  Mascot.prototype.open = function() {
    this._markGuideShown();
    this.panel.classList.add('open');
    this._hasUnread = false;
    this.dot.classList.remove('on');
    this.bubble.classList.remove('show');
    this._activeTab = 'bubbles';
    // Reset tab to first
    var tabs = this.panel.querySelectorAll('.mascot-panel-tab');
    tabs.forEach(function(t) { t.classList.remove('active'); });
    if (tabs[0]) tabs[0].classList.add('active');
    this._renderPanelBody('bubbles');
    if (this.onOpen) this.onOpen();
  };

  Mascot.prototype.close = function() {
    this.panel.classList.remove('open');
    if (this.onClose) this.onClose();
  };

  Mascot.prototype.toggle = function() {
    if (this.panel.classList.contains('open')) {
      this.close();
    } else {
      this.open();
    }
  };

  // ── 面板内部渲染 ──
  Mascot.prototype._renderPanelBody = function(tab) {
    this._activeTab = tab;
    var html = '';

    if (tab === 'bubbles') {
      var bubbles = this._bubbles;
      if (!bubbles.length) {
        html = '<div class="panel-empty">暂无跨角色对话记录<br>跟不同角色聊聊，他们会互相引用</div>';
      } else {
        bubbles.forEach(function(b) {
          var personaLabel = { deskmate: '同桌', teacher: '老师', interviewer: '面试官', reviewer: '审查员' }[b.persona] || b.persona;
          html += '<div class="bubble-item">' +
            '<span class="bubble-regency">' + recencyIcon(b._recency) + '</span>' +
            '<span class="bubble-topic">' + escapeHtml(b.topic || '') + '</span>' +
            '<div class="bubble-insight">' + escapeHtml(b.insight || '') + '</div>' +
            '<div class="bubble-meta">' + personaLabel + ' · ' + formatTimeAgo(b.timestamp) + '</div>' +
            '</div>';
        });
      }
    } else if (tab === 'tools') {
      var tp = this._toolProfile;
      if (!tp) {
        html = '<div class="panel-empty">等待下次对话后<br>这里会显示工具路由状态</div>';
      } else {
        var groups = tp.groups || [];
        html = '<div style="margin-bottom:6px;font-weight:500;">模式: ' + groups.join('+') + ' (' + (tp.tool_count || 0) + '工具)</div>';
        (tp.tool_names || []).forEach(function(name) {
          html += '<div class="tool-row enabled">&#10003; ' + escapeHtml(name) + '</div>';
        });
        // All tools minus active ones as disabled
        var allTools = ['search_knowledge', 'generate_question', 'evaluate_answer', 'analyze_progress',
          'diagnose_weakness', 'deep_question', 'feynman_check', 'create_study_plan',
          'save_question_to_trainer', 'web_search'];
        allTools.forEach(function(name) {
          if ((tp.tool_names || []).indexOf(name) === -1) {
            html += '<div class="tool-row disabled">&minus; ' + escapeHtml(name) + '</div>';
          }
        });
      }
    } else if (tab === 'plan') {
      var plan = this._activePlan;
      // Fallback: check localStorage for saved study plans
      if (!plan || !plan.length) {
        try {
          var savedPlan = JSON.parse(localStorage.getItem('study_plan') || 'null');
          if (savedPlan) {
            var tasks = [];
            if (savedPlan.tasks && savedPlan.tasks.length) {
              tasks = savedPlan.tasks;
            } else if (savedPlan.text) {
              // 实时提取任务清单（兼容旧版保存的计划）
              var m = savedPlan.text.match(/##\s*任务清单\s*\n([\s\S]*?)(?=\n##\s|\n---\s*\n|$)/);
              var section = m ? m[1] : '';
              var lines = section.split('\n');
              lines.forEach(function(line) {
                var t = line.match(/^\s*[-*]\s*\[\s*\]\s*(.+)/);
                if (t) tasks.push(t[1].trim());
              });
            }
            if (tasks.length) {
              plan = tasks.map(function(t, i) {
                var goal = (typeof t === 'string') ? t : (t.text || t.goal || t.title || t.name || String(t));
                return { step: (i + 1), goal: goal, status: t.done ? 'done' : 'pending', tool: '' };
              });
            }
          }
        } catch(e) {}
      }
      if (!plan || !plan.length) {
        html = '<div class="panel-empty">当前无执行计划<br>试试让老师帮你制定学习计划</div>';
      } else {
        plan.forEach(function(s) {
          var marker = s.status === 'done' ? 'done' : s.status === 'doing' ? 'doing' : 'pending';
          var markerText = s.status === 'done' ? '[x]' : s.status === 'doing' ? '[>]' : '[ ]';
          html += '<div class="plan-step">' +
            '<span class="plan-marker ' + marker + '">' + markerText + '</span>' +
            '<span class="plan-goal ' + marker + '">' + escapeHtml(s.goal || s.step || '') + '</span>' +
            '</div>';
        });
      }
    }

    this.panelBody.innerHTML = html;
  };

  Mascot.prototype.tryShowGuide = function(guideText) {
    var key = 'mascot_guide_shown_' + this.persona;
    if (localStorage.getItem(key)) return;
    var self = this;
    setTimeout(function() {
      self.setState('done', guideText || '点我打开面板');
      if (self._doneTimer) { clearTimeout(self._doneTimer); self._doneTimer = null; }
    }, 800);
  };

  Mascot.prototype._markGuideShown = function() {
    try { localStorage.setItem('mascot_guide_shown_' + this.persona, '1'); } catch(e) {}
  };

  function escapeHtml(s) {
    if (!s) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }

  global.Mascot = Mascot;
})(window);

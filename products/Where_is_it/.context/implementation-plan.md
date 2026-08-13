# Where_is_it 实施计划

> **For agentic workers:** 使用 superpowers:subagent-driven-development 或 superpowers:executing-plans 按任务逐一实施。步骤用 `- [ ]` checkbox 追踪。

**Goal:** 构建微信小程序 MVP，帮助用户通过语音记录+智能提醒防止丢失日常物品

**Architecture:** 微信小程序原生（WXML/WXSS/JS），纯本地 wx.Storage 存储。六个模块：存储层、Onboarding、场景管理、Agent NLP 解析、提醒引擎、主页+时间线 UI

**Tech Stack:** 微信小程序原生、wx.Storage、wx.getLocation、wx.startRecord、wx.requestSubscribeMessage

## Global Constraints

- 纯本地存储，不上传任何数据到云端
- 编码（记录位置）操作 <3 秒
- 字号清晰可读，面向中老年可用
- 提醒不过度打扰，频率分级可选
- 保留 LLM 接口但不接入
- 不创建文档文件

## 前置准备

### WeChat Developer Tools

1. 下载安装 [微信开发者工具](https://developers.weixin.qq.com/miniprogram/dev/devtools/download.html)
2. 注册小程序账号（个人即可）：[mp.weixin.qq.com](https://mp.weixin.qq.com) → 立即注册 → 小程序
3. 登录开发者工具，创建新项目：
   - 项目名称：Where_is_it
   - 目录：指向 `products/Where_is_it/`
   - AppID：用注册获得的（或选"测试号"先开发）
   - 开发模式：小程序
   - 模板：选择 "不使用模板"（JS 基础库）

### 项目文件结构

```
Where_is_it/
├── app.js
├── app.json
├── app.wxss
├── project.config.json
├── sitemap.json
├── pages/
│   ├── onboarding/
│   │   ├── onboarding.js
│   │   ├── onboarding.json
│   │   ├── onboarding.wxml
│   │   └── onboarding.wxss
│   ├── home/
│   │   ├── home.js
│   │   ├── home.json
│   │   ├── home.wxml
│   │   └── home.wxss
│   └── timeline/
│       ├── timeline.js
│       ├── timeline.json
│       ├── timeline.wxml
│       └── timeline.wxss
├── utils/
│   ├── storage.js
│   ├── agent.js
│   ├── reminder.js
│   └── scene.js
└── .context/    (已存在)
```

---

### Task 1: 项目脚手架

**Files:**
- Create: `app.js`, `app.json`, `app.wxss`, `project.config.json`, `sitemap.json`

**Produces:** 可启动的小程序骨架，在 DevTools 中看到模拟器界面

- [ ] **Step 1: 创建 project.config.json**

```json
{
  "description": "Where_is_it - 前瞻记忆辅助",
  "packOptions": { "ignore": [".context/**"] },
  "setting": {
    "urlCheck": true,
    "es6": true,
    "enhance": true,
    "postcss": true,
    "minified": true
  },
  "appid": "your-appid-here",
  "projectname": "Where_is_it",
  "libVersion": "3.3.4"
}
```

- [ ] **Step 2: 创建 sitemap.json**

```json
{
  "rules": [{ "action": "allow", "page": "*" }]
}
```

- [ ] **Step 3: 创建 app.json**

```json
{
  "pages": [
    "pages/onboarding/onboarding",
    "pages/home/home",
    "pages/timeline/timeline"
  ],
  "window": {
    "navigationBarTitleText": "Where is it",
    "navigationBarBackgroundColor": "#ffffff",
    "navigationBarTextStyle": "black",
    "backgroundColor": "#f5f5f5"
  },
  "permission": {
    "scope.userLocation": { "desc": "需要获取位置来识别你当前所在的场景" },
    "scope.record": { "desc": "需要麦克风权限来语音记录物品位置" }
  },
  "requiredPrivateInfos": ["getLocation"],
  "style": "v2",
  "sitemapLocation": "sitemap.json"
}
```

- [ ] **Step 4: 创建 app.js**

```javascript
App({
  onLaunch() {
    const answered = wx.getStorageSync('onboarding_done');
    if (answered) {
      wx.switchTab({ url: '/pages/home/home' });
    }
  },

  globalData: {
    currentScene: 'home',
    reminderSettings: null
  }
});
```

- [ ] **Step 5: 创建 app.wxss**

```css
/* 全局 CSS 变量 — 中老年友好：大字号、高对比度 */
page {
  --color-bg: #f5f5f5;
  --color-surface: #ffffff;
  --color-text: #1a1a1a;
  --color-text-secondary: #666666;
  --color-primary: #2563eb;
  --color-primary-light: #dbeafe;
  --color-danger: #dc2626;
  --color-divider: #e5e5e5;
  --font-size-title: 36rpx;
  --font-size-body: 32rpx;
  --font-size-caption: 26rpx;
  --font-size-large: 44rpx;
  --radius: 16rpx;
  --shadow: 0 2rpx 12rpx rgba(0,0,0,0.08);

  background-color: var(--color-bg);
  font-family: -apple-system, BlinkMacSystemFont, "PingFang SC", "Helvetica Neue", sans-serif;
  font-size: var(--font-size-body);
  color: var(--color-text);
  line-height: 1.6;
}
```

- [ ] **Step 6: 验证 — 在 DevTools 中打开项目**

在微信开发者工具中打开 `products/Where_is_it/` 目录，确认模拟器显示空白页面无报错。

- [ ] **Step 7: Commit**

```bash
git add -A && git commit -m "feat: mini-program project scaffold"
```

---

### Task 2: 存储层

**Files:**
- Create: `utils/storage.js`

**Produces:** 所有数据模型的 CRUD 函数，后续所有模块依赖此层

- [ ] **Step 1: 创建 utils/storage.js**

```javascript
// 数据键名常量
const KEYS = {
  ITEMS: 'items',
  HISTORY: 'location_history',
  SCENES: 'scenes',
  SETTINGS: 'reminder_settings',
  ONBOARDING: 'onboarding_answers',
  ONBOARDING_DONE: 'onboarding_done'
};

// === Items ===

function getItems() {
  return wx.getStorageSync(KEYS.ITEMS) || [];
}

function getItem(id) {
  return getItems().find(i => i.id === id) || null;
}

function upsertItem(item) {
  const items = getItems();
  const idx = items.findIndex(i => i.id === item.id);
  if (idx >= 0) {
    items[idx] = { ...items[idx], ...item, last_updated: Date.now() };
  } else {
    item.id = item.id || 'item_' + Date.now();
    item.created_at = item.created_at || Date.now();
    item.last_updated = Date.now();
    item.importance = item.importance || 1;
    item.icon = item.icon || '📦';
    item.current_location = item.current_location || '未记录';
    items.push(item);
  }
  wx.setStorageSync(KEYS.ITEMS, items);
  return item;
}

function deleteItem(id) {
  const items = getItems().filter(i => i.id !== id);
  wx.setStorageSync(KEYS.ITEMS, items);
}

// === Location History ===

function getHistory(itemId) {
  const all = wx.getStorageSync(KEYS.HISTORY) || [];
  return all.filter(h => h.item_id === itemId).sort((a, b) => b.timestamp - a.timestamp);
}

function addHistory(entry) {
  const all = wx.getStorageSync(KEYS.HISTORY) || [];
  entry.id = 'hist_' + Date.now();
  entry.timestamp = entry.timestamp || Date.now();
  all.push(entry);
  wx.setStorageSync(KEYS.HISTORY, all);
  return entry;
}

// === Scenes ===

function getScenes() {
  return wx.getStorageSync(KEYS.SCENES) || getDefaultScenes();
}

function getDefaultScenes() {
  return [
    { id: 'home', name: '家', icon: '🏠', geo_fence: null, is_default: true, trigger_items: [] },
    { id: 'door', name: '大门', icon: '🚪', geo_fence: null, is_default: true, trigger_items: [] },
    { id: 'office', name: '公司', icon: '🏢', geo_fence: null, is_default: true, trigger_items: [] },
    { id: 'car', name: '车上', icon: '🚗', geo_fence: null, is_default: true, trigger_items: [] }
  ];
}

function upsertScene(scene) {
  const scenes = getScenes();
  const idx = scenes.findIndex(s => s.id === scene.id);
  if (idx >= 0) {
    scenes[idx] = { ...scenes[idx], ...scene };
  } else {
    scene.id = scene.id || 'scene_' + Date.now();
    scenes.push(scene);
  }
  wx.setStorageSync(KEYS.SCENES, scenes);
  return scene;
}

// === Settings ===

function getSettings() {
  const defaults = {
    frequency_level: 2,
    quiet_start: 2200,
    quiet_end: 800,
    geo_reminder_enabled: true,
    curve_reminder_enabled: true
  };
  return { ...defaults, ...(wx.getStorageSync(KEYS.SETTINGS) || {}) };
}

function saveSettings(settings) {
  wx.setStorageSync(KEYS.SETTINGS, { ...getSettings(), ...settings });
}

// === Onboarding ===

function getOnboardingAnswers() {
  return wx.getStorageSync(KEYS.ONBOARDING) || null;
}

function saveOnboarding(answers) {
  wx.setStorageSync(KEYS.ONBOARDING, answers);
  wx.setStorageSync(KEYS.ONBOARDING_DONE, true);
}

function isOnboardingDone() {
  return !!wx.getStorageSync(KEYS.ONBOARDING_DONE);
}

// === Seed Data (Onboarding 后调用) ===

function seedDefaultItems(commonItems) {
  const icons = { '钥匙': '🔑', '手机': '📱', '钱包': '👛', '伞': '☂️', '耳机': '🎧', '眼镜': '👓', '水杯': '🥤' };
  commonItems.forEach(name => {
    if (!getItems().find(i => i.name === name)) {
      upsertItem({ name, icon: icons[name] || '📦', importance: 1 });
    }
  });
}

module.exports = {
  getItems, getItem, upsertItem, deleteItem,
  getHistory, addHistory,
  getScenes, upsertScene,
  getSettings, saveSettings,
  getOnboardingAnswers, saveOnboarding, isOnboardingDone,
  seedDefaultItems
};
```

- [ ] **Step 2: 验证 — 在 app.js 中引入并测试**

在 `app.js` 的 `onLaunch` 中临时加入：

```javascript
const storage = require('./utils/storage');
console.log('Items:', storage.getItems());
console.log('Scenes:', storage.getScenes());
console.log('Settings:', storage.getSettings());
```

在 DevTools Console 中确认输出正常。确认后删除临时 console 代码。

- [ ] **Step 3: Commit**

```bash
git add utils/storage.js && git commit -m "feat: storage layer with CRUD for items, history, scenes, settings"
```

---

### Task 3: Onboarding 页面

**Files:**
- Create: `pages/onboarding/onboarding.js`, `pages/onboarding/onboarding.json`, `pages/onboarding/onboarding.wxml`, `pages/onboarding/onboarding.wxss`

**Consumes:** `utils/storage.js` (saveOnboarding, seedDefaultItems)

**Produces:** 新用户首次打开看到的引导问卷，完成后跳转主页

- [ ] **Step 1: 创建 pages/onboarding/onboarding.json**

```json
{
  "usingComponents": {},
  "navigationBarTitleText": "欢迎使用"
}
```

- [ ] **Step 2: 创建 pages/onboarding/onboarding.js**

```javascript
const storage = require('../../utils/storage');

Page({
  data: {
    step: 0,
    selectedItems: [],
    selectedScenarios: [],
    scheduleType: '',
    reminderLevel: '',
    commonItems: ['钥匙', '手机', '钱包', '伞', '耳机', '眼镜', '水杯'],
    scenarioOptions: ['出门时', '下班时', '换地方时', '关门前'],
    scheduleOptions: [
      { value: 'fixed', label: '固定通勤（朝九晚五）' },
      { value: 'flexible', label: '不固定（时间自由）' },
      { value: 'mixed', label: '两者之间' }
    ],
    reminderOptions: [
      { value: 'light', label: '轻度 — 一天2~3次，温和提醒', maxPerDay: 3 },
      { value: 'medium', label: '中度 — 按记忆曲线，每天约5次', maxPerDay: 5 },
      { value: 'heavy', label: '重度 — 较频繁，适合容易忘东西', maxPerDay: 8 }
    ]
  },

  onToggleItem(e) {
    const name = e.currentTarget.dataset.name;
    let selected = this.data.selectedItems;
    if (selected.includes(name)) {
      selected = selected.filter(s => s !== name);
    } else {
      selected = [...selected, name];
    }
    this.setData({ selectedItems: selected });
  },

  onToggleScenario(e) {
    const name = e.currentTarget.dataset.name;
    let selected = this.data.selectedScenarios;
    if (selected.includes(name)) {
      selected = selected.filter(s => s !== name);
    } else {
      selected = [...selected, name];
    }
    this.setData({ selectedScenarios: selected });
  },

  onSelectSchedule(e) {
    this.setData({ scheduleType: e.currentTarget.dataset.value });
  },

  onSelectReminder(e) {
    this.setData({ reminderLevel: e.currentTarget.dataset.value });
  },

  onNext() {
    const { step, selectedItems, selectedScenarios, scheduleType, reminderLevel } = this.data;
    if (step === 0 && selectedItems.length === 0) return;
    if (step === 3 && !reminderLevel) return;
    this.setData({ step: step + 1 });
  },

  onFinish() {
    const { selectedItems, selectedScenarios, scheduleType, reminderLevel, reminderOptions } = this.data;
    const level = reminderOptions.find(r => r.value === reminderLevel);

    storage.saveOnboarding({
      common_items: selectedItems,
      forget_scenarios: selectedScenarios,
      schedule_type: scheduleType,
      reminder_preference: reminderLevel
    });

    storage.seedDefaultItems(selectedItems);

    storage.saveSettings({
      frequency_level: reminderLevel === 'light' ? 1 : reminderLevel === 'medium' ? 2 : 3,
      max_reminders_per_day: level ? level.maxPerDay : 5
    });

    wx.reLaunch({ url: '/pages/home/home' });
  }
});
```

- [ ] **Step 3: 创建 pages/onboarding/onboarding.wxml**

```xml
<view class="onboarding">
  <!-- Step 0: 选择常忘物品 -->
  <view class="step" wx:if="{{step === 0}}">
    <text class="step-title">你最容易忘带什么？</text>
    <text class="step-sub">可多选</text>
    <view class="option-grid">
      <view
        class="option-chip {{selectedItems.indexOf(item) > -1 ? 'active' : ''}}"
        wx:for="{{commonItems}}"
        wx:key="*this"
        data-name="{{item}}"
        bindtap="onToggleItem"
      >{{item}}</view>
    </view>
    <button class="btn-primary" bindtap="onNext">下一步</button>
  </view>

  <!-- Step 1: 常见遗忘场景 -->
  <view class="step" wx:if="{{step === 1}}">
    <text class="step-title">什么场景最容易忘东西？</text>
    <text class="step-sub">可多选</text>
    <view class="option-list">
      <view
        class="option-row {{selectedScenarios.indexOf(item) > -1 ? 'active' : ''}}"
        wx:for="{{scenarioOptions}}"
        wx:key="*this"
        data-name="{{item}}"
        bindtap="onToggleScenario"
      >{{item}}</view>
    </view>
    <button class="btn-primary" bindtap="onNext">下一步</button>
  </view>

  <!-- Step 2: 作息类型 -->
  <view class="step" wx:if="{{step === 2}}">
    <text class="step-title">你的日常作息？</text>
    <view class="option-list">
      <view
        class="option-row {{scheduleType === item.value ? 'active' : ''}}"
        wx:for="{{scheduleOptions}}"
        wx:key="value"
        data-value="{{item.value}}"
        bindtap="onSelectSchedule"
      >{{item.label}}</view>
    </view>
    <button class="btn-primary" bindtap="onNext" disabled="{{!scheduleType}}">下一步</button>
  </view>

  <!-- Step 3: 提醒频率 -->
  <view class="step" wx:if="{{step === 3}}">
    <text class="step-title">提醒频率偏好？</text>
    <text class="step-sub">后续可随时调整</text>
    <view class="option-list">
      <view
        class="option-row {{reminderLevel === item.value ? 'active' : ''}}"
        wx:for="{{reminderOptions}}"
        wx:key="value"
        data-value="{{item.value}}"
        bindtap="onSelectReminder"
      >
        <text class="option-label">{{item.label}}</text>
      </view>
    </view>
    <button class="btn-primary" bindtap="onFinish" disabled="{{!reminderLevel}}">开始使用</button>
  </view>
</view>
```

- [ ] **Step 4: 创建 pages/onboarding/onboarding.wxss**

```css
.onboarding {
  padding: 60rpx 40rpx;
  min-height: 100vh;
}

.step-title {
  display: block;
  font-size: var(--font-size-large);
  font-weight: 600;
  margin-bottom: 12rpx;
  color: var(--color-text);
}

.step-sub {
  display: block;
  font-size: var(--font-size-caption);
  color: var(--color-text-secondary);
  margin-bottom: 48rpx;
}

.option-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 20rpx;
  margin-bottom: 60rpx;
}

.option-chip {
  padding: 20rpx 40rpx;
  border-radius: 40rpx;
  background: var(--color-surface);
  border: 2rpx solid var(--color-divider);
  font-size: var(--font-size-body);
  transition: all 0.2s;
}

.option-chip.active {
  background: var(--color-primary-light);
  border-color: var(--color-primary);
  color: var(--color-primary);
}

.option-list {
  display: flex;
  flex-direction: column;
  gap: 20rpx;
  margin-bottom: 60rpx;
}

.option-row {
  padding: 28rpx 32rpx;
  border-radius: var(--radius);
  background: var(--color-surface);
  border: 2rpx solid var(--color-divider);
  font-size: var(--font-size-body);
}

.option-row.active {
  border-color: var(--color-primary);
  background: var(--color-primary-light);
}

.option-label {
  display: block;
}

.btn-primary {
  width: 100%;
  height: 96rpx;
  line-height: 96rpx;
  background: var(--color-primary);
  color: #ffffff;
  border-radius: var(--radius);
  font-size: var(--font-size-body);
  font-weight: 500;
  border: none;
}

.btn-primary[disabled] {
  background: #a0c4ff;
}
```

- [ ] **Step 5: 验证 — 模拟首次使用流程**

在 DevTools 模拟器中：
1. 进入 onboarding 页 → 选择至少 1 个物品 → 下一步
2. 选择场景 → 下一步
3. 选择作息 → 下一步
4. 选择提醒频率 → 点击"开始使用"
5. 确认跳转到主页（目前为空白页）
6. 在 Console 中检查 `wx.getStorageSync('onboarding_done')` 返回 true

- [ ] **Step 6: Commit**

```bash
git add pages/onboarding/ && git commit -m "feat: onboarding flow — 4-step questionnaire"
```

---

### Task 4: 场景管理器

**Files:**
- Create: `utils/scene.js`

**Consumes:** `utils/storage.js` (getScenes, upsertScene)

**Produces:** 场景检测和切换逻辑 — 基于 GPS 的地理围栏 + 手动切换

- [ ] **Step 1: 创建 utils/scene.js**

```javascript
const storage = require('./storage');

const EARTH_RADIUS = 6371000;

// Haversine 公式计算两点距离（米）
function distanceMeters(lat1, lon1, lat2, lon2) {
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  return EARTH_RADIUS * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

// 根据 GPS 坐标匹配最近场景（围栏半径内）
function matchSceneByLocation(lat, lon) {
  const scenes = storage.getScenes();
  for (const s of scenes) {
    if (!s.geo_fence || !s.geo_fence.lat) continue;
    const d = distanceMeters(lat, lon, s.geo_fence.lat, s.geo_fence.lon);
    const radius = s.geo_fence.radius || 200;
    if (d <= radius) return s;
  }
  return null;
}

// 获取当前场景：优先 GPS 自动匹配，fallback 到手动设置
function getCurrentScene() {
  return new Promise((resolve) => {
    wx.getLocation({
      type: 'gcj02',
      success(res) {
        const matched = matchSceneByLocation(res.latitude, res.longitude);
        resolve(matched || storage.getScenes().find(s => s.id === 'home'));
      },
      fail() {
        resolve(storage.getScenes().find(s => s.id === 'home'));
      }
    });
  });
}

// 为场景设置地理围栏
function setSceneGeofence(sceneId, lat, lon, radius) {
  const scene = storage.getScenes().find(s => s.id === sceneId);
  if (!scene) return null;
  scene.geo_fence = { lat, lon, radius: radius || 200 };
  return storage.upsertScene(scene);
}

// 关联物品到场景（场景切换时触发提醒）
function addTriggerItem(sceneId, itemId) {
  const scene = storage.getScenes().find(s => s.id === sceneId);
  if (!scene) return null;
  if (!scene.trigger_items.includes(itemId)) {
    scene.trigger_items.push(itemId);
  }
  return storage.upsertScene(scene);
}

module.exports = {
  getCurrentScene,
  matchSceneByLocation,
  setSceneGeofence,
  addTriggerItem
};
```

- [ ] **Step 2: 验证 — 在 app.js 临时测试**

在 `app.js` 中临时加入：

```javascript
const scene = require('./utils/scene');
scene.getCurrentScene().then(s => console.log('Current scene:', s));
```

在 DevTools 中确认打印当前场景（应返回默认"家"场景）。确认后删除。

- [ ] **Step 3: Commit**

```bash
git add utils/scene.js && git commit -m "feat: scene manager with geofence matching"
```

---

### Task 5: Agent NLP 解析引擎

**Files:**
- Create: `utils/agent.js`

**Produces:** 将用户自然语言输入解析为结构化意图+实体，本地规则引擎

- [ ] **Step 1: 创建 utils/agent.js**

```javascript
// 意图类型
const INTENTS = {
  UPDATE_LOCATION: 'update_location',
  QUERY_LOCATION: 'query_location',
  ADD_ITEM: 'add_item',
  SET_REMINDER: 'set_reminder'
};

// 已知物品名（动态从 storage 加载）
function getKnownItemNames() {
  try {
    const storage = require('./storage');
    return storage.getItems().map(i => i.name);
  } catch (e) {
    return [];
  }
}

// 核心解析函数
function parse(text) {
  const cleaned = text.trim().replace(/[，。！？、]/g, ',').replace(/\s+/g, ' ');

  // 句式1: "[物品]在[位置]" / "[物品]放[位置]" / "把[物品]放[位置]"
  const updatePatterns = [
    /(?:把)?(.{1,10}?)(?:放|在)(.{1,30})/,
    /(.{1,10}?)(?:放|在)(.{1,30})/,
  ];

  for (const pat of updatePatterns) {
    const m = cleaned.match(pat);
    if (m) {
      const itemName = m[1].trim();
      const location = m[2].trim();
      const known = getKnownItemNames();
      const matched = known.find(k => itemName.includes(k) || k.includes(itemName));

      return {
        intent: INTENTS.UPDATE_LOCATION,
        item: matched || itemName,
        location: location,
        isNewItem: !matched
      };
    }
  }

  // 句式2: "[物品]在哪"
  const queryMatch = cleaned.match(/(.{1,10})在哪/);
  if (queryMatch) {
    return {
      intent: INTENTS.QUERY_LOCATION,
      item: queryMatch[1].trim()
    };
  }

  // 句式3: "添加[物品]" / "新增[物品]" / "记住[物品]"
  const addMatch = cleaned.match(/(?:添加|新增|记住|加一个?)(.{1,20})/);
  if (addMatch) {
    return {
      intent: INTENTS.ADD_ITEM,
      item: addMatch[1].trim()
    };
  }

  // 句式4: "提醒我带[物品]" / "出门带[物品]"
  const remindMatch = cleaned.match(/(?:提醒|出门|别忘了?)(?:我|带)?(.{1,20})/);
  if (remindMatch) {
    return {
      intent: INTENTS.SET_REMINDER,
      item: remindMatch[1].trim()
    };
  }

  // Fallback: 当更新位置处理
  return {
    intent: INTENTS.UPDATE_LOCATION,
    item: cleaned.length > 10 ? cleaned.substring(0, 10) : cleaned,
    location: cleaned,
    isNewItem: true
  };
}

// === LLM 接口（预留，不接入） ===
// 未来如需接 LLM：
// async function parseLLM(text) {
//   const res = await wx.request({
//     url: 'https://your-api/parse',
//     method: 'POST',
//     data: { text }
//   });
//   return res.data;
// }

module.exports = { parse, INTENTS };
```

- [ ] **Step 2: 验证 — 单元测试式手动验证**

在 app.js 中临时加入测试用例：

```javascript
const agent = require('./utils/agent');
const cases = [
  '我把钥匙放门口篮子了',
  '手机在哪',
  '添加一个新物品叫眼镜盒',
  '提醒我带伞',
  '钥匙放门口篮子了'
];
cases.forEach(c => console.log(c, '→', agent.parse(c)));
```

在 DevTools Console 中确认每条解析结果符合预期。确认后删除测试代码。

- [ ] **Step 3: Commit**

```bash
git add utils/agent.js && git commit -m "feat: Agent NLP parser — rule-based intent/entity extraction"
```

---

### Task 6: 提醒引擎

**Files:**
- Create: `utils/reminder.js`

**Consumes:** `utils/storage.js` (getItems, getSettings, getScenes)

**Produces:** 双通道提醒系统 — 记忆曲线定时 + 事件触发，带防打扰

- [ ] **Step 1: 创建 utils/reminder.js**

```javascript
const storage = require('./storage');

// Ebbinghaus 记忆留存率计算
// R = e^(-t/S), S = 相对强度参数
function retentionRate(elapsedMinutes, strengthS) {
  return Math.exp(-elapsedMinutes / (strengthS || 600));
}

// 根据更新次数计算下一个提醒间隔（分钟）
// 级联：20min → 60min → 480min(8h) → 1440min(1d) → 4320min(3d) → ...
const INTERVALS = [20, 60, 480, 1440, 4320, 10080]; // 分钟

function nextReminderInterval(updateCount) {
  const idx = Math.min(updateCount, INTERVALS.length - 1);
  return INTERVALS[idx];
}

// 检查某物品是否需要提醒
function checkCurveReminder(item) {
  const settings = storage.getSettings();
  if (!settings.curve_reminder_enabled) return false;

  const elapsed = (Date.now() - item.last_updated) / 60000; // 分钟
  const history = storage.getHistory(item.id);
  const updateCount = history.length;
  const strengthS = 600 * (1 + updateCount * 0.5); // 每多更新一次，记忆强度提高

  const r = retentionRate(elapsed, strengthS);
  return r < 0.6; // 留存率低于 60% 触发
}

// 检查防打扰
function isInQuietHours() {
  const settings = storage.getSettings();
  const now = new Date();
  const minutes = now.getHours() * 100 + now.getMinutes();
  const start = settings.quiet_start; // e.g. 2200
  const end = settings.quiet_end;     // e.g. 800
  if (start < end) return minutes >= start && minutes < end;
  return minutes >= start || minutes < end; // 跨天（22:00-08:00）
}

// 获取待提醒物品列表（记忆曲线通道）
function getCurveReminders() {
  if (isInQuietHours()) return [];

  const settings = storage.getSettings();
  const items = storage.getItems();
  const now = Date.now();

  return items.filter(item => {
    // 2 小时内不重复提醒
    const recent = storage.getHistory(item.id);
    if (recent.length > 0) {
      const lastReminder = recent.find(h => h.type === 'reminder');
      if (lastReminder && (now - lastReminder.timestamp) < 7200000) return false;
    }

    return checkCurveReminder(item);
  });
}

// 获取场景切换提醒（事件触发通道）
function getSceneSwitchReminders(currentSceneId) {
  if (isInQuietHours()) return [];
  const settings = storage.getSettings();
  if (!settings.geo_reminder_enabled) return [];

  const scenes = storage.getScenes();
  const scene = scenes.find(s => s.id === currentSceneId);
  if (!scene || !scene.trigger_items || scene.trigger_items.length === 0) return [];

  const items = storage.getItems();
  return items.filter(i => scene.trigger_items.includes(i.id));
}

// 获取当天提醒计数
function getTodayReminderCount() {
  const all = wx.getStorageSync('location_history') || [];
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return all.filter(h => h.type === 'reminder' && h.timestamp >= today.getTime()).length;
}

// 是否超过每日上限
function isOverDailyLimit() {
  const settings = storage.getSettings();
  const max = settings.max_reminders_per_day || 5;
  return getTodayReminderCount() >= max;
}

// 发送提醒（通过模板消息或系统通知）
function sendReminder(item, reason) {
  // 记录提醒事件
  storage.addHistory({
    item_id: item.id,
    location: item.current_location,
    scene: 'system',
    source: 'reminder',
    type: 'reminder',
    reason: reason
  });

  // 微信内通知
  wx.showToast({
    title: `${item.icon} ${item.name}: ${item.current_location}`,
    icon: 'none',
    duration: 5000
  });
}

module.exports = {
  getCurveReminders,
  getSceneSwitchReminders,
  isOverDailyLimit,
  isInQuietHours,
  sendReminder,
  retentionRate,
  nextReminderInterval
};
```

- [ ] **Step 2: 验证 — 手动测试提醒逻辑**

在 app.js 中临时加入：

```javascript
const reminder = require('./utils/reminder');
console.log('Curve reminders:', reminder.getCurveReminders());
console.log('Quiet hours:', reminder.isInQuietHours());
console.log('Daily limit exceeded:', reminder.isOverDailyLimit());
```

确认无报错，输出合理。确认后删除。

- [ ] **Step 3: Commit**

```bash
git add utils/reminder.js && git commit -m "feat: reminder engine — Ebbinghaus curve + scene triggers + anti-disturb"
```

---

### Task 7: 主页

**Files:**
- Create: `pages/home/home.js`, `pages/home/home.json`, `pages/home/home.wxml`, `pages/home/home.wxss`

**Consumes:** 所有 utils 模块

**Produces:** 核心交互页面 — 场景标签、物品卡片列表、语音按钮

- [ ] **Step 1: 创建 pages/home/home.json**

```json
{
  "usingComponents": {},
  "navigationBarTitleText": "Where is it"
}
```

- [ ] **Step 2: 创建 pages/home/home.js**

```javascript
const storage = require('../../utils/storage');
const agent = require('../../utils/agent');
const sceneManager = require('../../utils/scene');
const reminder = require('../../utils/reminder');

Page({
  data: {
    currentScene: { id: 'home', name: '家', icon: '🏠' },
    scenes: [],
    items: [],
    inputText: '',
    showInput: false
  },

  onLoad() {
    if (!storage.isOnboardingDone()) {
      wx.redirectTo({ url: '/pages/onboarding/onboarding' });
      return;
    }
    this.refresh();
  },

  onShow() {
    if (storage.isOnboardingDone()) {
      this.refresh();
    }
  },

  refresh() {
    const items = storage.getItems().sort((a, b) => b.importance - a.importance || b.last_updated - a.last_updated);
    const scenes = storage.getScenes();

    sceneManager.getCurrentScene().then(cs => {
      this.setData({ items, scenes, currentScene: cs || scenes[0] });
    });

    // 检查是否有需要提醒的
    if (!reminder.isOverDailyLimit()) {
      const curveItems = reminder.getCurveReminders();
      if (curveItems.length > 0) {
        reminder.sendReminder(curveItems[0], 'curve');
      }
    }
  },

  onSwitchScene(e) {
    const sceneId = e.currentTarget.dataset.id;
    const scene = this.data.scenes.find(s => s.id === sceneId);
    if (scene) {
      this.setData({ currentScene: scene });

      // 场景切换提醒
      if (!reminder.isOverDailyLimit()) {
        const triggerItems = reminder.getSceneSwitchReminders(sceneId);
        triggerItems.forEach(item => reminder.sendReminder(item, 'scene_switch'));
      }
    }
  },

  onUpdateLocation(e) {
    const item = e.currentTarget.dataset.item;
    this.setData({
      activeItem: item,
      showInput: true,
      inputPlaceholder: `说说 ${item.name} 放哪了？`
    });
  },

  onViewTimeline(e) {
    const item = e.currentTarget.dataset.item;
    wx.navigateTo({ url: `/pages/timeline/timeline?itemId=${item.id}` });
  },

  onVoiceStart() {
    const recorder = wx.getRecorderManager();
    recorder.start({
      duration: 10000,
      sampleRate: 16000,
      numberOfChannels: 1,
      format: 'mp3'
    });
    this.setData({ recording: true });
  },

  onVoiceEnd() {
    const recorder = wx.getRecorderManager();
    recorder.stop();
    this.setData({ recording: false });
    wx.showLoading({ title: '识别中...' });

    recorder.onStop((res) => {
      // 微信语音识别（插件方式接入）
      // 简化方案：先用 input 输入代替语音识别
      // 生产环境接入 wx.plugins.speechRecognizer
      wx.hideLoading();
      wx.showToast({ title: '语音功能需接入微信同声传译插件', icon: 'none' });
    });
  },

  onTextSubmit(e) {
    const text = this.data.inputText || e.detail.value;
    if (!text.trim()) return;

    const result = agent.parse(text);

    if (result.intent === agent.INTENTS.UPDATE_LOCATION) {
      let item = storage.getItems().find(i => i.name === result.item);
      if (!item) {
        item = storage.upsertItem({ name: result.item, current_location: result.location });
      } else {
        item = storage.upsertItem({ ...item, current_location: result.location });
      }

      storage.addHistory({
        item_id: item.id,
        location: result.location,
        scene: this.data.currentScene.id,
        source: 'voice'
      });

      wx.showToast({ title: `已更新: ${item.name} → ${result.location}`, icon: 'success' });
    } else if (result.intent === agent.INTENTS.QUERY_LOCATION) {
      const item = storage.getItems().find(i => i.name === result.item);
      if (item) {
        wx.showToast({ title: `${item.name} 在 ${item.current_location}`, icon: 'none', duration: 4000 });
      } else {
        wx.showToast({ title: `未找到 ${result.item}`, icon: 'none' });
      }
    } else if (result.intent === agent.INTENTS.ADD_ITEM) {
      storage.upsertItem({ name: result.item, importance: 2 });
      wx.showToast({ title: `已添加: ${result.item}`, icon: 'success' });
    }

    this.setData({ inputText: '', showInput: false, activeItem: null });
    this.refresh();
  },

  onShowInput() {
    this.setData({ showInput: true, activeItem: null, inputPlaceholder: '说说你放了什么、放哪了？' });
  },

  onHideInput() {
    this.setData({ showInput: false, inputText: '' });
  }
});
```

- [ ] **Step 3: 创建 pages/home/home.wxml**

```xml
<view class="home">
  <!-- 场景标签栏 -->
  <scroll-view class="scene-bar" scroll-x>
    <view
      class="scene-tag {{currentScene.id === item.id ? 'active' : ''}}"
      wx:for="{{scenes}}"
      wx:key="id"
      data-id="{{item.id}}"
      bindtap="onSwitchScene"
    >{{item.icon}} {{item.name}}</view>
  </scroll-view>

  <!-- 物品卡片列表 -->
  <view class="item-list">
    <view class="item-card" wx:for="{{items}}" wx:key="id">
      <view class="item-main">
        <text class="item-icon">{{item.icon}}</text>
        <view class="item-info">
          <text class="item-name">{{item.name}}</text>
          <text class="item-location">📍 {{item.current_location}}</text>
          <text class="item-time">🕐 {{item.last_updated ? '更新于 ' + item.last_updated : '未记录'}}</text>
        </view>
      </view>
      <view class="item-actions">
        <button class="btn-sm btn-update" data-item="{{item}}" bindtap="onUpdateLocation">更新</button>
        <button class="btn-sm btn-timeline" data-item="{{item}}" bindtap="onViewTimeline">轨迹</button>
      </view>
    </view>

    <view class="empty" wx:if="{{items.length === 0}}">
      <text class="empty-text">还没有物品，按下语音按钮开始记录吧</text>
    </view>
  </view>

  <!-- 输入区域（语音/文字切换） -->
  <view class="input-area" wx:if="{{showInput}}">
    <view class="input-row">
      <input
        class="text-input"
        value="{{inputText}}"
        placeholder="{{inputPlaceholder}}"
        bindinput="onInputChange"
        focus="{{true}}"
        confirm-type="done"
        bindconfirm="onTextSubmit"
      />
      <button class="btn-send" bindtap="onTextSubmit">发送</button>
      <button class="btn-cancel" bindtap="onHideInput">取消</button>
    </view>
  </view>

  <view class="input-area" wx:else>
    <view class="voice-bar">
      <button
        class="voice-btn {{recording ? 'recording' : ''}}"
        bindtouchstart="onVoiceStart"
        bindtouchend="onVoiceEnd"
      >🎤 按住说话</button>
      <button class="keyboard-btn" bindtap="onShowInput">⌨</button>
    </view>
  </view>
</view>
```

- [ ] **Step 4: 创建 pages/home/home.wxss**

```css
.home {
  display: flex;
  flex-direction: column;
  height: 100vh;
  padding-bottom: 160rpx;
}

/* 场景标签栏 */
.scene-bar {
  white-space: nowrap;
  padding: 20rpx 24rpx;
  background: var(--color-surface);
  border-bottom: 1rpx solid var(--color-divider);
}

.scene-tag {
  display: inline-block;
  padding: 12rpx 28rpx;
  margin-right: 16rpx;
  border-radius: 40rpx;
  background: var(--color-bg);
  font-size: var(--font-size-body);
  transition: all 0.2s;
}

.scene-tag.active {
  background: var(--color-primary);
  color: #ffffff;
}

/* 物品卡片 */
.item-list {
  flex: 1;
  padding: 24rpx;
  overflow-y: auto;
}

.item-card {
  background: var(--color-surface);
  border-radius: var(--radius);
  padding: 28rpx;
  margin-bottom: 20rpx;
  box-shadow: var(--shadow);
}

.item-main {
  display: flex;
  align-items: flex-start;
  gap: 20rpx;
  margin-bottom: 20rpx;
}

.item-icon {
  font-size: 56rpx;
  line-height: 1;
}

.item-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 6rpx;
}

.item-name {
  font-size: var(--font-size-title);
  font-weight: 600;
}

.item-location {
  font-size: var(--font-size-body);
  color: var(--color-text-secondary);
}

.item-time {
  font-size: var(--font-size-caption);
  color: #999;
}

.item-actions {
  display: flex;
  gap: 16rpx;
}

.btn-sm {
  flex: 1;
  height: 64rpx;
  line-height: 64rpx;
  font-size: var(--font-size-caption);
  border-radius: 12rpx;
  border: none;
  text-align: center;
}

.btn-update {
  background: var(--color-primary);
  color: #ffffff;
}

.btn-timeline {
  background: var(--color-bg);
  color: var(--color-text-secondary);
  border: 1rpx solid var(--color-divider);
}

/* 输入区域 */
.input-area {
  position: fixed;
  bottom: 0;
  left: 0;
  right: 0;
  background: var(--color-surface);
  padding: 20rpx 24rpx;
  padding-bottom: calc(20rpx + env(safe-area-inset-bottom));
  border-top: 1rpx solid var(--color-divider);
}

.input-row {
  display: flex;
  gap: 16rpx;
  align-items: center;
}

.text-input {
  flex: 1;
  height: 80rpx;
  padding: 0 24rpx;
  background: var(--color-bg);
  border-radius: var(--radius);
  font-size: var(--font-size-body);
}

.btn-send {
  height: 80rpx;
  padding: 0 32rpx;
  background: var(--color-primary);
  color: #ffffff;
  border-radius: var(--radius);
  font-size: var(--font-size-body);
  border: none;
  line-height: 80rpx;
}

.btn-cancel {
  height: 80rpx;
  padding: 0 24rpx;
  background: var(--color-bg);
  color: var(--color-text-secondary);
  border-radius: var(--radius);
  font-size: var(--font-size-caption);
  border: none;
  line-height: 80rpx;
}

.voice-bar {
  display: flex;
  gap: 16rpx;
  align-items: center;
}

.voice-btn {
  flex: 1;
  height: 96rpx;
  line-height: 96rpx;
  background: var(--color-primary);
  color: #ffffff;
  border-radius: 48rpx;
  font-size: var(--font-size-title);
  border: none;
  text-align: center;
}

.voice-btn.recording {
  background: var(--color-danger);
}

.keyboard-btn {
  width: 80rpx;
  height: 80rpx;
  line-height: 80rpx;
  background: var(--color-bg);
  border-radius: 40rpx;
  font-size: var(--font-size-title);
  border: 1rpx solid var(--color-divider);
  text-align: center;
  padding: 0;
}

.empty {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 400rpx;
}

.empty-text {
  color: var(--color-text-secondary);
  font-size: var(--font-size-body);
}
```

- [ ] **Step 5: 验证 — 完整交互流程**

在 DevTools 模拟器中：
1. 首次进入应被重定向到 onboarding → 完成问卷
2. 主页显示刚选的物品卡片
3. 点击"更新"→ 输入"钥匙放门口篮子"→ 确认卡片位置更新
4. 切换场景标签
5. 点击"轨迹"→ 跳转到 timeline 页（目前空白）
6. 语音按钮显示正常

- [ ] **Step 6: Commit**

```bash
git add pages/home/ && git commit -m "feat: home page — scene bar, item cards, voice/text input"
```

---

### Task 8: 时间线页面

**Files:**
- Create: `pages/timeline/timeline.js`, `pages/timeline/timeline.json`, `pages/timeline/timeline.wxml`, `pages/timeline/timeline.wxss`

**Consumes:** `utils/storage.js` (getHistory, getItem)

**Produces:** 单个物品的位置变更历史时间线

- [ ] **Step 1: 创建 pages/timeline/timeline.json**

```json
{
  "usingComponents": {},
  "navigationBarTitleText": "位置轨迹"
}
```

- [ ] **Step 2: 创建 pages/timeline/timeline.js**

```javascript
const storage = require('../../utils/storage');

Page({
  data: {
    item: null,
    history: []
  },

  onLoad(options) {
    const itemId = options.itemId;
    const item = storage.getItem(itemId);
    const history = storage.getHistory(itemId);

    if (!item) {
      wx.showToast({ title: '物品不存在', icon: 'none' });
      setTimeout(() => wx.navigateBack(), 1500);
      return;
    }

    this.setData({ item, history });
  },

  formatTime(ts) {
    const d = new Date(ts);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
});
```

- [ ] **Step 3: 创建 pages/timeline/timeline.wxml**

```xml
<view class="timeline" wx:if="{{item}}">
  <view class="header">
    <text class="header-icon">{{item.icon}}</text>
    <view class="header-info">
      <text class="header-name">{{item.name}}</text>
      <text class="header-now">📍 当前位置: {{item.current_location}}</text>
    </view>
  </view>

  <view class="history-list">
    <text class="section-title">变更记录</text>

    <view class="timeline-item" wx:for="{{history}}" wx:key="id">
      <view class="dot"></view>
      <view class="timeline-content">
        <text class="timeline-location">→ {{item.location}}</text>
        <view class="timeline-meta">
          <text class="timeline-time">{{item.timestamp}}</text>
          <text class="timeline-scene">{{item.scene}}</text>
          <text class="timeline-source">{{item.source === 'voice' ? '🎤语音' : '⌨手动'}}</text>
        </view>
      </view>
    </view>

    <view class="empty" wx:if="{{history.length === 0}}">
      <text>暂无记录</text>
    </view>
  </view>
</view>
```

- [ ] **Step 4: 创建 pages/timeline/timeline.wxss**

```css
.timeline {
  padding: 24rpx;
}

.header {
  display: flex;
  align-items: center;
  gap: 20rpx;
  padding: 32rpx;
  background: var(--color-surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin-bottom: 32rpx;
}

.header-icon {
  font-size: 64rpx;
}

.header-info {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.header-name {
  font-size: var(--font-size-title);
  font-weight: 600;
}

.header-now {
  font-size: var(--font-size-body);
  color: var(--color-primary);
}

.section-title {
  display: block;
  font-size: var(--font-size-caption);
  color: var(--color-text-secondary);
  margin-bottom: 20rpx;
  padding-left: 8rpx;
}

.history-list {
  padding-left: 24rpx;
}

.timeline-item {
  display: flex;
  gap: 20rpx;
  padding-bottom: 32rpx;
  position: relative;
}

.timeline-item::before {
  content: '';
  position: absolute;
  left: 11rpx;
  top: 24rpx;
  bottom: 0;
  width: 2rpx;
  background: var(--color-divider);
}

.timeline-item:last-child::before {
  display: none;
}

.dot {
  width: 24rpx;
  height: 24rpx;
  border-radius: 12rpx;
  background: var(--color-primary);
  flex-shrink: 0;
  margin-top: 4rpx;
}

.timeline-content {
  display: flex;
  flex-direction: column;
  gap: 8rpx;
}

.timeline-location {
  font-size: var(--font-size-body);
  font-weight: 500;
}

.timeline-meta {
  display: flex;
  gap: 16rpx;
}

.timeline-time {
  font-size: var(--font-size-caption);
  color: var(--color-text-secondary);
}

.timeline-scene {
  font-size: var(--font-size-caption);
  color: var(--color-primary);
}

.timeline-source {
  font-size: var(--font-size-caption);
  color: #999;
}

.empty {
  text-align: center;
  padding: 80rpx 0;
  color: var(--color-text-secondary);
}
```

- [ ] **Step 5: 验证 — 时间线页面**

在 DevTools 模拟器中：
1. 从主页点击物品卡片的"轨迹"按钮
2. 跳转到 timeline 页显示物品信息和变更记录
3. 返回主页再更新一次物品位置
4. 再次进入时间线，确认新增记录出现

- [ ] **Step 6: Commit**

```bash
git add pages/timeline/ && git commit -m "feat: timeline page — item location history"
```

---

### Task 9: 集成收尾

**Files:**
- Modify: `app.js`, `app.json`

**Description:** 确保 Onboarding → Home 流程完整、场景切换触发提醒、时间线格式化正确

- [ ] **Step 1: 修复时间线时间格式化**

在 `pages/timeline/timeline.wxml` 中，时间戳显示应使用 `formatTime` filter。更新 wxml 中的 `{{item.timestamp}}`：

```xml
<text class="timeline-time">{{item.timestamp}}</text>
```

改为使用 wxs 格式化。创建 `utils/filters.wxs`：

```javascript
function formatTime(ts) {
  var d = getDate(ts);
  var pad = function(n) { return n < 10 ? '0' + n : '' + n; };
  return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()) + ' ' + pad(d.getHours()) + ':' + pad(d.getMinutes());
}

module.exports = { formatTime: formatTime };
```

在 `pages/timeline/timeline.wxml` 顶部引入：

```xml
<wxs module="f" src="../../utils/filters.wxs" />
```

然后更新时间显示：`<text class="timeline-time">{{f.formatTime(item.timestamp)}}</text>`

- [ ] **Step 2: 主页时间显示同样修复**

在 `pages/home/home.wxml` 顶部添加：

```xml
<wxs module="f" src="../../utils/filters.wxs" />
```

更新物品卡片时间：`<text class="item-time">🕐 {{item.last_updated ? '更新于 ' + f.formatTime(item.last_updated) : '未记录'}}</text>`

- [ ] **Step 3: 验证完整流程**

在 DevTools 模拟器中走通完整链路：
1. 清除存储 → 重新进入 → Onboarding 流程
2. 完成问卷 → 主页显示种子物品
3. 语音/文字更新位置 → 卡片即时刷新
4. 场景切换 → 提醒触发（如有配置）
5. 时间线 → 查看变更记录
6. 关闭小程序 → 重新打开 → 数据持久化

- [ ] **Step 4: Commit**

```bash
git add -A && git commit -m "feat: integration — time formatting, full flow polish"
```

---

## 实施顺序

```
Task 1 (脚手架) → Task 2 (存储层) → Task 3 (Onboarding)
                                    → Task 4 (场景)
                                    → Task 5 (Agent)
                                    → Task 6 (提醒)
                                    → Task 7 (主页) → Task 8 (时间线)
                                                      → Task 9 (收尾)
```

Task 3-6 可以并行开发（都只依赖 Task 2），Task 7 依赖 3-6 全部完成后集成。

## 语音识别备注

微信小程序语音识别需要接入"微信同声传译"插件。接入步骤（在 Task 7 之后单独处理）：

1. 在微信公众平台 → 设置 → 第三方服务 → 插件管理 → 添加"微信同声传译"插件
2. `app.json` 中声明：`"plugins": { "speech": { "version": "1.0.0", "provider": "wx4b9c7b4d0e4d0c7a" } }`
3. 调用 `wx.getPlugin('speech').speechRecognizer` 进行语音识别
4. MVP 阶段可先用键盘输入代替，语音作为增强功能

## 后续迭代方向（不在本次计划内）

- 语音识别正式接入
- 模板消息推送（`wx.requestSubscribeMessage`）
- 定位权限自动弹窗优化
- 地理围栏可视化设置
- LLM 接入（当规则覆盖不足时）
- 数据导出/备份

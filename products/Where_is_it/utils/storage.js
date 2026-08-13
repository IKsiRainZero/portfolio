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

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
  const updateCount = history.filter(h => h.source !== 'reminder').length;
  const strengthS = 600 * (1 + updateCount * 0.5);

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

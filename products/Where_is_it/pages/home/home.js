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
    const items = storage.getItems()
      .sort((a, b) => b.importance - a.importance || b.last_updated - a.last_updated)
      .map(item => ({ ...item, _time: item.last_updated ? this.formatTime(item.last_updated) : null }));
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

  onInputChange(e) {
    this.setData({ inputText: e.detail.value });
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
        source: 'text'
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
    } else if (result.intent === agent.INTENTS.SET_REMINDER) {
      const item = storage.getItems().find(i => i.name === result.item || result.item.includes(i.name));
      if (item) {
        reminder.sendReminder(item, 'user_request');
        wx.showToast({ title: `已记录提醒: ${item.name}`, icon: 'success' });
      } else {
        wx.showToast({ title: `未找到 ${result.item}，请先添加该物品`, icon: 'none' });
      }
    }

    this.setData({ inputText: '', showInput: false, activeItem: null });
    this.refresh();
  },

  onShowInput() {
    this.setData({ showInput: true, activeItem: null, inputPlaceholder: '说说你放了什么、放哪了？' });
  },

  onHideInput() {
    this.setData({ showInput: false, inputText: '' });
  },

  formatTime(ts) {
    const d = new Date(ts);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
});

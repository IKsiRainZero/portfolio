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

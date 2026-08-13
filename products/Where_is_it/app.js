const storage = require('./utils/storage');

App({
  onLaunch() {
    if (storage.isOnboardingDone()) {
      wx.reLaunch({ url: '/pages/home/home' });
    }
  },

  globalData: {
    currentScene: 'home',
    reminderSettings: null
  }
});

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

    this.setData({
      item,
      history: history.map(h => ({ ...h, _time: this.formatTime(h.timestamp) }))
    });
  },

  formatTime(ts) {
    const d = new Date(ts);
    const pad = n => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  }
});

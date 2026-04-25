const { fetchReadingGoal, saveReadingGoal } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');

Page({
  data: {
    loading: false,
    saving: false,
    period_days: 30,
    target_books: 1,
    target_days: 20
  },

  onShow() {
    this.loadGoal();
  },

  async loadGoal() {
    this.setData({ loading: true });
    try {
      const payload = await fetchReadingGoal();
      const goal = payload.goal || {};
      this.setData({
        period_days: Number(goal.period_days) || 30,
        target_books: Number(goal.target_books) || 1,
        target_days: Number(goal.target_days) || 20
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载目标失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  onInputPeriod(e) {
    this.setData({ period_days: Number(e.detail.value || 0) });
  },

  onInputBooks(e) {
    this.setData({ target_books: Number(e.detail.value || 0) });
  },

  onInputDays(e) {
    this.setData({ target_days: Number(e.detail.value || 0) });
  },

  async onSave() {
    this.setData({ saving: true });
    try {
      await saveReadingGoal({
        period_days: Number(this.data.period_days),
        target_books: Number(this.data.target_books),
        target_days: Number(this.data.target_days)
      });
      wx.showToast({ title: '已保存', icon: 'success' });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '保存失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ saving: false });
    }
  }
});

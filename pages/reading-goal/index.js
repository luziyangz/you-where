const { fetchReadingGoal, saveReadingGoal } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');

Page({
  data: {
    loading: false,
    saving: false,
    period_days: 30,
    target_books: 1,
    target_days: 20,
    progress: {
      completed_books: 0,
      target_books: 1,
      book_percent: 0,
      active_days: 0,
      target_days: 20,
      day_percent: 0
    }
  },

  onShow() {
    if (!requireLogin({ message: '请先登录后设置目标' })) {
      return;
    }
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
        target_days: Number(goal.target_days) || 20,
        progress: this.normalizeProgress(payload.progress)
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

  normalizeProgress(progress = {}) {
    return {
      completed_books: Number(progress.completed_books || 0),
      target_books: Number(progress.target_books || this.data.target_books || 1),
      book_percent: Math.min(100, Math.max(0, Number(progress.book_percent || 0))),
      active_days: Number(progress.active_days || 0),
      target_days: Number(progress.target_days || this.data.target_days || 20),
      day_percent: Math.min(100, Math.max(0, Number(progress.day_percent || 0)))
    };
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
      const payload = await saveReadingGoal({
        period_days: Number(this.data.period_days),
        target_books: Number(this.data.target_books),
        target_days: Number(this.data.target_days)
      });
      this.setData({
        progress: this.normalizeProgress(payload.progress)
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

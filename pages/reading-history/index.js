const { fetchReadingHistory } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');

Page({
  data: {
    loading: false,
    items: [],
    page: 1,
    pageSize: 10,
    hasMore: true
  },

  onShow() {
    if (!requireLogin({ message: '请先登录后查看历史' })) {
      return;
    }
    this.loadHistory(true);
  },

  async loadHistory(reset = false) {
    if (!reset && !this.data.hasMore) {
      return;
    }
    const nextPage = reset ? 1 : this.data.page;
    this.setData({ loading: true });
    try {
      const payload = await fetchReadingHistory(nextPage, this.data.pageSize);
      const rows = payload.items || [];
      this.setData({
        items: reset ? rows : [...this.data.items, ...rows],
        page: nextPage + 1,
        hasMore: !!payload.has_more
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载历史失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  onReachBottom() {
    this.loadHistory(false);
  }
});

const { fetchReminderConfig, saveReminderConfig } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');

Page({
  data: {
    loading: false,
    saving: false,
    enabled: true,
    remind_time: '21:00',
    timezone: 'Asia/Shanghai'
  },

  onShow() {
    this.loadReminder();
  },

  async loadReminder() {
    this.setData({ loading: true });
    try {
      const payload = await fetchReminderConfig();
      const reminder = payload.reminder || {};
      this.setData({
        enabled: !!reminder.enabled,
        remind_time: reminder.remind_time || '21:00',
        timezone: reminder.timezone || 'Asia/Shanghai'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '加载提醒失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ loading: false });
    }
  },

  onToggleEnabled(e) {
    this.setData({ enabled: !!e.detail.value });
  },

  onInputTime(e) {
    this.setData({ remind_time: e.detail.value || '' });
  },

  onInputTimezone(e) {
    this.setData({ timezone: e.detail.value || '' });
  },

  async onSave() {
    this.setData({ saving: true });
    try {
      await saveReminderConfig({
        enabled: !!this.data.enabled,
        remind_time: this.data.remind_time,
        timezone: this.data.timezone
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

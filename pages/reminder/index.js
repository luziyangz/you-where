const { fetchReminderConfig, saveReminderConfig } = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');

Page({
  data: {
    loading: false,
    saving: false,
    enabled: true,
    remind_time: '21:00',
    timezone: 'Asia/Shanghai',
    templateId: '',
    deliveryStatus: 'config_only',
    deliveryMessage: ''
  },

  onShow() {
    if (!requireLogin({ message: '请先登录后设置提醒' })) {
      return;
    }
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
        timezone: reminder.timezone || 'Asia/Shanghai',
        templateId: reminder.template_id || '',
        deliveryStatus: reminder.delivery_status || 'config_only',
        deliveryMessage: reminder.delivery_message || ''
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
      const subscribeStatus = await this.requestReminderSubscription();
      const payload = await saveReminderConfig({
        enabled: !!this.data.enabled,
        remind_time: this.data.remind_time,
        timezone: this.data.timezone
      });
      const reminder = payload.reminder || {};
      this.setData({
        templateId: reminder.template_id || this.data.templateId,
        deliveryStatus: reminder.delivery_status || this.data.deliveryStatus,
        deliveryMessage: reminder.delivery_message || this.data.deliveryMessage
      });
      wx.showToast({
        title: subscribeStatus === 'rejected' || subscribeStatus === 'failed' ? '已保存，需授权' : '已保存',
        icon: subscribeStatus === 'rejected' || subscribeStatus === 'failed' ? 'none' : 'success'
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '保存失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ saving: false });
    }
  },

  requestReminderSubscription() {
    if (!this.data.enabled || !this.data.templateId || typeof wx.requestSubscribeMessage !== 'function') {
      return Promise.resolve('skipped');
    }

    return new Promise((resolve) => {
      wx.requestSubscribeMessage({
        tmplIds: [this.data.templateId],
        success: (res) => {
          resolve(res[this.data.templateId] === 'accept' ? 'accepted' : 'rejected');
        },
        fail: () => {
          resolve('failed');
        }
      });
    });
  }
});

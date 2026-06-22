const { fetchReportReasons, submitReport } = require('../../services/api/report');
const { formatApiError } = require('../../utils/copywriting');
const { LEGAL_META } = require('../../utils/legal-content');
const { requireLogin } = require('../../utils/auth-gate');

const TARGET_LABELS = {
  feed_post: '内容记录',
  entry: '共读记录',
  reply: '补充备注',
  app: '功能或服务投诉'
};

Page({
  data: {
    targetType: 'app',
    targetId: '',
    targetHint: '',
    targetPreview: '',
    reasons: [],
    selectedReason: '',
    description: '',
    submitting: false,
    contactEmail: LEGAL_META.contactEmail,
    serviceTime: LEGAL_META.serviceTime
  },

  onLoad() {
    if (!requireLogin({ message: '请先登录后再反馈' })) {
      return;
    }
    const app = getApp();
    const ctx = app.globalData.pendingReportContext || {};
    app.globalData.pendingReportContext = null;
    const targetType = ctx.targetType || 'app';
    this.setData({
      targetType,
      targetId: ctx.targetId || '',
      targetHint: ctx.hint || TARGET_LABELS[targetType] || '功能或服务投诉',
      targetPreview: ctx.snapshot || ''
    });
    this.loadReasons();
  },

  async loadReasons() {
    try {
      const data = await fetchReportReasons();
      this.setData({ reasons: (data && data.reasons) || [] });
    } catch (error) {
      this.setData({
        reasons: [
          { code: 'illegal', label: '违法违规' },
          { code: 'porn', label: '色情低俗' },
          { code: 'spam', label: '垃圾广告' },
          { code: 'infringement', label: '侵权' },
          { code: 'abuse', label: '人身攻击或骚扰' },
          { code: 'other', label: '其他问题' }
        ]
      });
    }
  },

  onSelectReason(e) {
    this.setData({ selectedReason: e.currentTarget.dataset.code || '' });
  },

  onDescInput(e) {
    this.setData({ description: e.detail.value || '' });
  },

  onCopyEmail() {
    const { copyToClipboard } = require('../../utils/clipboard');
    copyToClipboard(this.data.contactEmail, { toastTitle: '邮箱已复制' });
  },

  async onSubmit() {
    if (!this.data.selectedReason || this.data.submitting) {
      return;
    }
    this.setData({ submitting: true });
    try {
      const res = await submitReport({
        target_type: this.data.targetType,
        target_id: this.data.targetId,
        reason_code: this.data.selectedReason,
        description: this.data.description
      });
      wx.showModal({
        title: '已提交',
        content: (res && res.message) || '我们会尽快处理你的反馈',
        showCancel: false,
        success: () => wx.navigateBack()
      });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '提交失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ submitting: false });
    }
  }
});

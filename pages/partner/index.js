const { bindPair, fetchCurrentPair, unbindPair } = require('../../services/api');
const { COPY, formatApiError, mapBindErrorMessage } = require('../../utils/copywriting');

const app = getApp();

Page({
  data: {
    // 加载状态
    loading:       false,
    bindLoading:   false,
    unbindLoading: false,

    // 是否已绑定伙伴
    hasPartner: false,

    // 输入的邀请码
    inviteCode: '',

    // 当前用户信息（用于显示自己的头像和共读码）
    myNickname: '',
    myAvatar:   '',
    myJoinCode: '',

    // 伙伴信息
    partnerNickname: '',
    partnerAvatar:   '',

    // 绑定天数
    bindDays: 0,

    // 共同阅读统计
    sharedBooks: 0,
    sharedNotes: 0
  },

  onLoad() {
    this.loadPairData();
  },

  onShow() {
    // 同步 tabBar 激活状态
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected:   0,
        hasPartner: this.data.hasPartner
      });
    }
    wx.setNavigationBarTitle({
      title: this.data.hasPartner ? '伙伴' : '结伴'
    });
  },

  // 从全局或后端拉取共读关系数据
  async loadPairData() {
    if (!app.globalData.token) {
      this.setData({ hasPartner: false });
      return;
    }

    this.setData({ loading: true });
    try {
      const res  = await fetchCurrentPair();
      const pair = res.pair || null;
      const user = app.globalData.user || {};

      if (pair && pair.partner) {
        this.setData({
          hasPartner:      true,
          myNickname:      user.nickname  || '',
          myAvatar:        user.avatar    || '',
          myJoinCode:      user.join_code || '',
          partnerNickname: pair.partner.nickname || '书友',
          partnerAvatar:   pair.partner.avatar   || '',
          bindDays:        pair.bind_days         || 1,
          sharedBooks:     pair.shared_books      || 0,
          sharedNotes:     pair.shared_notes      || 0
        });
        // 同步到全局
        app.globalData.pair = pair;
      } else {
        this.setData({
          hasPartner:  false,
          myNickname:  user.nickname  || '',
          myAvatar:    user.avatar    || '',
          myJoinCode:  user.join_code || ''
        });
        app.globalData.pair = null;
      }
    } catch (error) {
      if (error.code === 401) {
        app.logout();
      }
      wx.showToast({ title: formatApiError(error, '加载伙伴关系失败'), icon: 'none' });
    } finally {
      this.setData({ loading: false });
      // 拉取数据后刷新导航标题和 tabBar
      this.onShow();
    }
  },

  onInputInviteCode(e) {
    // 共读码固定为 6 位数字，输入过程即做清洗
    const inviteCode = (e.detail.value || '').replace(/\D/g, '').slice(0, 6);
    this.setData({ inviteCode });
  },

  // 通过邀请码绑定伙伴
  async bindPartner() {
    const joinCode = (this.data.inviteCode || '').trim();
    if (!joinCode || joinCode.length !== 6) {
      wx.showToast({ title: COPY.pair.codeInvalid, icon: 'none' });
      return;
    }
    if (!app.globalData.token) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }

    this.setData({ bindLoading: true });
    try {
      await bindPair(joinCode);
      await this.loadPairData();
      const user = app.globalData.user || {};

      this.setData({
        inviteCode:      '',
        hasPartner:      true,
        myNickname:      user.nickname  || '',
        myAvatar:        user.avatar    || '',
        myJoinCode:      user.join_code || '',
        partnerNickname: this.data.partnerNickname || '书友',
        partnerAvatar:   this.data.partnerAvatar || '',
        bindDays:        this.data.bindDays || 1,
        sharedBooks:     this.data.sharedBooks || 0,
        sharedNotes:     this.data.sharedNotes || 0
      });
      wx.showToast({ title: '绑定成功', icon: 'success' });
      this.onShow();
    } catch (error) {
      wx.showToast({ title: mapBindErrorMessage(error), icon: 'none' });
    } finally {
      this.setData({ bindLoading: false });
    }
  },

  // 扫码绑定：解析二维码中的 6 位共读码
  scanToBind() {
    if (!app.globalData.token) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    wx.scanCode({
      success: (res) => {
        // 二维码内容示例：youjinaye://bind/123456 或直接是 6 位数字
        const raw = (res.result || '').trim();
        // 尝试提取末尾 6 位数字
        const match = raw.match(/(\d{6})$/);
        const code  = match ? match[1] : raw;
        if (code.length === 6) {
          this.setData({ inviteCode: code });
          this.bindPartner();
        } else {
          wx.showToast({ title: '二维码格式不正确', icon: 'none' });
        }
      },
      fail: () => {
        wx.showToast({ title: '扫码失败', icon: 'none' });
      }
    });
  },

  // 解除绑定
  unbindPartner() {
    wx.showModal({
      title:   '解除绑定',
      content: '解除后不会删除历史共读记录，但你们将停止同步新的进度和笔记。确定解绑吗？',
      success: async (res) => {
        if (!res.confirm) return;

        this.setData({ unbindLoading: true });
        try {
          await unbindPair();
          app.globalData.pair        = null;
          app.globalData.currentBook = null;
          this.setData({
            hasPartner:      false,
            inviteCode:      '',
            partnerNickname: '',
            partnerAvatar:   '',
            bindDays:        0,
            sharedBooks:     0,
            sharedNotes:     0
          });
          wx.showToast({ title: '已解除绑定', icon: 'success' });
          this.onShow();
        } catch (error) {
          wx.showToast({ title: formatApiError(error, '解绑失败'), icon: 'none' });
        } finally {
          this.setData({ unbindLoading: false });
        }
      }
    });
  }
});

const { bindPair, fetchCurrentPair, fetchMe, unbindPair } = require('../../services/api');
const { COPY, formatApiError, mapBindErrorMessage } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');
const { createQrMatrix } = require('../../utils/qrcode');

const app = getApp();
const QR_CANVAS_SIZE = 128;
const QR_EXPORT_SIZE = 512;

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
    sharedNotes: 0,

    // 我的绑定二维码
    myBindQrText: '',
    myBindQrReady: false,
    myBindQrTempPath: ''
  },

  onShow() {
    if (!requireLogin({ message: '请先登录后再结伴' })) {
      return;
    }
    this.loadPairData();
    this.updateNavigationState();
  },

  updateNavigationState() {
    // 同步 tabBar 激活状态
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected:   0,
        hasPartner: this.data.hasPartner,
        hasBook: !!app.globalData.currentBook
      });
    }
    wx.setNavigationBarTitle({
      title: this.data.hasPartner ? '伙伴' : '结伴'
    });
  },

  // 从全局或后端拉取共读关系数据
  async loadPairData() {
    if (!app.globalData.token) {
      this.setData({
        hasPartner: false,
        inviteCode: '',
        myNickname: '',
        myAvatar: '',
        myJoinCode: '',
        partnerNickname: '',
        partnerAvatar: '',
        bindDays: 0,
        sharedBooks: 0,
        sharedNotes: 0,
        myBindQrText: '',
        myBindQrReady: false,
        myBindQrTempPath: ''
      });
      app.syncReadingContext({
        pair: null,
        currentBook: null
      });
      return;
    }

    this.setData({ loading: true });
    try {
      const [res, me] = await Promise.all([fetchCurrentPair(), fetchMe()]);
      const pair = res.pair || null;
      const user = me || app.globalData.user || {};
      app.syncReadingContext({
        user,
        pair
      }, { persistUser: true });

      if (pair && pair.partner) {
        const myJoinCode = user.join_code || '';
        const qrData = this.buildMyQrData(myJoinCode);
        this.setData({
          hasPartner:      true,
          myNickname:      user.nickname  || '',
          myAvatar:        user.avatar    || '',
          myJoinCode,
          partnerNickname: pair.partner.nickname || '书友',
          partnerAvatar:   pair.partner.avatar   || '',
          bindDays:        pair.bind_days         || 1,
          sharedBooks:     pair.shared_books      || 0,
          sharedNotes:     pair.shared_notes      || 0,
          ...qrData
        });
        this.scheduleDrawMyQrCode(qrData.myBindQrText);
      } else {
        const myJoinCode = user.join_code || '';
        const qrData = this.buildMyQrData(myJoinCode);
        this.setData({
          hasPartner:  false,
          myNickname:  user.nickname  || '',
          myAvatar:    user.avatar    || '',
          myJoinCode,
          ...qrData
        });
        this.scheduleDrawMyQrCode(qrData.myBindQrText);
      }
    } catch (error) {
      if (error.code === 401) {
        app.logout();
      }
      wx.showToast({ title: formatApiError(error, '加载伙伴关系失败'), icon: 'none' });
    } finally {
      this.setData({ loading: false });
      this.updateNavigationState();
    }
  },

  buildMyQrData(joinCode) {
    const code = (joinCode || '').trim();
    if (!code) {
      return {
        myBindQrText: '',
        myBindQrReady: false,
        myBindQrTempPath: ''
      };
    }
    // 统一二维码内容协议，便于后续多端互通。
    const qrText = `youzainaye://pair/bind?join_code=${code}`;
    return {
      myBindQrText: qrText,
      myBindQrReady: false,
      myBindQrTempPath: ''
    };
  },

  scheduleDrawMyQrCode(qrText) {
    if (!qrText) {
      return;
    }
    const draw = () => this.drawMyQrCode(qrText);
    if (typeof wx.nextTick === 'function') {
      wx.nextTick(draw);
      return;
    }
    setTimeout(draw, 0);
  },

  drawMyQrCode(qrText) {
    let matrix;
    try {
      matrix = createQrMatrix(qrText);
    } catch (error) {
      wx.showToast({ title: '二维码生成失败', icon: 'none' });
      return;
    }

    const canvasSize = QR_CANVAS_SIZE;
    const quietZone = 4;
    const moduleCount = matrix.length + quietZone * 2;
    const moduleSize = Math.floor(canvasSize / moduleCount);
    const qrSize = moduleCount * moduleSize;
    const offset = Math.floor((canvasSize - qrSize) / 2);
    const ctx = wx.createCanvasContext('myBindQrCanvas', this);

    ctx.setFillStyle('#ffffff');
    ctx.fillRect(0, 0, canvasSize, canvasSize);
    ctx.setFillStyle('#111827');
    matrix.forEach((row, y) => {
      row.forEach((dark, x) => {
        if (!dark) {
          return;
        }
        ctx.fillRect(
          offset + (x + quietZone) * moduleSize,
          offset + (y + quietZone) * moduleSize,
          moduleSize,
          moduleSize
        );
      });
    });
    ctx.draw(false, () => {
      this.setData({ myBindQrReady: true, myBindQrTempPath: '' });
    });
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
      this.updateNavigationState();
    } catch (error) {
      wx.showToast({ title: mapBindErrorMessage(error), icon: 'none' });
    } finally {
      this.setData({ bindLoading: false });
    }
  },

  parseJoinCodeFromScanResult(rawValue) {
    const raw = (rawValue || '').trim();
    if (!raw) {
      return '';
    }

    // 1) 直接是 6 位数字。
    if (/^\d{6}$/.test(raw)) {
      return raw;
    }

    // 2) URL / scheme 参数：?join_code=123456
    const queryMatch = raw.match(/[?&]join_code=(\d{6})\b/i);
    if (queryMatch) {
      return queryMatch[1];
    }

    // 3) 路径末尾：.../bind/123456
    const pathMatch = raw.match(/\/bind\/(\d{6})\b/i);
    if (pathMatch) {
      return pathMatch[1];
    }

    // 4) JSON 文本：{"join_code":"123456"}
    const jsonMatch = raw.match(/"join_code"\s*:\s*"(\d{6})"/i);
    if (jsonMatch) {
      return jsonMatch[1];
    }

    // 5) 兜底提取：末尾 6 位数字。
    const tailMatch = raw.match(/(\d{6})$/);
    return tailMatch ? tailMatch[1] : '';
  },

  // 扫码绑定：解析二维码中的 6 位共读码
  scanToBind() {
    if (!app.globalData.token) {
      wx.showToast({ title: COPY.common.loginRequired, icon: 'none' });
      return;
    }
    wx.scanCode({
      scanType: ['qrCode', 'barCode'],
      success: (res) => {
        const code = this.parseJoinCodeFromScanResult(res.result || '');
        if (!code) {
          wx.showToast({ title: '二维码格式不正确', icon: 'none' });
          return;
        }
        if (code === (this.data.myJoinCode || '').trim()) {
          wx.showToast({ title: '不能绑定自己的共读码', icon: 'none' });
          return;
        }
        if (code.length === 6) {
          this.setData({ inviteCode: code });
          this.bindPartner();
        }
      },
      fail: () => {
        wx.showToast({ title: '扫码失败', icon: 'none' });
      }
    });
  },

  onPreviewMyQr() {
    if (!this.data.myBindQrReady) {
      wx.showToast({ title: '二维码生成中，请稍后', icon: 'none' });
      return;
    }
    if (this.data.myBindQrTempPath) {
      wx.previewImage({
        urls: [this.data.myBindQrTempPath],
        current: this.data.myBindQrTempPath
      });
      return;
    }
    wx.canvasToTempFilePath({
      canvasId: 'myBindQrCanvas',
      x: 0,
      y: 0,
      width: QR_CANVAS_SIZE,
      height: QR_CANVAS_SIZE,
      destWidth: QR_EXPORT_SIZE,
      destHeight: QR_EXPORT_SIZE,
      success: (res) => {
        const path = res.tempFilePath;
        this.setData({ myBindQrTempPath: path });
        wx.previewImage({
          urls: [path],
          current: path
        });
      },
      fail: () => {
        wx.showToast({ title: '二维码预览失败', icon: 'none' });
      }
    }, this);
  },

  onSaveMyQr() {
    if (!this.data.myBindQrReady) {
      wx.showToast({ title: '二维码生成中，请稍后', icon: 'none' });
      return;
    }
    wx.canvasToTempFilePath({
      canvasId: 'myBindQrCanvas',
      x: 0,
      y: 0,
      width: QR_CANVAS_SIZE,
      height: QR_CANVAS_SIZE,
      destWidth: QR_EXPORT_SIZE,
      destHeight: QR_EXPORT_SIZE,
      success: (res) => {
        wx.saveImageToPhotosAlbum({
          filePath: res.tempFilePath,
          success: () => wx.showToast({ title: '二维码已保存', icon: 'success' }),
          fail: () => wx.showToast({ title: '保存失败，请检查相册权限', icon: 'none' })
        });
      },
      fail: () => {
        wx.showToast({ title: '二维码保存失败', icon: 'none' });
      }
    }, this);
  },

  // 一键复制自己的共读码，方便分享给对方绑定
  onCopyMyJoinCode() {
    const code = (this.data.myJoinCode || '').trim();
    if (!code) {
      wx.showToast({ title: '暂无可复制的共读码', icon: 'none' });
      return;
    }
    wx.setClipboardData({
      data: code,
      success: () => {
        wx.showToast({ title: '共读码已复制', icon: 'success' });
      },
      fail: () => {
        wx.showToast({ title: '复制失败，请重试', icon: 'none' });
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
          app.syncReadingContext({
            pair: null,
            currentBook: null
          });
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
          this.updateNavigationState();
        } catch (error) {
          wx.showToast({ title: formatApiError(error, '解绑失败'), icon: 'none' });
        } finally {
          this.setData({ unbindLoading: false });
        }
      }
    });
  }
});

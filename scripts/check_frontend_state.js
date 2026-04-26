const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.resolve(__dirname, '..');

const requireFromRoot = (relativePath) => require(path.join(ROOT_DIR, relativePath));
const resolveFromRoot = (relativePath) => require.resolve(path.join(ROOT_DIR, relativePath));

const storage = {};
const appHolder = { config: null };
const pageHolder = { config: null };
const componentHolder = { config: null };
let latestTabBarState = {};
let capturedRequests = [];

global.wx = {
  getStorageSync(key) {
    return storage[key];
  },
  setStorageSync(key, value) {
    storage[key] = value;
  },
  removeStorageSync(key) {
    delete storage[key];
  },
  getAccountInfoSync() {
    return { miniProgram: { envVersion: 'develop' } };
  },
  getSystemInfoSync() {
    return { platform: 'devtools' };
  },
  login(options) {
    options.success({ code: 'wx_login_code' });
  },
  nextTick(callback) {
    callback();
  },
  createCanvasContext() {
    return {
      setFillStyle() {},
      fillRect() {},
      draw(_reserve, callback) {
        if (typeof callback === 'function') {
          callback();
        }
      }
    };
  },
  canvasToTempFilePath(options) {
    if (typeof options.success === 'function') {
      options.success({ tempFilePath: 'tmp/bind-qr.png' });
    }
  },
  saveImageToPhotosAlbum(options) {
    if (typeof options.success === 'function') {
      options.success();
    }
  },
  setNavigationBarTitle() {},
  showToast(options) {
    storage.latestToast = options || {};
  },
  switchTab(options) {
    storage.latestSwitchTab = options && options.url;
  },
  navigateTo(options) {
    storage.latestNavigateTo = options && options.url;
  },
  previewImage() {},
  setClipboardData(options) {
    storage.latestClipboard = options.data;
    if (typeof options.success === 'function') {
      options.success();
    }
  },
  scanCode() {},
  requestSubscribeMessage(options) {
    if (typeof options.success === 'function') {
      const templateId = (options.tmplIds || [])[0];
      options.success({ [templateId]: 'accept' });
    }
  }
};

global.App = (config) => {
  appHolder.config = config;
};

global.Page = (config) => {
  pageHolder.config = config;
};

global.Component = (config) => {
  componentHolder.config = config;
};

const apiPath = resolveFromRoot('services/api.js');
const copywritingPath = resolveFromRoot('utils/copywriting.js');
const requestPath = resolveFromRoot('utils/request.js');

require.cache[requestPath] = {
  id: requestPath,
  filename: requestPath,
  loaded: true,
  exports: {
    request: async (options) => {
      capturedRequests.push({
        url: options.url,
        method: options.method || 'GET',
        data: options.data || {}
      });
      if (options.url === '/auth/login') {
        assert.strictEqual(options.data.code, 'wx_login_code');
        assert.ok(options.data.debug_open_id);
        return { token: 'token_wechat', user: { user_id: 'u_wechat', nickname: '微信用户', join_code: '111111' } };
      }
      if (options.url === '/auth/phone-login') {
        assert.strictEqual(options.data.code, 'wx_login_code');
        assert.strictEqual(options.data.phone_code, 'phone_code_1');
        assert.ok(options.data.debug_open_id);
        return { token: 'token_phone', user: { user_id: 'u_phone', nickname: '手机号用户', join_code: '222222' } };
      }
      return {};
    },
    makeClientRequestId: () => 'req_state'
  }
};

requireFromRoot('app.js');

const app = {
  ...appHolder.config,
  globalData: JSON.parse(JSON.stringify(appHolder.config.globalData))
};

global.getApp = () => app;

require.cache[copywritingPath] = {
  id: copywritingPath,
  filename: copywritingPath,
  loaded: true,
  exports: {
    COPY: {
      common: { loginRequired: '请先登录' },
      pair: { codeInvalid: '请输入正确的共读码' }
    },
    formatApiError: (error, fallback) => error && error.message ? error.message : fallback,
    mapBindErrorMessage: (error) => error && error.message ? error.message : '绑定失败'
  }
};

const { createQrMatrix } = requireFromRoot('utils/qrcode.js');

const buildPageInstance = (config) => ({
  ...config,
  data: JSON.parse(JSON.stringify(config.data || {})),
  setData(update, callback) {
    Object.keys(update || {}).forEach((key) => {
      this.data[key] = update[key];
    });
    if (typeof callback === 'function') {
      callback();
    }
  },
  getTabBar() {
    return {
      setData(update) {
        latestTabBarState = { ...latestTabBarState, ...update };
      }
    };
  }
});

const buildComponentInstance = (config) => ({
  ...config,
  data: JSON.parse(JSON.stringify(config.data || {})),
  setData(update) {
    Object.keys(update || {}).forEach((key) => {
      this.data[key] = update[key];
    });
  },
  ...(config.methods || {})
});

const assertRequest = (index, method, url) => {
  assert.strictEqual(capturedRequests[index].method, method);
  assert.strictEqual(capturedRequests[index].url, url);
};

(async () => {
  await app.loginFlow();
  assert.strictEqual(app.globalData.token, 'token_wechat');
  assert.strictEqual(app.globalData.user.user_id, 'u_wechat');

  await app.loginFlow({ method: 'phone', phoneCode: 'phone_code_1' });
  assert.strictEqual(app.globalData.token, 'token_phone');
  assert.strictEqual(app.globalData.user.user_id, 'u_phone');

  app.syncReadingContext({
    user: { user_id: 'u_state_1', nickname: 'Me' },
    pair: {
      pair_id: 'p_state_1',
      current_book: { book_id: 'b_state_1', title: 'State Book' }
    }
  }, { persistUser: true });
  assert.strictEqual(app.globalData.currentBook.book_id, 'b_state_1');
  assert.strictEqual(storage.user.user_id, 'u_state_1');

  app.syncReadingContext({ pair: null });
  assert.strictEqual(app.globalData.pair, null);
  assert.strictEqual(app.globalData.currentBook, null);

  requireFromRoot('custom-tab-bar/index.js');
  const tabBar = buildComponentInstance(componentHolder.config);
  app.globalData.token = '';
  app.globalData.user = null;
  storage.latestSwitchTab = '';
  tabBar.switchTab.call(tabBar, { currentTarget: { dataset: { path: '/pages/bookstore/index', index: 2 } } });
  assert.strictEqual(storage.latestSwitchTab, '');
  assert.strictEqual(storage.latestToast.title, '请先登录后使用');
  app.globalData.token = 'token_state';
  app.globalData.user = { user_id: 'u_state_1' };
  tabBar.switchTab.call(tabBar, { currentTarget: { dataset: { path: '/pages/bookstore/index', index: 2 } } });
  assert.strictEqual(storage.latestSwitchTab, '/pages/bookstore/index');

  ['pages/home/index.wxml', 'pages/profile/index.wxml'].forEach((target) => {
    const content = fs.readFileSync(path.join(ROOT_DIR, target), 'utf8');
    assert.strictEqual(content.includes('测试用户'), false);
    assert.strictEqual(content.includes('test-login'), false);
  });

  const partnerWxml = fs.readFileSync(path.join(ROOT_DIR, 'pages/partner/index.wxml'), 'utf8');
  const partnerWxss = fs.readFileSync(path.join(ROOT_DIR, 'pages/partner/index.wxss'), 'utf8');
  assert.strictEqual(partnerWxml.includes('my-code-inline-copy'), false);
  assert.strictEqual(partnerWxss.includes('210rpx'), false);

  const actualApi = requireFromRoot('services/api.js');
  capturedRequests = [];
  await actualApi.fetchMe();
  await actualApi.updateMe({ nickname: 'New Name' });
  await actualApi.fetchProfileMe();
  await actualApi.fetchProfileStats();
  await actualApi.fetchReadingHistory(2, 5);
  await actualApi.fetchReadingGoal();
  await actualApi.saveReadingGoal({ period_days: 30, target_books: 2, target_days: 10 });
  await actualApi.fetchReminderConfig();
  await actualApi.saveReminderConfig({ enabled: true, remind_time: '21:00', timezone: 'Asia/Shanghai' });
  await actualApi.bindPair('654321');
  await actualApi.unbindPair();
  await actualApi.fetchCurrentPair();
  await actualApi.fetchCurrentBook();
  await actualApi.createEntry({ book_id: 'b_state_1', page: 1, note_content: 'note' });
  await actualApi.markBookEntriesRead('b_state_1', 'e_state_1');
  await actualApi.storeSearchBooks('', 1, 'history');
  await actualApi.storeGetBook('catalog_1');
  await actualApi.storeReadPage('catalog_1', 2);

  [
    ['GET', '/users/me'],
    ['PUT', '/users/me'],
    ['GET', '/users/me/profile'],
    ['GET', '/users/me/stats'],
    ['GET', '/users/me/reading-history?page=2&page_size=5'],
    ['GET', '/users/me/reading-goal'],
    ['PUT', '/users/me/reading-goal'],
    ['GET', '/users/me/reminder-config'],
    ['PUT', '/users/me/reminder-config'],
    ['POST', '/pairs'],
    ['DELETE', '/pairs/current'],
    ['GET', '/pairs/current'],
    ['GET', '/pairs/current/books/current'],
    ['POST', '/books/b_state_1/entries'],
    ['PUT', '/books/b_state_1/read-mark'],
    ['GET', '/store/books?query=&page=1&category=history'],
    ['GET', '/store/books/catalog_1'],
    ['GET', '/store/books/catalog_1/read?page=2']
  ].forEach(([method, url], index) => assertRequest(index, method, url));
  assert.strictEqual(capturedRequests[13].data.book_id, undefined);

  require.cache[apiPath] = {
    id: apiPath,
    filename: apiPath,
    loaded: true,
    exports: {
      bindPair: async () => ({}),
      fetchCurrentPair: async () => ({
        pair: {
          pair_id: 'p_state_1',
          partner: { nickname: 'Partner', avatar: '' },
          current_book: { book_id: 'b_state_1', title: 'State Book', total_pages: 120 }
        }
      }),
      fetchMe: async () => ({ user_id: 'u_state_1', nickname: 'Me', avatar: '', join_code: '123456' }),
      fetchProfileMe: async () => ({ user: { user_id: 'u_state_1', nickname: 'Me', join_code: '123456' }, partner: null }),
      fetchProfileStats: async () => ({ total_books: 0, total_pages: 0, total_entries: 0 }),
      fetchReadingGoal: async () => ({ progress: { completed_books: 0, target_books: 1, active_days: 0, target_days: 20 } }),
      fetchReminderConfig: async () => ({
        reminder: {
          enabled: true,
          remind_time: '21:00',
          timezone: 'Asia/Shanghai',
          delivery_status: 'ready',
          template_id: 'tmpl_state',
          delivery_message: 'ready'
        }
      }),
      saveReminderConfig: async () => ({ reminder: { delivery_status: 'ready', template_id: 'tmpl_state', delivery_message: 'ready' } }),
      unbindPair: async () => ({})
    }
  };

  requireFromRoot('pages/partner/index.js');
  const partnerPage = buildPageInstance(pageHolder.config);

  app.globalData.token = 'token';
  await partnerPage.loadPairData.call(partnerPage);

  assert.strictEqual(partnerPage.data.hasPartner, true);
  assert.strictEqual(app.globalData.pair.pair_id, 'p_state_1');
  assert.strictEqual(app.globalData.currentBook.book_id, 'b_state_1');
  assert.strictEqual(latestTabBarState.hasPartner, true);
  assert.strictEqual(latestTabBarState.hasBook, true);
  assert.strictEqual(partnerPage.parseJoinCodeFromScanResult('youzainaye://pair/bind?join_code=654321'), '654321');
  assert.strictEqual(partnerPage.parseJoinCodeFromScanResult('{"join_code":"654321"}'), '654321');
  assert.ok(partnerPage.data.myBindQrText.includes('join_code=123456'));
  assert.strictEqual(partnerPage.data.myBindQrReady, true);
  const matrix = createQrMatrix(partnerPage.data.myBindQrText);
  assert.strictEqual(matrix.length, 33);
  assert.strictEqual(matrix[0].length, 33);
  partnerPage.onCopyMyJoinCode.call(partnerPage);
  assert.strictEqual(storage.latestClipboard, '123456');

  [
    'pages/bookstore/index.js',
    'pages/home/index.js',
    'pages/progress/index.js',
    'pages/profile/index.js',
    'pages/book-detail/index.js',
    'pages/reader/index.js',
    'pages/reading-history/index.js',
    'pages/reading-goal/index.js',
    'pages/reminder/index.js',
    'pages/settings/index.js'
  ].forEach((target) => {
    requireFromRoot(target);
  });

  console.log('frontend state check ok');
})().catch((error) => {
  console.error(error);
  process.exit(1);
});

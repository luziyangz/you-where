// 统一维护关键中文文案，避免多处散落导致文案不一致或乱码
const COPY = {
  common: {
    loginRequired: '请先登录后再操作',
    networkRetry: '网络异常，内容已保留，请稍后重试'
  },
  pair: {
    codeInvalid: '请输入 6 位数字共读码',
    codeNotFound: '未找到对应用户，请确认对方共读码是否正确',
    codeUsed: '对方已与其他伙伴共读，无法绑定',
    selfBind: '不能与自己绑定'
  },
  entry: {
    pageInvalid: '请输入正确的页码',
    pageExceed: '页码不能超过总页数',
    pageRollback: '页码不能小于当前进度',
    lockHint: '读到第{page}页可解锁'
  }
};

const mapBindErrorMessage = (error) => {
  if (!error) {
    return '绑定失败，请重试';
  }
  if (error.code === 40011) {
    return COPY.pair.codeNotFound;
  }
  if (error.code === 40012) {
    return COPY.pair.codeUsed;
  }
  if (error.code === 40013) {
    return COPY.pair.selfBind;
  }
  if (error.code === 40014) {
    return '你们曾强制解除关系，无法再次绑定';
  }
  if (error.code === 40015) {
    return '你已有待对方同意的绑定申请，请先等待处理';
  }
  if (error.code === 40035) {
    return '伙伴已发起解绑申请，请先在首页处理';
  }
  if (error.code === 40036) {
    return '绑定未满 7 天且解绑申请未超时，暂不能强制解除';
  }
  return error.message || '绑定失败，请重试';
};

const looksLikeTechnicalMessage = (message) => {
  const text = String(message || '');
  if (!text) {
    return false;
  }
  return (
    /https?:\/\//i.test(text) ||
    /API\s*地址/i.test(text) ||
    /localhost|127\.0\.0\.1/i.test(text) ||
    /\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b/.test(text) ||
    /www\.[a-z0-9.-]+\.[a-z]{2,}/i.test(text)
  );
};

/** 将网络层错误转为简短中文，避免向用户展示 URL 等技术信息 */
const mapNetworkErrorMessage = (error, fallback) => {
  const errMsg = String(
    (error && error.detail && error.detail.errMsg) ||
    (error && error.errMsg) ||
    (error && error.message) ||
    ''
  ).toLowerCase();

  if (/timeout|timed\s*out|超时/.test(errMsg)) {
    return '网络超时';
  }
  if (/abort|cancel/.test(errMsg)) {
    return '请求已取消';
  }
  if (/fail|network|connect|socket|dns|ssl|certificate|unreachable|offline|异常/.test(errMsg)) {
    return '网络异常';
  }

  const message = (error && error.message) || '';
  if (looksLikeTechnicalMessage(message)) {
    return fallback || COPY.common.networkRetry;
  }
  return message || fallback || '请求失败，请稍后重试';
};

const formatApiError = (error, fallback) => {
  const code = error && (error.code || error.statusCode);
  const message = (error && error.message) || '';
  const mappedByCode = {
    40014: '你们曾强制解除关系，无法再次绑定',
    40015: '你已有待对方同意的绑定申请，请先等待处理',
    40021: '当前已有一本正在共读的书，请申请换书并等待伙伴同意',
    40035: '伙伴已发起解绑申请，请先处理',
    40036: '绑定未满 7 天且解绑申请未超时，暂不能强制解除',
    40022: '这本书已归档，不能继续更新进度',
    40023: COPY.entry.pageRollback,
    40024: COPY.entry.pageExceed,
    40031: '这条记录暂未解锁，读到对应页码后可补充备注',
    40100: '登录状态已失效，请重新登录',
    40301: '请先绑定伙伴后再添加书籍',
    40402: '当前还没有可解绑的伙伴关系',
    40941: '你已反馈过该内容，我们会尽快处理',
    42900: '操作过于频繁，请稍后再试',
    42901: '今日反馈次数已达上限，请明日再试'
  };
  if (code && mappedByCode[code]) {
    return mappedByCode[code];
  }
  if (code === -1) {
    return mapNetworkErrorMessage(error, fallback);
  }
  if (looksLikeTechnicalMessage(message)) {
    return fallback || '请求失败，请稍后重试';
  }
  return message || fallback || '请求失败，请稍后重试';
};

module.exports = {
  COPY,
  mapBindErrorMessage,
  mapNetworkErrorMessage,
  formatApiError
};

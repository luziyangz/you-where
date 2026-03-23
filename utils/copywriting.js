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
  return error.message || '绑定失败，请重试';
};

const formatApiError = (error, fallback) => {
  const code = error && (error.code || error.statusCode);
  const message = (error && error.message) || fallback || '请求失败';
  if (code === undefined || code === null || code === '') {
    return message;
  }
  return `[${code}] ${message}`;
};

module.exports = {
  COPY,
  mapBindErrorMessage,
  formatApiError
};

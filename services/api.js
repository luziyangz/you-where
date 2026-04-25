const { request, makeClientRequestId } = require('../utils/request');

const getV2BaseUrl = () => {
  const app = getApp();
  const baseUrl = (app && app.globalData && app.globalData.apiBaseUrl) || '';
  if (/\/api\/v1$/i.test(baseUrl)) {
    return baseUrl.replace(/\/api\/v1$/i, '/api/v2');
  }
  if (/\/api\/v2$/i.test(baseUrl)) {
    return baseUrl;
  }
  return `${baseUrl}/api/v2`;
};

const requestV2 = (options) => {
  return request({
    ...options,
    baseUrl: getV2BaseUrl()
  });
};

const fetchHome = () => {
  return requestV2({
    url: '/home',
    method: 'GET'
  });
};

const fetchMe = () => {
  return requestV2({
    url: '/me',
    method: 'GET'
  });
};

const updateMe = (payload) => {
  return requestV2({
    url: '/me',
    method: 'PUT',
    data: payload
  });
};

const acceptAgreement = () => {
  return requestV2({
    url: '/auth/accept-agreement',
    method: 'POST',
    data: {
      accepted: true
    }
  });
};

const bindPair = (joinCode) => {
  return requestV2({
    url: '/pair/bind',
    method: 'POST',
    data: {
      join_code: joinCode
    }
  });
};

const unbindPair = () => {
  return requestV2({
    url: '/pair/unbind',
    method: 'POST'
  });
};

const createBook = (payload) => {
  return requestV2({
    url: '/books',
    method: 'POST',
    data: payload
  });
};

const fetchCurrentBook = () => {
  return requestV2({
    url: '/books/current',
    method: 'GET'
  });
};

const fetchBookEntries = (bookId, page = 1, pageSize = 30) => {
  const safePage = Number(page) > 0 ? Number(page) : 1;
  const safePageSize = Number(pageSize) > 0 ? Number(pageSize) : 30;
  return requestV2({
    url: `/books/${bookId}/entries?page=${safePage}&page_size=${safePageSize}`,
    method: 'GET'
  });
};

const markBookEntriesRead = (bookId, lastEntryId) => {
  return requestV2({
    url: `/books/${bookId}/entries/read`,
    method: 'POST',
    data: {
      last_entry_id: lastEntryId || ''
    }
  });
};

const createEntry = (payload) => {
  return requestV2({
    url: '/entries',
    method: 'POST',
    // createEntry 支持 client_request_id，网络波动时可安全重试一次
    retryTimes: 1,
    data: {
      ...payload,
      client_request_id: payload.client_request_id || makeClientRequestId()
    }
  });
};

const replyEntry = (entryId, content) => {
  return requestV2({
    url: `/entries/${entryId}/replies`,
    method: 'POST',
    data: {
      content
    }
  });
};

const fetchStats = () => {
  return requestV2({
    url: '/me/stats',
    method: 'GET'
  });
};

const fetchBooks = (status) => {
  return requestV2({
    url: `/books${status ? `?status=${status}` : ''}`,
    method: 'GET'
  });
};

// ─────────────────────────── 书城（公版书） ───────────────────────────

const storeSearchBooks = (query, page = 1) => {
  return requestV2({
    url: `/store/books?query=${encodeURIComponent(query || '')}&page=${page}`,
    method: 'GET'
  });
};

const storeGetBook = (catalogId) => {
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}`,
    method: 'GET'
  });
};

const storeReadPage = (catalogId, page = 1) => {
  return requestV2({
    url: `/store/books/${encodeURIComponent(catalogId || '')}/read?page=${page}`,
    method: 'GET'
  });
};

const fetchCurrentPair = () => {
  return requestV2({
    url: '/pair/current',
    method: 'GET'
  });
};

// ─────────────────────────── 我的页（v2） ───────────────────────────

const fetchProfileMe = () => {
  return requestV2({
    url: '/profile/me',
    method: 'GET'
  });
};

const fetchProfileStats = () => {
  return requestV2({
    url: '/profile/stats',
    method: 'GET'
  });
};

const fetchReadingHistory = (page = 1, pageSize = 10) => {
  return requestV2({
    url: `/profile/history?page=${page}&page_size=${pageSize}`,
    method: 'GET'
  });
};

const fetchReadingGoal = () => {
  return requestV2({
    url: '/profile/goals',
    method: 'GET'
  });
};

const saveReadingGoal = (payload) => {
  return requestV2({
    url: '/profile/goals',
    method: 'PUT',
    data: payload
  });
};

const fetchReminderConfig = () => {
  return requestV2({
    url: '/profile/reminders',
    method: 'GET'
  });
};

const saveReminderConfig = (payload) => {
  return requestV2({
    url: '/profile/reminders',
    method: 'PUT',
    data: payload
  });
};

module.exports = {
  acceptAgreement,
  bindPair,
  createBook,
  createEntry,
  fetchBookEntries,
  fetchBooks,
  fetchCurrentBook,
  fetchCurrentPair,
  fetchProfileMe,
  fetchProfileStats,
  fetchHome,
  fetchMe,
  updateMe,
  fetchReadingGoal,
  fetchReadingHistory,
  fetchStats,
  markBookEntriesRead,
  replyEntry,
  saveReadingGoal,
  saveReminderConfig,
  storeGetBook,
  storeReadPage,
  storeSearchBooks,
  fetchReminderConfig,
  unbindPair
};

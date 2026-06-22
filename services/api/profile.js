const { requestV2 } = require('./base');

const fetchMe = () => {
  return requestV2({
    url: '/users/me',
    method: 'GET'
  });
};

const updateMe = (payload) => {
  return requestV2({
    url: '/users/me',
    method: 'PUT',
    data: payload
  });
};

const fetchStats = () => {
  return requestV2({
    url: '/users/me/stats',
    method: 'GET'
  });
};

const fetchProfileMe = () => {
  return requestV2({
    url: '/users/me/profile',
    method: 'GET'
  });
};

const fetchProfileStats = () => {
  return requestV2({
    url: '/users/me/stats',
    method: 'GET'
  });
};

const fetchReadingHistory = (page = 1, pageSize = 10) => {
  return requestV2({
    url: `/users/me/reading-history?page=${page}&page_size=${pageSize}`,
    method: 'GET'
  });
};

const fetchReadingGoal = () => {
  return requestV2({
    url: '/users/me/reading-goal',
    method: 'GET'
  });
};

const saveReadingGoal = (payload) => {
  return requestV2({
    url: '/users/me/reading-goal',
    method: 'PUT',
    data: payload
  });
};

const fetchReminderConfig = () => {
  return requestV2({
    url: '/users/me/reminder-config',
    method: 'GET'
  });
};

const saveReminderConfig = (payload) => {
  return requestV2({
    url: '/users/me/reminder-config',
    method: 'PUT',
    data: payload
  });
};

/** 书城阅读器偏好（字号、主题、亮度），账号级 */
const fetchReaderOptions = () => {
  return requestV2({
    url: '/users/me/reader-options',
    method: 'GET'
  });
};

const saveReaderOptions = (payload) => {
  const p = payload || {};
  return requestV2({
    url: '/users/me/reader-options',
    method: 'PUT',
    data: {
      font_size: p.font_size,
      reading_mode: p.reading_mode,
      brightness: p.brightness
    }
  });
};

module.exports = {
  fetchMe,
  fetchProfileMe,
  fetchProfileStats,
  fetchReaderOptions,
  fetchReadingGoal,
  fetchReadingHistory,
  fetchReminderConfig,
  fetchStats,
  saveReaderOptions,
  saveReadingGoal,
  saveReminderConfig,
  updateMe
};

const { request, makeClientRequestId } = require('../utils/request');

const fetchHome = () => {
  return request({
    url: '/home',
    method: 'GET'
  });
};

const fetchMe = () => {
  return request({
    url: '/me',
    method: 'GET'
  });
};

const acceptAgreement = () => {
  return request({
    url: '/auth/accept-agreement',
    method: 'POST',
    data: {
      accepted: true
    }
  });
};

const bindPair = (joinCode) => {
  return request({
    url: '/pair/bind',
    method: 'POST',
    data: {
      join_code: joinCode
    }
  });
};

const unbindPair = () => {
  return request({
    url: '/pair/unbind',
    method: 'POST'
  });
};

const createBook = (payload) => {
  return request({
    url: '/books',
    method: 'POST',
    data: payload
  });
};

const fetchCurrentBook = () => {
  return request({
    url: '/books/current',
    method: 'GET'
  });
};

const fetchBookEntries = (bookId) => {
  return request({
    url: `/books/${bookId}/entries`,
    method: 'GET'
  });
};

const markBookEntriesRead = (bookId, lastEntryId) => {
  return request({
    url: `/books/${bookId}/entries/read`,
    method: 'POST',
    data: {
      last_entry_id: lastEntryId || ''
    }
  });
};

const createEntry = (payload) => {
  return request({
    url: '/entries',
    method: 'POST',
    data: {
      ...payload,
      client_request_id: payload.client_request_id || makeClientRequestId()
    }
  });
};

const replyEntry = (entryId, content) => {
  return request({
    url: `/entries/${entryId}/replies`,
    method: 'POST',
    data: {
      content
    }
  });
};

const fetchStats = () => {
  return request({
    url: '/me/stats',
    method: 'GET'
  });
};

const fetchBooks = (status) => {
  return request({
    url: `/books${status ? `?status=${status}` : ''}`,
    method: 'GET'
  });
};

const fetchCurrentPair = () => {
  return request({
    url: '/pair/current',
    method: 'GET'
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
  fetchHome,
  fetchMe,
  fetchStats,
  markBookEntriesRead,
  replyEntry,
  unbindPair
};

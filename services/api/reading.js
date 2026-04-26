const { makeClientRequestId, requestV2 } = require('./base');

const fetchHome = () => {
  return requestV2({
    url: '/home',
    method: 'GET'
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
    url: '/pairs/current/books/current',
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
    url: `/books/${bookId}/read-mark`,
    method: 'PUT',
    data: {
      last_entry_id: lastEntryId || ''
    }
  });
};

const createEntry = (payload) => {
  const bookId = payload.book_id;
  const body = {
    page: payload.page,
    note_content: payload.note_content || '',
    mark_finished: !!payload.mark_finished,
    client_request_id: payload.client_request_id || makeClientRequestId()
  };
  return requestV2({
    url: `/books/${bookId}/entries`,
    method: 'POST',
    retryTimes: 1,
    data: body
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

const fetchBooks = (status) => {
  return requestV2({
    url: `/books${status ? `?status=${status}` : ''}`,
    method: 'GET'
  });
};

module.exports = {
  createBook,
  createEntry,
  fetchBookEntries,
  fetchBooks,
  fetchCurrentBook,
  fetchHome,
  markBookEntriesRead,
  replyEntry
};

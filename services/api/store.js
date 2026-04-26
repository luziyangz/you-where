const { requestV2 } = require('./base');

const storeSearchBooks = (query = '', page = 1, category = 'all') => {
  const params = [
    `query=${encodeURIComponent(query || '')}`,
    `page=${page}`,
    `category=${encodeURIComponent(category || 'all')}`
  ];
  return requestV2({
    url: `/store/books?${params.join('&')}`,
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

module.exports = {
  storeGetBook,
  storeReadPage,
  storeSearchBooks
};

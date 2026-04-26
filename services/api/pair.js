const { requestV2 } = require('./base');

const bindPair = (joinCode) => {
  return requestV2({
    url: '/pairs',
    method: 'POST',
    data: {
      join_code: joinCode
    }
  });
};

const unbindPair = () => {
  return requestV2({
    url: '/pairs/current',
    method: 'DELETE'
  });
};

const fetchCurrentPair = () => {
  return requestV2({
    url: '/pairs/current',
    method: 'GET'
  });
};

module.exports = {
  bindPair,
  fetchCurrentPair,
  unbindPair
};

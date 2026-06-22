const auth = require('./api/auth');
const pair = require('./api/pair');
const profile = require('./api/profile');
const reading = require('./api/reading');
const store = require('./api/store');
const feed = require('./api/feed');
const report = require('./api/report');

module.exports = {
  ...auth,
  ...pair,
  ...profile,
  ...reading,
  ...store,
  ...feed,
  ...report
};

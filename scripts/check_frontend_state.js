const assert = require('assert');
const fs = require('fs');
const path = require('path');

const ROOT_DIR = path.resolve(__dirname, '..');

const readText = (relativePath) => fs.readFileSync(path.join(ROOT_DIR, relativePath), 'utf8');
const exists = (relativePath) => fs.existsSync(path.join(ROOT_DIR, relativePath));

const appJson = JSON.parse(readText('app.json'));
const homeJson = JSON.parse(readText('pages/home/index.json'));

const disabledPageDirs = [
  'pages/bookstore',
  'pages/book-detail',
  'pages/reader',
  'pages/webview'
];

const disabledRoutePatterns = [
  'pages/bookstore/index',
  'pages/book-detail/index',
  'pages/reader/index',
  'pages/webview/index'
];

const frontendTargets = [
  'app.json',
  'custom-tab-bar/index.js',
  'utils/auth-gate.js',
  'utils/share.js',
  'services/api/profile.js',
  'services/api/store.js',
  'pages/home/index.js',
  'pages/home/index.json',
  'pages/home/index.wxml',
  'pages/profile/index.js',
  'pages/profile/index.wxml',
  'pages/progress/index.js',
  'pages/progress/index.wxml',
  'pages/partner/index.js',
  'pages/partner/index.wxml',
  'pages/reading-history/index.js',
  'pages/reading-history/index.wxml',
  'pages/privacy-authorize/index.js',
  'pages/privacy-authorize/index.wxml'
];

disabledRoutePatterns.forEach((route) => {
  assert.ok(!appJson.pages.includes(route), `${route} must not be registered`);
});

disabledPageDirs.forEach((dir) => {
  assert.strictEqual(exists(dir), false, `${dir} must be removed from frontend package`);
});

assert.ok(appJson.pages.includes('pages/home/index'), 'home page must remain registered');
assert.ok(appJson.pages.includes('pages/profile/index'), 'profile page must remain registered');
assert.ok(appJson.pages.includes('pages/reading-history/index'), 'history page must remain registered');

const tabRoutes = appJson.tabBar.list.map((item) => item.pagePath);
assert.deepStrictEqual(tabRoutes, [
  'pages/home/index',
  'pages/reading-history/index',
  'pages/progress/index',
  'pages/profile/index'
]);

assert.strictEqual(homeJson.usingComponents, undefined, 'home must not mount login panel');

const homeWxml = readText('pages/home/index.wxml');
assert.ok(!homeWxml.includes('login-consent-panel'), 'home must not render login panel');
assert.ok(!homeWxml.includes('test-login'), 'home must not expose review login on first screen');

const profileWxml = readText('pages/profile/index.wxml');
assert.ok(profileWxml.includes('login-consent-panel'), 'login stays available from profile only');

const sensitivePatterns = [
  /bookstore/i,
  /book-detail/i,
  /reader/i,
  /webview/i,
  /buildReaderUrl/i,
  /catalog_id/i,
  /chooseMessageFile/i,
  /reader-options/i,
  /reading-progress-cache/i,
  /choose-txt/i,
  /open-link/i,
  /小说/,
  /出版物/,
  /在线阅读/,
  /正文阅读/,
  /导入 TXT/,
  /TXT 全书/
];

frontendTargets.forEach((target) => {
  const content = readText(target);
  sensitivePatterns.forEach((pattern) => {
    assert.ok(!pattern.test(content), `${target} contains disabled review-sensitive pattern: ${pattern}`);
  });
});

const api = require(path.join(ROOT_DIR, 'services/api.js'));
assert.strictEqual(typeof api.fetchReaderOptions, 'undefined');
assert.strictEqual(typeof api.saveReaderOptions, 'undefined');
assert.strictEqual(typeof api.storeSearchBooks, 'undefined');
assert.strictEqual(typeof api.storeReadPage, 'undefined');

console.log('frontend review-safe state check ok');

const {
  createEntry,
  fetchHome,
  fetchReaderOptions,
  saveReaderOptions,
  storeDeleteCatalogMark,
  storeGetCatalogReadingProgress,
  storeGetCatalogToc,
  storeListCatalogMarks,
  storePutCatalogReadingProgress,
  storeReadPage,
  storeUpsertCatalogMark
} = require('../../services/api');
const { formatApiError } = require('../../utils/copywriting');
const { requireLogin } = require('../../utils/auth-gate');
const { syncReadingProgressCache } = require('../../utils/reading-progress-cache');

const app = getApp();
const PAGE_CACHE_PREFIX = 'readerPageCache';
const PAGE_CACHE_INDEX_PREFIX = 'readerPageCacheIndex';
const PAGE_CACHE_LIMIT = 80;

Page({
  data: {
    catalogId: '',
    loading: false,
    syncing: false,
    usingCache: false,
    cacheHint: '',
    page: 1,
    pageData: null,
    fontSize: 32,
    readingMode: 'paper',
    showCatalog: false,
    showSettings: false,
    pageTurnClass: '',
    catalogItems: [],
    /** 服务端自动解析的章节目录 */
    tocChapters: [],
    /** 当前页段落划重点：{ [paragraphIndex]: { style, note, textSnap } } */
    highlightDetailMap: {},
    highlightItems: [],
    highlightCount: 0,
    showNotePopup: false,
    noteDraft: '',
    noteEditIndex: '',
    noteEditStyle: 'marker',
    showQuoteJournalPopup: false,
    quoteJournalText: '',
    quoteJournalDraft: '',
    quoteJournalPage: 1,
    quoteJournalSubmitting: false,
    pageSlices: [],
    sliceIndex: 0,
    sliceTotal: 1,
    controlsVisible: false,
    panelTab: 'catalog',
    brightness: 90,
    brightnessMaskOpacity: 0.055,
    screenWidth: 375,
    touchStartX: 0,
    touchStartY: 0
  },

  onLoad(query) {
    const catalogId = query && query.catalog_id ? decodeURIComponent(query.catalog_id) : '';
    // 仅目录/章节跳转时带 page + jump=1；日常「继续阅读」由服务端进度 + 本地屏位恢复
    const forceJump = query && (query.jump === '1' || query.jump === 'true');
    const forceRestart = query && (query.restart === '1' || query.restart === 'true');
    const rawPage = query && query.page ? Number(query.page) : 0;
    const explicitPage = Number.isFinite(rawPage) && rawPage > 0;
    this._forceRestart = !!forceRestart;
    this._forcePageJump = forceJump && explicitPage;
    this._pendingJumpPage = this._forcePageJump ? Math.floor(rawPage) : 0;
    this._resumePageHint = !forceJump && !forceRestart && explicitPage ? Math.floor(rawPage) : 0;
    this._resumeBootstrapped = false;
    this._pendingSliceRatio = null;
    const options = this.restoreReaderOptions();
    const systemInfo = wx.getSystemInfoSync ? wx.getSystemInfoSync() : {};
    this._tocCatalogId = '';
    this._tocFetched = false;
    this._tocLoadingPromise = null;
    this._catalogMarksCache = [];
    this._marksFetchedFor = '';
    this._pageLoadSeq = 0;
    if (typeof wx.onNetworkStatusChange === 'function') {
      wx.onNetworkStatusChange((res) => {
        if (res && res.isConnected && this.data.pageData) {
          this.refreshCurrentPageInBackground();
        }
      });
    }
    this.setData({
      catalogId,
      tocChapters: [],
      page: 1,
      usingCache: false,
      cacheHint: '',
      screenWidth: Number(systemInfo.windowWidth || 375),
      screenHeight: Number(systemInfo.windowHeight || 700),
      ...options
    });
  },

  onHide() {
    this.saveLocalResume();
    this.flushReadingProgress();
  },

  onUnload() {
    this.saveLocalResume();
    this.flushReadingProgress();
  },

  /** 立即写入书城阅读进度（退出阅读页时） */
  flushReadingProgress() {
    if (this._saveCatalogTimer) {
      clearTimeout(this._saveCatalogTimer);
      this._saveCatalogTimer = null;
    }
    const cid = this.data.catalogId;
    const pd = this.data.pageData;
    if (cid && pd && pd.page && app.globalData.token) {
      const pageNum = Number(pd.page);
      syncReadingProgressCache(cid, pageNum);
      storePutCatalogReadingProgress(cid, pageNum).catch(() => {});
    }
  },

  async onShow() {
    if (!requireLogin({ message: '请先登录后阅读' })) {
      return;
    }
    if (this._resumeBootstrapped || this._bootstrapRunning) {
      return;
    }
    this._resumeBootstrapped = true;
    this._bootstrapRunning = true;
    try {
      await this.syncReaderOptionsFromServer();
      await this.bootstrapReadingPosition();
      await this.loadPage();
    } finally {
      this._bootstrapRunning = false;
    }
  },

  /** 从服务端进度（及可选 jump 页码）恢复阅读位置 */
  async bootstrapReadingPosition() {
    const cid = this.data.catalogId;
    if (!cid) {
      return;
    }
    let targetPage = 1;
    let totalPages = 0;
    if (this._forceRestart) {
      this._pendingSliceRatio = null;
      targetPage = 1;
      if (app.globalData.token) {
        try {
          await storePutCatalogReadingProgress(cid, 1);
        } catch (e) {
          /* 重置失败时仍从第 1 页开始 */
        }
      }
      this._forceRestart = false;
    } else {
      try {
        const pr = await storeGetCatalogReadingProgress(cid);
        targetPage = Math.max(1, Number(pr.last_page || 1));
        totalPages = Number(pr.total_pages || 0);
        syncReadingProgressCache(cid, targetPage);
      } catch (e) {
        const hint = Number(this._resumePageHint || 0);
        const localResume = this.readLocalResume(cid);
        const latestCache = this.readLatestCachedPageMeta(cid);
        targetPage = Math.max(
          1,
          hint ||
            Number(localResume && localResume.page) ||
            Number(latestCache && latestCache.page) ||
            Number(this.data.page || 1)
        );
        syncReadingProgressCache(cid, targetPage);
      }
    }
    if (this._forcePageJump && this._pendingJumpPage) {
      targetPage = this._pendingJumpPage;
      this._forcePageJump = false;
      this._pendingJumpPage = 0;
      this._pendingSliceRatio = null;
    } else {
      this._pendingSliceRatio = this.readLocalResumeSliceRatio(cid, targetPage);
    }
    if (totalPages > 0) {
      targetPage = Math.min(targetPage, totalPages);
    }
    if (Number(this.data.page) !== targetPage) {
      this.setData({ page: targetPage });
    }
  },

  /** 读取本页屏内位置（与页码绑定） */
  readLocalResume(catalogId) {
    try {
      const raw = wx.getStorageSync(`readerResume:${catalogId}`);
      if (!raw || !Number(raw.page)) {
        return null;
      }
      return raw;
    } catch (e) {
      return null;
    }
  },

  readLocalResumeSliceRatio(catalogId, pageNum) {
    try {
      const raw = wx.getStorageSync(`readerResume:${catalogId}`);
      if (!raw || Number(raw.page) !== Number(pageNum)) {
        return null;
      }
      const ratio = Number(raw.sliceRatio);
      if (!Number.isFinite(ratio)) {
        return null;
      }
      return Math.max(0, Math.min(1, ratio));
    } catch (e) {
      return null;
    }
  },

  /** 持久化屏内位置，退出再进可回到同一屏 */
  saveLocalResume() {
    const cid = this.data.catalogId;
    const pd = this.data.pageData;
    if (!cid || !pd || !pd.page) {
      return;
    }
    const total = Math.max(1, Number(this.data.sliceTotal) || 1);
    const idx = Math.max(0, Number(this.data.sliceIndex) || 0);
    const sliceRatio = total > 1 ? idx / (total - 1) : 0;
    const pageNum = Number(pd.page);
    try {
      wx.setStorageSync(`readerResume:${cid}`, {
        page: pageNum,
        sliceIndex: idx,
        sliceRatio,
        updatedAt: Date.now()
      });
      syncReadingProgressCache(cid, pageNum);
    } catch (e) {
      /* ignore */
    }
  },

  /** 自服务端拉取阅读偏好，失败则沿用本地 readerOptions */
  async syncReaderOptionsFromServer() {
    if (!app.globalData.token) {
      return;
    }
    try {
      const res = await fetchReaderOptions();
      const ro = (res && res.reader_options) || {};
      let fontSize = Number(ro.font_size);
      if (!Number.isFinite(fontSize)) {
        fontSize = Number(this.data.fontSize || 32);
      }
      fontSize = Math.max(28, Math.min(42, fontSize));
      let readingMode = ro.reading_mode;
      readingMode = ['paper', 'night', 'focus'].includes(readingMode) ? readingMode : this.data.readingMode || 'paper';
      let brightness = Number(ro.brightness);
      if (!Number.isFinite(brightness)) {
        brightness = Number(this.data.brightness || 90);
      }
      brightness = Math.max(25, Math.min(100, brightness));
      const brightnessMaskOpacity = this.calcBrightnessMaskOpacity(brightness);
      this.setData({ fontSize, readingMode, brightness, brightnessMaskOpacity });
      wx.setStorageSync('readerOptions', { fontSize, readingMode, brightness });
    } catch (e) {
      /* 保留 onLoad 恢复的本地偏好 */
    }
  },

  scheduleSaveReaderOptionsRemote() {
    if (!app.globalData.token) {
      return;
    }
    if (this._readerOptRemoteTimer) {
      clearTimeout(this._readerOptRemoteTimer);
    }
    this._readerOptRemoteTimer = setTimeout(() => {
      saveReaderOptions({
        font_size: Number(this.data.fontSize),
        reading_mode: this.data.readingMode,
        brightness: Number(this.data.brightness)
      }).catch(() => {});
    }, 900);
  },

  async syncHomeContext() {
    if (!app.globalData.token) {
      return null;
    }

    try {
      const payload = await fetchHome();
      app.syncReadingContext({
        user: payload.user,
        pair: payload.pair,
        currentBook: payload.current_book || null
      }, { persistUser: true });
      return payload;
    } catch (error) {
      if (error.code === 401) {
        app.logout();
      }
      throw error;
    }
  },

  pageCacheKey(catalogId, pageNum) {
    return `${PAGE_CACHE_PREFIX}:${catalogId}:${Number(pageNum) || 1}`;
  },

  pageCacheIndexKey(catalogId) {
    return `${PAGE_CACHE_INDEX_PREFIX}:${catalogId}`;
  },

  readCachedPage(catalogId, pageNum) {
    try {
      const raw = wx.getStorageSync(this.pageCacheKey(catalogId, pageNum));
      if (!raw || !raw.payload || Number(raw.payload.page) !== Number(pageNum)) {
        return null;
      }
      return raw;
    } catch (e) {
      return null;
    }
  },

  readLatestCachedPageMeta(catalogId) {
    try {
      const index = wx.getStorageSync(this.pageCacheIndexKey(catalogId)) || [];
      if (!Array.isArray(index) || !index.length) {
        return null;
      }
      return index.slice().sort((a, b) => Number(b.updatedAt || 0) - Number(a.updatedAt || 0))[0] || null;
    } catch (e) {
      return null;
    }
  },

  writeCachedPage(catalogId, payload) {
    const pageNum = Number(payload && payload.page);
    if (!catalogId || !pageNum || !payload || !payload.content) {
      return;
    }
    const updatedAt = Date.now();
    try {
      wx.setStorageSync(this.pageCacheKey(catalogId, pageNum), { payload, updatedAt });
      const indexKey = this.pageCacheIndexKey(catalogId);
      const rawIndex = wx.getStorageSync(indexKey) || [];
      const nextIndex = (Array.isArray(rawIndex) ? rawIndex : [])
        .filter((item) => Number(item.page) !== pageNum)
        .concat([{ page: pageNum, updatedAt }])
        .sort((a, b) => Number(b.updatedAt || 0) - Number(a.updatedAt || 0));
      nextIndex.slice(PAGE_CACHE_LIMIT).forEach((item) => {
        try {
          wx.removeStorageSync(this.pageCacheKey(catalogId, item.page));
        } catch (e) {
          /* ignore */
        }
      });
      wx.setStorageSync(indexKey, nextIndex.slice(0, PAGE_CACHE_LIMIT));
    } catch (e) {
      /* 本地缓存空间不足时不影响阅读 */
    }
  },

  applyPagePayload(payload, options = {}) {
    const catalogId = this.data.catalogId;
    const pageData = this.decoratePage(payload);
    const highlightDetailMap = this.buildDetailMapFromMarks(this._catalogMarksCache, pageData.page);
    const sliceRatio = this._pendingSliceRatio;
    this._pendingSliceRatio = null;
    this.setData({
      pageData,
      catalogItems: this.buildCatalog(payload),
      highlightDetailMap,
      highlightItems: this.buildHighlightItems(catalogId, pageData),
      highlightCount: this.countHighlightMarks(),
      sliceIndex: 0,
      usingCache: !!options.fromCache,
      cacheHint: options.fromCache ? '已显示本地缓存，联网后会自动刷新' : ''
    }, () => {
      this.reflowPageSlices(0, sliceRatio != null ? sliceRatio : null);
      this.scheduleSaveCatalogProgress();
      this.ensureCatalogToc().catch(() => {});
      if (!options.fromCache) {
        this.prefetchAdjacentPages(pageData);
      }
    });
  },

  async refreshCurrentPageInBackground() {
    const pd = this.data.pageData;
    if (!pd || !this.data.catalogId) {
      return;
    }
    const pageNum = Number(pd.page || this.data.page || 1);
    try {
      const payload = await storeReadPage(this.data.catalogId, pageNum);
      this.writeCachedPage(this.data.catalogId, payload);
      if (Number(this.data.pageData && this.data.pageData.page) === pageNum) {
        await this.ensureCatalogMarksLoaded(Number(payload.total_pages || 0), false);
        this.applyPagePayload(payload, { fromCache: false });
      }
    } catch (e) {
      /* 后台刷新失败时继续使用缓存 */
    }
  },

  prefetchAdjacentPages(pageData) {
    const catalogId = this.data.catalogId;
    const pageNum = Number(pageData && pageData.page);
    const total = Number(pageData && pageData.total_pages);
    if (!catalogId || !pageNum || !total) {
      return;
    }
    [pageNum + 1, pageNum - 1]
      .filter((p) => p >= 1 && p <= total && !this.readCachedPage(catalogId, p))
      .slice(0, 2)
      .forEach((p) => {
        storeReadPage(catalogId, p)
          .then((payload) => this.writeCachedPage(catalogId, payload))
          .catch(() => {});
      });
  },

  async loadPage() {
    const catalogId = this.data.catalogId;
    if (!catalogId) {
      this.setData({ pageData: null });
      return;
    }

    const requestedPage = Math.max(1, Number(this.data.page || 1));
    const previousPage = Number(this.data.pageData && this.data.pageData.page) || requestedPage;
    const cached = this.readCachedPage(catalogId, requestedPage);
    const seq = (this._pageLoadSeq || 0) + 1;
    this._pageLoadSeq = seq;

    if (cached && cached.payload) {
      await this.ensureCatalogMarksLoaded(Number(cached.payload.total_pages || 0), false);
      this.applyPagePayload(cached.payload, { fromCache: true });
      this.setData({ loading: false });
      this.refreshCurrentPageInBackground();
      return;
    }

    this.setData({
      loading: !this.data.pageData,
      cacheHint: this.data.pageData ? '正在加载下一页，当前页会保持显示' : ''
    });
    try {
      const payload = await storeReadPage(catalogId, requestedPage);
      if (seq !== this._pageLoadSeq) {
        return;
      }
      this.writeCachedPage(catalogId, payload);
      await this.ensureCatalogMarksLoaded(Number(payload.total_pages || 0), false);
      this.applyPagePayload(payload, { fromCache: false });
    } catch (error) {
      wx.showToast({
        title: this.data.pageData ? '网络不稳，已保留当前页' : formatApiError(error, '加载失败'),
        icon: 'none'
      });
      if (this.data.pageData) {
        this.setData({
          page: previousPage,
          cacheHint: '网络不稳，已保留当前页'
        });
      } else {
        this.setData({ pageData: null });
      }
    } finally {
      if (seq === this._pageLoadSeq) {
        this.setData({ loading: false });
      }
    }
  },

  noop() {},

  // 防抖同步书城阅读进度到服务端
  scheduleSaveCatalogProgress() {
    const cid = this.data.catalogId;
    const pd = this.data.pageData;
    if (!cid || !pd || !pd.page) {
      return;
    }
    if (this._saveCatalogTimer) {
      clearTimeout(this._saveCatalogTimer);
    }
    this._saveCatalogTimer = setTimeout(() => {
      const pageNum = Number(pd.page);
      if (!pageNum) {
        return;
      }
      syncReadingProgressCache(cid, pageNum);
      storePutCatalogReadingProgress(cid, pageNum).catch(() => {});
    }, 700);
  },

  restoreReaderOptions() {
    const saved = wx.getStorageSync('readerOptions') || {};
    const fontSize = Number(saved.fontSize || 32);
    const brightness = Math.max(25, Math.min(100, Number(saved.brightness || 90)));
    return {
      fontSize: Math.max(28, Math.min(42, fontSize)),
      readingMode: ['paper', 'night', 'focus'].includes(saved.readingMode) ? saved.readingMode : 'paper',
      brightness,
      brightnessMaskOpacity: this.calcBrightnessMaskOpacity(brightness)
    };
  },

  persistReaderOptions(nextOptions = {}) {
    const options = {
      fontSize: this.data.fontSize,
      readingMode: this.data.readingMode,
      brightness: this.data.brightness,
      ...nextOptions
    };
    wx.setStorageSync('readerOptions', {
      fontSize: options.fontSize,
      readingMode: options.readingMode,
      brightness: options.brightness
    });
    this.scheduleSaveReaderOptionsRemote();
  },

  calcBrightnessMaskOpacity(brightness) {
    const safe = Math.max(25, Math.min(100, Number(brightness) || 100));
    return Number((((100 - safe) / 100) * 0.55).toFixed(3));
  },

  decoratePage(payload) {
    const raw = payload && payload.content ? payload.content : '';
    let paragraphs = raw
      .split(/\n+/)
      .map((item) => item.trim())
      .filter(Boolean);
    if (paragraphs.length <= 1 && raw.length > 120) {
      paragraphs = raw
        .split(/(?<=[。！？；])/)
        .map((item) => item.trim())
        .filter(Boolean);
    }
    return {
      ...payload,
      paragraphs: paragraphs.length ? paragraphs : [raw || '本页暂无正文内容。']
    };
  },

  estimateMaxCharsPerScreen() {
    const screenWidth = Number(this.data.screenWidth || 375);
    const screenHeight = Number(this.data.screenHeight || 700);
    const fontSizeRpx = Number(this.data.fontSize || 32);
    const fontSizePx = (fontSizeRpx * screenWidth) / 750;
    const lineHeightPx = fontSizePx * 1.95;
    const horizontalPaddingPx = (50 * screenWidth) / 750;
    const usableWidth = Math.max(120, screenWidth - horizontalPaddingPx * 2);
    const usableHeight = Math.max(220, screenHeight - 230);
    const charsPerLine = Math.max(8, Math.floor(usableWidth / (fontSizePx * 1.02)));
    const linesPerScreen = Math.max(6, Math.floor(usableHeight / lineHeightPx));
    return Math.max(120, charsPerLine * linesPerScreen);
  },

  buildPageSlices(paragraphs = []) {
    const maxChars = this.estimateMaxCharsPerScreen();
    const slices = [];
    let bucket = [];
    let bucketChars = 0;
    paragraphs.forEach((text, index) => {
      const itemText = String(text || '');
      const weight = Math.max(12, itemText.length + 2);
      if (bucket.length && bucketChars + weight > maxChars) {
        slices.push({ items: bucket });
        bucket = [];
        bucketChars = 0;
      }
      bucket.push({
        text: itemText,
        index,
        lineKey: `fb-${index}-${bucket.length}`,
        paraGapBefore: false,
        isParaStart: true,
        isParaEnd: true
      });
      bucketChars += weight;
    });
    if (bucket.length) {
      slices.push({ items: bucket });
    }
    return slices.length
      ? slices
      : [{ items: [{ text: '本页暂无正文内容。', index: -1, lineKey: 'fb-empty', paraGapBefore: false, isParaStart: true, isParaEnd: true }] }];
  },

  // 行宽测量：与 WXSS 段落 letter-spacing 对齐（字间额外间距）
  measureLineVisualWidth(ctx, str, letterSpacingPx) {
    const s = String(str || '');
    if (!s) {
      return 0;
    }
    const ls = Number(letterSpacingPx) || 0;
    const units = Array.from(s);
    const base = ctx.measureText(s).width;
    return base + Math.max(0, units.length - 1) * ls;
  },

  isLatinBoundaryChar(ch) {
    return !!(ch && /[a-zA-Z0-9]/.test(ch));
  },

  // 不宜出现在行首的标点（挤压到上一行末尾，并受宽度约束）
  isForbiddenLineStartChar(ch) {
    if (!ch) {
      return false;
    }
    if ('，。！？；：、」』】〉）》％…·'.includes(ch)) {
      return true;
    }
    if (',.;:!?)]}'.includes(ch)) {
      return true;
    }
    if (ch === '"' || ch === '\u201d') {
      return true;
    }
    return false;
  },

  adjustLinesAvoidLeadingPunctuation(ctx, lines, maxWidth, letterSpacingPx) {
    const widthOf = (s) => this.measureLineVisualWidth(ctx, s, letterSpacingPx);
    const out = lines.map((l) => String(l || ''));
    for (let i = 1; i < out.length; i += 1) {
      let cur = out[i];
      let prev = out[i - 1];
      while (cur.length && this.isForbiddenLineStartChar(cur[0])) {
        const ch = cur[0];
        const merged = prev + ch;
        if (widthOf(merged) > maxWidth) {
          break;
        }
        prev = merged;
        cur = cur.slice(1);
        out[i - 1] = prev;
        out[i] = cur;
      }
    }
    return out.filter((l) => l.length > 0);
  },

  // Canvas measureText + 字间距；英文尽量整词换行，超长词再逐字断开
  wrapParagraphLines(ctx, text, maxWidth, letterSpacingPx) {
    const raw = String(text || '');
    if (!raw.trim()) {
      return [''];
    }

    const tokens = [];
    let i = 0;
    while (i < raw.length) {
      const ch = raw[i];
      if (/\s/.test(ch)) {
        let j = i + 1;
        while (j < raw.length && /\s/.test(raw[j])) {
          j += 1;
        }
        tokens.push({ kind: 'ws', text: raw.slice(i, j) });
        i = j;
      } else if (/[a-zA-Z]/.test(ch)) {
        let j = i + 1;
        while (j < raw.length && /[a-zA-Z0-9._\-'’]/.test(raw[j])) {
          j += 1;
        }
        tokens.push({ kind: 'word', text: raw.slice(i, j) });
        i = j;
      } else {
        tokens.push({ kind: 'cjk', text: ch });
        i += 1;
      }
    }

    const lines = [];
    let line = '';

    const flushLine = () => {
      const trimmed = line.replace(/[ \u3000\t]+$/u, '');
      lines.push(trimmed || '');
      line = '';
    };

    const widthOf = (candidate) => this.measureLineVisualWidth(ctx, candidate, letterSpacingPx);

    const appendSepIfNeeded = (nextTok) => {
      if (!line) {
        return '';
      }
      const last = line[line.length - 1];
      const first = nextTok[0];
      if (this.isLatinBoundaryChar(last) && this.isLatinBoundaryChar(first)) {
        return ' ';
      }
      return '';
    };

    const pushCharsFromToken = (tokText) => {
      const chars = Array.from(tokText);
      chars.forEach((char) => {
        const cand = line + char;
        if (!line || widthOf(cand) <= maxWidth) {
          line = cand;
          return;
        }
        // 拉丁字母词内断开：上一行末尾加连字符（宽度允许时）
        if (/[a-zA-Z]/.test(char) && /[a-zA-Z]$/.test(line)) {
          const hyphenated = `${line}-`;
          if (widthOf(hyphenated) <= maxWidth) {
            line = hyphenated;
            flushLine();
            line = char;
            return;
          }
        }
        flushLine();
        line = char;
      });
    };

    tokens.forEach((tok) => {
      if (tok.kind === 'ws') {
        if (line && !/\s$/.test(line)) {
          line += ' ';
        }
        return;
      }

      const sep = appendSepIfNeeded(tok.text);
      const candidate = line + sep + tok.text;

      if (!line || widthOf(candidate) <= maxWidth) {
        line = candidate;
        return;
      }

      if (line.trim()) {
        flushLine();
      } else {
        line = '';
      }

      if (widthOf(tok.text) <= maxWidth) {
        line = tok.text;
        return;
      }

      pushCharsFromToken(tok.text);
    });

    if (line.trim()) {
      flushLine();
    }

    const baseLines = lines.length ? lines : [''];
    const adjusted = this.adjustLinesAvoidLeadingPunctuation(ctx, baseLines, maxWidth, letterSpacingPx);
    return adjusted.length ? adjusted : [''];
  },

  buildMeasuredPageSlices(ctx, paragraphs, layout) {
    const { contentWidth, contentHeight, lineHeightPx, paragraphGapPx, letterSpacingPx } = layout;
    const lineUnits = [];
    paragraphs.forEach((paraText, pIndex) => {
      const wrapped = this.wrapParagraphLines(ctx, String(paraText || ''), contentWidth, letterSpacingPx);
      wrapped.forEach((lineText, lineIdx) => {
        lineUnits.push({
          text: lineText,
          index: pIndex,
          isParaStart: lineIdx === 0,
          isParaEnd: lineIdx === wrapped.length - 1,
          lineKey: `m-${pIndex}-${lineIdx}`
        });
      });
    });

    const slices = [];
    let bucket = [];
    let usedHeight = 0;
    let i = 0;

    while (i < lineUnits.length) {
      const unit = lineUnits[i];
      const paraGap =
        unit.isParaStart && (bucket.length > 0 || slices.length > 0) ? paragraphGapPx : 0;

      if (bucket.length > 0 && usedHeight + paraGap + lineHeightPx > contentHeight) {
        slices.push({ items: bucket });
        bucket = [];
        usedHeight = 0;
        continue;
      }

      usedHeight += paraGap;
      bucket.push({
        text: unit.text,
        index: unit.index,
        lineKey: unit.lineKey,
        paraGapBefore: unit.isParaStart && bucket.length > 0,
        isParaStart: !!unit.isParaStart,
        isParaEnd: !!unit.isParaEnd
      });
      usedHeight += lineHeightPx;
      i += 1;
    }

    if (bucket.length) {
      slices.push({ items: bucket });
    }
    return slices.length
      ? slices
      : [{ items: [{ text: '本页暂无正文内容。', index: -1, lineKey: 'm-empty', paraGapBefore: false, isParaStart: true, isParaEnd: true }] }];
  },

  applySliceLayout(targetIndex, slices) {
    const pageData = this.data.pageData;
    if (!pageData || !slices || !slices.length) {
      return;
    }
    const maxIndex = Math.max(0, slices.length - 1);
    const safeIndex = Math.max(0, Math.min(maxIndex, Number(targetIndex) || 0));
    this.setData({
      pageSlices: slices,
      sliceIndex: safeIndex,
      sliceTotal: slices.length
    });
  },

  reflowPageSlices(targetIndex, preserveRatio = null) {
    const pageData = this.data.pageData;
    if (!pageData) {
      this.setData({
        pageSlices: [],
        sliceIndex: 0,
        sliceTotal: 1
      });
      return;
    }
    this._reflowSeq = (this._reflowSeq || 0) + 1;
    const seq = this._reflowSeq;

    const fallbackSlices = this.buildPageSlices(pageData.paragraphs || []);
    const fbMax = Math.max(0, fallbackSlices.length - 1);
    const fbSafe = Math.max(0, Math.min(fbMax, Number(targetIndex) || 0));
    this.setData({
      pageSlices: fallbackSlices,
      sliceIndex: fbSafe,
      sliceTotal: fallbackSlices.length
    });

    wx.nextTick(() => {
      setTimeout(() => this.measureReflowPageSlices(seq, fbSafe, fallbackSlices.length, preserveRatio), 32);
    });
  },

  // 顶栏/底栏显隐后正文可视高度变化，按当前屏进度比例重新测量分页
  scheduleViewportRemeasure() {
    if (!this.data.pageData) {
      return;
    }
    const total = Math.max(1, Number(this.data.sliceTotal) || 1);
    const idx = Math.max(0, Number(this.data.sliceIndex) || 0);
    const preserveRatio = total > 1 ? idx / (total - 1) : 0;
    this._reflowSeq = (this._reflowSeq || 0) + 1;
    const seq = this._reflowSeq;
    wx.nextTick(() => {
      setTimeout(() => this.measureReflowPageSlices(seq, 0, 1, preserveRatio), 48);
    });
  },

  // preserveRatio：0~1，工具栏显隐等仅重测视口时保持阅读进度比例
  measureReflowPageSlices(seq, targetIndex, fallbackTotal, preserveRatio) {
    if (seq !== this._reflowSeq || !this.data.pageData) {
      return;
    }
    wx.createSelectorQuery()
      .in(this)
      .select('.reader-content')
      .boundingClientRect()
      .select('#readerMeasureCanvas')
      .fields({ node: true, size: true })
      .exec((res) => {
      if (seq !== this._reflowSeq || !this.data.pageData) {
        return;
      }
      const rect = res[0];
      const canvasNode = res[1] && res[1].node;
      if (!rect || !canvasNode || rect.width <= 0 || rect.height <= 0) {
        return;
      }

      const screenWidth = Number(this.data.screenWidth || 375);
      const paddingPx = (50 * screenWidth) / 750;
      const letterSpacingPx = (1 * screenWidth) / 750;
      const contentWidth = Math.max(80, rect.width - paddingPx * 2 - letterSpacingPx * 2 - 2);
      const contentHeight = Math.max(120, rect.height - 6);

      const fontSizeRpx = Number(this.data.fontSize || 32);
      const fontSizePx = (fontSizeRpx * screenWidth) / 750;
      const lineHeightPx = fontSizePx * 1.95;
      const paragraphGapPx = (32 * screenWidth) / 750;

      try {
        const ctx = canvasNode.getContext('2d');
        const dpr = wx.getSystemInfoSync().pixelRatio || 2;
        canvasNode.width = Math.ceil(400 * dpr);
        canvasNode.height = Math.ceil(80 * dpr);
        ctx.scale(dpr, dpr);
        // 与 app.wxss 中 page 字体栈、正文非加粗一致，测量更接近真机
        ctx.font = `normal ${fontSizePx}px "Songti SC","STSong","FZShuSong-Z01","PingFang SC","Microsoft YaHei",serif`;

        const slices = this.buildMeasuredPageSlices(ctx, this.data.pageData.paragraphs || [], {
          contentWidth,
          contentHeight,
          lineHeightPx,
          paragraphGapPx,
          letterSpacingPx
        });

        const maxIdx = Math.max(0, slices.length - 1);
        let resolvedIndex = 0;
        if (preserveRatio != null && Number.isFinite(Number(preserveRatio))) {
          const r = Math.max(0, Math.min(1, Number(preserveRatio)));
          resolvedIndex = Math.max(0, Math.min(maxIdx, Math.round(r * maxIdx)));
        } else {
          const fb = Math.max(1, Number(fallbackTotal) || 1);
          const ratio = fb > 1 ? Number(targetIndex) / (fb - 1) : 0;
          resolvedIndex = Math.max(0, Math.min(maxIdx, Math.round(ratio * maxIdx)));
        }

        if (seq !== this._reflowSeq) {
          return;
        }
        this.applySliceLayout(resolvedIndex, slices);
      } catch (e) {
        // 测量失败时保留字符估算分页
      }
    });
  },

  ensureCatalogToc() {
    const cid = this.data.catalogId;
    if (!cid || !app.globalData.token) {
      return Promise.resolve();
    }
    if (this._tocCatalogId === cid && this._tocFetched) {
      return Promise.resolve();
    }
    if (this._tocLoadingPromise) {
      return this._tocLoadingPromise;
    }
    this._tocLoadingPromise = storeGetCatalogToc(cid)
      .then((data) => {
        this._tocCatalogId = cid;
        this._tocFetched = true;
        const chapters = data.chapters || [];
        this.setData({ tocChapters: chapters }, () => {
          if (this.data.pageData) {
            this.setData({ catalogItems: this.buildCatalog(this.data.pageData) });
          }
        });
      })
      .catch(() => {
        this._tocFetched = true;
        this.setData({ tocChapters: [] });
      })
      .finally(() => {
        this._tocLoadingPromise = null;
      });
    return this._tocLoadingPromise;
  },

  buildCatalog(payload) {
    const chapters = this.data.tocChapters || [];
    const curPage = Number(this.data.page || (payload && payload.page) || 1);
    const totalPages = Number(payload && payload.total_pages) || 1;

    if (chapters.length >= 2) {
      return chapters.map((c, idx) => {
        const p = Number(c.page) || 1;
        const nextP =
          idx + 1 < chapters.length ? Number(chapters[idx + 1].page) || totalPages + 1 : totalPages + 1;
        return {
          tocIdx: `t-${idx}`,
          page: p,
          title: c.title || `第 ${p} 页`,
          active: curPage >= p && curPage < nextP
        };
      });
    }

    const chunk = Math.max(1, Math.ceil(totalPages / 8));
    const items = [];
    for (let start = 1; start <= totalPages; start += chunk) {
      const end = Math.min(totalPages, start + chunk - 1);
      items.push({
        tocIdx: `f-${start}`,
        page: start,
        title: start === end ? `第 ${start} 页` : `第 ${start}-${end} 页`,
        active: curPage >= start && curPage <= end
      });
    }
    return items;
  },

  /** 兼容本地旧版划重点（一次性上传到云端） */
  normalizeHighlightPageMap(raw) {
    if (!raw || typeof raw !== 'object') {
      return {};
    }
    const out = {};
    Object.keys(raw).forEach((k) => {
      const v = raw[k];
      if (v === true) {
        out[k] = { style: 'marker', note: '', textSnap: '' };
      } else if (v && typeof v === 'object') {
        const style = v.style === 'underline' ? 'underline' : 'marker';
        out[k] = {
          style,
          note: String(v.note || '').slice(0, 500),
          textSnap: String(v.textSnap || '').slice(0, 200)
        };
      }
    });
    return out;
  },

  /** 从服务端拉取本书全部摘抄；必要时把旧本地缓存迁入云端 */
  async ensureCatalogMarksLoaded(totalPages, force = false) {
    const cid = this.data.catalogId;
    if (!cid || !app.globalData.token) {
      this._catalogMarksCache = [];
      return;
    }
    if (!force && this._marksFetchedFor === cid && Array.isArray(this._catalogMarksCache)) {
      return;
    }
    try {
      const data = await storeListCatalogMarks(cid);
      let marks = data.marks || [];
      if (!force && marks.length === 0 && totalPages) {
        await this.migrateLocalMarksToServer(cid, totalPages);
        const again = await storeListCatalogMarks(cid);
        marks = again.marks || [];
      }
      this._catalogMarksCache = (marks || []).map((m) => ({
        page: Number(m.page),
        para_index: Number(m.para_index),
        style: m.style === 'underline' ? 'underline' : 'marker',
        note: m.note || '',
        text_snap: m.text_snap || ''
      }));
      this._marksFetchedFor = cid;
    } catch (e) {
      this._catalogMarksCache = [];
    }
  },

  async migrateLocalMarksToServer(cid, totalPages) {
    const tp = Math.min(Number(totalPages) || 0, 2000);
    for (let p = 1; p <= tp; p += 1) {
      const raw = wx.getStorageSync(`readerHighlights:${cid}:${p}`) || {};
      const norm = this.normalizeHighlightPageMap(raw);
      const keys = Object.keys(norm);
      if (!keys.length) {
        continue;
      }
      for (let ki = 0; ki < keys.length; ki += 1) {
        const k = keys[ki];
        const row = norm[k];
        try {
          await storeUpsertCatalogMark(cid, {
            page: p,
            para_index: Number(k),
            style: row.style,
            note: row.note || '',
            text_snap: row.textSnap || ''
          });
        } catch (err) {
          /* 单条失败不影响其余迁移 */
        }
      }
      try {
        wx.removeStorageSync(`readerHighlights:${cid}:${p}`);
      } catch (e) {
        /* ignore */
      }
    }
  },

  buildDetailMapFromMarks(marks, pageNum) {
    const map = {};
    const pn = Number(pageNum);
    (marks || []).forEach((m) => {
      if (Number(m.page) !== pn) {
        return;
      }
      map[String(m.para_index)] = {
        style: m.style,
        note: m.note || '',
        textSnap: m.text_snap || ''
      };
    });
    return map;
  },

  countHighlightMarks() {
    return (this._catalogMarksCache || []).length;
  },

  closePanels() {
    this.setData({
      showCatalog: false,
      showSettings: false,
      controlsVisible: false
    }, () => this.scheduleViewportRemeasure());
  },

  onBack() {
    this.closePanels();
    const pages = getCurrentPages();
    if (pages.length > 1) {
      wx.navigateBack();
      return;
    }
    wx.switchTab({ url: '/pages/home/index' });
  },

  onTouchStart(e) {
    const touch = e.touches && e.touches[0];
    if (!touch) {
      return;
    }
    this.setData({
      touchStartX: touch.clientX,
      touchStartY: touch.clientY
    });
  },

  onTouchEnd(e) {
    const touch = e.changedTouches && e.changedTouches[0];
    if (!touch) {
      return;
    }
    const dx = touch.clientX - this.data.touchStartX;
    const dy = touch.clientY - this.data.touchStartY;
    if (Math.abs(dx) < 58 || Math.abs(dx) < Math.abs(dy) * 1.35) {
      return;
    }
    if (dx < 0) {
      this.onNext();
    } else {
      this.onPrev();
    }
  },

  onScreenTap(e) {
    if (this.data.showCatalog || this.data.showSettings) {
      this.closePanels();
      return;
    }
    const x = Number(e.detail && e.detail.x);
    const width = Number(this.data.screenWidth || 375);
    if (Number.isFinite(x) && x < width * 0.28) {
      this.onPrev();
      return;
    }
    if (Number.isFinite(x) && x > width * 0.72) {
      this.onNext();
      return;
    }
    this.setData({
      controlsVisible: !this.data.controlsVisible
    }, () => this.scheduleViewportRemeasure());
  },

  onToggleCatalog() {
    const nextShow = !this.data.showCatalog;
    const apply = () => {
      this.setData(
        {
          showCatalog: nextShow,
          showSettings: false,
          panelTab: 'catalog',
          controlsVisible: true,
          catalogItems:
            nextShow && this.data.pageData ? this.buildCatalog(this.data.pageData) : this.data.catalogItems
        },
        () => this.scheduleViewportRemeasure()
      );
    };
    if (nextShow) {
      this.ensureCatalogToc().then(apply).catch(apply);
      return;
    }
    apply();
  },

  onToggleSettings() {
    this.setData({
      showSettings: !this.data.showSettings,
      showCatalog: false,
      controlsVisible: true
    }, () => this.scheduleViewportRemeasure());
  },

  onSwitchPanelTab(e) {
    const tab = e.currentTarget.dataset.tab;
    if (!['catalog', 'highlights'].includes(tab)) {
      return;
    }
    this.setData({ panelTab: tab });
  },

  onProgressChanging(e) {
    const value = Number(e.detail && e.detail.value);
    if (!Number.isFinite(value)) {
      return;
    }
    this.setData({ page: Math.max(1, Math.round(value)) });
  },

  onProgressChange(e) {
    const value = Number(e.detail && e.detail.value);
    if (!Number.isFinite(value) || !this.data.pageData) {
      return;
    }
    const currentPage = Number(this.data.pageData.page || 1);
    const maxPage = Number(this.data.pageData.total_pages || 1);
    const nextPage = Math.max(1, Math.min(maxPage, Math.round(value)));
    if (nextPage === currentPage) {
      return;
    }
    this._pendingSliceRatio = null;
    this.setData({
      page: nextPage,
      pageTurnClass: nextPage > currentPage ? 'turn-next' : 'turn-prev'
    }, () => this.loadPage());
    setTimeout(() => this.setData({ pageTurnClass: '' }), 260);
  },

  onSetMode(e) {
    const mode = e.currentTarget.dataset.mode;
    if (!['paper', 'night', 'focus'].includes(mode)) {
      return;
    }
    this.setData({ readingMode: mode });
    this.persistReaderOptions({ readingMode: mode });
  },

  onFontDecrease() {
    const currentRatio = this.data.sliceTotal > 1 ? (this.data.sliceIndex / (this.data.sliceTotal - 1)) : 0;
    const next = Math.max(28, Number(this.data.fontSize || 32) - 2);
    this.setData({ fontSize: next });
    const targetIndex = Math.round(currentRatio * Math.max(0, this.data.sliceTotal - 1));
    this.reflowPageSlices(targetIndex);
    this.persistReaderOptions({ fontSize: next });
  },

  onFontIncrease() {
    const currentRatio = this.data.sliceTotal > 1 ? (this.data.sliceIndex / (this.data.sliceTotal - 1)) : 0;
    const next = Math.min(42, Number(this.data.fontSize || 32) + 2);
    this.setData({ fontSize: next });
    const targetIndex = Math.round(currentRatio * Math.max(0, this.data.sliceTotal - 1));
    this.reflowPageSlices(targetIndex);
    this.persistReaderOptions({ fontSize: next });
  },

  onBrightnessChange(e) {
    const value = Number(e.detail && e.detail.value);
    if (!Number.isFinite(value)) {
      return;
    }
    const brightness = Math.max(25, Math.min(100, Math.round(value)));
    this.setData({
      brightness,
      brightnessMaskOpacity: this.calcBrightnessMaskOpacity(brightness)
    });
    this.persistReaderOptions({ brightness });
  },

  onGoCatalogPage(e) {
    const page = Number(e.currentTarget.dataset.page || 1);
    const maxPage = Number(this.data.pageData && this.data.pageData.total_pages) || page;
    const nextPage = Math.max(1, Math.min(maxPage, page));
    this._pendingSliceRatio = null;
    this.setData({
      page: nextPage,
      showCatalog: false,
      panelTab: 'catalog',
      sliceIndex: 0,
      pageTurnClass: 'turn-next'
    }, () => this.loadPage());
    setTimeout(() => this.setData({ pageTurnClass: '' }), 260);
  },

  async applyParagraphHighlight(indexStr, style, note) {
    const pageData = this.data.pageData;
    const catalogId = this.data.catalogId;
    if (!pageData || !catalogId || !app.globalData.token) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    const idx = Number(indexStr);
    if (idx < 0 || Number.isNaN(idx)) {
      return;
    }
    const safeStyle = style === 'underline' ? 'underline' : 'marker';
    const paraText = (pageData.paragraphs || [])[idx] || '';
    const textSnap = String(paraText).replace(/\s+/g, ' ').slice(0, 160);
    try {
      await storeUpsertCatalogMark(catalogId, {
        page: pageData.page,
        para_index: idx,
        style: safeStyle,
        note: String(note || '').slice(0, 500),
        text_snap: textSnap
      });
      await this.ensureCatalogMarksLoaded(Number(pageData.total_pages || 0), true);
      const highlightDetailMap = this.buildDetailMapFromMarks(this._catalogMarksCache, pageData.page);
      this.setData({
        highlightDetailMap,
        highlightItems: this.buildHighlightItems(catalogId, pageData),
        highlightCount: this.countHighlightMarks()
      });
    } catch (err) {
      wx.showToast({
        title: formatApiError(err, '同步摘抄失败'),
        icon: 'none'
      });
      throw err;
    }
  },

  async clearParagraphHighlight(indexStr) {
    const pageData = this.data.pageData;
    const catalogId = this.data.catalogId;
    if (!pageData || !catalogId || !app.globalData.token) {
      return;
    }
    const idx = Number(indexStr);
    if (Number.isNaN(idx)) {
      return;
    }
    try {
      await storeDeleteCatalogMark(catalogId, pageData.page, idx);
      await this.ensureCatalogMarksLoaded(Number(pageData.total_pages || 0), true);
      const highlightDetailMap = this.buildDetailMapFromMarks(this._catalogMarksCache, pageData.page);
      this.setData({
        highlightDetailMap,
        highlightItems: this.buildHighlightItems(catalogId, pageData),
        highlightCount: this.countHighlightMarks()
      });
      wx.showToast({ title: '已取消标记', icon: 'none' });
    } catch (err) {
      wx.showToast({
        title: formatApiError(err, '删除失败'),
        icon: 'none'
      });
    }
  },

  getParagraphText(paraIndex) {
    const pageData = this.data.pageData;
    const paragraphs = pageData && pageData.paragraphs ? pageData.paragraphs : [];
    const idx = Number(paraIndex);
    if (!Number.isFinite(idx) || idx < 0) {
      return '';
    }
    return String(paragraphs[idx] || '').trim();
  },

  openQuoteJournalPopup(paraIndex, quoteTextOverride, pageOverride) {
    const text = (quoteTextOverride || this.getParagraphText(paraIndex) || '').trim();
    if (!text) {
      wx.showToast({ title: '无法获取段落原文', icon: 'none' });
      return;
    }
    this.setData({
      showQuoteJournalPopup: true,
      quoteJournalText: text.slice(0, 800),
      quoteJournalDraft: '',
      quoteJournalPage: pageOverride || Number(this.data.pageData && this.data.pageData.page) || 1,
      quoteJournalSubmitting: false
    });
  },

  onQuoteJournalDraftInput(e) {
    this.setData({ quoteJournalDraft: e.detail.value || '' });
  },

  onCloseQuoteJournalPopup() {
    this.setData({
      showQuoteJournalPopup: false,
      quoteJournalText: '',
      quoteJournalDraft: '',
      quoteJournalSubmitting: false
    });
  },

  async onSubmitQuoteJournal() {
    const note = (this.data.quoteJournalDraft || '').trim();
    if (!note) {
      wx.showToast({ title: '请填写阅读备注', icon: 'none' });
      return;
    }
    if (!app.globalData.token) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }
    this.setData({ quoteJournalSubmitting: true });
    try {
      const homeData = await this.syncHomeContext();
      const book = homeData && homeData.current_book;
      if (!book) {
        wx.showToast({ title: '请先在书籍详情页「加入共读」', icon: 'none' });
        return;
      }
      await createEntry({
        book_id: book.book_id,
        page: this.data.quoteJournalPage,
        note_content: note,
        quote_text: this.data.quoteJournalText
      });
      this.onCloseQuoteJournalPopup();
      wx.showToast({ title: '已保存到进度记录', icon: 'success' });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '保存失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ quoteJournalSubmitting: false });
    }
  },

  async quoteParagraphToJournal(paraIndex) {
    this.openQuoteJournalPopup(paraIndex);
  },

  onParagraphLongPress(e) {
    const index = String(e.currentTarget.dataset.index);
    const pageData = this.data.pageData;
    if (!pageData || index === '-1') {
      return;
    }
    const existing = this.data.highlightDetailMap[index];
    if (existing && existing.style) {
      wx.showActionSheet({
        itemList: ['修改标注样式', '引用到进度记录', '取消标注'],
        success: (res) => {
          if (res.tapIndex === 0) {
            this.setData({
              showNotePopup: true,
              noteDraft: existing.note || '',
              noteEditIndex: index,
              noteEditStyle: existing.style === 'underline' ? 'underline' : 'marker'
            });
          } else if (res.tapIndex === 1) {
            this.openQuoteJournalPopup(index);
          } else if (res.tapIndex === 2) {
            this.clearParagraphHighlight(index);
          }
        }
      });
      return;
    }
    wx.showActionSheet({
      itemList: ['温柔荧光重点', '细腻下划线', '划重点并写备注', '引用到进度记录'],
      success: async (res) => {
        if (res.tapIndex === 0) {
          await this.applyParagraphHighlight(index, 'marker', '');
          wx.showToast({ title: '已温柔标记', icon: 'success' });
        } else if (res.tapIndex === 1) {
          await this.applyParagraphHighlight(index, 'underline', '');
          wx.showToast({ title: '已画线下划线', icon: 'success' });
        } else if (res.tapIndex === 2) {
          this.setData({
            showNotePopup: true,
            noteDraft: '',
            noteEditIndex: index,
            noteEditStyle: 'marker'
          });
        } else if (res.tapIndex === 3) {
          await this.quoteParagraphToJournal(index);
        }
      }
    });
  },

  onHighlightLongPress(e) {
    const page = Number(e.currentTarget.dataset.page);
    const index = Number(e.currentTarget.dataset.index);
    const item = (this.data.highlightItems || []).find(
      (row) => Number(row.page) === page && Number(row.index) === index
    );
    const text = item && item.text ? item.text : this.getParagraphText(index);
    this.openQuoteJournalPopup(index, text, page || undefined);
  },

  onTapNoteStyleChip(e) {
    const s = e.currentTarget.dataset.style;
    if (s === 'underline' || s === 'marker') {
      this.setData({ noteEditStyle: s });
    }
  },

  onNoteDraftInput(e) {
    this.setData({ noteDraft: e.detail.value || '' });
  },

  onCloseNotePopup() {
    this.setData({
      showNotePopup: false,
      noteDraft: '',
      noteEditIndex: ''
    });
  },

  async onConfirmNotePopup() {
    const idx = this.data.noteEditIndex;
    if (idx === '' || idx === undefined || idx === null) {
      this.onCloseNotePopup();
      return;
    }
    const style = this.data.noteEditStyle === 'underline' ? 'underline' : 'marker';
    const note = (this.data.noteDraft || '').trim();
    try {
      await this.applyParagraphHighlight(String(idx), style, note);
      wx.showToast({ title: note ? '备注已显示在段落下方' : '已收进摘抄本', icon: 'success' });
      this.onCloseNotePopup();
    } catch (e) {
      /* 失败提示已在 applyParagraphHighlight 中 */
    }
  },

  buildHighlightItems(catalogId, pagePayload) {
    if (!catalogId || !pagePayload) {
      return [];
    }
    const curPage = Number(pagePayload.page || 0);
    const paragraphs = pagePayload.paragraphs || [];
    const marks = this._catalogMarksCache || [];
    const items = marks.map((m) => {
      const snap =
        m.text_snap ||
        (Number(m.page) === curPage ? String(paragraphs[m.para_index] || '') : '') ||
        '';
      const preview = snap.replace(/\s+/g, ' ').slice(0, 48);
      const styleLabel = m.style === 'underline' ? '下划线' : '荧光';
      return {
        id: `${m.page}-${m.para_index}`,
        page: m.page,
        index: m.para_index,
        text: snap,
        preview: preview || `第 ${m.para_index + 1} 段`,
        note: String(m.note || '').slice(0, 120),
        styleLabel
      };
    });
    items.sort((a, b) => a.page - b.page || a.index - b.index);
    return items;
  },

  onPrev() {
    const pageData = this.data.pageData;
    if (!pageData) {
      return;
    }
    if (this.data.sliceIndex > 0) {
      this.setData({
        sliceIndex: this.data.sliceIndex - 1,
        pageTurnClass: 'turn-prev'
      }, () => this.saveLocalResume());
      setTimeout(() => this.setData({ pageTurnClass: '' }), 260);
      return;
    }
    if (pageData.page <= 1) {
      return;
    }
    this._pendingSliceRatio = null;
    this.setData({
      page: pageData.page - 1,
      sliceIndex: 0,
      pageTurnClass: 'turn-prev'
    }, () => this.loadPage());
    setTimeout(() => this.setData({ pageTurnClass: '' }), 260);
  },

  onNext() {
    const pageData = this.data.pageData;
    if (!pageData) {
      return;
    }
    if (this.data.sliceIndex < this.data.sliceTotal - 1) {
      this.setData({
        sliceIndex: this.data.sliceIndex + 1,
        pageTurnClass: 'turn-next'
      }, () => this.saveLocalResume());
      setTimeout(() => this.setData({ pageTurnClass: '' }), 260);
      return;
    }
    if (pageData.page >= pageData.total_pages) {
      return;
    }
    this._pendingSliceRatio = null;
    this.setData({
      page: pageData.page + 1,
      sliceIndex: 0,
      pageTurnClass: 'turn-next'
    }, () => this.loadPage());
    setTimeout(() => this.setData({ pageTurnClass: '' }), 260);
  },

  async onSyncProgress() {
    if (!app.globalData.token) {
      wx.showToast({ title: '请先登录', icon: 'none' });
      return;
    }

    this.setData({ syncing: true });
    try {
      // 仅当已经存在“正在共读的书”时才同步进度。
      // 用户可能只是预览阅读（尚未加入共读），此时给出提示。
      const homeData = await this.syncHomeContext();
      const book = homeData && homeData.current_book ? homeData.current_book : null;
      if (!book) {
        wx.showToast({ title: '请先在书籍详情页「加入共读」', icon: 'none' });
        return;
      }

      await createEntry({
        book_id: book.book_id,
        page: Number(this.data.pageData && this.data.pageData.page) || 1,
        note_content: ''
      });
      const latestHomeData = await this.syncHomeContext();
      if (latestHomeData && latestHomeData.current_book) {
        app.syncCurrentBook(latestHomeData.current_book);
      }
      wx.showToast({ title: '已记到共读日记', icon: 'success' });
    } catch (error) {
      wx.showToast({
        title: formatApiError(error, '同步失败'),
        icon: 'none'
      });
    } finally {
      this.setData({ syncing: false });
    }
  }
});

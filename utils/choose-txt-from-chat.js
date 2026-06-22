/**
 * 从微信聊天记录选择 TXT（wx.chooseMessageFile）
 * 微信原生流程：先选聊天对象 → 再展示该会话内可导入文件（无 TXT 则为空列表）。
 * 须在用户 tap 回调里同步调用；不要先 await 隐私检查或 setTimeout 再调起。
 */

const TXT_EXT_RE = /\.txt$/i;

const isTxtFileName = (name) => {
  const n = String(name || '').trim();
  if (!n) {
    return true;
  }
  return TXT_EXT_RE.test(n);
};

const normalizeChosenFile = (file) => {
  if (!file || !file.path) {
    return null;
  }
  const name = String(file.name || '').trim() || 'import.txt';
  if (!isTxtFileName(name)) {
    return { error: '请选择 .txt 文本文件（文件名需以 .txt 结尾）' };
  }
  const size = Number(file.size || 0);
  return {
    path: file.path,
    name,
    size,
    guessTitle: name.replace(TXT_EXT_RE, '').trim(),
    sizeUnknown: size <= 0
  };
};

const parseChooseFail = (err) => {
  const msg = (err && err.errMsg) || '';
  if ((err && Number(err.errno) === 112) || /api scope is not declared in the privacy agreement/i.test(msg)) {
    return {
      code: 'privacy_scope_missing',
      message: '小程序后台隐私保护指引未声明“选中的文件”，暂不能从聊天记录选择 TXT'
    };
  }
  if (/cancel/i.test(msg)) {
    return { code: 'cancel', message: '已取消' };
  }
  if (/privacy|authorize|auth deny|need.*authorization/i.test(msg)) {
    return { code: 'privacy', message: '需先同意隐私指引后再选文件' };
  }
  return { code: 'fail', message: msg || '选择文件失败' };
};

const shouldRetryWithoutExtension = (err) => {
  const msg = ((err && err.errMsg) || '').toLowerCase();
  return /extension|filter|invalid param|parameter/i.test(msg);
};

/**
 * 在用户点击事件内同步调起选文件（success/fail/complete 回调）
 * @param {object} handlers
 * @param {object} [options]
 * @param {boolean} [options.preferTxtExtension=true] 优先只展示会话内 txt（无则空列表）
 */
const openTxtFromChatPicker = (handlers = {}, options = {}) => {
  const { onSuccess, onFail, onComplete } = handlers;
  const preferTxtExtension = options.preferTxtExtension !== false;

  const done = () => {
    if (typeof onComplete === 'function') {
      onComplete();
    }
  };

  if (typeof wx.chooseMessageFile !== 'function') {
    console.log('[txt-import]', 'chooseMessageFile unsupported');
    if (typeof onFail === 'function') {
      onFail({ code: 'unsupported', message: '当前微信版本不支持从聊天选文件' });
    }
    done();
    return;
  }

  const invoke = (withExtension) => {
    console.log('[txt-import]', 'chooseMessageFile call', {
      withExtension,
      preferTxtExtension
    });
    const params = {
      count: 1,
      type: 'file',
      success(res) {
        console.log('[txt-import]', 'chooseMessageFile success', res);
        const list = (res && res.tempFiles) || [];
        if (!list.length) {
          if (typeof onFail === 'function') {
            onFail({
              code: 'empty',
              message:
                '该聊天中没有可选的 TXT。请先把 .txt 发到「文件传输助手」或该联系人，再重新选择。'
            });
          }
          done();
          return;
        }
        const normalized = normalizeChosenFile(list[0]);
        if (!normalized) {
          if (typeof onFail === 'function') {
            onFail({ code: 'empty', message: '未选择有效文件' });
          }
          done();
          return;
        }
        if (normalized.error) {
          if (typeof onFail === 'function') {
            onFail({ code: 'invalid', message: normalized.error });
          }
          done();
          return;
        }
        if (typeof onSuccess === 'function') {
          onSuccess(normalized);
        }
        done();
      },
      fail(err) {
        console.log('[txt-import]', 'chooseMessageFile fail', err);
        if (withExtension && preferTxtExtension && shouldRetryWithoutExtension(err)) {
          invoke(false);
          return;
        }
        if (typeof onFail === 'function') {
          onFail(parseChooseFail(err));
        }
        done();
      }
    };
    if (withExtension && preferTxtExtension) {
      params.extension = ['txt'];
    }
    wx.chooseMessageFile(params);
  };

  invoke(preferTxtExtension);
};

const CHOOSE_TXT_HELP_CONTENT =
  '点击后将打开微信界面：\n' +
  '1. 先选择含有文件的会话或「文件传输助手」\n' +
  '2. 再查看该会话里已发送的 TXT；没有 .txt 时会显示空列表\n\n' +
  '请先把 TXT 文件发到聊天后再导入。小程序无法打开手机文件管理器。';

const showChooseTxtHelpModal = (pageCtx, options = {}) => {
  wx.showModal({
    title: options.title || '如何从聊天记录导入 TXT',
    content: options.content || CHOOSE_TXT_HELP_CONTENT,
    confirmText: options.confirmText || '用链接导入',
    cancelText: '知道了',
    success: (res) => {
      if (res.confirm && pageCtx && typeof pageCtx.onOpenUrlPopup === 'function') {
        if (typeof pageCtx.onCloseTxtPopup === 'function') {
          pageCtx.onCloseTxtPopup();
        }
        pageCtx.onOpenUrlPopup();
      }
    }
  });
};

const openPrivacyContract = () => {
  if (typeof wx.openPrivacyContract === 'function') {
    wx.openPrivacyContract({
      fail: () => {
        wx.showToast({ title: '暂时无法打开隐私指引', icon: 'none' });
      }
    });
    return;
  }
  wx.showToast({ title: '请在设置中查看隐私保护指引', icon: 'none' });
};

module.exports = {
  openTxtFromChatPicker,
  showChooseTxtHelpModal,
  openPrivacyContract,
  isTxtFileName,
  CHOOSE_TXT_HELP_CONTENT
};

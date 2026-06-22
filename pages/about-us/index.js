const { LEGAL_META, ABOUT_SECTIONS } = require("../../utils/legal-content");
const { copyToClipboard } = require("../../utils/clipboard");
const { openReportPage } = require("../../utils/report-nav");

Page({
  data: {
    meta: LEGAL_META,
    sections: ABOUT_SECTIONS,
  },

  onCopyEmail() {
    copyToClipboard(this.data.meta.contactEmail, { toastTitle: "邮箱已复制" });
  },

  onTapReport() {
    openReportPage({ targetType: "app", hint: "功能或服务投诉" });
  },
});

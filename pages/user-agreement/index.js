const { LEGAL_META, AGREEMENT_SECTIONS } = require("../../utils/legal-content");

Page({
  data: {
    meta: LEGAL_META,
    sections: AGREEMENT_SECTIONS,
    expandedIds: AGREEMENT_SECTIONS.map((item) => item.id),
  },

  onJumpSection(e) {
    const id = e.currentTarget.dataset.id || "";
    if (!id) {
      return;
    }
    this.onToggleSection(e);
    wx.pageScrollTo({
      selector: `#section-${id}`,
      duration: 250,
    });
  },

  onToggleSection(e) {
    const id = e.currentTarget.dataset.id || "";
    if (!id) {
      return;
    }
    const current = new Set(this.data.expandedIds || []);
    if (current.has(id)) {
      current.delete(id);
    } else {
      current.add(id);
    }
    this.setData({ expandedIds: Array.from(current) });
  },
});

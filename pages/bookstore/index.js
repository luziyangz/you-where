Page({
  data: {
    categories: ['推荐', '小说', '文学', '心理学', '历史', '传记'],
    activeCategory: 0,
    books: [
      {
        id: 1,
        title: '百年孤独',
        author: '加西亚·马尔克斯',
        cover: 'https://images.unsplash.com/photo-1544947950-fa07a98d237f?auto=format&fit=crop&w=200&q=80',
        desc: '魔幻现实主义代表作，展现了布恩迪亚家族七代人的传奇故事。'
      },
      {
        id: 2,
        title: '人类简史',
        author: '尤瓦尔·赫拉利',
        cover: 'https://images.unsplash.com/photo-1589829085413-56de8ae18c73?auto=format&fit=crop&w=200&q=80',
        desc: '从十万年前有生命迹象开始到21世纪资本、科技交织的人类发展史。'
      },
      {
        id: 3,
        title: '三体',
        author: '刘慈欣',
        cover: 'https://images.unsplash.com/photo-1614165936126-22485f58c4ee?auto=format&fit=crop&w=200&q=80',
        desc: '中国科幻文学的里程碑之作，讲述了地球人类文明和三体文明的信息交流、生死搏杀及两个文明在宇宙中的兴衰历程。'
      }
    ]
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({
        selected: 2
      });
    }
  },

  onCategoryTap(e) {
    const index = e.currentTarget.dataset.index;
    this.setData({
      activeCategory: index
    });
    // 这里可以添加请求不同分类书籍的逻辑
  },

  onBookTap(e) {
    const bookId = e.currentTarget.dataset.id;
    wx.showToast({
      title: '书籍详情开发中',
      icon: 'none'
    });
  }
});
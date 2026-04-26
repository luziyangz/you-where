# 错误记录

## 记录规则
- 同一问题累计出现 3 次及以上时必须记录。
- 如果问题尚未定位根因，也要先记录现象和影响。

## 当前记录

### 2026-04-26 `app.globalData` 状态漏同步重复问题
- 现象：
  - 不同页面分别自行写 `app.globalData`
  - 页面经常只同步 `user / pair / currentBook` 的一部分，导致全局状态互相覆盖或遗漏
  - 已先后在 `home / progress / book-detail / reader / partner` 链路上重复暴露
- 触发条件：
  - 页面从不同接口拿到不同形态的数据后，直接局部写全局状态
  - 典型场景是 `/pair/current` 返回了 `pair.current_book`，但页面只写了 `pair`
- 影响：
  - 页面间跳转后会出现“服务端已有在读书，但前端按无书处理”的错态
  - 依赖全局状态的按钮分流、Tab 状态和前置校验会出现错误判断
- 临时措施：
  - 建立 `app.js` 统一状态写入口
  - 将 `book-detail / reader / progress / partner` 改为优先通过统一入口同步
- 根因：
  - 全局状态模型没有被强约束，页面层长期存在散写
  - 不同接口返回结构不一致，例如 `currentBook` 有时顶层返回，有时嵌套在 `pair.current_book`
- 本轮修复：
  - `syncReadingContext` 增加对 `pair.current_book` 的自动回写与清空逻辑
  - `partner` 页改为通过统一入口回写 `user + pair`
- 后续动作：
  - 为前端状态链路补最小自动化校验脚本
  - 后续新增页面若写全局状态，必须复用统一入口，不允许再直接散写

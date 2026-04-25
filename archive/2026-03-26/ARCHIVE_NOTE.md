# 归档记录（2026-03-26）

## 本次归档对象
- `.tmp-you-where-rollback/`
- `backend/app.py`
- `backend/test_app.py`
- `backend/README.md`

## 归档原因
- 该目录属于历史回滚快照，会干扰当前主线检索与统一改造判断。
- 目录内内容不作为当前企业级主线实现输入。
- `backend/app.py` 为单体 v1 实现，已被 v2 原生接口替代。
- `backend/test_app.py` 与旧 v1 路由强绑定，不再适配统一主线。
- `backend/README.md` 描述旧 v1 启动与接口，已由根 `README.md` 和 `docs/` 文档替代。

## 恢复方法
- 如需恢复，可将 `archive/2026-03-26/.tmp-you-where-rollback/` 移回仓库根目录。
- 如需回滚单体实现，可将 `archive/2026-03-26/app.py` 移回 `backend/app.py`。
- 如需恢复旧测试/说明，可将对应文件移回 `backend/`。

## 后续计划
- 完成主线统一与验证后，再评估是否永久删除本归档目录。

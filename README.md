# TODO 小程序企业化主线说明

## 项目主线
- 后端唯一入口：`backend/app_main.py`
- API 主版本：`/api/v2`
- 数据库：MySQL（默认）

## 快速启动（后端）
1. 配置环境变量：`DB_BACKEND=mysql`、`MYSQL_HOST`、`MYSQL_PORT`、`MYSQL_USER`、`MYSQL_PASSWORD`、`MYSQL_DB`
2. 初始化表结构：`python backend/scripts/init_mysql_schema.py`
3. 启动服务：`backend/start.bat`

## 目录约定
- `backend/api/v2`：接口层
- `backend/service`：业务层
- `backend/repo`：数据访问层
- `backend/common`：公共基础设施
- `services`：小程序 API 调用聚合

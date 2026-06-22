# MySQL 集成测试

 覆盖 `common/models.py` 全部 **22** 张业务表。

## 常见失败：`root@localhost (using password: NO)`

原因：`backend/.env` 里配置了生产库 `MYSQL_USER=root` / `MYSQL_PORT=3306`，而集成测应连 **Docker 测试库**（`you_where_test` @ `127.0.0.1:3307`）。

`tests_mysql/conftest.py` 会在跑用例前 **强制覆盖** `MYSQL_*`，无需改 `.env`。若仍报 root 无密码，请确认：

1. 已拉最新代码（含 conftest 强制覆盖）
2. 只跑 `pytest tests_mysql/`，不要混跑其它目录后又复用旧进程
3. 先执行诊断：

```powershell
cd backend
python scripts/check_mysql_test_env.py
```

输出应显示 `you_where_test@127.0.0.1:3307/you_where_test`，而不是 `root@...:3306`。

## 启动测试库

```powershell
# 启动 Docker Desktop 后
docker compose -f docker-compose.test.yml up -d
python scripts/check_mysql_test_env.py
python -m pytest tests_mysql/ -v --tb=short
```

## 与云服务器的关系

| 环境 | 用途 |
|------|------|
| 云 API + `you_where` | 生产 |
| 本机 3307 `you_where_test` | 集成测（会清空业务表） |

勿对生产库跑 `tests_mysql/`。

## SQLite 回归（不依赖 Docker）

```powershell
python -m pytest test_v2_store_reading.py test_v2_profile.py -q
```
  



  

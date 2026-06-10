# 2026-05-31 迁移体系与任务运行态实施记录

## 本轮目标

1. 初始化数据库迁移体系
2. 为任务流接入 Redis 运行态状态管理

## 本轮完成内容

1. 新增 Alembic 配置：
   - `backend/alembic.ini`
   - `backend/migrations/env.py`
   - `backend/migrations/versions/20260531_0001_initial_schema.py`
2. 新增模型聚合导入文件，供迁移体系统一加载。
3. 调整应用启动逻辑：
   - SQLite 开发模式下仍允许 `create_all()`
   - PostgreSQL / 容器模式应走 Alembic
4. 新增 Redis 配置项 `REDIS_URL`
5. 新增 Redis 客户端封装
6. 新增任务运行态服务：
   - 写入任务运行态
   - 读取任务运行态
7. 新增任务运行态 API：
   - `GET /api/v1/projects/{project_id}/tasks/{task_id}/runtime`
   - `POST /api/v1/projects/{project_id}/tasks/{task_id}/runtime`
8. 创建任务时自动写入初始运行态到 Redis

## 当前意义

这一步把项目从“只有持久化任务记录”推进到了“同时具备数据库历史记录 + Redis 运行时状态”的结构，后续实现 ReAct 任务执行器时不需要推翻现有任务模型。

## 当前限制

1. Redis 当前只用于任务运行态，不负责队列调度。
2. Alembic 已初始化，但尚未演示完整的自动生成迁移工作流。
3. 生产模式下还需增加启动前自动执行迁移或单独迁移步骤。

## 下一步建议

1. 增加任务步骤状态写入 Redis 的细粒度接口
2. 接入 Redis Stream / 队列 或 Celery/RQ 类执行器
3. 为 AI 任务流增加 `queued/running/succeeded/failed` 状态机
4. 把 ReAct 的 step 执行记录同步到 `task_steps + Redis runtime`

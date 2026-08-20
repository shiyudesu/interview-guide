# Django/Flask/FastAPI 面试重点（框架、数据访问与运行时）

## 框架定位与对比
- Django：全栈框架（ORM/Admin/Auth/Template 内置），"batteries included" 哲学，适合快速交付。
- Flask：微框架（路由+模板引擎核心），扩展生态灵活，适合定制化与微服务。
- FastAPI：ASGI、类型驱动校验、依赖注入和 OpenAPI 集成，适合 API 与异步 I/O 服务。
- 选型需要比较团队经验、生态、管理后台、异步依赖、交付速度和长期维护，而不是只比较吞吐跑分。
- FastAPI：异步原生、Pydantic 类型校验、自动生成 OpenAPI 文档，适合新项目。

## 请求生命周期
- Django：URLconf 路由→Middleware 链→View 函数/类→Template/JSON 响应→Middleware 链（逆序返回）。
- Flask：Werkzeug WSGI 路由→before_request 钩子→View 函数→after_request 钩子→响应。
- FastAPI/Starlette：ASGI Server→Middleware→路由与依赖解析→参数校验→Endpoint→响应序列化。
- 中间件/钩子：认证注入、请求日志、异常捕获、数据库事务管理。
- 请求上下文：Django 显式 request、Flask context local、异步代码中的 `contextvars`，注意后台任务的上下文生命周期。

## ORM 与查询优化
- Django ORM：QuerySet 惰性求值、`select_related`（JOIN，一对一/外键）vs `prefetch_related`（二次查询，多对多）。
- N+1 问题：循环中触发懒加载，解法为 `select_related`/`prefetch_related` 批量预加载。
- Flask-SQLAlchemy：Session 管理、eager loading（`joinedload`/`subqueryload`）、批量操作。
- FastAPI 常结合 SQLAlchemy；Session 生命周期、事务边界和同步/异步驱动必须与执行模型一致。
- 查询优化：`only()`/`defer()` 延迟加载字段、`bulk_create` 批量插入、`iterator()` 流式读取大结果集。

## 认证、权限与安全
- Django Auth：User 模型、`authenticate`/`login`/`logout` 流程、Permission/Group 权限体系。
- Token 认证：JWT（djangorestframework-simplejwt）/ DRF TokenAuthentication。
- 安全防护：CSRF Token（Django 内置）、XSS 转义（模板自动转义）、SQL 注入（ORM 参数化）、CORS 配置。
- 密码存储：Django 使用 PBKDF2 + salt，可配置 bcrypt/argon2。

## 缓存与性能
- Django 缓存框架：`@cache_page` 装饰器、缓存后端（Redis/Memcached/本地内存）。
- Flask 缓存：Flask-Caching 扩展，`@cached` 装饰器、Jinja2 片段缓存。
- 数据库查询缓存：`QuerySet.cache()`、手动缓存策略、缓存失效与一致性。
- 静态文件：Django Collectstatic + CDN、Flask 静态文件服务（生产环境用 Nginx）。
- 异步 Endpoint 只有在依赖链真正非阻塞时才有收益；同步阻塞代码应放入受限线程池。
- 连接池、Worker 数量和任务并发必须服从数据库及外部服务容量，不能仅靠增加进程扩容。

## 部署与运维
- WSGI（同步）：Gunicorn/uWSGI，多 Worker 进程 + preload + 优雅重启。
- ASGI（异步）：Uvicorn/Daphne，支持 WebSocket 和 async view。
- 容器化：Docker 多阶段构建、环境变量管理、健康检查端点。
- 监控：Sentry 异常捕获、Prometheus 指标暴露、日志结构化输出（JSON logging）。
- 优雅停止需要停止接流量、等待在途请求、关闭后台任务和释放连接池。

## 面试追问模板
- Django ORM 的 N+1 问题你怎么发现的？怎么解决的？
- Flask 的上下文是怎么实现的？多线程下安全吗？
- 你的项目用的 WSGI 还是 ASGI？为什么？遇到什么瓶颈？
- 线上一个接口突然变慢，从框架层面怎么排查？
- FastAPI 中在 async 路由里调用同步 ORM，会对事件循环和容量产生什么影响？

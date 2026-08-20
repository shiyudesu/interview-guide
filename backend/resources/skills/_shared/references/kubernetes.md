# 容器与 Kubernetes 面试重点

## 容器基础
- 容器依赖 namespace 隔离视图、cgroup 限制资源和分层文件系统，不是轻量虚拟机。
- 镜像层应可复现、最小化并使用非 root 用户；运行数据进入 Volume 或外部存储。
- CPU limit 可能触发 throttling，内存超限会被 OOM Kill；应用并发需根据 requests/limits 调整。
- 容器网络、端口暴露、DNS 和宿主机路由要分层排查，不能把容器可达等同于服务可达。

## 工作负载与调度
- Deployment 管理无状态副本和滚动更新，StatefulSet 提供稳定身份与存储语义，DaemonSet 面向每节点任务。
- requests 参与调度，limits 约束运行；亲和性、污点容忍、拓扑分布和 PDB 共同影响可用性。
- Job/CronJob 要处理并发策略、失败重试、超时、历史清理和任务幂等。
- HPA 扩容受指标窗口、启动时间和下游容量限制，扩 Pod 不能解决数据库瓶颈。

## 网络、服务与存储
- Service 提供稳定访问入口，Ingress/Gateway 负责外部路由；NetworkPolicy 控制允许的流量边界。
- readiness、liveness 和 startup probe 目的不同，错误配置可能造成流量打入未就绪实例或重启风暴。
- PV/PVC/StorageClass 分离容量声明和实现，状态应用还要考虑拓扑、备份、恢复和故障切换。
- DNS、Endpoint、kube-proxy/CNI 和应用监听地址是服务不通时的不同排查层次。

## 配置、安全与升级
- ConfigMap 和 Secret 的更新语义不同，敏感信息仍需加密、访问控制、轮换和审计。
- ServiceAccount、RBAC、Pod Security、镜像签名和 NetworkPolicy 构成多层防线。
- 滚动升级需协调 maxSurge、maxUnavailable、连接排空、终止宽限期和数据库兼容。
- 控制面和节点升级应验证版本跨度、弃用 API、CNI/CSI 兼容和回滚路径。

## 场景与追问
- Pod Running 但请求不通，应按什么顺序检查？
- 应用频繁 OOMKilled，如何区分泄漏、峰值和限制配置不合理？
- 滚动发布期间为什么仍可能出现 502？如何验证连接排空？
- 节点故障时，有状态服务如何满足 RTO 和 RPO？

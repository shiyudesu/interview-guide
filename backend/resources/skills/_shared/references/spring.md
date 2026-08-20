# Spring 面试重点

## IoC 与 Bean
- IoC 解决什么问题：解耦对象创建与依赖管理。
- `@Component` vs `@Bean`：声明方式、代理对象、第三方库集成。
- `@Autowired` vs `@Resource`：按类型 vs 按名称，优先级规则。
- 构造器注入 vs Setter 注入 vs 字段注入：不可变性、循环依赖、测试友好度。
- Bean 作用域（singleton/prototype/request/session），线程安全分析。
- Bean 生命周期：实例化→属性注入→Aware→初始化→销毁，各阶段扩展点。

## AOP
- 核心概念：切面/切点/通知/连接点。
- Spring AOP vs AspectJ：动态代理 vs 编译期织入，性能与功能差异。
- 通知类型：@Before/@After/@AfterReturning/@AfterThrowing/@Around。
- 同类内部调用 AOP 失效原因与解决方案（AopContext/exposeProxy）。

## Spring MVC
- DispatcherServlet 工作流程：HandlerMapping→HandlerAdapter→ViewResolver。
- 统一异常处理：@ControllerAdvice + @ExceptionHandler。
- 拦截器 vs 过滤器：执行时机与适用场景。

## 事务
- 声明式事务：@Transactional 属性（propagation/isolation/rollbackFor）。
- 七种传播行为：REQUIRED/REQUIRES_NEW/NESTED 等使用场景。
- 事务失效场景：同类内部调用、非 public 方法、异常被吞、异步调用。

## 循环依赖
- 三级缓存解决 setter 注入循环依赖：singletonObjects/earlySingletonObjects/singletonFactories。
- 构造器注入循环依赖无法自动解决，需 @Lazy。
- SpringBoot 2.6+ 默认禁止循环依赖。

## Spring Boot
- 自动配置原理：@SpringBootApplication→@EnableAutoConfiguration→spring.factories/Imports。
- 条件装配：@ConditionalOnClass/@ConditionalOnMissingBean 等。
- 配置文件加载优先级：properties > yaml > 环境变量 > 命令行参数。
- Java 21+ 可启用虚拟线程执行任务，但数据库连接数、下游容量和任务取消仍需显式治理。

## Web、异步与安全
- Spring MVC 基于 Servlet 请求模型，WebFlux 基于响应式流；选型取决于依赖是否非阻塞和团队复杂度承受能力。
- `@Async`、调度任务和消息监听器都需要独立执行器、异常处理、上下文传播和优雅停止。
- Spring Security 过滤器链负责认证与授权；方法级授权不能替代资源归属校验。
- OAuth2 Resource Server 需校验 issuer、audience、签名算法和时钟偏差，不能只解析 JWT 内容。

## 生产工程
- Actuator 与 Micrometer Observation 支持健康、指标和追踪；敏感端点必须限制暴露和访问权限。
- 配置刷新、灰度发布和数据库迁移要保持版本兼容，避免新旧实例并存时协议不一致。
- 启动慢、Bean 创建失败、线程池耗尽和连接池耗尽应分别建立可观测指标和排查路径。

## 面试追问模板
- @Transactional 标在 private 方法上会生效吗？为什么？
- 如何自定义一个 Spring Boot Starter？
- Spring AOP 在你的项目中用来做了什么？遇到过什么坑？
- MVC、WebFlux 和虚拟线程分别适合什么负载？如何用压测验证选择？

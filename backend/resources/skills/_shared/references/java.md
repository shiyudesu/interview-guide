# Java 面试重点（基础 + 集合 + 并发 + JVM）

## 基础概念
- JVM/JDK/JRE 区别，字节码与"编译+解释"执行模型，AOT vs JIT。
- 8 种基本类型与包装类，自动装箱/拆箱与 Integer Cache。
- `==` vs `equals()`，`hashCode()` 与 `equals()` 一致性约束。
- 方法重载 vs 重写，静态分派与动态分派。
- 接口 vs 抽象类，Java 8+ default 方法的影响。
- 深拷贝 vs 浅拷贝，序列化方案。
- 泛型擦除、桥接方法与运行时类型边界；反射、MethodHandle 和动态代理的适用场景。
- record、sealed class、模式匹配等现代语法解决的问题，以及升级时的兼容性考虑。

## String
- 不可变性原理（final byte[]），安全与性能影响。
- 字符串常量池：`intern()`、编译期优化、`new String("abc")` 创建对象数。
- `String` vs `StringBuilder` vs `StringBuffer`。

## 集合框架
- List：ArrayList（动态数组、扩容 1.5 倍）vs LinkedList（双向链表），RandomAccess 标记。
- Map：HashMap 底层（数组+链表+红黑树）、负载因子与扩容、线程不安全场景。
- HashMap 长度为何是 2 的幂次方，多线程死循环问题。
- ConcurrentHashMap：JDK 7 分段锁 vs JDK 8 CAS+synchronized，key/value 不为 null。
- Set：HashSet（基于 HashMap）、LinkedHashSet、TreeSet（红黑树）。
- Queue：BlockingQueue 接口，ArrayBlockingQueue vs LinkedBlockingQueue。
- fail-fast vs fail-safe 机制。

## 并发
- 线程生命周期与状态转换，上下文切换成本。
- 死锁：条件、检测（jstack/arthuras）、预防策略。
- JMM：可见性、有序性、happens-before；volatile 保证可见性+禁止重排序但不保证原子性。
- synchronized 底层原理（Monitor）、锁升级（偏向→轻量→重量）、偏向锁废弃。
- ReentrantLock vs synchronized：可中断、公平锁、Condition、超时获取。
- CAS 与 ABA 问题，Atomic 原理。
- 线程池：核心参数（corePoolSize/maxPoolSize/queue/handler）、拒绝策略、动态配置。
- AQS 原理（state + CLH 队列），Semaphore/CountDownLatch/CyclicBarrier。
- ThreadLocal：原理、内存泄漏与弱引用、跨线程传递（TransmittableThreadLocal）。
- CompletableFuture：编排、异常处理、自定义线程池。
- 虚拟线程（Java 21+）：适合大量阻塞式 I/O 任务，不用于让 CPU 密集计算自动并行；关注 pinning、ThreadLocal 和限流。

## JVM
- 运行时数据区：堆/栈/方法区/元空间/程序计数器/直接内存。
- 对象创建流程、内存布局、访问定位（句柄 vs 直接指针）。
- GC 判断：引用计数 vs 可达性分析；四种引用（强/软/弱/虚）。
- GC 算法：标记-清除、复制、标记-整理、分代收集。
- 垃圾收集器：Serial→Parallel→CMS→G1→ZGC，各自适用场景。
- G1 回收流程（Young GC / Mixed GC），ZGC 着色指针与读屏障。
- 双亲委派模型与打破方式（SPI、OSGi、线程上下文类加载器）。
- OOM 排查：Heap Dump、jmap/jstat/Arthas、JFR、GC 日志与 Native Memory Tracking。

## I/O 与运行时工程
- BIO、NIO 与异步 I/O 的线程模型差异；Selector、ByteBuffer、零拷贝和背压的适用边界。
- Java 序列化的安全与演进风险；服务间契约优先使用显式 Schema 并处理前后兼容。
- 线程池、连接池和队列必须有容量、超时、拒绝、监控与关闭策略，不能只使用默认参数。
- CPU 飙升、频繁 Full GC、直接内存耗尽和类加载泄漏需要采用不同证据链排查。

## 面试追问模板
- 这个机制底层是怎么实现的？有什么性能代价？
- 多线程环境下会有什么问题？如何保证线程安全？
- 框架（Spring/MyBatis）中哪里用到了这个机制？
- 线上遇到 OOM/GC 频繁怎么排查？参数怎么调？
- 引入虚拟线程后，数据库连接池和下游限流为什么仍然必要？

# Go 并发面试重点

## Goroutine 与调度
- goroutine 是由运行时调度的轻量执行单元；并发不等于并行，吞吐仍受 CPU、锁和下游容量限制。
- G/M/P 调度模型需要理解本地队列、全局队列、work stealing、系统调用和抢占的基本作用。
- goroutine 创建便宜但不是免费资源，无界启动会造成内存、调度和下游压力。

## Channel 与所有权
- 无缓冲 channel 同步交接，缓冲 channel 提供有限解耦；容量选择应基于背压策略而不是隐藏延迟。
- 发送方通常负责关闭 channel；向已关闭 channel 发送会 panic，从关闭 channel 接收会得到剩余值和零值。
- `select` 处理多个通信事件；default 会变成非阻塞轮询，使用不当可能造成空转。
- nil channel 永久阻塞，可用于动态关闭 select 分支，也可能因初始化遗漏造成泄漏。

## 取消、超时与泄漏
- `context.Context` 传递截止时间、取消信号和请求范围值，不应存入结构体或用于可选参数容器。
- 每个启动的 goroutine 都要回答由谁停止；发送无人接收、等待永不完成和 ticker 未停止是常见泄漏源。
- fan-out/fan-in、worker pool 和 pipeline 必须处理上游取消、下游退出、错误聚合和 channel 关闭顺序。
- `errgroup` 类模式适合关联任务失败后统一取消，仍要避免阻塞操作忽略 context。

## 共享内存与同步
- 数据竞争是正确性问题，使用 race detector 验证；不能因为测试暂时通过就认为线程安全。
- Mutex 保护复合不变量，RWMutex 只有在读多、临界区合适且争用明显时才可能获益。
- atomic 适合简单状态和计数，复杂业务状态应通过锁或所有权转移保持不变量。
- WaitGroup 只等待任务结束，不传播错误；Add、Done 和 Wait 的时序必须清楚。

## 场景与追问
- 如何设计一个有并发上限、可取消且不会泄漏 goroutine 的批处理器？
- channel 已有缓冲，为什么服务仍需要入口限流？
- 请求超时返回后，后台 goroutine 继续写数据库会产生什么问题？
- 如何用 goroutine dump、阻塞分析和指标定位并发泄漏？

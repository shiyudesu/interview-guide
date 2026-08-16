package interview.guide.common.aspect;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.redisson.Redisson;
import org.redisson.api.RScript;
import org.redisson.api.RedissonClient;
import org.redisson.client.codec.StringCodec;
import org.redisson.config.Config;
import org.springframework.core.io.ClassPathResource;
import org.testcontainers.containers.GenericContainer;
import org.testcontainers.junit.jupiter.Container;
import org.testcontainers.junit.jupiter.Testcontainers;
import org.testcontainers.utility.DockerImageName;

import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.UUID;

import static org.junit.jupiter.api.Assertions.assertEquals;

/**
 * 限流功能集成测试
 *
 * <p>通过 Testcontainers 启动独立 Redis，避免依赖本地固定端口和残留数据。
 */
@DisplayName("限流功能集成测试")
@Testcontainers(disabledWithoutDocker = true)
class RateLimitIntegrationTest {

    private static final int REDIS_PORT = 6379;

    @Container
    private static final GenericContainer<?> REDIS = new GenericContainer<>(
            DockerImageName.parse("redis:7-alpine"))
            .withExposedPorts(REDIS_PORT);

    private RedissonClient redissonClient;
    private String luaScript;
    private String luaScriptSha;

    @BeforeEach
    void setUp() throws Exception {
        ClassPathResource resource = new ClassPathResource("scripts/rate_limit_single.lua");
        luaScript = new String(resource.getContentAsByteArray(), StandardCharsets.UTF_8);

        Config config = new Config();
        config.useSingleServer()
                .setAddress("redis://" + REDIS.getHost() + ":" + REDIS.getMappedPort(REDIS_PORT))
                .setConnectionPoolSize(5)
                .setConnectionMinimumIdleSize(1);

        redissonClient = Redisson.create(config);
        redissonClient.getKeys().deleteByPattern("ratelimit:test*");

        // 预加载脚本
        luaScriptSha = redissonClient.getScript(StringCodec.INSTANCE).scriptLoad(luaScript);
    }

    @Test
    @DisplayName("验证限流：令牌充足时允许，耗尽时拒绝")
    void testRateLimit() {
        String key = "ratelimit:test:basic";
        long maxCount = 2;

        // 初始化2个令牌
        redissonClient.getBucket(key + ":value", StringCodec.INSTANCE).set(String.valueOf(maxCount));

        // 前两次请求应成功
        assertEquals(1L, executeLuaScript(key, maxCount));
        assertEquals(1L, executeLuaScript(key, maxCount));

        // 第三次请求应被拒绝
        assertEquals(-1L, executeLuaScript(key, maxCount));
    }

    @Test
    @DisplayName("验证多规则限流：任一规则不足时不扣减其他规则")
    void testMultiRule() {
        String globalKey = "ratelimit:test:multi:global";
        String ipKey = "ratelimit:test:multi:ip";
        long globalMax = 10;
        long ipMax = 1;

        // 初始化：全局10个令牌，IP维度1个令牌
        redissonClient.getBucket(globalKey + ":value", StringCodec.INSTANCE).set("10");
        redissonClient.getBucket(ipKey + ":value", StringCodec.INSTANCE).set("1");

        // 第一次请求：两条规则都通过
        assertEquals(1L, executeLuaScript(List.of(globalKey, ipKey), List.of(globalMax, ipMax)));

        // 第二次请求：IP规则拒绝，全局规则不能被误扣
        assertEquals(-2L, executeLuaScript(List.of(globalKey, ipKey), List.of(globalMax, ipMax)));
        assertEquals("9", redissonClient.getBucket(globalKey + ":value", StringCodec.INSTANCE).get());
        assertEquals("0", redissonClient.getBucket(ipKey + ":value", StringCodec.INSTANCE).get());
    }

    @Test
    @DisplayName("验证原子回收：后续规则拒绝时不删除前一规则的过期记录")
    void testExpiredPermitsRemainWhenLaterRuleRejects() {
        String globalKey = "ratelimit:test:expired:global";
        String ipKey = "ratelimit:test:expired:ip";

        redissonClient.getBucket(globalKey + ":value", StringCodec.INSTANCE).set("0");
        redissonClient.getScoredSortedSet(globalKey + ":permits", StringCodec.INSTANCE)
                .add(System.currentTimeMillis() - 2_000, "expired-request:1");
        redissonClient.getBucket(ipKey + ":value", StringCodec.INSTANCE).set("0");

        assertEquals(-2L, executeLuaScript(List.of(globalKey, ipKey), List.of(1L, 1L)));
        assertEquals("0", redissonClient.getBucket(globalKey + ":value", StringCodec.INSTANCE).get());
        assertEquals(1, redissonClient.getScoredSortedSet(
                globalKey + ":permits", StringCodec.INSTANCE).size());

        redissonClient.getBucket(ipKey + ":value", StringCodec.INSTANCE).set("1");
        assertEquals(1L, executeLuaScript(List.of(globalKey, ipKey), List.of(1L, 1L)));
    }

    @Test
    @DisplayName("验证独立计数：不同维度拥有独立的令牌池")
    void testIndependentCountPerDimension() {
        String globalKey = "ratelimit:test:independent:global";
        String ipKey = "ratelimit:test:independent:ip";

        // 全局只允许2次，IP允许5次
        redissonClient.getBucket(globalKey + ":value", StringCodec.INSTANCE).set("2");
        redissonClient.getBucket(ipKey + ":value", StringCodec.INSTANCE).set("5");

        // 全局维度耗尽
        assertEquals(1L, executeLuaScript(globalKey, 2));
        assertEquals(1L, executeLuaScript(globalKey, 2));
        assertEquals(-1L, executeLuaScript(globalKey, 2));

        // IP维度仍有令牌（证明独立计数）
        assertEquals(1L, executeLuaScript(ipKey, 5));
    }

    private long executeLuaScript(String key, long maxCount) {
        return executeLuaScript(Collections.singletonList(key), Collections.singletonList(maxCount));
    }

    private long executeLuaScript(List<String> keys, List<Long> maxCounts) {
        RScript script = redissonClient.getScript(StringCodec.INSTANCE);

        List<Object> args = new ArrayList<>(3 + keys.size() * 3);
        args.add(String.valueOf(System.currentTimeMillis()));
        args.add(UUID.randomUUID().toString());
        args.add(String.valueOf(keys.size()));

        for (Long maxCount : maxCounts) {
            args.add(String.valueOf(1));
            args.add(String.valueOf(1000));
            args.add(String.valueOf(maxCount));
        }

        Object result = script.evalSha(
                RScript.Mode.READ_WRITE,
                luaScriptSha,
                RScript.ReturnType.VALUE,
                new ArrayList<>(keys),
                args.toArray()
        );

        if (result instanceof Number) {
            return ((Number) result).longValue();
        } else if (result instanceof String) {
            return Long.parseLong((String) result);
        }
        throw new AssertionError("Unexpected result type: " + result);
    }

    @AfterEach
    void tearDown() {
        if (redissonClient != null) {
            redissonClient.getKeys().deleteByPattern("ratelimit:test*");
            redissonClient.shutdown();
        }
    }
}

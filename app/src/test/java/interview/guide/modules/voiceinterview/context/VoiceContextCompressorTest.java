package interview.guide.modules.voiceinterview.context;

import interview.guide.common.ai.LlmProviderRegistry;
import interview.guide.modules.voiceinterview.config.VoiceInterviewProperties;
import interview.guide.modules.voiceinterview.model.VoiceInterviewMessageEntity;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Nested;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.ai.chat.client.ChatClient;
import org.springframework.core.io.DefaultResourceLoader;

import java.util.ArrayList;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.*;

/**
 * VoiceContextCompressor 单元测试。
 *
 * <p>覆盖：happy path（关闭/窗口/摘要触发）、边界（空输入、未达批次数）、
 * 兼容性（关闭时格式化与改前一致）、LLM 摘要失败降级。
 */
@ExtendWith(MockitoExtension.class)
@DisplayName("VoiceContextCompressor 测试")
class VoiceContextCompressorTest {

    @Mock
    private LlmProviderRegistry llmProviderRegistry;

    private VoiceInterviewProperties properties;
    private VoiceContextCompressor compressor;

    @BeforeEach
    void setUp() {
        properties = new VoiceInterviewProperties();
        properties.setContextCompression(new VoiceInterviewProperties.ContextCompressionConfig());
        compressor = new VoiceContextCompressor(
            llmProviderRegistry, properties, new DefaultResourceLoader());
    }

    private VoiceInterviewMessageEntity turn(int seq, String ai, String user) {
        return VoiceInterviewMessageEntity.builder()
                .sequenceNum(seq)
                .aiGeneratedText(ai)
                .userRecognizedText(user)
                .build();
    }

    private List<VoiceInterviewMessageEntity> turns(int n) {
        List<VoiceInterviewMessageEntity> list = new ArrayList<>();
        for (int i = 0; i < n; i++) {
            list.add(turn(i + 1, "面试官问题" + i, "候选人回答" + i));
        }
        return list;
    }

    @Nested
    @DisplayName("happy path")
    class HappyPath {

        @Test
        @DisplayName("关闭时返回全量，且与 formatRecent 等价（向后兼容）")
        void disabledReturnsAll() {
            properties.getContextCompression().setEnabled(false);
            List<VoiceInterviewMessageEntity> all = turns(30);

            VoiceContextCompressor.CompressedHistory r = compressor.compress(all, null, 0);

            assertNull(r.summary());
            assertFalse(r.changed());
            assertEquals(30, r.recent().size());
            verify(llmProviderRegistry, never()).getPlainChatClient();
        }

        @Test
        @DisplayName("WINDOW 模式：仅保留最近 windowSize 轮，不调用 LLM")
        void windowMode() {
            properties.getContextCompression().setEnabled(true);
            properties.getContextCompression().setMode(VoiceInterviewProperties.Mode.WINDOW);
            properties.getContextCompression().setWindowSize(20);
            List<VoiceInterviewMessageEntity> all = turns(30);

            VoiceContextCompressor.CompressedHistory r = compressor.compress(all, null, 0);

            assertNull(r.summary());
            assertFalse(r.changed());
            assertEquals(20, r.recent().size());
            verify(llmProviderRegistry, never()).getPlainChatClient();
        }

        @Test
        @DisplayName("SUMMARY 模式 + 达到批次数：触发增量摘要，changed=true")
        void summaryTriggered() {
            properties.getContextCompression().setEnabled(true);
            properties.getContextCompression().setMode(VoiceInterviewProperties.Mode.SUMMARY);
            properties.getContextCompression().setWindowSize(20);
            properties.getContextCompression().setSummaryBatchSize(10);
            // total=35 → earlyCount=15 >= 10 → 触发
            List<VoiceInterviewMessageEntity> all = turns(35);
            ChatClient chatClient = mockChatClient("合并后的摘要");

            VoiceContextCompressor.CompressedHistory r = compressor.compress(all, null, 0);

            assertEquals("合并后的摘要", r.summary());
            assertTrue(r.changed());
            assertEquals(15, r.coveredTurns());
            assertEquals(20, r.recent().size());
            verify(llmProviderRegistry, times(1)).getPlainChatClient();
        }

        @Test
        @DisplayName("SUMMARY 模式使用会话选择的 LLM 提供商")
        void summaryUsesSessionProvider() {
            properties.getContextCompression().setEnabled(true);
            properties.getContextCompression().setMode(VoiceInterviewProperties.Mode.SUMMARY);
            properties.getContextCompression().setWindowSize(20);
            properties.getContextCompression().setSummaryBatchSize(10);
            List<VoiceInterviewMessageEntity> all = turns(35);
            ChatClient chatClient = mockChatClient("glm", "合并后的摘要");

            VoiceContextCompressor.CompressedHistory result =
                compressor.compress(all, null, 0, "glm");

            assertEquals("合并后的摘要", result.summary());
            verify(llmProviderRegistry).getPlainChatClient("glm");
            verify(llmProviderRegistry, never()).getPlainChatClient();
        }
    }

    @Nested
    @DisplayName("边界情况")
    class Boundary {

        @Test
        @DisplayName("空输入：返回空，不报错")
        void emptyInput() {
            VoiceContextCompressor.CompressedHistory r = compressor.compress(List.of(), null, 0);
            assertNull(r.summary());
            assertFalse(r.changed());
            assertTrue(r.recent().isEmpty());
        }

        @Test
        @DisplayName("未达窗口大小：返回全量，不压缩")
        void belowWindow() {
            properties.getContextCompression().setEnabled(true);
            properties.getContextCompression().setMode(VoiceInterviewProperties.Mode.SUMMARY);
            properties.getContextCompression().setWindowSize(20);
            List<VoiceInterviewMessageEntity> all = turns(15);

            VoiceContextCompressor.CompressedHistory r = compressor.compress(all, null, 0);

            assertNull(r.summary());
            assertFalse(r.changed());
            assertEquals(15, r.recent().size());
        }

        @Test
        @DisplayName("SUMMARY 模式但未达批次数：不调用 LLM，保留所有尚未被摘要覆盖的轮次")
        void summaryNotTriggered() {
            properties.getContextCompression().setEnabled(true);
            properties.getContextCompression().setMode(VoiceInterviewProperties.Mode.SUMMARY);
            properties.getContextCompression().setWindowSize(20);
            properties.getContextCompression().setSummaryBatchSize(10);
            // total=25 → earlyCount=5 < 10 → 不触发
            List<VoiceInterviewMessageEntity> all = turns(25);

            VoiceContextCompressor.CompressedHistory r = compressor.compress(all, "已有摘要", 0);

            assertEquals("已有摘要", r.summary());
            assertFalse(r.changed());
            assertEquals(25, r.recent().size());
            assertEquals(1, r.recent().getFirst().getSequenceNum());
            verify(llmProviderRegistry, never()).getPlainChatClient();
        }

        @Test
        @DisplayName("SUMMARY 模式但 coveredTurns 大于 earlyCount（脏数据）：前置条件拦截，跳过摘要且不抛异常")
        void dirtyCoveredTurnsSkipsSafely() {
            properties.getContextCompression().setEnabled(true);
            properties.getContextCompression().setMode(VoiceInterviewProperties.Mode.SUMMARY);
            properties.getContextCompression().setWindowSize(20);
            properties.getContextCompression().setSummaryBatchSize(10);
            // total=35 → earlyCount=15，但传入脏数据 coveredTurns=20（> earlyCount）
            List<VoiceInterviewMessageEntity> all = turns(35);

            VoiceContextCompressor.CompressedHistory r = compressor.compress(all, "已有摘要", 20);

            // earlyCount > coveredTurns 前置条件拦住，subList 不会收到 from > to，不会抛 IllegalArgumentException
            assertEquals("已有摘要", r.summary());
            assertFalse(r.changed());
            assertEquals(20, r.recent().size());
            verify(llmProviderRegistry, never()).getPlainChatClient();
        }
    }

    @Nested
    @DisplayName("LLM 失败降级 & 兼容性")
    class FailureAndCompat {

        @Test
        @DisplayName("摘要生成抛异常：降级沿用已有摘要，并保留所有未覆盖轮次")
        void summaryFailureFallback() {
            properties.getContextCompression().setEnabled(true);
            properties.getContextCompression().setMode(VoiceInterviewProperties.Mode.SUMMARY);
            properties.getContextCompression().setWindowSize(20);
            properties.getContextCompression().setSummaryBatchSize(10);
            List<VoiceInterviewMessageEntity> all = turns(35);
            ChatClient chatClient = mock(ChatClient.class);
            ChatClient.ChatClientRequestSpec spec = mock(ChatClient.ChatClientRequestSpec.class);
            ChatClient.CallResponseSpec callSpec = mock(ChatClient.CallResponseSpec.class);
            when(chatClient.prompt()).thenReturn(spec);
            when(spec.user(anyString())).thenReturn(spec);
            when(spec.call()).thenReturn(callSpec);
            when(callSpec.content()).thenThrow(new RuntimeException("llm down"));
            when(llmProviderRegistry.getPlainChatClient()).thenReturn(chatClient);

            VoiceContextCompressor.CompressedHistory r = compressor.compress(all, "已有摘要", 0);

            // 失败降级：summary 仍为已有摘要，且未标记 changed（避免无谓持久化）
            assertEquals("已有摘要", r.summary());
            assertFalse(r.changed());
            assertEquals(35, r.recent().size());
            assertEquals(1, r.recent().getFirst().getSequenceNum());
        }

        @Test
        @DisplayName("formatRecent 与原 getHistory 格式化一致：AI+用户成对、孤立 AI 暂挂起")
        void formatRecentMatchesLegacy() {
            List<VoiceInterviewMessageEntity> all = new ArrayList<>();
            all.add(turn(1, "你介绍一下项目", "做过订单系统"));
            all.add(turn(2, "用了什么数据库", null));      // 孤立 AI：挂起
            all.add(turn(3, null, "MySQL 和 Redis"));        // 用户回答，配对上一条 AI
            all.add(turn(4, "为什么选 Redis", "因为缓存热数据"));

            List<String> formatted = compressor.formatRecent(all);

            assertEquals(List.of(
                    "面试官：你介绍一下项目",
                    "候选人：做过订单系统",
                    "面试官：用了什么数据库",
                    "候选人：MySQL 和 Redis",
                    "面试官：为什么选 Redis",
                    "候选人：因为缓存热数据"
            ), formatted);
        }
    }

    private ChatClient mockChatClient(String content) {
        ChatClient chatClient = mock(ChatClient.class);
        ChatClient.ChatClientRequestSpec spec = mock(ChatClient.ChatClientRequestSpec.class);
        ChatClient.CallResponseSpec callSpec = mock(ChatClient.CallResponseSpec.class);
        when(chatClient.prompt()).thenReturn(spec);
        when(spec.user(anyString())).thenReturn(spec);
        when(spec.call()).thenReturn(callSpec);
        when(callSpec.content()).thenReturn(content);
        when(llmProviderRegistry.getPlainChatClient()).thenReturn(chatClient);
        return chatClient;
    }

    private ChatClient mockChatClient(String provider, String content) {
        ChatClient chatClient = mock(ChatClient.class);
        ChatClient.ChatClientRequestSpec spec = mock(ChatClient.ChatClientRequestSpec.class);
        ChatClient.CallResponseSpec callSpec = mock(ChatClient.CallResponseSpec.class);
        when(chatClient.prompt()).thenReturn(spec);
        when(spec.user(anyString())).thenReturn(spec);
        when(spec.call()).thenReturn(callSpec);
        when(callSpec.content()).thenReturn(content);
        when(llmProviderRegistry.getPlainChatClient(provider)).thenReturn(chatClient);
        return chatClient;
    }
}

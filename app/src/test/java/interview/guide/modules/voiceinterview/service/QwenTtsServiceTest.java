package interview.guide.modules.voiceinterview.service;

import com.alibaba.dashscope.audio.qwen_tts_realtime.QwenTtsRealtimeParam;
import interview.guide.modules.voiceinterview.config.VoiceInterviewProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;

import java.time.Duration;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("QwenTtsService Unit Tests")
class QwenTtsServiceTest {

    private QwenTtsService ttsService;

    @BeforeEach
    void setUp() {
        VoiceInterviewProperties properties = new VoiceInterviewProperties();
        VoiceInterviewProperties.QwenTtsConfig tts = properties.getQwen().getTts();
        tts.setModel("qwen3-tts-flash-realtime");
        tts.setApiKey("test-api-key");
        tts.setVoice("Cherry");
        tts.setFormat("pcm");
        tts.setSampleRate(16000);
        tts.setMode("server_commit");
        tts.setLanguageType("Chinese");
        tts.setSpeechRate(1.0f);
        tts.setVolume(60);

        ttsService = new QwenTtsService(properties);
    }

    @Test
    @DisplayName("Should initialize service successfully")
    void testInit() {
        assertDoesNotThrow(() -> ttsService.init());
    }

    @Test
    @DisplayName("Should return empty array for empty text")
    void testSynthesizeEmptyText() {
        ttsService.init();

        byte[] result = ttsService.synthesize("");

        assertNotNull(result);
        assertEquals(0, result.length);
    }

    @Test
    @DisplayName("Should return empty array for null text")
    void testSynthesizeNullText() {
        ttsService.init();

        byte[] result = ttsService.synthesize(null);

        assertNotNull(result);
        assertEquals(0, result.length);
    }

    @Test
    @DisplayName("Should return empty array for whitespace text")
    void testSynthesizeWhitespaceText() {
        ttsService.init();

        byte[] result = ttsService.synthesize("   ");

        assertNotNull(result);
        assertEquals(0, result.length);
    }

    @Test
    @DisplayName("Should cleanup resources on destroy")
    void testDestroy() {
        ttsService.init();

        // Destroy should cleanup resources without error
        assertDoesNotThrow(() -> ttsService.destroy());
    }

    @Test
    @DisplayName("WebSocket 握手失败时应在超时内返回")
    void shouldReturnPromptlyWhenWebSocketHandshakeFails() {
        String originalUrl = QwenTtsRealtimeParam.baseWebsocketApiUrl;
        try {
            QwenTtsRealtimeParam.baseWebsocketApiUrl = "ws://127.0.0.1:1";
            VoiceInterviewProperties properties = new VoiceInterviewProperties();
            VoiceInterviewProperties.QwenTtsConfig tts = properties.getQwen().getTts();
            tts.setModel("qwen3-tts-flash-realtime");
            tts.setApiKey("test-api-key");
            properties.setTtsConnectTimeoutSeconds(1);
            ttsService = new QwenTtsService(properties);

            assertTimeoutPreemptively(
                Duration.ofSeconds(2),
                () -> assertEquals(0, ttsService.synthesize("握手失败测试").length)
            );
        } finally {
            QwenTtsRealtimeParam.baseWebsocketApiUrl = originalUrl;
        }
    }

    @Test
    @DisplayName("reload 应更新所有 TTS 配置字段")
    void testReloadUpdatesAllFields() throws Exception {
        VoiceInterviewProperties newProps = new VoiceInterviewProperties();
        VoiceInterviewProperties.QwenTtsConfig newTts = newProps.getQwen().getTts();
        newTts.setModel("new-tts-model");
        newTts.setApiKey("new-api-key");
        newTts.setVoice("Serena");
        newTts.setFormat("mp3");
        newTts.setSampleRate(48000);
        newTts.setMode("user_commit");
        newTts.setLanguageType("English");
        newTts.setSpeechRate(1.5f);
        newTts.setVolume(80);

        ttsService.reload(newProps);

        assertEquals("new-tts-model", field(ttsService, "model"));
        assertEquals("new-api-key", field(ttsService, "apiKey"));
        assertEquals("Serena", field(ttsService, "voice"));
        assertEquals("mp3", field(ttsService, "format"));
        assertEquals(48000, field(ttsService, "sampleRate"));
        assertEquals("user_commit", field(ttsService, "mode"));
        assertEquals("English", field(ttsService, "languageType"));
        assertEquals(1.5f, field(ttsService, "speechRate"));
        assertEquals(80, field(ttsService, "volume"));
    }

    private static Object field(Object obj, String name) throws Exception {
        java.lang.reflect.Field f = obj.getClass().getDeclaredField(name);
        f.setAccessible(true);
        return f.get(obj);
    }
}

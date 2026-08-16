package interview.guide.modules.voiceinterview.service;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import interview.guide.modules.voiceinterview.config.VoiceInterviewProperties;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.DisplayName;

import java.util.concurrent.atomic.AtomicReference;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

import static org.junit.jupiter.api.Assertions.*;

@DisplayName("QwenAsrService Unit Tests")
class QwenAsrServiceTest {

    private QwenAsrService asrService;

    @BeforeEach
    void setUp() {
        VoiceInterviewProperties properties = new VoiceInterviewProperties();
        VoiceInterviewProperties.AsrConfig asr = properties.getQwen().getAsr();
        asr.setUrl("wss://dashscope.aliyuncs.com/api-ws/v1/realtime");
        asr.setModel("qwen3-asr-flash-realtime");
        asr.setApiKey("test-api-key");
        asr.setLanguage("zh");
        asr.setFormat("pcm");
        asr.setSampleRate(16000);
        asr.setEnableTurnDetection(true);
        asr.setTurnDetectionType("server_vad");
        asr.setTurnDetectionThreshold(0.0f);
        asr.setTurnDetectionSilenceDurationMs(400);

        asrService = new QwenAsrService(properties);
    }

    @Test
    @DisplayName("Should initialize service successfully")
    void testInit() {
        assertDoesNotThrow(() -> asrService.init());
    }

    @Test
    @DisplayName("Should start transcription and create session")
    void testStartTranscription() throws Exception {
        asrService.init();

        String sessionId = "test-session-1";
        AtomicReference<String> resultRef = new AtomicReference<>();
        AtomicReference<Throwable> errorRef = new AtomicReference<>();

        asrService.startTranscription(
            sessionId,
            text -> resultRef.set(text),
            error -> errorRef.set(error)
        );

        // Verify session was created
        assertTrue(asrService.hasActiveSession(sessionId));

        // Cleanup
        asrService.stopTranscription(sessionId);
    }

    @Test
    @DisplayName("Should stop transcription and remove session")
    void testStopTranscription() throws Exception {
        asrService.init();

        String sessionId = "test-session-2";
        CountDownLatch latch = new CountDownLatch(1);

        asrService.startTranscription(
            sessionId,
            text -> {},
            error -> latch.countDown()
        );

        assertTrue(asrService.hasActiveSession(sessionId));

        asrService.stopTranscription(sessionId);

        assertFalse(asrService.hasActiveSession(sessionId));
    }

    @Test
    @DisplayName("Should handle multiple concurrent sessions")
    void testMultipleSessions() throws Exception {
        asrService.init();

        String session1 = "session-1";
        String session2 = "session-2";

        asrService.startTranscription(session1, text -> {}, error -> {});
        asrService.startTranscription(session2, text -> {}, error -> {});

        assertTrue(asrService.hasActiveSession(session1));
        assertTrue(asrService.hasActiveSession(session2));

        asrService.stopTranscription(session1);
        asrService.stopTranscription(session2);

        assertFalse(asrService.hasActiveSession(session1));
        assertFalse(asrService.hasActiveSession(session2));
    }

    @Test
    @DisplayName("Should throw exception when sending audio to non-existent session")
    void testSendAudioToNonExistentSession() {
        asrService.init();

        byte[] audioData = new byte[1024];

        assertThrows(IllegalStateException.class, () -> {
            asrService.sendAudio("non-existent-session", audioData);
        });
    }

    @Test
    @DisplayName("extractTranscriptPayload should concatenate text + stash for partial ASR events")
    void extractTranscriptPayload_textAndStash() {
        JsonObject o = JsonParser.parseString(
                "{\"type\":\"conversation.item.input_audio_transcription.text\",\"text\":\"\",\"stash\":\"北京的\"}"
        ).getAsJsonObject();
        assertEquals("北京的", QwenAsrService.extractTranscriptPayload(o));
    }

    @Test
    @DisplayName("extractTranscriptPayload should merge confirmed prefix and draft suffix")
    void extractTranscriptPayload_mixedPrefixSuffix() {
        JsonObject o = JsonParser.parseString(
                "{\"type\":\"conversation.item.input_audio_transcription.text\",\"text\":\"今天天气不错，\",\"stash\":\"阳光\"}"
        ).getAsJsonObject();
        assertEquals("今天天气不错，阳光", QwenAsrService.extractTranscriptPayload(o));
    }

    @Test
    @DisplayName("Should cleanup resources on destroy")
    void testDestroy() throws Exception {
        asrService.init();

        // Create multiple sessions
        asrService.startTranscription("session-1", text -> {}, error -> {});
        asrService.startTranscription("session-2", text -> {}, error -> {});

        // Destroy should cleanup all sessions
        assertDoesNotThrow(() -> asrService.destroy());

        assertFalse(asrService.hasActiveSession("session-1"));
        assertFalse(asrService.hasActiveSession("session-2"));
    }

    @Test
    @DisplayName("reload 应更新所有 ASR 配置字段")
    void testReloadUpdatesAllFields() throws Exception {
        VoiceInterviewProperties newProps = new VoiceInterviewProperties();
        VoiceInterviewProperties.AsrConfig newAsr = newProps.getQwen().getAsr();
        newAsr.setUrl("wss://new-host.example.com/ws");
        newAsr.setModel("new-asr-model");
        newAsr.setApiKey("new-api-key");
        newAsr.setLanguage("en");
        newAsr.setFormat("wav");
        newAsr.setSampleRate(8000);
        newAsr.setEnableTurnDetection(false);
        newAsr.setTurnDetectionType("client_vad");
        newAsr.setTurnDetectionThreshold(0.5f);
        newAsr.setTurnDetectionSilenceDurationMs(200);

        asrService.reload(newProps);

        assertEquals("wss://new-host.example.com/ws", field(asrService, "url"));
        assertEquals("new-asr-model", field(asrService, "model"));
        assertEquals("new-api-key", field(asrService, "apiKey"));
        assertEquals("en", field(asrService, "language"));
        assertEquals("wav", field(asrService, "format"));
        assertEquals(8000, field(asrService, "sampleRate"));
        assertEquals(false, field(asrService, "enableTurnDetection"));
        assertEquals("client_vad", field(asrService, "turnDetectionType"));
        assertEquals(0.5f, field(asrService, "turnDetectionThreshold"));
        assertEquals(200, field(asrService, "turnDetectionSilenceDurationMs"));
    }

    private static Object field(Object obj, String name) throws Exception {
        java.lang.reflect.Field f = obj.getClass().getDeclaredField(name);
        f.setAccessible(true);
        return f.get(obj);
    }
}

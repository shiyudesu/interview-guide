package interview.guide.modules.voiceinterview.handler;

import com.fasterxml.jackson.databind.ObjectMapper;
import io.micrometer.core.instrument.MeterRegistry;
import interview.guide.modules.voiceinterview.config.VoiceInterviewProperties;
import interview.guide.modules.voiceinterview.context.VoiceContextCompressor;
import interview.guide.modules.voiceinterview.service.DashscopeLlmService;
import interview.guide.modules.voiceinterview.service.QwenAsrService;
import interview.guide.modules.voiceinterview.service.QwenTtsService;
import interview.guide.modules.voiceinterview.service.VoiceInterviewService;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.web.socket.TextMessage;
import org.springframework.web.socket.WebSocketSession;

import java.lang.reflect.Constructor;
import java.lang.reflect.Field;
import java.lang.reflect.Method;
import java.util.Map;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.lenient;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class VoiceInterviewWebSocketHandlerTest {

  @Mock
  private ObjectMapper objectMapper;
  @Mock
  private QwenAsrService sttService;
  @Mock
  private QwenTtsService ttsService;
  @Mock
  private DashscopeLlmService llmService;
  @Mock
  private VoiceInterviewService interviewService;
  @Mock
  private VoiceContextCompressor voiceContextCompressor;
  @Mock
  private ObjectProvider<MeterRegistry> meterRegistryProvider;

  private VoiceInterviewWebSocketHandler handler;

  @AfterEach
  void tearDown() {
    if (handler != null) {
      handler.destroy();
    }
  }

  @Test
  @DisplayName("默认关闭开场音频预热，应用启动时不调用云端 TTS")
  void shouldNotWarmupOpeningAudioByDefault() throws InterruptedException {
    VoiceInterviewProperties properties = new VoiceInterviewProperties();
    CountDownLatch ttsCalled = new CountDownLatch(1);
    lenient().when(ttsService.synthesize(anyString())).thenAnswer(invocation -> {
      ttsCalled.countDown();
      return new byte[0];
    });
    handler = newHandler(properties);

    assertThat(properties.isOpeningAudioWarmupEnabled()).isFalse();

    handler.warmupOpeningAudioCache();

    assertThat(ttsCalled.await(300, TimeUnit.MILLISECONDS)).isFalse();
  }

  @Test
  @DisplayName("显式开启开场音频预热后才调用云端 TTS")
  void shouldWarmupOpeningAudioWhenExplicitlyEnabled() throws InterruptedException {
    VoiceInterviewProperties properties = new VoiceInterviewProperties();
    properties.setOpeningAudioWarmupEnabled(true);
    properties.getOpening().setSkillQuestions(Map.of("java-backend", "你好，开始面试。"));
    properties.getOpening().setAlgorithmQuestion("");
    properties.getOpening().setBackendQuestion("");
    CountDownLatch ttsCalled = new CountDownLatch(1);
    when(ttsService.synthesize("你好，开始面试。")).thenAnswer(invocation -> {
      ttsCalled.countDown();
      return new byte[0];
    });
    handler = newHandler(properties);

    handler.warmupOpeningAudioCache();

    assertThat(ttsCalled.await(1, TimeUnit.SECONDS)).isTrue();
  }

  @Test
  @DisplayName("上一轮提交后到达的临时字幕不会推送到当前轮")
  void shouldIgnoreLatePartialAfterPreviousTurnWasSubmitted() throws Exception {
    WebSocketSession session = mock(WebSocketSession.class);
    handler = newHandler(new VoiceInterviewProperties(), new ObjectMapper());
    prepareSttState("49", session, true);

    invokeHandleSttResult("49", "这是上一轮回答", false);

    verify(session, never()).sendMessage(any(TextMessage.class));
  }

  @Test
  @DisplayName("上一轮处理完成后当前轮临时字幕可以正常推送")
  void shouldSendPartialForCurrentTurnWhenNotProcessing() throws Exception {
    WebSocketSession session = mock(WebSocketSession.class);
    when(session.isOpen()).thenReturn(true);
    handler = newHandler(new VoiceInterviewProperties(), new ObjectMapper());
    prepareSttState("49", session, false);

    invokeHandleSttResult("49", "这是当前轮回答", false);

    ArgumentCaptor<TextMessage> messageCaptor = ArgumentCaptor.forClass(TextMessage.class);
    verify(session).sendMessage(messageCaptor.capture());
    assertThat(messageCaptor.getValue().getPayload())
        .contains("\"type\":\"subtitle\"")
        .contains("这是当前轮回答");
  }

  private VoiceInterviewWebSocketHandler newHandler(VoiceInterviewProperties properties) {
    return newHandler(properties, objectMapper);
  }

  private VoiceInterviewWebSocketHandler newHandler(
      VoiceInterviewProperties properties,
      ObjectMapper handlerObjectMapper) {
    return new VoiceInterviewWebSocketHandler(
        handlerObjectMapper,
        sttService,
        ttsService,
        llmService,
        interviewService,
        voiceContextCompressor,
        properties,
        meterRegistryProvider
    );
  }

  private void prepareSttState(
      String sessionId,
      WebSocketSession session,
      boolean processing) throws Exception {
    fieldMap("sessions").put(sessionId, session);

    Class<?> stateType = Class.forName(
        VoiceInterviewWebSocketHandler.class.getName() + "$SessionState");
    Constructor<?> constructor = stateType.getDeclaredConstructor();
    constructor.setAccessible(true);
    Object state = constructor.newInstance();
    Method isProcessing = stateType.getDeclaredMethod("isProcessing");
    isProcessing.setAccessible(true);
    ((AtomicBoolean) isProcessing.invoke(state)).set(processing);
    fieldMap("sessionStates").put(sessionId, state);
  }

  private void invokeHandleSttResult(
      String sessionId,
      String text,
      boolean finalSegment) throws Exception {
    Method method = VoiceInterviewWebSocketHandler.class.getDeclaredMethod(
        "handleSttResult", String.class, String.class, boolean.class);
    method.setAccessible(true);
    method.invoke(handler, sessionId, text, finalSegment);
  }

  @SuppressWarnings("unchecked")
  private Map<String, Object> fieldMap(String fieldName) throws Exception {
    Field field = VoiceInterviewWebSocketHandler.class.getDeclaredField(fieldName);
    field.setAccessible(true);
    return (Map<String, Object>) field.get(handler);
  }
}

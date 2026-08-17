package interview.guide.modules.knowledgebase;

import interview.guide.modules.knowledgebase.model.RagChatDTO.SendMessageRequest;
import interview.guide.modules.knowledgebase.service.RagChatSessionService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import reactor.core.publisher.Flux;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class RagChatControllerStreamBehaviorTest {

    @Mock
    private RagChatSessionService sessionService;

    @Test
    void explicitFakeNormalCompletionPersistsFullContent() {
        when(sessionService.prepareStreamMessage(1L, "问题")).thenReturn(11L);
        when(sessionService.getStreamAnswer(1L, "问题")).thenReturn(Flux.just("第一段", "\n第二段"));
        var controller = new RagChatController(sessionService);

        var events = controller.sendMessageStream(1L, new SendMessageRequest("问题"))
            .collectList()
            .block();

        assertEquals("第一段", events.get(0).data());
        assertEquals("\\n第二段", events.get(1).data());
        verify(sessionService).completeStreamMessage(11L, "第一段\n第二段");
    }

    @Test
    void explicitFakeModelErrorPersistsReceivedPartialContent() {
        when(sessionService.prepareStreamMessage(2L, "问题")).thenReturn(12L);
        when(sessionService.getStreamAnswer(2L, "问题")).thenReturn(
            Flux.just("部分内容").concatWith(Flux.error(new IllegalStateException("固定错误")))
        );
        var controller = new RagChatController(sessionService);

        var error = assertThrows(
            IllegalStateException.class,
            () -> controller.sendMessageStream(2L, new SendMessageRequest("问题")).blockLast()
        );

        assertEquals("固定错误", error.getMessage());
        verify(sessionService).completeStreamMessage(12L, "部分内容");
    }

    @Test
    void explicitFakeClientCancellationDoesNotCompleteAssistantPlaceholder() {
        when(sessionService.prepareStreamMessage(3L, "问题")).thenReturn(13L);
        when(sessionService.getStreamAnswer(3L, "问题")).thenReturn(
            Flux.concat(Flux.just("部分内容"), Flux.never())
        );
        var controller = new RagChatController(sessionService);

        var subscription = controller.sendMessageStream(3L, new SendMessageRequest("问题"))
            .subscribe();
        subscription.dispose();

        verify(sessionService, never()).completeStreamMessage(13L, "部分内容");
    }
}

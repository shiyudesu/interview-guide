package interview.guide.modules.llmprovider.controller;

import interview.guide.common.result.Result;
import interview.guide.modules.llmprovider.dto.DefaultProviderDTO;
import interview.guide.modules.llmprovider.dto.ProviderDTO;
import interview.guide.modules.llmprovider.service.LlmProviderConfigService;
import org.junit.jupiter.api.DisplayName;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.mockito.Mockito.doNothing;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
@DisplayName("LlmProviderController 测试")
class LlmProviderControllerTest {

    @Mock private LlmProviderConfigService configService;
    @InjectMocks private LlmProviderController controller;

    @Test
    @DisplayName("listProviders 返回 provider 列表")
    void listProvidersReturnsProviderList() {
        ProviderDTO dto = ProviderDTO.builder()
            .id("dashscope")
            .baseUrl("http://test")
            .maskedApiKey("sk-***key")
            .model("qwen")
            .embeddingModel("text-embedding-v3")
            .build();
        when(configService.listProviders()).thenReturn(List.of(dto));

        Result<List<ProviderDTO>> result = controller.listProviders();

        assertEquals(200, result.getCode());
        assertEquals(1, result.getData().size());
        assertEquals("dashscope", result.getData().get(0).id());
    }

    @Test
    @DisplayName("getDefaultProvider 返回全局默认 provider")
    void getDefaultProviderReturnsDefaultProvider() {
        when(configService.getDefaultProvider())
            .thenReturn(new DefaultProviderDTO("glm"));

        Result<DefaultProviderDTO> result = controller.getDefaultProvider();

        assertEquals(200, result.getCode());
        assertEquals("glm", result.getData().defaultProvider());
    }

    @Test
    @DisplayName("deleteProvider 调用 service")
    void deleteProviderCallsService() {
        doNothing().when(configService).deleteProvider("lmstudio");

        Result<Void> result = controller.deleteProvider("lmstudio");

        assertEquals(200, result.getCode());
        verify(configService).deleteProvider("lmstudio");
    }
}

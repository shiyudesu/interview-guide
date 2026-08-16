package interview.guide.common.config;

import interview.guide.common.ai.LlmProviderRegistry;
import lombok.extern.slf4j.Slf4j;
import org.springframework.ai.document.Document;
import org.springframework.ai.embedding.EmbeddingModel;
import org.springframework.ai.embedding.EmbeddingRequest;
import org.springframework.ai.embedding.EmbeddingResponse;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
@Slf4j
public class LlmEmbeddingConfig {

  @Bean
  public EmbeddingModel embeddingModel(LlmProviderRegistry registry) {
    log.info("EmbeddingModel bean initialized as registry delegate");
    return new EmbeddingModel() {
      @Override
      public EmbeddingResponse call(EmbeddingRequest request) {
        return registry.getDefaultEmbeddingModel().call(request);
      }

      @Override
      public float[] embed(Document document) {
        return registry.getDefaultEmbeddingModel().embed(document);
      }
    };
  }
}

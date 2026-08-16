package interview.guide.modules.llmprovider.dto;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class TtsConfigDTO {
  private String model;
  private String maskedApiKey;
  private String voice;
  private String format;
  private int sampleRate;
  private String mode;
  private String languageType;
  private float speechRate;
  private int volume;
}

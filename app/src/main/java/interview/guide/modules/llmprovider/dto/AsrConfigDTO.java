package interview.guide.modules.llmprovider.dto;

import lombok.Builder;
import lombok.Data;

@Data
@Builder
public class AsrConfigDTO {
  private String url;
  private String model;
  private String maskedApiKey;
  private String language;
  private String format;
  private int sampleRate;
  private boolean enableTurnDetection;
  private String turnDetectionType;
  private float turnDetectionThreshold;
  private int turnDetectionSilenceDurationMs;
}

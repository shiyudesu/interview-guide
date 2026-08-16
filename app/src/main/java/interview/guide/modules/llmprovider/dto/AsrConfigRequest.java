package interview.guide.modules.llmprovider.dto;

public record AsrConfigRequest(
    String url,
    String model,
    String apiKey,
    String language,
    String format,
    Integer sampleRate,
    Boolean enableTurnDetection,
    String turnDetectionType,
    Float turnDetectionThreshold,
    Integer turnDetectionSilenceDurationMs
) {}

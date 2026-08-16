package interview.guide.modules.llmprovider.dto;

import lombok.Builder;

@Builder
public record ProviderTestResult(
    boolean success,
    String message,
    String model
) {}

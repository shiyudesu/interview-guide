package interview.guide.common.ai;

import static org.junit.jupiter.api.Assertions.assertEquals;

import interview.guide.common.config.LlmProviderProperties;
import interview.guide.common.testing.MigrationTestOverrides;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

class PromptSanitizerTest {

    @AfterEach
    void clearOverride() {
        System.clearProperty(
            MigrationTestOverrides.PROPERTY_PREFIX + "uuid.prompt-boundary"
        );
        MigrationTestOverrides.resetForTests();
    }

    @Test
    void usesFixedBoundaryUuidWhenConfigured() {
        System.setProperty(
            MigrationTestOverrides.PROPERTY_PREFIX + "uuid.prompt-boundary",
            "12345678-0000-0000-0000-000000000000"
        );
        PromptSanitizer sanitizer = new PromptSanitizer(new LlmProviderProperties());

        assertEquals(
            """
            <data-boundary-12345678-resume>
            fixed content
            </data-boundary-12345678-resume>""",
            sanitizer.wrapWithDelimiters("resume", "fixed content")
        );
    }
}

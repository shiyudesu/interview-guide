package interview.guide.common.async;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotEquals;

import org.junit.jupiter.api.Test;

class AbstractStreamConsumerTest {

    @Test
    void usesFixedMigrationSuffixOnlyWhenExplicitlyConfigured() {
        String property = AbstractStreamConsumer.MIGRATION_CONSUMER_SUFFIX_PROPERTY;
        String previous = System.getProperty(property);
        try {
            System.setProperty(property, "comparison");
            assertEquals(
                "consumer-comparison",
                AbstractStreamConsumer.resolveConsumerName("consumer-")
            );

            System.clearProperty(property);
            String generated = AbstractStreamConsumer.resolveConsumerName("consumer-");
            assertNotEquals("consumer-comparison", generated);
            assertEquals("consumer-".length() + 8, generated.length());
        } finally {
            if (previous == null) {
                System.clearProperty(property);
            } else {
                System.setProperty(property, previous);
            }
        }
    }
}

package interview.guide.modules.llmprovider.service;

import static org.junit.jupiter.api.Assertions.assertEquals;

import interview.guide.common.config.LlmProviderProperties;
import interview.guide.common.testing.MigrationTestOverrides;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

class ApiKeyEncryptionServiceTest {

    @AfterEach
    void clearOverride() {
        System.clearProperty(
            MigrationTestOverrides.PROPERTY_PREFIX
                + "bytes.provider-api-key-nonce"
        );
        MigrationTestOverrides.resetForTests();
    }

    @Test
    void usesFixedNonceWhenConfigured() {
        System.setProperty(
            MigrationTestOverrides.PROPERTY_PREFIX
                + "bytes.provider-api-key-nonce",
            "000102030405060708090a0b"
        );
        LlmProviderProperties properties = new LlmProviderProperties();
        properties.getSecurity().setApiKeyEncryptionKey("fixed-test-key");
        ApiKeyEncryptionService service = new ApiKeyEncryptionService(properties);
        service.init();

        ApiKeyEncryptionService.EncryptedValue encrypted =
            service.encrypt("provider-secret");

        assertEquals("AAECAwQFBgcICQoL", encrypted.nonce());
        assertEquals(
            "provider-secret",
            service.decrypt(encrypted.nonce(), encrypted.ciphertext())
        );
    }
}

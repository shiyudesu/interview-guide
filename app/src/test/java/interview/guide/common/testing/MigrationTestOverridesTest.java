package interview.guide.common.testing;

import static org.junit.jupiter.api.Assertions.assertArrayEquals;
import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertThrows;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.UUID;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;

class MigrationTestOverridesTest {

    @AfterEach
    void clearOverrides() {
        System.getProperties().stringPropertyNames().stream()
            .filter(name -> name.startsWith(MigrationTestOverrides.PROPERTY_PREFIX))
            .toList()
            .forEach(System::clearProperty);
        MigrationTestOverrides.resetForTests();
    }

    @Test
    void returnsFixedTimeWhenConfigured() {
        System.setProperty(
            MigrationTestOverrides.PROPERTY_PREFIX + "fixed-time",
            "2026-08-16T08:00:00"
        );

        assertEquals(
            LocalDateTime.of(2026, 8, 16, 8, 0),
            MigrationTestOverrides.now()
        );
    }

    @Test
    void consumesUuidSequenceWithoutReusingValues() {
        String property = MigrationTestOverrides.PROPERTY_PREFIX + "uuid.session";
        System.setProperty(
            property,
            "00000000-0000-0000-0000-000000000001,"
                + "00000000-0000-0000-0000-000000000002"
        );

        assertEquals(
            UUID.fromString("00000000-0000-0000-0000-000000000001"),
            MigrationTestOverrides.uuid("session")
        );
        assertEquals(
            UUID.fromString("00000000-0000-0000-0000-000000000002"),
            MigrationTestOverrides.uuid("session")
        );
        assertThrows(
            IllegalStateException.class,
            () -> MigrationTestOverrides.uuid("session")
        );
    }

    @Test
    void fillsNonceFromHexSequence() {
        System.setProperty(
            MigrationTestOverrides.PROPERTY_PREFIX + "bytes.nonce",
            "000102030405060708090a0b"
        );
        byte[] nonce = new byte[12];

        MigrationTestOverrides.fillBytes("nonce", nonce, new SecureRandom());

        assertArrayEquals(
            new byte[] {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11},
            nonce
        );
    }

    @Test
    void rejectsConfiguredIntegerOutsideRequestedRange() {
        System.setProperty(
            MigrationTestOverrides.PROPERTY_PREFIX + "int.selection",
            "4"
        );

        assertThrows(
            IllegalStateException.class,
            () -> MigrationTestOverrides.nextInt("selection", 0, 4)
        );
    }
}

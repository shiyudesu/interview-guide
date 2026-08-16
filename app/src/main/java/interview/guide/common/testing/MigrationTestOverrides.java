package interview.guide.common.testing;

import java.security.SecureRandom;
import java.time.LocalDateTime;
import java.util.Collections;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ThreadLocalRandom;
import java.util.concurrent.atomic.AtomicInteger;

public final class MigrationTestOverrides {

    public static final String PROPERTY_PREFIX = "interview.guide.migration.";
    private static final Map<String, AtomicInteger> POSITIONS = new ConcurrentHashMap<>();

    private MigrationTestOverrides() {
    }

    public static LocalDateTime now() {
        String fixedTime = System.getProperty(PROPERTY_PREFIX + "fixed-time");
        return fixedTime == null || fixedTime.isBlank()
            ? LocalDateTime.now()
            : LocalDateTime.parse(fixedTime);
    }

    public static long currentTimeMillis(String purpose) {
        String value = nextConfiguredValue("millis", purpose);
        return value == null ? System.currentTimeMillis() : Long.parseLong(value);
    }

    public static UUID uuid(String purpose) {
        String value = nextConfiguredValue("uuid", purpose);
        return value == null ? UUID.randomUUID() : UUID.fromString(value);
    }

    public static String configuredString(String purpose) {
        String value = System.getProperty(PROPERTY_PREFIX + "string." + purpose);
        return value == null || value.isBlank() ? null : value;
    }

    public static void fillBytes(
        String purpose,
        byte[] target,
        SecureRandom secureRandom
    ) {
        String value = nextConfiguredValue("bytes", purpose);
        if (value == null) {
            secureRandom.nextBytes(target);
            return;
        }
        byte[] configured = decodeHex(value);
        if (configured.length != target.length) {
            throw new IllegalStateException(
                "Configured byte sequence for " + purpose + " has length "
                    + configured.length + ", expected " + target.length
            );
        }
        System.arraycopy(configured, 0, target, 0, target.length);
    }

    public static int nextInt(String purpose, int origin, int bound) {
        String value = nextConfiguredValue("int", purpose);
        if (value == null) {
            return ThreadLocalRandom.current().nextInt(origin, bound);
        }
        int configured = Integer.parseInt(value);
        if (configured < origin || configured >= bound) {
            throw new IllegalStateException(
                "Configured integer for " + purpose + " is outside ["
                    + origin + ", " + bound + "): " + configured
            );
        }
        return configured;
    }

    public static <T> void shuffle(List<T> values, String purpose) {
        if (!hasConfiguredValue("int", purpose)) {
            Collections.shuffle(values);
            return;
        }
        for (int index = values.size(); index > 1; index--) {
            int selected = nextInt(purpose, 0, index);
            Collections.swap(values, index - 1, selected);
        }
    }

    public static void resetForTests() {
        POSITIONS.clear();
    }

    private static String nextConfiguredValue(String type, String purpose) {
        String property = PROPERTY_PREFIX + type + "." + purpose;
        String configured = System.getProperty(property);
        if (configured == null || configured.isBlank()) {
            return null;
        }
        String[] values = configured.split(",", -1);
        int index = POSITIONS.computeIfAbsent(property, ignored -> new AtomicInteger())
            .getAndIncrement();
        if (index >= values.length) {
            throw new IllegalStateException(
                "Configured migration test sequence exhausted: " + property
            );
        }
        String value = values[index].trim();
        if (value.isEmpty()) {
            throw new IllegalStateException(
                "Configured migration test sequence contains an empty value: " + property
            );
        }
        return value;
    }

    private static boolean hasConfiguredValue(String type, String purpose) {
        String configured = System.getProperty(PROPERTY_PREFIX + type + "." + purpose);
        return configured != null && !configured.isBlank();
    }

    private static byte[] decodeHex(String value) {
        if ((value.length() & 1) != 0) {
            throw new IllegalStateException("Hex value must contain an even number of characters");
        }
        byte[] decoded = new byte[value.length() / 2];
        for (int index = 0; index < decoded.length; index++) {
            int high = Character.digit(value.charAt(index * 2), 16);
            int low = Character.digit(value.charAt(index * 2 + 1), 16);
            if (high < 0 || low < 0) {
                throw new IllegalStateException("Invalid hex value: " + value);
            }
            decoded[index] = (byte) ((high << 4) | low);
        }
        return decoded;
    }
}

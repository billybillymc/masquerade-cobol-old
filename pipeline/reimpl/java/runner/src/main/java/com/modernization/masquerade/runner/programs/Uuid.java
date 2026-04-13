package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of CobolCraft program UUID (uuid.cob).
 *
 * <p>Mirrors {@code pipeline/reimpl/cc_uuid.py} byte-for-byte. Two
 * operations:
 * <ul>
 *   <li><b>to_string:</b> 16-byte big-endian UUID → 36-char hyphenated
 *       lowercase hex string. Dashes are inserted after bytes 4, 6, 8, 10
 *       (1-based), matching the COBOL {@code IF INPUT-INDEX = 4 OR 6 OR 8 OR 10}.</li>
 *   <li><b>from_string:</b> 36-char hyphenated UUID string → 16-byte buffer.
 *       Input is case-insensitive (matches Python's {@code c.lower()}),
 *       output bytes are byte-identical.</li>
 * </ul>
 *
 * <p>Binary data is carried across the JSON contract as lowercase hex
 * strings (32 chars for a 16-byte UUID). This matches the Python adapter
 * in {@code cc_uuid.py}.
 *
 * <p>Class name is {@code Uuid} rather than {@code UUID} to avoid a
 * compile-time name collision with {@link java.util.UUID}. The program
 * is still registered as "UUID" in {@link ProgramRegistry}.
 */
public class Uuid implements ProgramRunner {

    private static final String HEX = "0123456789abcdef";

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String op = inputs.getOrDefault("op", "").trim().toLowerCase();
        Map<String, String> out = new LinkedHashMap<>();

        try {
            switch (op) {
                case "to_string": {
                    String hexBytes = inputs.getOrDefault("HEX_BYTES", "");
                    if (hexBytes.length() != 32) {
                        out.put("UUID_STRING", "");
                        out.put("error", "HEX_BYTES must be 32 chars, got " + hexBytes.length());
                        return out;
                    }
                    byte[] buf = decodeHexString(hexBytes);
                    out.put("UUID_STRING", uuidToString(buf));
                    out.put("error", "");
                    return out;
                }
                case "from_string": {
                    String uuidStr = inputs.getOrDefault("UUID_STRING", "");
                    if (uuidStr.length() != 36) {
                        out.put("HEX_BYTES", "");
                        out.put("error", "UUID_STRING must be 36 chars, got " + uuidStr.length());
                        return out;
                    }
                    byte[] buf = uuidFromString(uuidStr);
                    out.put("HEX_BYTES", encodeHexString(buf));
                    out.put("error", "");
                    return out;
                }
                default:
                    out.put("error", "unknown op: '" + op + "'");
                    return out;
            }
        } catch (IllegalArgumentException | IndexOutOfBoundsException e) {
            out.put("error", e.getClass().getSimpleName() + ": " + e.getMessage());
            return out;
        }
    }

    /**
     * Convert a 16-byte UUID buffer to the 36-char hyphenated hex string.
     * Dashes appear AFTER positions 4, 6, 8, 10 (1-based) in the byte index,
     * matching the COBOL source exactly.
     */
    static String uuidToString(byte[] buf) {
        StringBuilder sb = new StringBuilder(36);
        for (int i = 0; i < buf.length; i++) {
            int b = buf[i] & 0xFF;
            sb.append(HEX.charAt(b >>> 4));
            sb.append(HEX.charAt(b & 0x0F));
            int bytePos = i + 1;  // 1-based like the COBOL
            if (bytePos == 4 || bytePos == 6 || bytePos == 8 || bytePos == 10) {
                sb.append('-');
            }
        }
        return sb.toString();
    }

    /**
     * Parse a 36-char hyphenated UUID string back to 16 bytes. Case-
     * insensitive input (matches Python's {@code c.lower()}).
     */
    static byte[] uuidFromString(String s) {
        byte[] out = new byte[16];
        int idx = 0;
        for (int bytePos = 1; bytePos <= 16; bytePos++) {
            int hi = decodeHexChar(s.charAt(idx++));
            int lo = decodeHexChar(s.charAt(idx++));
            out[bytePos - 1] = (byte) ((hi << 4) | lo);
            if (bytePos == 4 || bytePos == 6 || bytePos == 8 || bytePos == 10) {
                idx++;  // skip dash
            }
        }
        return out;
    }

    /** Case-insensitive single hex-char decode. Matches Python's `_HEX.index(c.lower())`. */
    private static int decodeHexChar(char c) {
        char lower = Character.toLowerCase(c);
        int i = HEX.indexOf(lower);
        if (i < 0) {
            throw new IllegalArgumentException("invalid hex char: '" + c + "'");
        }
        return i;
    }

    /** Convert a hex string to a byte array. */
    private static byte[] decodeHexString(String hex) {
        int len = hex.length();
        byte[] out = new byte[len / 2];
        for (int i = 0; i < out.length; i++) {
            int hi = decodeHexChar(hex.charAt(i * 2));
            int lo = decodeHexChar(hex.charAt(i * 2 + 1));
            out[i] = (byte) ((hi << 4) | lo);
        }
        return out;
    }

    /** Convert a byte array to a lowercase hex string. */
    private static String encodeHexString(byte[] buf) {
        StringBuilder sb = new StringBuilder(buf.length * 2);
        for (byte b : buf) {
            int v = b & 0xFF;
            sb.append(HEX.charAt(v >>> 4));
            sb.append(HEX.charAt(v & 0x0F));
        }
        return sb.toString();
    }
}

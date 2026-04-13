package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.LinkedHashMap;
import java.util.Map;

/**
 * Java reimplementation of CobolCraft JSON token parser — cc_json_parse.
 *
 * <p>Mirrors {@code pipeline/reimpl/cc_json_parse.py} byte-for-byte. Python is
 * the source of truth. All offsets are 1-based to match the COBOL BINARY-LONG
 * convention.
 */
public class CcJsonParse implements ProgramRunner {

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "SIMPLE_OBJECT").toUpperCase();
        String jsonStr = buildScenario(scenarioName);
        if (jsonStr == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("INPUT", jsonStr);

        // Parse object start
        int[] objStart = parseObjectStart(jsonStr, 1);
        out.put("OBJ_START_FLAG", String.valueOf(objStart[0]));
        out.put("OBJ_START_OFFSET", String.valueOf(objStart[1]));

        if (objStart[0] == 0) {
            // Parse first key
            Object[] keyResult = parseObjectKey(jsonStr, objStart[1]);
            int kflag = (int) keyResult[0];
            int koffset = (int) keyResult[1];
            String key = (String) keyResult[2];
            out.put("FIRST_KEY_FLAG", String.valueOf(kflag));
            out.put("FIRST_KEY_OFFSET", String.valueOf(koffset));
            out.put("FIRST_KEY", key);

            if (kflag == 0) {
                // Try string value
                Object[] sResult = parseString(jsonStr, koffset);
                int sflag = (int) sResult[0];
                int soffset = (int) sResult[1];
                String sval = (String) sResult[2];

                if (sflag == 0) {
                    out.put("FIRST_VALUE_TYPE", "STRING");
                    out.put("FIRST_VALUE", sval);
                    out.put("FIRST_VALUE_OFFSET", String.valueOf(soffset));
                } else {
                    // Try integer
                    int[] iResult = parseInteger(jsonStr, koffset);
                    if (iResult[0] == 0) {
                        out.put("FIRST_VALUE_TYPE", "INTEGER");
                        out.put("FIRST_VALUE", String.valueOf(iResult[2]));
                        out.put("FIRST_VALUE_OFFSET", String.valueOf(iResult[1]));
                    } else {
                        // Try boolean
                        int[] bResult = parseBoolean(jsonStr, koffset);
                        if (bResult[0] == 0) {
                            out.put("FIRST_VALUE_TYPE", "BOOLEAN");
                            out.put("FIRST_VALUE", String.valueOf(bResult[2]));
                            out.put("FIRST_VALUE_OFFSET", String.valueOf(bResult[1]));
                        } else {
                            // Skip value (complex type)
                            int[] skResult = parseSkipValue(jsonStr, koffset);
                            out.put("FIRST_VALUE_TYPE", "COMPLEX");
                            out.put("FIRST_VALUE", jsonStr.substring(koffset - 1, skResult[1] - 1));
                            out.put("FIRST_VALUE_OFFSET", String.valueOf(skResult[1]));
                        }
                    }
                }
            }
        }

        // find_value test
        if ("SIMPLE_OBJECT".equals(scenarioName)) {
            int[] fvResult = parseFindValue(jsonStr, 2, "age");
            out.put("FIND_AGE_FLAG", String.valueOf(fvResult[0]));
            out.put("FIND_AGE_OFFSET", String.valueOf(fvResult[1]));
            if (fvResult[0] == 0) {
                int[] av = parseInteger(jsonStr, fvResult[1]);
                out.put("FIND_AGE_VALUE", String.valueOf(av[2]));
            }
        } else if ("NESTED".equals(scenarioName)) {
            int[] fvResult = parseFindValue(jsonStr, 2, "c");
            out.put("FIND_C_FLAG", String.valueOf(fvResult[0]));
            out.put("FIND_C_OFFSET", String.valueOf(fvResult[1]));
            if (fvResult[0] == 0) {
                int[] bv = parseBoolean(jsonStr, fvResult[1]);
                out.put("FIND_C_VALUE", String.valueOf(bv[2]));
            }
        }

        return out;
    }

    // ── Scenarios ─────────────────────────────────────────────────────────

    private String buildScenario(String name) {
        switch (name) {
            case "SIMPLE_OBJECT": return "{\"name\":\"Alice\",\"age\":30}";
            case "NESTED":        return "{\"a\":{\"b\":[1,2,3]},\"c\":true}";
            case "EMPTY_OBJECT":  return "{}";
            default: return null;
        }
    }

    // ── JSON parsing functions (1-based offsets) ─────────────────────────

    private static final String ESCAPE_CHARS = "\"\\/bfnrt";
    private static final String ESCAPE_VALS = "\"\\/\b\f\n\r\t";

    private int skipWhitespace(String s, int offset) {
        int n = s.length();
        while (offset <= n && " \t\r\n".indexOf(s.charAt(offset - 1)) >= 0) {
            offset++;
        }
        return offset;
    }

    int[] parseObjectStart(String s, int offset) {
        offset = skipWhitespace(s, offset);
        if (offset > s.length() || s.charAt(offset - 1) != '{') {
            return new int[]{1, offset};
        }
        return new int[]{0, offset + 1};
    }

    int[] parseObjectEnd(String s, int offset) {
        offset = skipWhitespace(s, offset);
        if (offset > s.length() || s.charAt(offset - 1) != '}') {
            return new int[]{1, offset};
        }
        return new int[]{0, offset + 1};
    }

    int[] parseArrayStart(String s, int offset) {
        offset = skipWhitespace(s, offset);
        if (offset > s.length() || s.charAt(offset - 1) != '[') {
            return new int[]{1, offset};
        }
        return new int[]{0, offset + 1};
    }

    int[] parseArrayEnd(String s, int offset) {
        offset = skipWhitespace(s, offset);
        if (offset > s.length() || s.charAt(offset - 1) != ']') {
            return new int[]{1, offset};
        }
        return new int[]{0, offset + 1};
    }

    int[] parseComma(String s, int offset) {
        offset = skipWhitespace(s, offset);
        if (offset > s.length() || s.charAt(offset - 1) != ',') {
            return new int[]{1, offset};
        }
        return new int[]{0, offset + 1};
    }

    Object[] parseString(String s, int offset) {
        int n = s.length();
        offset = skipWhitespace(s, offset);
        if (offset > n || s.charAt(offset - 1) != '"') {
            return new Object[]{1, offset, ""};
        }
        offset++; // consume opening quote

        StringBuilder out = new StringBuilder();
        boolean escaping = false;
        while (offset <= n) {
            char ch = s.charAt(offset - 1);
            if (escaping) {
                if (ch == 'u') {
                    if (offset + 4 > n) {
                        return new Object[]{1, offset, ""};
                    }
                    String hex4 = s.substring(offset, offset + 4);
                    out.append((char) Integer.parseInt(hex4, 16));
                    offset += 4;
                } else {
                    int idx = ESCAPE_CHARS.indexOf(ch);
                    if (idx >= 0) {
                        out.append(ESCAPE_VALS.charAt(idx));
                        offset++;
                    } else {
                        return new Object[]{1, offset, ""};
                    }
                }
                escaping = false;
            } else {
                if (ch == '"') {
                    return new Object[]{0, offset + 1, out.toString()};
                } else if (ch == '\\') {
                    escaping = true;
                    offset++;
                } else {
                    out.append(ch);
                    offset++;
                }
            }
        }
        return new Object[]{1, offset, ""}; // unterminated
    }

    Object[] parseObjectKey(String s, int offset) {
        int n = s.length();
        Object[] strResult = parseString(s, offset);
        int flag = (int) strResult[0];
        offset = (int) strResult[1];
        String key = (String) strResult[2];
        if (flag != 0) {
            return new Object[]{1, offset, ""};
        }
        offset = skipWhitespace(s, offset);
        if (offset > n || s.charAt(offset - 1) != ':') {
            return new Object[]{1, offset, ""};
        }
        return new Object[]{0, offset + 1, key};
    }

    int[] parseNull(String s, int offset) {
        int n = s.length();
        offset = skipWhitespace(s, offset);
        if (offset + 3 > n || s.charAt(offset - 1) != 'n') {
            return new int[]{1, offset};
        }
        return new int[]{0, offset + 4};
    }

    int[] parseBoolean(String s, int offset) {
        int n = s.length();
        offset = skipWhitespace(s, offset);
        if (offset > n) {
            return new int[]{1, offset, 0};
        }
        char ch = s.charAt(offset - 1);
        if (ch == 't') {
            if (offset + 3 > n) return new int[]{1, offset, 0};
            return new int[]{0, offset + 4, 1};
        } else if (ch == 'f') {
            if (offset + 4 > n) return new int[]{1, offset, 0};
            return new int[]{0, offset + 5, 0};
        }
        return new int[]{1, offset, 0};
    }

    int[] parseInteger(String s, int offset) {
        int n = s.length();
        offset = skipWhitespace(s, offset);
        if (offset > n) {
            return new int[]{1, offset, 0};
        }

        int sign = 1;
        if (s.charAt(offset - 1) == '-') {
            sign = -1;
            offset++;
        }

        boolean found = false;
        int value = 0;
        while (offset <= n) {
            int code = s.charAt(offset - 1);
            if (code < 48 || code > 57) break;
            value = value * 10 + (code - 48);
            offset++;
            found = true;
        }

        if (!found) return new int[]{1, offset, 0};
        return new int[]{0, offset, sign * value};
    }

    double[] parseFloat(String s, int offset) {
        int[] intResult = parseInteger(s, offset);
        double result = intResult[2];
        int flag = intResult[0];
        offset = intResult[1];
        if (flag != 0) {
            return new double[]{flag, offset, result};
        }

        int n = s.length();
        if (offset > n || s.charAt(offset - 1) != '.') {
            return new double[]{0, offset, result};
        }

        offset++; // consume '.'
        double multiplier = result >= 0 ? 0.1 : -0.1;
        boolean found = false;
        while (offset <= n) {
            int code = s.charAt(offset - 1);
            if (code < 48 || code > 57) break;
            result += (code - 48) * multiplier;
            multiplier /= 10;
            offset++;
            found = true;
        }

        if (!found) return new double[]{1, offset, result};

        if (offset > n || (s.charAt(offset - 1) != 'e' && s.charAt(offset - 1) != 'E')) {
            return new double[]{0, offset, result};
        }

        offset++; // consume 'e'/'E'
        if (offset <= n && s.charAt(offset - 1) == '+') {
            offset++;
        }

        int[] expResult = parseInteger(s, offset);
        if (expResult[0] != 0) return new double[]{expResult[0], expResult[1], result};
        result *= Math.pow(10, expResult[2]);
        return new double[]{0, expResult[1], result};
    }

    int[] parseSkipValue(String s, int offset) {
        int n = s.length();
        offset = skipWhitespace(s, offset);
        if (offset > n) return new int[]{1, offset};

        char ch = s.charAt(offset - 1);

        if (ch == '"') {
            Object[] sr = parseString(s, offset);
            return new int[]{0, (int) sr[1]};
        } else if (ch == 'n') {
            return parseNull(s, offset);
        } else if (ch == 't') {
            return new int[]{0, offset + 4};
        } else if (ch == 'f') {
            return new int[]{0, offset + 5};
        } else if (ch == '-' || (ch >= '0' && ch <= '9')) {
            double[] fr = parseFloat(s, offset);
            return new int[]{(int) fr[0], (int) fr[1]};
        } else if (ch == '[') {
            offset++;
            offset = skipWhitespace(s, offset);
            if (offset > n) return new int[]{1, offset};
            if (s.charAt(offset - 1) == ']') return new int[]{0, offset + 1};
            while (true) {
                int[] svr = parseSkipValue(s, offset);
                if (svr[0] == 1) return new int[]{1, svr[1]};
                offset = svr[1];
                int[] cr = parseComma(s, offset);
                if (cr[0] == 1) break;
                offset = cr[1];
            }
            offset = skipWhitespace(s, offset);
            if (offset > n || s.charAt(offset - 1) != ']') return new int[]{1, offset};
            return new int[]{0, offset + 1};
        } else if (ch == '{') {
            offset++;
            offset = skipWhitespace(s, offset);
            if (offset > n) return new int[]{1, offset};
            if (s.charAt(offset - 1) == '}') return new int[]{0, offset + 1};
            while (true) {
                offset = skipWhitespace(s, offset);
                if (offset > n || s.charAt(offset - 1) != '"') return new int[]{1, offset};
                // skip key string
                offset++;
                while (offset <= n) {
                    char kch = s.charAt(offset - 1);
                    offset++;
                    if (kch == '"') break;
                    if (kch == '\\') offset++;
                }
                offset = skipWhitespace(s, offset);
                if (offset > n || s.charAt(offset - 1) != ':') return new int[]{1, offset};
                offset++;
                int[] svr = parseSkipValue(s, offset);
                if (svr[0] == 1) return new int[]{1, svr[1]};
                offset = svr[1];
                int[] cr = parseComma(s, offset);
                if (cr[0] == 1) break;
                offset = cr[1];
            }
            offset = skipWhitespace(s, offset);
            if (offset > n || s.charAt(offset - 1) != '}') return new int[]{1, offset};
            return new int[]{0, offset + 1};
        } else {
            return new int[]{1, offset};
        }
    }

    int[] parseFindValue(String s, int offset, String key) {
        int cur = offset;
        while (true) {
            Object[] kr = parseObjectKey(s, cur);
            int flag = (int) kr[0];
            cur = (int) kr[1];
            String foundKey = (String) kr[2];
            if (flag == 1) return new int[]{1, offset};
            if (foundKey.trim().equals(key.trim())) {
                return new int[]{0, cur};
            }
            int[] svr = parseSkipValue(s, cur);
            if (svr[0] == 1) return new int[]{1, offset};
            cur = svr[1];
            int[] cr = parseComma(s, cur);
            if (cr[0] == 1) return new int[]{1, offset};
            cur = cr[1];
        }
    }
}

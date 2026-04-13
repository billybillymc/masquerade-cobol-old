package com.modernization.masquerade.runner;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

/**
 * Entry point for the Java side of the differential harness runner contract.
 *
 * <p>Reads a single JSON request from stdin:
 * <pre>
 *   {"program": "COSGN00C", "vector_id": "V001",
 *    "inputs":  {"USERID": "ADMIN001", "PASSWD": "PASS1234"}}
 * </pre>
 *
 * Dispatches to the registered {@link ProgramRunner} for that program and
 * writes a JSON response to stdout:
 * <pre>
 *   {"vector_id": "V001",
 *    "outputs": {"XCTL_TARGET": "COADM01C", ...},
 *    "errors":  []}
 * </pre>
 *
 * <p>Exit code 0 always — runner-level failures (unknown program, exception
 * inside the program) are reported via the {@code errors} array, not via
 * non-zero exit. The Python {@code JavaRunner} parses both. Hard exit codes
 * are reserved for jar-level failures (bad JSON, classpath errors).
 */
public final class RunnerMain {

    private static final ObjectMapper MAPPER = new ObjectMapper();

    public static void main(String[] args) {
        try {
            TypeReference<Map<String, Object>> ref = new TypeReference<>() {};
            Map<String, Object> request = MAPPER.readValue(System.in, ref);

            String program = asString(request.get("program"));
            String vectorId = asString(request.get("vector_id"));
            Map<String, String> inputs = asStringMap(request.get("inputs"));

            Map<String, Object> response = new LinkedHashMap<>();
            response.put("vector_id", vectorId);

            ProgramRunner runner = ProgramRegistry.get(program);
            if (runner == null) {
                response.put("outputs", new LinkedHashMap<String, String>());
                response.put("errors", List.of(
                        "Unknown program: " + program
                                + " (registered: " + ProgramRegistry.registered() + ")"
                ));
            } else {
                try {
                    Map<String, String> outputs = runner.runVector(inputs);
                    response.put("outputs", outputs == null ? new LinkedHashMap<>() : outputs);
                    response.put("errors", new ArrayList<String>());
                } catch (Exception e) {
                    response.put("outputs", new LinkedHashMap<String, String>());
                    response.put("errors", List.of(
                            e.getClass().getSimpleName() + ": " + e.getMessage()
                    ));
                }
            }

            MAPPER.writeValue(System.out, response);
            System.out.println();  // newline so Python's text-mode subprocess sees a clean EOL
        } catch (Exception e) {
            // Hard failure — bad JSON, missing class, etc. Surface to stderr and exit non-zero.
            System.err.println("RunnerMain hard failure: " + e.getClass().getSimpleName() + ": " + e.getMessage());
            e.printStackTrace(System.err);
            System.exit(2);
        }
    }

    private static String asString(Object o) {
        return o == null ? "" : o.toString();
    }

    @SuppressWarnings("unchecked")
    private static Map<String, String> asStringMap(Object o) {
        Map<String, String> result = new LinkedHashMap<>();
        if (o instanceof Map) {
            for (Map.Entry<String, Object> e : ((Map<String, Object>) o).entrySet()) {
                result.put(e.getKey(), e.getValue() == null ? "" : e.getValue().toString());
            }
        }
        return result;
    }
}

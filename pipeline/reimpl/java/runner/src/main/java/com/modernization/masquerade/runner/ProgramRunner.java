package com.modernization.masquerade.runner;

import java.util.Map;

/**
 * The contract every Java COBOL reimplementation implements so the differential
 * harness runner can invoke it without knowing program-specific argument shapes.
 *
 * <p>Mirrors the {@code run_vector(inputs: dict) -> dict} convention used by
 * the Python reimplementations. Inputs and outputs are both string-keyed maps
 * with string values — same wire format as the JSON contract documented in
 * {@code pipeline/vector_runner.py}.
 */
public interface ProgramRunner {

    /**
     * Run a single test vector through this program's business logic.
     *
     * @param inputs Map of canonical input field names to string values
     * @return Map of canonical output field names to string values
     * @throws Exception if the program fails — the runner dispatcher will
     *         catch and report it as a structured error in the JSON response
     */
    Map<String, String> runVector(Map<String, String> inputs) throws Exception;
}

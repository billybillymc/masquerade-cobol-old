package com.modernization.masquerade.cobol;

/**
 * Raised when {@link CobolDecimal.OnSizeError#RAISE} is configured and a value
 * exceeds the PIC capacity of the target field.
 *
 * <p>Parity: mirrors {@code CobolOverflowError} in {@code pipeline/cobol_decimal.py}.
 */
public class CobolOverflowError extends ArithmeticException {

    public CobolOverflowError(String message) {
        super(message);
    }
}

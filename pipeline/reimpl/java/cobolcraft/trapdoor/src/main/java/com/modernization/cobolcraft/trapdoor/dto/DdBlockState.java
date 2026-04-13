package com.modernization.cobolcraft.trapdoor.dto;

import com.modernization.masquerade.cobol.CobolDecimal;

/**
 * Data structure from COBOL copybook DD-BLOCK-STATE.
 * 2 fields extracted from PIC clauses.
 */
public class DdBlockState {
    private String prefixPropertyName = "";
    private String prefixPropertyValue = "";

    public String getPrefixPropertyName() { return prefixPropertyName; }
    public void setPrefixPropertyName(String value) { this.prefixPropertyName = value; }
    public String getPrefixPropertyValue() { return prefixPropertyValue; }
    public void setPrefixPropertyValue(String value) { this.prefixPropertyValue = value; }
}

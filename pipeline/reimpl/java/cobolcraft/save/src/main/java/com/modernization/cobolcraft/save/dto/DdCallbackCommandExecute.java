package com.modernization.cobolcraft.save.dto;

import com.modernization.masquerade.cobol.CobolDecimal;

/**
 * Data structure from COBOL copybook DD-CALLBACK-COMMAND-EXECUTE.
 * 1 fields extracted from PIC clauses.
 */
public class DdCallbackCommandExecute {
    private String lkPartValue = "";

    public String getLkPartValue() { return lkPartValue; }
    public void setLkPartValue(String value) { this.lkPartValue = value; }
}

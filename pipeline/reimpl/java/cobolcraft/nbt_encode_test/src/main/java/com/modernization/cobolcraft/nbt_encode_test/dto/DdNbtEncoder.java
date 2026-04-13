package com.modernization.cobolcraft.nbt_encode_test.dto;

import com.modernization.masquerade.cobol.CobolDecimal;

/**
 * Data structure from COBOL copybook DD-NBT-ENCODER.
 * 2 fields extracted from PIC clauses.
 */
public class DdNbtEncoder {
    private String nbtencStackType = "";
    private String nbtencStackListType = "";

    public String getNbtencStackType() { return nbtencStackType; }
    public void setNbtencStackType(String value) { this.nbtencStackType = value; }
    public String getNbtencStackListType() { return nbtencStackListType; }
    public void setNbtencStackListType(String value) { this.nbtencStackListType = value; }
}

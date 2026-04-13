package com.modernization.cobolcraft.nbt_decode_test.dto;

import com.modernization.masquerade.cobol.CobolDecimal;

/**
 * Data structure from COBOL copybook DD-NBT-DECODER.
 * 2 fields extracted from PIC clauses.
 */
public class DdNbtDecoder {
    private String nbtdecStackType = "";
    private String nbtdecStackListType = "";

    public String getNbtdecStackType() { return nbtdecStackType; }
    public void setNbtdecStackType(String value) { this.nbtdecStackType = value; }
    public String getNbtdecStackListType() { return nbtdecStackListType; }
    public void setNbtdecStackListType(String value) { this.nbtdecStackListType = value; }
}

package com.modernization.cobolcraft.blocks_parse_state.dto;

import com.modernization.masquerade.cobol.CobolDecimal;
import java.util.ArrayList;
import java.util.List;

/**
 * Data structure from COBOL copybook DD-BLOCKS.
 * 5 fields extracted from PIC clauses.
 */
public class DdBlocks {
    private String blockEntryName = "";
    private String blockEntryType = "";
    private String blockEntryPropertyName = "";
    private List<String> blockEntryPropertyValue = new ArrayList<>(32);
    private String blockNamesEntryName = "";

    public String getBlockEntryName() { return blockEntryName; }
    public void setBlockEntryName(String value) { this.blockEntryName = value; }
    public String getBlockEntryType() { return blockEntryType; }
    public void setBlockEntryType(String value) { this.blockEntryType = value; }
    public String getBlockEntryPropertyName() { return blockEntryPropertyName; }
    public void setBlockEntryPropertyName(String value) { this.blockEntryPropertyName = value; }
    public List<String> getBlockEntryPropertyValue() { return blockEntryPropertyValue; }
    public void setBlockEntryPropertyValue(List<String> value) { this.blockEntryPropertyValue = value; }
    public String getBlockNamesEntryName() { return blockNamesEntryName; }
    public void setBlockNamesEntryName(String value) { this.blockNamesEntryName = value; }
}

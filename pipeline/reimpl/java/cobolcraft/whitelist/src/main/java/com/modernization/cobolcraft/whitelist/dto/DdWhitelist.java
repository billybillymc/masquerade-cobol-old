package com.modernization.cobolcraft.whitelist.dto;

import com.modernization.masquerade.cobol.CobolDecimal;

/**
 * Data structure from COBOL copybook DD-WHITELIST.
 * 2 fields extracted from PIC clauses.
 */
public class DdWhitelist {
    private String whitelistName = "";
    private String whitelistUuid = "";

    public String getWhitelistName() { return whitelistName; }
    public void setWhitelistName(String value) { this.whitelistName = value; }
    public String getWhitelistUuid() { return whitelistUuid; }
    public void setWhitelistUuid(String value) { this.whitelistUuid = value; }
}

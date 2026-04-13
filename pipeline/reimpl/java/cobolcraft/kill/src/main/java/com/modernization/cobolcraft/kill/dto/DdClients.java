package com.modernization.cobolcraft.kill.dto;

import com.modernization.masquerade.cobol.CobolDecimal;

/**
 * Data structure from COBOL copybook DD-CLIENTS.
 * 2 fields extracted from PIC clauses.
 */
public class DdClients {
    private String clientHndl = "";
    private int clientErrnoSend = 0;

    public String getClientHndl() { return clientHndl; }
    public void setClientHndl(String value) { this.clientHndl = value; }
    public int getClientErrnoSend() { return clientErrnoSend; }
    public void setClientErrnoSend(int value) { this.clientErrnoSend = value; }
}

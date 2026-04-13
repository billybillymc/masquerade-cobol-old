package com.modernization.cobolcraft.blocks.dto;

import com.modernization.masquerade.cobol.CobolDecimal;

/**
 * Data structure from COBOL copybook DD-PLAYERS.
 * 2 fields extracted from PIC clauses.
 */
public class DdPlayers {
    private String playerUuid = "";
    private String playerName = "";

    public String getPlayerUuid() { return playerUuid; }
    public void setPlayerUuid(String value) { this.playerUuid = value; }
    public String getPlayerName() { return playerName; }
    public void setPlayerName(String value) { this.playerName = value; }
}

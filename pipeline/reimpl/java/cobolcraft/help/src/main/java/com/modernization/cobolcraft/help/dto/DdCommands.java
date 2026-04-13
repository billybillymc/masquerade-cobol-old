package com.modernization.cobolcraft.help.dto;

import com.modernization.masquerade.cobol.CobolDecimal;

/**
 * Data structure from COBOL copybook DD-COMMANDS.
 * 2 fields extracted from PIC clauses.
 */
public class DdCommands {
    private String commandName = "";
    private String commandHelp = "";

    public String getCommandName() { return commandName; }
    public void setCommandName(String value) { this.commandName = value; }
    public String getCommandHelp() { return commandHelp; }
    public void setCommandHelp(String value) { this.commandHelp = value; }
}

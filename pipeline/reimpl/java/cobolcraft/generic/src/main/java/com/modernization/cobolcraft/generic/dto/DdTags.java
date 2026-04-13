package com.modernization.cobolcraft.generic.dto;

import com.modernization.masquerade.cobol.CobolDecimal;

/**
 * Data structure from COBOL copybook DD-TAGS.
 * 4 fields extracted from PIC clauses.
 */
public class DdTags {
    private String tagsRegistryName = "";
    private String tagsRegistryTagName = "";
    private String tagsCurrentTagName = "";
    private String tagsCurrentTagEntry = "";

    public String getTagsRegistryName() { return tagsRegistryName; }
    public void setTagsRegistryName(String value) { this.tagsRegistryName = value; }
    public String getTagsRegistryTagName() { return tagsRegistryTagName; }
    public void setTagsRegistryTagName(String value) { this.tagsRegistryTagName = value; }
    public String getTagsCurrentTagName() { return tagsCurrentTagName; }
    public void setTagsCurrentTagName(String value) { this.tagsCurrentTagName = value; }
    public String getTagsCurrentTagEntry() { return tagsCurrentTagEntry; }
    public void setTagsCurrentTagEntry(String value) { this.tagsCurrentTagEntry = value; }
}

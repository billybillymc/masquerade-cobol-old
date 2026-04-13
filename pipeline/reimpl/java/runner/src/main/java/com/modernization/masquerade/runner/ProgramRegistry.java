package com.modernization.masquerade.runner;

import com.modernization.masquerade.runner.programs.Cbact01c;
import com.modernization.masquerade.runner.programs.Cbact02c;
import com.modernization.masquerade.runner.programs.Cbact03c;
import com.modernization.masquerade.runner.programs.Cbact04c;
import com.modernization.masquerade.runner.programs.Cbcus01c;
import com.modernization.masquerade.runner.programs.Cbexport;
import com.modernization.masquerade.runner.programs.Cbimport;
import com.modernization.masquerade.runner.programs.Cbstm03a;
import com.modernization.masquerade.runner.programs.Cbstm03b;
import com.modernization.masquerade.runner.programs.Cbtrn01c;
import com.modernization.masquerade.runner.programs.Cbtrn02c;
import com.modernization.masquerade.runner.programs.Cbtrn03c;
import com.modernization.masquerade.runner.programs.CcJsonParse;
import com.modernization.masquerade.runner.programs.Coactupc;
import com.modernization.masquerade.runner.programs.Coactvwc;
import com.modernization.masquerade.runner.programs.Coadm01c;
import com.modernization.masquerade.runner.programs.Cobil00c;
import com.modernization.masquerade.runner.programs.Cobswait;
import com.modernization.masquerade.runner.programs.CobolDecimalOp;
import com.modernization.masquerade.runner.programs.Cocrdlic;
import com.modernization.masquerade.runner.programs.Cocrdslc;
import com.modernization.masquerade.runner.programs.Cocrdupc;
import com.modernization.masquerade.runner.programs.Comen01c;
import com.modernization.masquerade.runner.programs.Corpt00c;
import com.modernization.masquerade.runner.programs.Cosgn00c;
import com.modernization.masquerade.runner.programs.Cotrn00c;
import com.modernization.masquerade.runner.programs.Cotrn01c;
import com.modernization.masquerade.runner.programs.Cotrn02c;
import com.modernization.masquerade.runner.programs.Cousr00c;
import com.modernization.masquerade.runner.programs.Cousr01c;
import com.modernization.masquerade.runner.programs.Cousr02c;
import com.modernization.masquerade.runner.programs.Cousr03c;
import com.modernization.masquerade.runner.programs.Csutldtc;
import com.modernization.masquerade.runner.programs.Dbcrfun;
import com.modernization.masquerade.runner.programs.StarTrek;
import com.modernization.masquerade.runner.programs.TaxeFonciere;
import com.modernization.masquerade.runner.programs.Uuid;

import java.util.HashMap;
import java.util.Map;

/**
 * Static registry mapping COBOL program IDs to their Java reimplementations.
 *
 * <p>New programs register themselves here as they're hand-ported. The
 * dispatcher in {@link RunnerMain} looks up the right runner by name from
 * the JSON request's {@code program} field.
 */
public final class ProgramRegistry {

    private static final Map<String, ProgramRunner> REGISTRY = new HashMap<>();

    static {
        // W6 pilot — first program ported to Java
        REGISTRY.put("COSGN00C", new Cosgn00c());
        // Second pilot — date validation utility
        REGISTRY.put("CSUTLDTC", new Csutldtc());
        // Third pilot — CBSA debit/credit engine (first to use CobolDecimal)
        REGISTRY.put("DBCRFUN", new Dbcrfun());
        // Synthetic op dispatcher for CobolDecimal cross-language fuzz tests.
        // NOT a real reimplementation — exercises CobolDecimal directly.
        REGISTRY.put("COBOL_DECIMAL_OP", new CobolDecimalOp());
        // Fourth pilot — CardDemo batch interest calculator
        REGISTRY.put("CBACT04C", new Cbact04c());
        // Fifth pilot — CobolCraft UUID encoder/decoder
        REGISTRY.put("UUID", new Uuid());
        // Sixth pilot — CardDemo daily transaction posting
        REGISTRY.put("CBTRN02C", new Cbtrn02c());
        // Seventh pilot — French property tax (fourth codebase)
        REGISTRY.put("TAXE_FONCIERE", new TaxeFonciere());
        // Eighth pilot — Star Trek game core engine (fifth and final codebase)
        REGISTRY.put("STAR_TREK", new StarTrek());
        // Batch file readers — simple sequential display programs
        REGISTRY.put("CBACT02C", new Cbact02c());
        REGISTRY.put("CBACT03C", new Cbact03c());
        REGISTRY.put("CBCUS01C", new Cbcus01c());
        // Wait utility — coercion only, no sleep
        REGISTRY.put("COBSWAIT", new Cobswait());
        // CICS screen programs — admin/user menus, bill pay, transactions
        REGISTRY.put("COADM01C", new Coadm01c());
        REGISTRY.put("COMEN01C", new Comen01c());
        REGISTRY.put("COBIL00C", new Cobil00c());
        REGISTRY.put("COTRN00C", new Cotrn00c());
        REGISTRY.put("COTRN01C", new Cotrn01c());
        REGISTRY.put("COTRN02C", new Cotrn02c());
        // User management screens
        REGISTRY.put("COUSR00C", new Cousr00c());
        REGISTRY.put("COUSR01C", new Cousr01c());
        REGISTRY.put("COUSR02C", new Cousr02c());
        REGISTRY.put("COUSR03C", new Cousr03c());
        // Credit card screens
        REGISTRY.put("COCRDLIC", new Cocrdlic());
        REGISTRY.put("COCRDSLC", new Cocrdslc());
        REGISTRY.put("COCRDUPC", new Cocrdupc());
        // Account update screen
        REGISTRY.put("COACTUPC", new Coactupc());
        // Account view screen
        REGISTRY.put("COACTVWC", new Coactvwc());
        // Report submission screen
        REGISTRY.put("CORPT00C", new Corpt00c());
        // Batch programs — account reader, transaction validation/reports, statements
        REGISTRY.put("CBACT01C", new Cbact01c());
        REGISTRY.put("CBTRN01C", new Cbtrn01c());
        REGISTRY.put("CBTRN03C", new Cbtrn03c());
        REGISTRY.put("CBSTM03A", new Cbstm03a());
        REGISTRY.put("CBSTM03B", new Cbstm03b());
        REGISTRY.put("CBEXPORT", new Cbexport());
        REGISTRY.put("CBIMPORT", new Cbimport());
        // CobolCraft JSON parser
        REGISTRY.put("CC_JSON_PARSE", new CcJsonParse());
    }

    private ProgramRegistry() {}

    /** Look up a program runner by its COBOL program ID. Null if not registered. */
    public static ProgramRunner get(String programId) {
        if (programId == null) return null;
        return REGISTRY.get(programId.toUpperCase());
    }

    /** Return the set of registered program IDs (for diagnostics). */
    public static java.util.Set<String> registered() {
        return REGISTRY.keySet();
    }
}

package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.math.BigDecimal;
import java.math.MathContext;
import java.math.RoundingMode;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * Java reimplementation of EFITA3B8 — Taxe Fonciere Batie (French built property tax).
 * Mirrors {@code pipeline/reimpl/taxe_fonciere.py} byte-for-byte.
 *
 * <p>Fourth codebase exercised in the Java track (CardDemo, CBSA, CobolCraft,
 * and now taxe-fonciere). Heavy arithmetic: 8 cotisation calculations, 6 OM zone
 * evaluations (EVALUATE on zone codes), 3 fee brackets with rebalancing logic.
 * All computations use COBOL ROUNDED semantics (ROUND_HALF_UP to integer).
 */
public class TaxeFonciere implements ProgramRunner {

    private static final MathContext PY_CTX = new MathContext(28, RoundingMode.HALF_EVEN);
    private static final BigDecimal BD_100 = new BigDecimal("100");

    // Fee rate constants (WORKING-STORAGE lines 99-104)
    private static final BigDecimal F800_FRS = new BigDecimal("0.0800");
    private static final BigDecimal F800_ARN = new BigDecimal("0.0440");
    private static final BigDecimal F300_FRS = new BigDecimal("0.0300");
    private static final BigDecimal F300_ARN = new BigDecimal("0.0100");
    private static final BigDecimal F900_FRS = new BigDecimal("0.0900");
    private static final BigDecimal F900_ARN = new BigDecimal("0.0540");

    private static final Set<String> VALID_GTAUOM = Set.of(
            "  ", " P", "P ", "RA", "RB", "RC", "RD", "RE"
    );

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenarioName = inputs.getOrDefault("SCENARIO", "").toUpperCase();
        Object[] scn = buildScenario(scenarioName);
        if (scn == null) {
            Map<String, String> err = new LinkedHashMap<>();
            err.put("error", "unknown scenario: '" + scenarioName + "'");
            return err;
        }
        CombatInput combat = (CombatInput) scn[0];
        AllRates rates = (AllRates) scn[1];

        int[] crRc = new int[]{0, 0};
        Retour retour = calculateTaxBatie(combat, rates, crRc);

        Map<String, String> out = new LinkedHashMap<>();
        out.put("CR", String.valueOf(crRc[0]));
        out.put("RC", String.valueOf(crRc[1]));
        out.put("MCTCOM", String.valueOf(retour.mctcom));
        out.put("MCTDEP", String.valueOf(retour.mctdep));
        out.put("MCTSYN", String.valueOf(retour.mctsyn));
        out.put("MCTCU", String.valueOf(retour.mctcu));
        out.put("MCOGE3", String.valueOf(retour.mcoge3));
        out.put("MCOTA3", String.valueOf(retour.mcota3));
        out.put("MCBT13_0", String.valueOf(retour.mcbt13[0]));
        out.put("MCBT13_1", String.valueOf(retour.mcbt13[1]));
        out.put("MCBTSA", String.valueOf(retour.mcbtsa));
        out.put("TCTOM", String.valueOf(retour.tctom));
        out.put("TCTHFR", String.valueOf(retour.tcthfr));
        out.put("MFA300", String.valueOf(retour.mfa300));
        out.put("MFN300", String.valueOf(retour.mfn300));
        out.put("MFA800", String.valueOf(retour.mfa800));
        out.put("MFN800", String.valueOf(retour.mfn800));
        out.put("MFA900", String.valueOf(retour.mfa900));
        out.put("MFN900", String.valueOf(retour.mfn900));
        out.put("TCTFRA", String.valueOf(retour.tctfra));
        out.put("TCTDU", String.valueOf(retour.tctdu));
        out.put("MVLTIM", String.valueOf(retour.mvltim));
        return out;
    }

    /** COBOL COMPUTE ... ROUNDED → ROUND_HALF_UP to integer. */
    private static int cobolRound(BigDecimal value) {
        return value.setScale(0, RoundingMode.HALF_UP).intValue();
    }

    /** base * rate / 100, then COBOL ROUNDED to integer. */
    private static int cotisation(int base, BigDecimal rate) {
        return cobolRound(
                new BigDecimal(base).multiply(rate, PY_CTX).divide(BD_100, PY_CTX)
        );
    }

    Retour calculateTaxBatie(CombatInput combat, AllRates rates, int[] crRc) {
        Retour retour = new Retour();
        int cr = 0, rc = 0;

        // Validation
        if (!"2".equals(combat.ccobnb)) { cr = 12; rc = 1; }
        if (!"2018".equals(combat.dan)) { if (cr == 0) { cr = 12; rc = 2; } }

        // OM zone validation + zero-out blanks
        for (int i = 0; i < 6; i++) {
            if (!VALID_GTAUOM.contains(combat.abaomCode[i])) { cr = 12; rc = 5; }
            if ("  ".equals(combat.abaomCode[i]) || combat.abaomCode[i].trim().isEmpty()) {
                combat.abaomBase[i] = 0;
            }
        }

        if (cr <= 0) {
            // --- Cotisations ---
            int coticom = cotisation(combat.mbacom, rates.taucom);
            int cotidep = cotisation(combat.mbadep, rates.taudep);
            int cotisyn = cotisation(combat.mbasyn, rates.tausyn);
            int coticu  = cotisation(combat.mbacu,  rates.taucu);
            int mcoge3  = cotisation(combat.mbage3, rates.taugem);
            int mcota3  = cotisation(combat.mbata3, rates.tautas);
            int cotitsen1 = cotisation(combat.mbbt13_0, rates.tautsen0);
            int cotitsen2 = cotisation(combat.mbbt13_1, rates.tautsen1);
            int mcbtsa  = cobolRound(new BigDecimal(cotitsen1 + cotitsen2 + mcota3));

            // --- OM cotisations ---
            int[] cotisOm = new int[6];
            for (int i = 0; i < 6; i++) {
                String code = combat.abaomCode[i];
                int base = combat.abaomBase[i];
                switch (code) {
                    case "P ": case " P":
                        cotisOm[i] = cotisation(base, rates.tauom[0]); break;
                    case "RA":
                        cotisOm[i] = cotisation(base, rates.tauom[1]); break;
                    case "RB":
                        cotisOm[i] = cotisation(base, rates.tauom[2]); break;
                    case "RC":
                        cotisOm[i] = cotisation(base, rates.tauom[3]); break;
                    case "RD":
                        cotisOm[i] = cotisation(base, rates.tauom[4]); break;
                    case "RE":
                        cotisOm[i] = cotisation(base, rates.tauom[5]); break;
                    default:
                        cotisOm[i] = 0; break;
                }
            }

            int cotisOmi = combat.mvltim;
            int wTotcotom = 0;
            for (int v : cotisOm) wTotcotom += v;
            wTotcotom += cotisOmi;

            // --- Frais ---
            int wTotcot3 = coticom + cotidep + coticu + mcoge3;
            int wTotcot8 = wTotcotom + cotisyn + mcota3;
            int wTotcot9 = cotitsen1 + cotitsen2;

            int fa300 = cobolRound(new BigDecimal(wTotcot3).multiply(F300_ARN, PY_CTX));
            int wFrais300 = cobolRound(new BigDecimal(wTotcot3).multiply(F300_FRS, PY_CTX));
            int fn300 = wFrais300 - fa300;

            int fa800 = cobolRound(new BigDecimal(wTotcot8).multiply(F800_ARN, PY_CTX));
            int wFrais800 = cobolRound(new BigDecimal(wTotcot8).multiply(F800_FRS, PY_CTX));
            int fn800 = wFrais800 - fa800;

            int fa900 = cobolRound(new BigDecimal(wTotcot9).multiply(F900_ARN, PY_CTX));
            int wFrais900 = cobolRound(new BigDecimal(wTotcot9).multiply(F900_FRS, PY_CTX));
            int fn900 = wFrais900 - fa900;

            // Rebalancing
            if (fa800 < fn800) { fa800++; fn800--; }
            if (fa900 < fn900) { fa900++; fn900--; }

            // --- Populate retour ---
            retour.mctcom = coticom;
            retour.mctdep = cotidep;
            retour.mctsyn = cotisyn;
            retour.mctcu = coticu;
            retour.mcoge3 = mcoge3;
            retour.mcota3 = mcota3;
            retour.mcbt13[0] = cotitsen1;
            retour.mcbt13[1] = cotitsen2;
            retour.mcbtsa = mcbtsa;
            retour.tctom = wTotcotom;
            retour.mvltim = cotisOmi;
            retour.tcthfr = wTotcot3 + wTotcot8 + wTotcot9;
            retour.mfa300 = fa300; retour.mfn300 = fn300;
            retour.mfa800 = fa800; retour.mfn800 = fn800;
            retour.mfa900 = fa900; retour.mfn900 = fn900;
            retour.tctfra = fa300 + fn300 + fa800 + fn800 + fa900 + fn900;
            retour.tctdu = retour.tcthfr + retour.tctfra;
        }

        crRc[0] = cr;
        crRc[1] = rc;
        return retour;
    }

    // ── Scenarios ─────────────────────────────────────────────────────────

    private Object[] buildScenario(String name) {
        switch (name) {
            case "HAPPY_BASIC": return scenarioHappyBasic();
            case "WITH_OM":     return scenarioWithOm();
            case "BAD_CCOBNB":  return scenarioBadCcobnb();
            case "BAD_YEAR":    return scenarioBadYear();
            default: return null;
        }
    }

    private Object[] scenarioHappyBasic() {
        CombatInput c = new CombatInput();
        c.ccobnb = "2"; c.dan = "2018"; c.cc2dep = "75"; c.ccodir = "2";
        c.ccocom = "056"; c.dsrpar = "A"; c.cgroup = "P"; c.nnupro = 12345;
        c.mbacom = 10000; c.mbadep = 10000; c.mbasyn = 5000; c.mbacu = 5000;
        c.mbage3 = 10000; c.mbata3 = 10000; c.mbbt13_0 = 5000; c.mbbt13_1 = 5000;
        AllRates r = new AllRates();
        r.taucom = bd("18.99"); r.taudep = bd("12.50"); r.tausyn = bd("2.00");
        r.taucu = bd("4.00"); r.taugem = bd("0.50"); r.tautas = bd("1.00");
        r.tautsen0 = bd("0.80"); r.tautsen1 = bd("0.20");
        return new Object[]{c, r};
    }

    private Object[] scenarioWithOm() {
        CombatInput c = new CombatInput();
        c.ccobnb = "2"; c.dan = "2018"; c.cc2dep = "75"; c.ccodir = "2";
        c.ccocom = "056"; c.dsrpar = "A"; c.cgroup = "P"; c.nnupro = 12345;
        c.mbacom = 10000; c.mbadep = 10000; c.mbasyn = 5000; c.mbacu = 5000;
        c.mbage3 = 10000; c.mbata3 = 10000; c.mbbt13_0 = 5000; c.mbbt13_1 = 5000;
        c.abaomCode = new String[]{"P ", "RA", "RB", "  ", "  ", "  "};
        c.abaomBase = new int[]{10000, 8000, 6000, 0, 0, 0};
        c.mvltim = 0;
        AllRates r = new AllRates();
        r.taucom = bd("18.99"); r.taudep = bd("12.50"); r.tausyn = bd("2.00");
        r.taucu = bd("4.00"); r.taugem = bd("0.50"); r.tautas = bd("1.00");
        r.tautsen0 = bd("0.80"); r.tautsen1 = bd("0.20");
        r.tauom = new BigDecimal[]{
                bd("10.00"), bd("7.50"), bd("5.00"),
                bd("3.00"), bd("2.00"), bd("1.00")
        };
        return new Object[]{c, r};
    }

    private Object[] scenarioBadCcobnb() {
        CombatInput c = new CombatInput();
        c.ccobnb = "1"; c.dan = "2018"; c.cc2dep = "75"; c.ccodir = "2";
        c.ccocom = "056"; c.dsrpar = "A"; c.cgroup = "P"; c.nnupro = 12345;
        return new Object[]{c, new AllRates()};
    }

    private Object[] scenarioBadYear() {
        CombatInput c = new CombatInput();
        c.ccobnb = "2"; c.dan = "2017"; c.cc2dep = "75"; c.ccodir = "2";
        c.ccocom = "056"; c.dsrpar = "A"; c.cgroup = "P"; c.nnupro = 12345;
        return new Object[]{c, new AllRates()};
    }

    private static BigDecimal bd(String s) { return new BigDecimal(s); }

    // ── Inner data types ─────────────────────────────────────────────────

    static class CombatInput {
        String ccobnb = ""; String dan = ""; String cc2dep = "";
        String ccodir = ""; String ccocom = ""; String dsrpar = "";
        String cgroup = ""; int nnupro = 0;
        int mbacom = 0, mbadep = 0, mbasyn = 0, mbacu = 0;
        int mbage3 = 0, mbata3 = 0;
        int mbbt13_0 = 0, mbbt13_1 = 0;
        String[] abaomCode = {"  ", "  ", "  ", "  ", "  ", "  "};
        int[] abaomBase = {0, 0, 0, 0, 0, 0};
        int mvltim = 0;
    }

    static class AllRates {
        BigDecimal taucom = BigDecimal.ZERO, taudep = BigDecimal.ZERO;
        BigDecimal tausyn = BigDecimal.ZERO, taucu = BigDecimal.ZERO;
        BigDecimal taugem = BigDecimal.ZERO, tautas = BigDecimal.ZERO;
        BigDecimal tautsen0 = BigDecimal.ZERO, tautsen1 = BigDecimal.ZERO;
        BigDecimal[] tauom = {
                BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO,
                BigDecimal.ZERO, BigDecimal.ZERO, BigDecimal.ZERO
        };
    }

    static class Retour {
        int mctcom, mctdep, mctsyn, mctcu, mcoge3, mcota3;
        int[] mcbt13 = {0, 0};
        int mcbtsa, tctom, mvltim, tcthfr;
        int mfa300, mfn300, mfa800, mfn800, mfa900, mfn900;
        int tctfra, tctdu;
    }
}

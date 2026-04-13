package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.TreeMap;

/**
 * Java reimplementation of the Star Trek COBOL game (ctrek.cob) — full
 * deterministic engine including all game commands.
 *
 * <p>Mirrors the complete {@code pipeline/reimpl/star_trek.py} class.
 */
public class StarTrek implements ProgramRunner {

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "").toUpperCase();

        switch (scenario) {
            case "INIT_STATE": {
                int seed = parseInt(inputs.getOrDefault("SEED", "12345678"));
                int skill = parseInt(inputs.getOrDefault("SKILL_LEVEL", "1"));
                String name = inputs.getOrDefault("CAPTAIN_NAME", "KIRK");
                StarTrekGame game = new StarTrekGame(seed, name, skill);
                return game.galaxyFingerprint();
            }
            case "MISSION_PARAMS": {
                int skill = parseInt(inputs.getOrDefault("SKILL_LEVEL", "1"));
                Map<String, String> out = new LinkedHashMap<>();
                int klingons = skill * 8;
                out.put("KLINGONS", String.valueOf(klingons));
                out.put("STAR_DATES", String.valueOf(klingons));
                out.put("FUEL", "40000");
                out.put("TORPEDOES", "5");
                return out;
            }
            case "SKILL_VALIDATION": {
                String level = inputs.getOrDefault("LEVEL", "1");
                Map<String, String> out = new LinkedHashMap<>();
                try {
                    int n = Integer.parseInt(level.trim());
                    if (n < 1 || n > 4) {
                        out.put("VALID", "N");
                        out.put("MESSAGE", "INVALID SKILL LEVEL");
                    } else {
                        out.put("VALID", "Y");
                        out.put("MESSAGE", "");
                    }
                } catch (NumberFormatException e) {
                    out.put("VALID", "N");
                    out.put("MESSAGE", "INVALID SKILL LEVEL");
                }
                return out;
            }
            case "GAME_STATUS": {
                int seed = parseInt(inputs.getOrDefault("SEED", "12345678"));
                int skill = parseInt(inputs.getOrDefault("SKILL_LEVEL", "1"));
                String name = inputs.getOrDefault("CAPTAIN_NAME", "KIRK");
                StarTrekGame game = new StarTrekGame(seed, name, skill);
                return game.getStatus();
            }
            case "PROCESS_COMMANDS": {
                int seed = parseInt(inputs.getOrDefault("SEED", "12345678"));
                int skill = parseInt(inputs.getOrDefault("SKILL_LEVEL", "1"));
                String name = inputs.getOrDefault("CAPTAIN_NAME", "KIRK");
                StarTrekGame game = new StarTrekGame(seed, name, skill);
                // Flush initial output
                game.getInitialOutput();
                String cmds = inputs.getOrDefault("COMMANDS", "");
                if (!cmds.isEmpty()) {
                    String[] cmdArr = cmds.split(";");
                    for (String cmd : cmdArr) {
                        cmd = cmd.trim();
                        if (!cmd.isEmpty()) {
                            game.processCommand(cmd);
                        }
                    }
                }
                return game.getStatus();
            }
            case "INITIAL_OUTPUT": {
                int seed = parseInt(inputs.getOrDefault("SEED", "12345678"));
                int skill = parseInt(inputs.getOrDefault("SKILL_LEVEL", "1"));
                String name = inputs.getOrDefault("CAPTAIN_NAME", "KIRK");
                StarTrekGame game = new StarTrekGame(seed, name, skill);
                List<String> lines = game.getInitialOutput();
                Map<String, String> out = new LinkedHashMap<>();
                out.put("LINE_COUNT", String.valueOf(lines.size()));
                if (!lines.isEmpty()) {
                    out.put("FIRST_LINE", lines.get(0));
                    out.put("LAST_LINE", lines.get(lines.size() - 1));
                } else {
                    out.put("FIRST_LINE", "");
                    out.put("LAST_LINE", "");
                }
                return out;
            }
            default: {
                Map<String, String> err = new LinkedHashMap<>();
                err.put("error", "unknown scenario: '" + scenario + "'");
                return err;
            }
        }
    }

    private static int parseInt(String s) {
        try { return Integer.parseInt(s.trim()); }
        catch (NumberFormatException e) { return 0; }
    }

    // ══════════════════════════════════════════════════════════════════════
    // Core game engine — full implementation
    // ══════════════════════════════════════════════════════════════════════

    static class StarTrekGame {
        // Master table: 127x127 (1-indexed, [0] unused)
        final char[][] masterTbl = new char[127][127];

        // Mini table: 15x15 (1-indexed, [0] unused)
        final char[][] miniTable = new char[15][15];

        // Star table: 43x43 (1-indexed, [0] unused)
        final char[][] starTable = new char[43][43];

        // Scan table: 15x15 (1-indexed, [0] unused)
        final char[][] scanTable = new char[15][15];

        // Captain name
        String captainName;
        int skillLevel;

        // Output buffer
        List<String> output = new ArrayList<>();

        // Enterprise position in master table
        int mrctr, mkctr;
        // Current quadrant
        int q1, q2, qs1, qs2;
        // HQ quadrant
        int hq1, hq2;
        // Klingon / base / romulon counts
        int kOr, klingons, vab1, vab2;
        // Klingons/romulons/bases in current quadrant
        int klgns, romulons, baseCnt;
        // Star dates
        int sDate, dsDate, wsDate;
        // Time flag
        int timeFlag;
        // RNG state
        double seedX;
        // Misc
        int fuelCount = 40000;
        int torps = 5;
        int nx = 0;
        int shieldCnt = 0;
        int damageCnt = 0;
        int indicateZ = 0;   // 0 = just-starting
        int genrteResult = 0;
        int indicateX = 0;   // 1 = bye-bye
        int indicateY = 0;   // 1 = trap-vec
        int attackFlag = 0;  // 1 = klingons-attacking
        int tooLateFlag = 0;
        int var1 = 1;
        int khTl = 0;

        // Distance tracking
        int distX = 30;
        int distR = 30;
        int distB = 30;
        int ctK = 0;
        int ctR = 0;

        // Distance arrays
        int[] distKStr = new int[46];   // dkc(1..45)
        int[] distRStr = new int[61];   // drc(1..60)

        // Positions found by compute-dist
        int e1, e2, k1, k2, r1, r2, b1, b2;

        // rx = number of K's to skip when destroying nearest
        int rx = 0;
        int qx = 0;

        // Scan keep: cv(1..18)
        int[] scanKeep = new int[19];

        // Game state
        boolean gameOver = false;
        boolean gameWon = false;

        // Generate table
        final char[] generateTable;

        // Seed table (25 chars, COBOL SEED-TABLE)
        static final String SEED_TABLE = "a4hfxnc89kd3jxf5dks3hb3m1";

        StarTrekGame(int seed, String captainName, int skillLevel) {
            this.generateTable = SEED_TABLE.toCharArray();

            String name = captainName.toUpperCase();
            if (name.length() > 12) name = name.substring(0, 12);
            this.captainName = name;
            this.skillLevel = Math.max(1, Math.min(4, skillLevel));

            // -- Skill-based computations --
            // Pad name to 12 chars for computation (like Python ljust(12)[:12])
            String nameX = name;
            while (nameX.length() < 12) nameX += " ";
            int vab6 = 0;
            for (int i = 0; i < nameX.length(); i++) {
                char ch = Character.toLowerCase(nameX.charAt(i));
                if (ch == 'a') vab6++;
                if (ch == 'e') vab6++;
            }
            vab6 += 1;
            int vab5 = 0;
            for (int i = 0; i < nameX.length(); i++) {
                if (nameX.charAt(i) == ' ') vab5++;
            }
            // COMPUTE vab6 ROUNDED = (vab5 / 1.75) + (vab6 / skill-lev)
            vab6 = cobolRound(vab5 / 1.75 + vab6 / (double) this.skillLevel);
            // COMPUTE k-or ROUNDED = (skill-lev * 4) + vab6 + 5
            this.kOr = cobolRound(this.skillLevel * 4.0 + vab6 + 5);
            this.vab1 = 9 - this.skillLevel;
            // COMPUTE vab2 ROUNDED = (skill-lev / 3) * k-or
            this.vab2 = cobolRound((this.skillLevel / 3.0) * this.kOr);
            this.klingons = this.kOr;

            // -- Seed initialisation --
            String seedStr = String.format("%08d", seed);
            int wsMin = Integer.parseInt(seedStr.substring(2, 4));
            int wsSec = Integer.parseInt(seedStr.substring(4, 6));
            int wsSixty = Integer.parseInt(seedStr.substring(6, 8));

            this.sDate = wsMin * 100 + wsSec;
            int dsMinDeadline = wsMin + 16;
            if (dsMinDeadline > 59) {
                this.timeFlag = 1;
            } else {
                this.timeFlag = 0;
            }
            this.dsDate = dsMinDeadline * 100 + wsSec;

            // time-rev: CC SS MM
            String revStrS = String.format("%02d%02d%02d", wsSixty, wsSec, wsMin);
            int revStr = Integer.parseInt(revStrS);
            this.seedX = revStr / 1000000.0;

            // ws-date for too-late tracking
            this.wsDate = this.dsDate;

            // -- Initialize galaxy --
            initializeGalaxy();

            // Build initial output
            buildInitialOutput();
        }

        // ── Output helpers ──────────────────────────────────────────────

        void display(String text) {
            output.add(text);
        }

        List<String> flushOutput() {
            List<String> out = output;
            output = new ArrayList<>();
            return out;
        }

        // ── Properties (Java methods) ───────────────────────────────────

        boolean noWay() {
            return genrteResult == 1;
        }

        boolean trapVec() {
            return indicateY == 1;
        }

        boolean byeBye() {
            return indicateX == 1;
        }

        boolean justStarting() {
            return indicateZ == 0;
        }

        boolean klingonsAttacking() {
            return attackFlag == 1;
        }

        boolean tooLate() {
            return tooLateFlag == 1;
        }

        // ── RNG (1220-roll) ──────────────────────────────────────────────

        int roll(int maxNo) {
            double seedAst = 262147.0 * this.seedX;
            double frac = seedAst - (double)((long) seedAst);
            // PIC V9(6) but 12dp to avoid short cycles
            this.seedX = (long)(frac * 1000000000000.0) / 1000000000000.0;
            int rollX = (int)(this.seedX * maxNo) + 1;
            return rollX;
        }

        int[] dblRoll(int maxNo) {
            int a = roll(maxNo);
            int b = roll(maxNo);
            return new int[]{a, b};
        }

        // ── Generate (8400-generate) ─────────────────────────────────────

        void generate() {
            if (nx > 24) {
                nx = 0;
            }
            nx += 1;
            char ch = generateTable[nx - 1];
            if (Character.isDigit(ch)) {
                genrteResult = 1;   // no-way
            } else {
                indicateY = 0;
                genrteResult = 0;
                if (ch == 'f') {
                    indicateY = 1;  // trap-vec
                }
            }
        }

        // ── Galaxy init (1200-initialize-galaxy) ─────────────────────────

        void initializeGalaxy() {
            // Clear
            for (int r = 0; r < 127; r++)
                for (int c = 0; c < 127; c++)
                    masterTbl[r][c] = ' ';

            // Clear mini table
            for (int r = 0; r < 15; r++)
                for (int c = 0; c < 15; c++)
                    miniTable[r][c] = ' ';

            // Clear star table
            for (int r = 0; r < 43; r++)
                for (int c = 0; c < 43; c++)
                    starTable[r][c] = ' ';

            // Clear scan table
            for (int r = 0; r < 15; r++)
                for (int c = 0; c < 15; c++)
                    scanTable[r][c] = ' ';

            // Stars: 275
            for (int i = 0; i < 275; i++) {
                int[] ab = dblRoll(126);
                masterTbl[ab[0]][ab[1]] = '*';
            }

            // Romulons: vab2
            for (int i = 0; i < vab2; i++) {
                int[] ab = dblRoll(126);
                masterTbl[ab[0]][ab[1]] = 'R';
            }

            // Klingons: kOr, placed in empty cells
            for (int i = 0; i < kOr; i++) {
                int[] ab = dblRoll(126);
                while (masterTbl[ab[0]][ab[1]] != ' ') {
                    ab = dblRoll(126);
                }
                masterTbl[ab[0]][ab[1]] = 'K';
            }

            // Bases: vab1, placed in empty cells
            for (int i = 0; i < vab1; i++) {
                int[] ab = dblRoll(126);
                while (masterTbl[ab[0]][ab[1]] != ' ') {
                    ab = dblRoll(126);
                }
                masterTbl[ab[0]][ab[1]] = 'B';
            }

            // Enterprise: in empty cell
            int[] ab = dblRoll(126);
            while (masterTbl[ab[0]][ab[1]] != ' ') {
                ab = dblRoll(126);
            }
            this.mrctr = ab[0];
            this.mkctr = ab[1];
            masterTbl[this.mrctr][this.mkctr] = 'E';

            // HQ: in empty cell
            ab = dblRoll(126);
            while (masterTbl[ab[0]][ab[1]] != ' ') {
                ab = dblRoll(126);
            }
            masterTbl[ab[0]][ab[1]] = 'H';
            // COBOL: hq1 = (b-1)/14 + 1, hq2 = (a-1)/14 + 1
            this.hq1 = (ab[1] - 1) / 14 + 1;
            this.hq2 = (ab[0] - 1) / 14 + 1;
        }

        // ── Transfer helpers ─────────────────────────────────────────────

        void trans() {
            // 5900-trans: copy from master table to mini table for current quadrant
            int x = (q1 - 1) * 14;
            int y = (q2 - 1) * 14;
            for (int kcntr = 1; kcntr <= 14; kcntr++) {
                for (int rcntr = 1; rcntr <= 14; rcntr++) {
                    int a = y + rcntr;
                    int b = x + kcntr;
                    if (a >= 1 && a <= 126 && b >= 1 && b <= 126) {
                        miniTable[rcntr][kcntr] = masterTbl[a][b];
                    } else {
                        miniTable[rcntr][kcntr] = ' ';
                    }
                }
            }
        }

        void transBack() {
            // 5400-trans-back: copy mini table back to master table
            int x = (q1 - 1) * 14;
            int y = (q2 - 1) * 14;
            for (int kcntr = 1; kcntr <= 14; kcntr++) {
                for (int rcntr = 1; rcntr <= 14; rcntr++) {
                    int a = y + rcntr;
                    int b = x + kcntr;
                    if (a >= 1 && a <= 126 && b >= 1 && b <= 126) {
                        masterTbl[a][b] = miniTable[rcntr][kcntr];
                    }
                }
            }
        }

        void transStar() {
            // 7650-trans-star: copy 42x42 region from master to star table
            int q9;
            if (q1 == 1) {
                q9 = 2;
            } else if (q1 == 9) {
                q9 = 8;
            } else {
                q9 = q1;
            }
            int r9;
            if (q2 == 1) {
                r9 = 2;
            } else if (q2 == 9) {
                r9 = 8;
            } else {
                r9 = q2;
            }
            int w = (q9 - 2) * 14;
            int z = (r9 - 2) * 14;
            for (int rctr = 1; rctr <= 42; rctr++) {
                for (int kctr = 1; kctr <= 42; kctr++) {
                    int a = z + rctr;
                    int b = w + kctr;
                    if (a >= 1 && a <= 126 && b >= 1 && b <= 126) {
                        starTable[rctr][kctr] = masterTbl[a][b];
                    } else {
                        starTable[rctr][kctr] = ' ';
                    }
                }
            }
        }

        // ── Display helpers ──────────────────────────────────────────────

        void displayQuadrantGrid() {
            // 6500-display-mt / 6600-mini-dis / 6700-mini-mod
            display("= = = = = = = = = = = = = = = =");
            for (int row = 1; row <= 14; row++) {
                char[] mdRow = new char[29];
                for (int i = 0; i < 29; i++) mdRow[i] = ' ';
                for (int col = 1; col <= 14; col++) {
                    int modCtr = 2 * col;
                    if (modCtr < 29) {
                        mdRow[modCtr] = miniTable[row][col];
                    }
                }
                display("=" + new String(mdRow) + " =");
            }
            display("= = = = = = = = = = = = = = = =");
        }

        String conRedStr() {
            return String.format("*Condition RED* %02d Klingons in quadrant", klgns);
        }

        String conGreenStr() {
            return "*Condition GREEN*";
        }

        String quadrantStr() {
            return String.format("Quadrant %d,%d    STAR DATE: %04d", q1, q2, sDate);
        }

        // ── Initial output (0100-housekeeping display portion) ───────────

        void buildInitialOutput() {
            display("      ");
            display("      *STAR TREK* ");
            display("      ");
            display("Congratulations - you have just been appointed ");
            display("Captain of the U.S.S. Enterprise. ");
            display("      ");
            display("      ");
            display("      *MESSAGE FROM STAR FLEET COMMAND* ");
            display("      ");
            display("Attention - Captain " + captainName);
            display("Your mission is to destroy the ");
            display(String.format("%02d Klingon ships that have invaded ", kOr));
            display("the galaxy to attack Star Fleet HQ ");
            display(String.format("on star date %04d - giving you 16 star dates.", dsDate));
            // Initial quadrant display (4000-display-g)
            displayG();
            indicateZ = 1;
        }

        // ── 4000-display-g ───────────────────────────────────────────────

        void displayG() {
            // 4000-display-g: determine quadrant, display it, handle klingon fire
            klgns = 0;
            romulons = 0;
            baseCnt = 0;
            qs1 = q1;
            qs2 = q2;
            q1 = (mkctr - 1) / 14 + 1;
            q2 = (mrctr - 1) / 14 + 1;
            if (q1 != qs1 || q2 != qs2) {
                khTl = 0;
            }
            trans();
            for (int r = 1; r <= 14; r++) {
                for (int c = 1; c <= 14; c++) {
                    char ch = miniTable[r][c];
                    if (ch == 'K') {
                        klgns++;
                    } else if (ch == 'R') {
                        romulons++;
                    } else if (ch == 'B') {
                        baseCnt++;
                    }
                }
            }

            display("      ");
            if (justStarting()) {
                display(String.format("You begin in quadrant %d,%d with 40,000 ", q1, q2));
                display("units of fuel and 5 photon torpedoes. ");
                display("      ");
                display("Good luck, Captain " + captainName);
                display("      ");
                if (klgns > 0) {
                    display(conRedStr());
                } else {
                    display(conGreenStr());
                }
            } else {
                if (klgns > 0) {
                    display(conRedStr());
                    int var2 = klgns * fuelCount / (shieldCnt + 27);
                    var2 = testVar(var2);
                    int var3 = (int)(0.75 * var2);
                    damageCnt += var2;
                    shieldCnt -= var3;
                    display("*ENTERPRISE ENCOUNTERING KLINGON FIRE* ");
                    display(String.format("%6d unit hit on Enterprise ", var2));
                } else {
                    display(conGreenStr());
                }
            }

            display(quadrantStr());
            displayQuadrantGrid();
            display("      ");
            ckFuelDamage();
            ckDone();
        }

        int testVar(int var2) {
            // 4200-test-var
            if (var2 < 1776 && klgns > 0) {
                var2 += 223;
                var2 = (int)(
                    klgns * var2 / 3.5
                    + var2 * damageCnt / 760.0
                    + nx * 17.0
                );
            }
            return var2;
        }

        // ── 1100-chk-galaxy ──────────────────────────────────────────────

        void chkGalaxy() {
            // 1100-chk-galaxy
            var1 += 1;
            if (var1 == 7) {
                masterReplaceAll("      K", "K      ");
                reset1120();
            } else if (var1 == 12) {
                masterReplaceAll("R      ", "      R");
                reset1120();
            } else if (var1 == 15) {
                masterReplaceAll("K           ", "           K");
                reset1120();
            } else if (var1 > 20) {
                masterReplaceAll("         R", "R         ");
                reset1120();
                var1 = 1;
            }
        }

        void masterReplaceAll(String old, String replacement) {
            // INSPECT master-tbl REPLACING ALL old BY new (linear)
            StringBuilder flat = new StringBuilder();
            for (int r = 1; r <= 126; r++) {
                for (int c = 1; c <= 126; c++) {
                    flat.append(masterTbl[r][c]);
                }
            }
            String flatStr = flat.toString().replace(old, replacement);
            int idx = 0;
            for (int r = 1; r <= 126; r++) {
                for (int c = 1; c <= 126; c++) {
                    masterTbl[r][c] = flatStr.charAt(idx);
                    idx++;
                }
            }
        }

        void reset1120() {
            // 1120-reset: re-transfer and recount
            trans();
            klgns = 0;
            romulons = 0;
            baseCnt = 0;
            for (int r = 1; r <= 14; r++) {
                for (int c = 1; c <= 14; c++) {
                    char ch = miniTable[r][c];
                    if (ch == 'K') {
                        klgns++;
                    } else if (ch == 'R') {
                        romulons++;
                    } else if (ch == 'B') {
                        baseCnt++;
                    }
                }
            }
        }

        // ── 7220-compute-dist ────────────────────────────────────────────

        void computeDist() {
            // 7220-compute-dist: find E, compute distances to K, R, B
            distB = 30;
            distX = 30;
            distR = 30;
            ctK = 0;
            ctR = 0;

            // 7225-find-e
            for (int rcntr = 1; rcntr <= 14; rcntr++) {
                for (int kcntr = 1; kcntr <= 14; kcntr++) {
                    if (miniTable[rcntr][kcntr] == 'E') {
                        e1 = rcntr;
                        e2 = kcntr;
                    }
                }
            }

            // 7230-compute
            for (int rcntr = 1; rcntr <= 14; rcntr++) {
                for (int kcntr = 1; kcntr <= 14; kcntr++) {
                    char ch = miniTable[rcntr][kcntr];
                    if (ch == 'K') {
                        int lk1 = rcntr;
                        int lk2 = kcntr;
                        ctK++;
                        int strA = distX;
                        int dk1 = Math.abs(lk1 - e1);
                        int dk2 = Math.abs(lk2 - e2);
                        int d = cobolRound(Math.sqrt(dk1 * dk1 + dk2 * dk2));
                        distX = d;
                        if (ctK <= 45) {
                            distKStr[ctK] = d;
                        }
                        if (distX > strA) {
                            distX = strA;
                        }
                    }
                    if (ch == 'R') {
                        int lr1 = rcntr;
                        int lr2 = kcntr;
                        ctR++;
                        int strR = distR;
                        int dr1 = Math.abs(lr1 - e1);
                        int dr2 = Math.abs(lr2 - e2);
                        int d = cobolRound(Math.sqrt(dr1 * dr1 + dr2 * dr2));
                        distR = d;
                        if (ctR <= 60) {
                            distRStr[ctR] = d;
                        }
                        if (distR > strR) {
                            distR = strR;
                        }
                    }
                    if (ch == 'B') {
                        int lb1 = rcntr;
                        int lb2 = kcntr;
                        int strX = distB;
                        int db1 = Math.abs(lb1 - e1);
                        int db2 = Math.abs(lb2 - e2);
                        distB = cobolRound(Math.sqrt(db1 * db1 + db2 * db2));
                        if (distB > strX) {
                            distB = strX;
                        }
                    }
                }
            }

            // 7247-est-nbr
            int strX = 30;
            rx = 0;
            for (int rt = 1; rt <= ctK; rt++) {
                if (rt <= 45 && distKStr[rt] < strX) {
                    strX = distKStr[rt];
                    rx = rt - 1;
                }
            }

            int strR = 30;
            qx = 0;
            for (int qt = 1; qt <= ctR; qt++) {
                if (qt <= 60 && distRStr[qt] < strR) {
                    strR = distRStr[qt];
                    qx = qt - 1;
                }
            }
        }

        // ── Mini-table helpers ───────────────────────────────────────────

        void miniReplaceFirst(char old, char replacement) {
            // INSPECT mini-table REPLACING FIRST old BY new
            for (int r = 1; r <= 14; r++) {
                for (int c = 1; c <= 14; c++) {
                    if (miniTable[r][c] == old) {
                        miniTable[r][c] = replacement;
                        return;
                    }
                }
            }
        }

        void miniReplaceAll(char old, char replacement) {
            // INSPECT mini-table REPLACING ALL old BY new
            for (int r = 1; r <= 14; r++) {
                for (int c = 1; c <= 14; c++) {
                    if (miniTable[r][c] == old) {
                        miniTable[r][c] = replacement;
                    }
                }
            }
        }

        int miniCount(char ch) {
            int count = 0;
            for (int r = 1; r <= 14; r++) {
                for (int c = 1; c <= 14; c++) {
                    if (miniTable[r][c] == ch) {
                        count++;
                    }
                }
            }
            return count;
        }

        // ── Navigation (7100-nav) ────────────────────────────────────────

        void nav(int courseA, int courseB, int warpA, int warpB) {
            // 7100-nav: navigate the Enterprise
            if (!ckFl()) {
                return;
            }

            fuelCount -= 200 * warpA;
            double rxS;
            if (warpA > 0) {
                rxS = (double) warpA;
            } else {
                rxS = warpB / 100.0;
            }

            int srctr = mrctr;
            int skctr = mkctr;

            int warp1 = cobolRound(warpA * 5 + warpB * 0.05);
            int warp2 = cobolRound(warpA * 8 + warpB * 0.08);
            int warp3 = cobolRound(courseB * 0.05 * rxS);
            int warp4 = cobolRound(courseB * 0.03 * rxS);

            if (courseA == 1) {
                srctr = srctr - warp2 + warp4;
                skctr = skctr + warp3;
            } else if (courseA == 2) {
                srctr = srctr - warp1 + warp3;
                skctr = skctr + warp1 + warp4;
            } else if (courseA == 3) {
                srctr = srctr + warp3;
                skctr = skctr + warp2 - warp4;
            } else if (courseA == 4) {
                srctr = srctr + warp1 + warp4;
                skctr = skctr + warp1 - warp3;
            } else if (courseA == 5) {
                srctr = srctr + warp2 - warp4;
                skctr = skctr - warp3;
            } else if (courseA == 6) {
                srctr = srctr + warp1 - warp3;
                skctr = skctr - warp1 - warp4;
            } else if (courseA == 7) {
                srctr = srctr - warp3;
                skctr = skctr - warp2 + warp4;
            } else if (courseA == 8) {
                srctr = srctr - warp1 - warp4;
                skctr = skctr - warp1 + warp3;
            } else {
                display("INVALID COURSE");
                return;
            }

            navCk(srctr, skctr);
        }

        void navCk(int srctr, int skctr) {
            // 7000-nav-ck: check navigation bounds and move
            if (srctr < 1 || srctr > 126 || skctr < 1 || skctr > 126) {
                display("Warp drive shut down - ");
                display("UNAUTHORIZED ATTEMPT TO LEAVE GALAXY ");
                dmgCom();
            } else {
                masterTbl[mrctr][mkctr] = ' ';
                mrctr = srctr;
                mkctr = skctr;
                char target = masterTbl[mrctr][mkctr];
                if (target == 'K' || target == 'R' || target == 'B') {
                    bomb();
                } else {
                    masterTbl[mrctr][mkctr] = 'E';
                }
            }
        }

        void bomb() {
            // 8000-bomb: collision
            char target = masterTbl[mrctr][mkctr];
            if (target == 'K') {
                display("*ENTERPRISE DESTROYED IN COLLISION WITH KLINGON*");
            } else if (target == 'R') {
                display("*ENTERPRISE DESTROYED IN COLLISION WITH ROMULON*");
            } else {
                display("*ENTERPRISE DESTROYED IN COLLISION WITH STAR BASE*");
            }
            indicateX = 1;
            ckDone();
        }

        // ── Phasers (7200-pha) ───────────────────────────────────────────

        void pha(int var4Input) {
            // 7200-pha: fire phasers
            if (klgns < 1 && romulons < 1) {
                display("Science Officer Spock reports no enemy ");
                display("vessels in this quadrant, " + captainName);
                return;
            }

            if (!ckFl()) {
                return;
            }

            if (fuelCount < 9999) {
                display(String.format("Maximum of %5d units available to phasers ", fuelCount));
            }

            int var4 = var4Input;
            if (var4 < 300) {
                var4 = 300;
            }

            computeDist();
            int var2 = 450000 / (shieldCnt + 100);
            generate();
            var2 = testAgn(var2);

            if (klgns > 1 && trapVec()) {
                display("*ENTERPRISE DESTROYED* ");
                display(String.format("Direct hits from %d klingons ", klgns));
                indicateX = 1;
                ckDone();
                return;
            }

            int dmVar4 = var4 - damageCnt / 15;
            int var3 = var2 / 2;

            if (klgns > 0) {
                if (distX >= 10) {
                    var2 = var2 / (distX / 10);
                }
                fuelCount -= var4;
                var4 = dmVar4;
                var4 += khTl;
                if (var4 < 400) {
                    display(String.format("%6d unit hit on Klingon ", var4));
                    display("*KLINGON DISABLED* ");
                    display(String.format("%6d unit hit on Enterprise ", var2));
                    var4 = (int)(0.75 * var4);
                    khTl += var4;
                    damageCnt += var2;
                    shieldCnt -= (int)(0.75 * var2);
                } else {
                    for (int i = 0; i < rx; i++) {
                        miniReplaceFirst('K', 'x');
                    }
                    miniReplaceFirst('K', ' ');
                    miniReplaceAll('x', 'K');
                    if (distX > 0) {
                        var4 = (int)(var4 / Math.pow(distX, 0.224));
                    }
                    display(String.format("%6d unit hit on Klingon ", var4));
                    display("*KLINGON DESTROYED* ");
                    khTl = 0;
                    klgns--;
                    klingons--;
                    transBack();
                    if (klgns > 0) {
                        display(String.format("%6d unit hit on Enterprise ", var2));
                        damageCnt += var2;
                        var2 = (int)(0.75 * var2);
                        shieldCnt -= var2;
                    } else {
                        var2 = var3;
                        display(String.format("%6d unit hit on Enterprise ", var2));
                        damageCnt += var3;
                        shieldCnt -= var3;
                    }
                }
            } else {
                display(String.format(
                    "There are 0 Klingons in this quadrant, %s", captainName
                ));
            }

            damComRomulon();
            ckFuelDamage();
            ckDone();
        }

        void phaRomulon(int var4) {
            // 7250-romulon-ck for phasers
            if (romulons > 2 && noWay()) {
                display("*ENTERPRISE FIRING ON ROMULONS*");
                display("*ROMULONS RETURNING FIRE* ");
                display(String.format("Simultaneous hits from %d Romulons ", romulons));
                display("*ENTERPRISE DESTROYED*");
                indicateX = 1;
                ckDone();
                return;
            }

            generate();
            display("*ENTERPRISE FIRING ON ROMULONS* ");
            fuelCount -= var4;
            int var2 = 450000 / (shieldCnt + 100);
            var2 = testAgn(var2);
            int var3 = var2 / 2;

            if (noWay() || var4 < 447) {
                int var4Hit;
                if (distR > 0) {
                    var4Hit = (int)(var4 / Math.pow(distR, 0.224));
                } else {
                    var4Hit = var4;
                }
                display(String.format("%6d unit hit on Romulon ", var4Hit));
                display("*ROMULON RETURNING FIRE*");
                generate();
                if (noWay()) {
                    display("*ENTERPRISE DESTROYED BY ROMULON TORPEDO* ");
                    indicateX = 1;
                    ckDone();
                    return;
                } else {
                    if (distR >= 10) {
                        var2 = 3 * var2 / (distR / 10);
                    } else {
                        var2 = 3 * var2;
                    }
                    display(String.format("%6d unit hit on Enterprise ", var2));
                    damageCnt += var2;
                    var3 = var2 / 2;
                    if (var3 < 9999) {
                        shieldCnt -= var3;
                    } else {
                        shieldCnt = 0;
                    }
                }
            } else {
                int var4Hit;
                if (distX > 0) {
                    var4Hit = (int)(var4 / Math.pow(distX, 0.125));
                } else {
                    var4Hit = var4;
                }
                display(String.format("%6d unit hit on Romulon ", var4Hit));
                display("*ROMULON DESTROYED*");
                for (int i = 0; i < qx; i++) {
                    miniReplaceFirst('R', 'x');
                }
                miniReplaceFirst('R', ' ');
                miniReplaceAll('x', 'R');
                romulons--;
                transBack();
            }

            dmgCom();
            ckFuelDamage();
            ckDone();
        }

        // ── Torpedoes (7300-tor) ─────────────────────────────────────────

        void tor() {
            // 7300-tor: fire torpedo
            if (klgns < 1 && romulons < 1) {
                display(String.format(
                    "There are 0 enemy vessels in this quadrant, %s", captainName
                ));
                return;
            }

            generate();
            int var2 = 250000 / (shieldCnt + 100);
            var2 = testAgn(var2);
            computeDist();
            if (klgns > 2) {
                var2 = var2 * (klgns + 1) / 2;
            }
            int var3 = (int)(0.75 * var2);

            if (torps > 0) {
                if (klgns > 0) {
                    if (shieldCnt < 475 && noWay()) {
                        display("*ENTERPRISE DESTROYED*");
                        display("Low shields at time of enemy attack ");
                        indicateX = 1;
                        ckDone();
                        return;
                    } else {
                        if (noWay() && distX > 4) {
                            if (distX >= 10) {
                                var2 = var2 / (distX / 10);
                            }
                            display("torpedo missed ");
                            display(String.format("%6d unit hit on Enterprise ", var2));
                            damageCnt += var2;
                            torps--;
                            shieldCnt -= var3;
                            damComRomulon();
                        } else {
                            display("*KLINGON DESTROYED*");
                            damageCnt -= var3;
                            for (int i = 0; i < rx; i++) {
                                miniReplaceFirst('K', 'x');
                            }
                            miniReplaceFirst('K', ' ');
                            miniReplaceAll('x', 'K');
                            torps--;
                            klgns--;
                            klingons--;
                            transBack();
                            if (klgns > 0) {
                                display(String.format("%6d unit hit on Enterprise ", var2));
                                damageCnt += var2;
                                shieldCnt -= var3;
                                damComRomulon();
                            } else {
                                damComRomulon();
                            }
                        }
                    }
                } else {
                    display(String.format(
                        "There are 0 Klingon vessels in this quadrant, %s",
                        captainName
                    ));
                }
            } else {
                display(String.format("0 torpedoes remaining, %s", captainName));
            }

            ckFuelDamage();
            ckDone();
        }

        void torRomulon() {
            // 7350-romulon-ck for torpedoes
            int var2 = 250000 / (shieldCnt + 100);
            var2 = testAgn(var2);
            int var3 = (int)(0.75 * var2);

            if (romulons > 1 && noWay()) {
                display("*ENTERPRISE FIRING ON ROMULONS*");
                display("*ROMULONS RETURNING FIRE*");
                display(String.format("Simultaneous hits from %d Romulons ", romulons));
                display("*ENTERPRISE DESTROYED*");
                indicateX = 1;
                ckDone();
                return;
            }

            display("*ENTERPRISE FIRING ON ROMULONS*");
            torps--;
            if (noWay() && distR > 4) {
                display("torpedo missed ");
                display("*ROMULONS RETURNING FIRE*");
                generate();
                if (noWay() && shieldCnt < 4000) {
                    display("*ENTERPRISE DESTROYED BY ROMULON TORPEDO*");
                    indicateX = 1;
                    ckDone();
                    return;
                } else {
                    if (distR >= 10) {
                        var2 = 3 * var2 / (distR / 10);
                    } else {
                        var2 = 3 * var2;
                    }
                    display(String.format("%6d unit hit on Enterprise ", var2));
                    damageCnt += var2;
                    var3 = var2 / 2;
                    shieldCnt -= var3;
                }
            } else {
                display("*ROMULON DESTROYED*");
                for (int i = 0; i < qx; i++) {
                    miniReplaceFirst('R', 'x');
                }
                miniReplaceFirst('R', ' ');
                miniReplaceAll('x', 'R');
                romulons--;
                transBack();
            }

            ckFuelDamage();
            ckDone();
        }

        // ── Shields (7500-def) ───────────────────────────────────────────

        void def(int amount) {
            // 7500-def: set shield level
            fuelCount += shieldCnt;
            shieldCnt = amount;
            if (shieldCnt < fuelCount) {
                fuelCount -= shieldCnt;
            } else {
                display(String.format("Maximum amount to shields: %5d", fuelCount));
                shieldCnt = Math.min(amount, fuelCount);
                fuelCount -= shieldCnt;
            }
            display(String.format("Shields at %4d per your command ", shieldCnt));
        }

        // ── Docking (7600-doc) ───────────────────────────────────────────

        void doc() {
            // 7600-doc: attempt to dock at starbase
            generate();
            if (baseCnt > 0) {
                computeDist();
                if (distB < 7) {
                    if (noWay()) {
                        display("*UNSUCCESSFUL DOCKING ATTEMPT* ");
                        display("Star base reports all bays in use ");
                        dmgCom();
                    } else {
                        torps = 5;
                        fuelCount = 25000;
                        damageCnt = 0;
                        shieldCnt = 0;
                        display("Shields dropped to dock at star base ");
                        display("*DOCK SUCCESSFUL* ");
                    }
                } else {
                    display(String.format("The nearest star base is %d parsecs ", distB));
                    display("You must maneuver to within 6 parsecs to dock ");
                }
            } else {
                display(String.format(
                    "There are 0 star bases in this quadrant, %s", captainName
                ));
            }
            ckFuelDamage();
            ckDone();
        }

        // ── Library Computer (3000-com-fun) ──────────────────────────────

        void comFun(int compCom) {
            // 3000-com-fun: library computer commands 1-6
            display("      ");
            if (compCom == 1) {
                sta();
            } else if (compCom == 2) {
                displayG();
            } else if (compCom == 3) {
                lrs();
            } else if (compCom == 4) {
                com4();
            } else if (compCom == 5) {
                intelligence();
            } else if (compCom == 6) {
                com6();
            } else {
                display(" INVALID COMPUTER COMMAND ");
            }
        }

        void sta() {
            // 7400-sta: ship status
            int var3 = damageCnt / 60;
            display("      ");
            display("FUEL UNITS   DAMAGE ");
            display("REMAINING    LEVEL  ");
            display("      ");
            display(String.format("   %5d  %6d%%", fuelCount, var3));
            display("      ");
            display("===================");
            display("      ");
            display(" PHOTON      SHIELD ");
            display("TORPEDOES    LEVEL ");
            display("      ");
            display(String.format("    %d         %4d", torps, shieldCnt));
            display("      ");
            dmgCom();
            ckFuelDamage();
            ckDone();
        }

        void lrs() {
            // 7700-lrs: long range scan
            transStar();
            scanKeep = new int[19];
            int scanCtr = 0;

            int qt1, qt3;
            if (q1 == 1) {
                qt1 = 1; qt3 = 3;
            } else if (q1 == 9) {
                qt1 = 7; qt3 = 9;
            } else {
                qt1 = q1 - 1; qt3 = q1 + 1;
            }

            int qt2, qt4;
            if (q2 == 1) {
                qt2 = 1; qt4 = 3;
            } else if (q2 == 9) {
                qt2 = 7; qt4 = 9;
            } else {
                qt2 = q2 - 1; qt4 = q2 + 1;
            }

            for (int tr2 = 0; tr2 < 3; tr2++) {
                for (int tr1 = 0; tr1 < 3; tr1++) {
                    int qt = tr1 * 14;
                    int rt = tr2 * 14;
                    for (int ktctr = 1; ktctr <= 14; ktctr++) {
                        for (int rtctr = 1; rtctr <= 14; rtctr++) {
                            int qxIdx = qt + ktctr;
                            int rxIdx = rt + rtctr;
                            if (rxIdx >= 1 && rxIdx <= 42 && qxIdx >= 1 && qxIdx <= 42) {
                                scanTable[rtctr][ktctr] = starTable[rxIdx][qxIdx];
                            } else {
                                scanTable[rtctr][ktctr] = ' ';
                            }
                        }
                    }

                    scanCtr++;
                    int kCount = 0;
                    for (int r = 1; r <= 14; r++) {
                        for (int c = 1; c <= 14; c++) {
                            if (scanTable[r][c] == 'K') {
                                kCount++;
                            }
                        }
                    }
                    if (scanCtr <= 18) {
                        scanKeep[scanCtr] = kCount;
                    }

                    scanCtr++;
                    int bCount = 0;
                    for (int r = 1; r <= 14; r++) {
                        for (int c = 1; c <= 14; c++) {
                            if (scanTable[r][c] == 'B') {
                                bCount++;
                            }
                        }
                    }
                    if (scanCtr <= 18) {
                        scanKeep[scanCtr] = bCount;
                    }
                }
            }

            int[] cv = scanKeep;
            display("      ");
            display(String.format("====%d===============%d====", qt1, qt3));
            display("=       =       =       =");
            display(String.format(
                "= %02d,%02d = %02d,%02d = %02d,%02d = ",
                cv[1], cv[2], cv[3], cv[4], cv[5], cv[6]
            ));
            display("=       =       =       =");
            display("=========================");
            display("=       =       =       =");
            display(String.format(
                "= %02d,%02d = %02d,%02d = %02d,%02d =",
                cv[7], cv[8], cv[9], cv[10], cv[11], cv[12]
            ));
            display("=       =       =       =");
            display("=========================");
            display("=       =       =       =");
            display(String.format(
                "= %02d,%02d = %02d,%02d = %02d,%02d =",
                cv[13], cv[14], cv[15], cv[16], cv[17], cv[18]
            ));
            display("=       =       =       =");
            display("=========================");
            display("KEY: ");
            display(String.format("Quadrants %d,%d thru %d,%d", qt1, qt2, qt3, qt4));
            display("Format - KLINGONS,STAR BASES ");
            if (q1 == 1 || q1 == 9 || q2 == 1 || q2 == 9) {
                display("*ENTERPRISE ON GALACTIC BOUNDARY*");
            }
            display(String.format("Enterprise in quadrant %d,%d", q1, q2));
            display("      ");
            dmgCom();
            ckFuelDamage();
            ckDone();
        }

        void com4() {
            // 3040-com: klingon tally
            int byeK = kOr - klingons;
            display("      ");
            display(String.format(
                "%02d Klingons destroyed, %02d remain ", byeK, klingons
            ));
            display(String.format("ATTACK DATE: %04d", dsDate));
            display(String.format("STAR DATE: %04d", sDate));
            display("      ");
            dmgCom();
        }

        void intelligence() {
            // 7800-int: intelligence report
            if (klingons > 0) {
                int cx = 1;
                int dx = 1;
                boolean found = false;
                while (dx <= 126) {
                    if (cx >= 1 && cx <= 126 && masterTbl[cx][dx] == 'K') {
                        found = true;
                        break;
                    }
                    cx++;
                    if (cx > 126) {
                        dx++;
                        cx = 1;
                    }
                }
                if (found) {
                    int cx1 = (dx - 1) / 14 + 1;
                    int dx1 = (cx - 1) / 14 + 1;
                    display(" ");
                    display("Latest intelligence gathering reports ");
                    display("indicate 1 or more Klingon vessels ");
                    display(String.format("in the vicinity of quadrant %d,%d", cx1, dx1));
                    display(" ");
                    display(String.format("Enterprise in quadrant %d,%d", q1, q2));
                    display(" ");
                }
            }
        }

        void com6() {
            // 3060-com: terminate
            display("      ");
            display("*ENTERPRISE STRANDED - CAPTAIN BOOKED* ");
            display("      ");
            indicateX = 1;
            ckDone();
        }

        // ── Damage / fuel checks ─────────────────────────────────────────

        void dmgCom() {
            // 8100-dmg-com: klingon fire after action
            if (klgns > 0) {
                int var2 = (
                    (kOr - klingons) * klgns * fuelCount
                    / (shieldCnt + 21)
                );
                var2 = testAgn(var2);
                int var3 = (int)(0.75 * var2);
                display("*ENTERPRISE ENCOUNTERING KLINGON FIRE*");
                display(String.format("%6d unit hit on Enterprise ", var2));
                damageCnt += var2;
                shieldCnt -= var3;
            }
        }

        void damComRomulon() {
            // 8120-dam-com: romulon fire after action
            if (romulons > 0) {
                int var2 = romulons * fuelCount / (shieldCnt + 7);
                var2 = testAgnRomulon(var2);
                int var3 = (int)(0.75 * var2);
                display("*ENTERPRISE ENCOUNTERING ROMULON FIRE*");
                display(String.format("%6d unit hit on Enterprise ", var2));
                damageCnt += var2;
                shieldCnt -= var3;
            }
        }

        int testAgn(int var2) {
            // 8150-test-agn
            if (var2 < 325 && klgns > 0) {
                var2 += 177;
                var2 = (int)(
                    klgns * var2 / 2.7 + var2 * damageCnt / 980.0
                );
            }
            return var2;
        }

        int testAgnRomulon(int var2) {
            // 8160-test-agn
            if (var2 < 525 && romulons > 0) {
                var2 += 254;
                var2 = (int)(
                    romulons * var2 / 4.7 + var2 * damageCnt / 365.0
                );
            }
            return var2;
        }

        void ckDone() {
            // 8200-ck-done
            if (byeBye()) {
                gameOver = true;
            }
        }

        void ckFuelDamage() {
            // 8300-ck-fuel-damage
            if (fuelCount > 0 && fuelCount < 4500) {
                display(String.format(
                    "Lt. Scott reports fuel is running low, %s", captainName
                ));
            } else if (fuelCount <= 0) {
                display("Fuel reserves depleted ");
                display("the Enterprise is drifting in space ");
                ckShift();
            }
            if (damageCnt > 6000) {
                display("Enterprise stranded because of heavy damage ");
                indicateX = 1;
                ckDone();
                return;
            }
            if (damageCnt > 4500) {
                display(String.format(
                    "Damage Control reports heavy damage to Enterprise, %s",
                    captainName
                ));
            }
            if (shieldCnt < 800 && (klgns > 0 || romulons > 0)) {
                display(String.format(
                    "Lt. Sulu reports shields dangerously low, %s", captainName
                ));
            }
        }

        boolean ckFl() {
            // 8340-ck-fl: check fuel. Returns false if cannot continue
            if (fuelCount <= 180) {
                display("*INSUFFICIENT FUEL TO CONTINUE*");
                ckShift();
                return false;
            }
            return true;
        }

        void ckShift() {
            // 8350-ck-shift
            if (shieldCnt > 200) {
                display("Lt. Sulu advises you lower shields ");
                display("to increase fuel supply, " + captainName);
            } else {
                indicateX = 1;
                ckDone();
            }
        }

        // ── Finish game (8500-finish-game) ───────────────────────────────

        void finishGame() {
            // 8500-finish-game
            display("      ");
            if (byeBye()) {
                if (sDate > dsDate) {
                    int vae1 = klingons;
                    dsDate = wsDate;
                    display(String.format("It is now star date %d", sDate));
                    display(String.format("STAR DATE %d Star Fleet HQ", dsDate));
                    display(String.format("was destroyed by %d klingon vessels", vae1));
                    display(captainName + " COURT MARTIALED");
                } else {
                    display(captainName + " COURT MARTIALED");
                }
            } else {
                display("Congratulations on a job well done. ");
                display(String.format(
                    "The Federation is proud of you, %s", captainName
                ));
                gameWon = true;
            }
            display("      ");
        }

        // ── Command processing (2000-process) ───────────────────────────

        List<String> processCommand(String command) {
            output = new ArrayList<>();

            if (gameOver) {
                finishGame();
                return flushOutput();
            }

            String[] parts = command.trim().split("\\s+");
            if (parts.length == 0 || parts[0].isEmpty()) {
                display("INVALID COMMAND - Do you want a list of commands? ");
                return flushOutput();
            }

            String cmd = parts[0].toLowerCase();

            // Pre-command: generate and check (from 2000-process)
            generate();
            if (noWay() || klgns > 1) {
                nx += 4;
            }

            if (cmd.equals("nav") || cmd.equals("navigate")) {
                if (parts.length >= 3) {
                    String courseStr = parts[1];
                    String warpStr = parts[2];
                    int courseA, courseB, warpA, warpB;
                    if (courseStr.contains(".")) {
                        String[] cp = courseStr.split("\\.");
                        courseA = (cp.length > 0 && !cp[0].isEmpty()) ? Integer.parseInt(cp[0]) : 0;
                        courseB = (cp.length > 1 && !cp[1].isEmpty()) ? Integer.parseInt(cp[1]) : 0;
                    } else {
                        courseA = Integer.parseInt(courseStr);
                        courseB = 0;
                    }
                    if (warpStr.contains(".")) {
                        String[] wp = warpStr.split("\\.");
                        warpA = (wp.length > 0 && !wp[0].isEmpty()) ? Integer.parseInt(wp[0]) : 0;
                        warpB = (wp.length > 1 && !wp[1].isEmpty()) ? Integer.parseInt(wp[1]) : 0;
                    } else {
                        warpA = Integer.parseInt(warpStr);
                        warpB = 0;
                    }

                    if (courseA < 1 || courseA > 8) {
                        display("INVALID COURSE");
                    } else {
                        nav(courseA, courseB, warpA, warpB);
                        displayG();
                    }
                } else if (parts.length == 2) {
                    String entry = parts[1];
                    if (entry.length() >= 2) {
                        int courseA = Character.getNumericValue(entry.charAt(0));
                        int warpA = Character.getNumericValue(entry.charAt(1));
                        nav(courseA, 0, warpA, 0);
                        displayG();
                    } else {
                        display("INVALID COURSE");
                    }
                } else {
                    display("What course (1 - 8.99)? ");
                    return flushOutput();
                }

            } else if (cmd.equals("pha") || cmd.equals("phasers")) {
                if (parts.length >= 2) {
                    int var4 = Integer.parseInt(parts[1]);
                    pha(var4);
                } else {
                    display("How many units to phaser banks? ");
                    return flushOutput();
                }

            } else if (cmd.equals("pha_romulon")) {
                if (parts.length >= 2) {
                    int var4 = Integer.parseInt(parts[1]);
                    phaRomulon(var4);
                } else {
                    display("How many units to phaser banks? ");
                }

            } else if (cmd.equals("tor") || cmd.equals("torpedo")) {
                tor();

            } else if (cmd.equals("tor_romulon")) {
                torRomulon();

            } else if (cmd.equals("def") || cmd.equals("shields")) {
                if (parts.length >= 2) {
                    int amount = Integer.parseInt(parts[1]);
                    def(amount);
                } else {
                    display("How many units to shields (0 - 9999)? ");
                }

            } else if (cmd.equals("doc") || cmd.equals("dock")) {
                doc();

            } else if (cmd.equals("com") || cmd.equals("computer")) {
                if (parts.length >= 2) {
                    int compCom = Integer.parseInt(parts[1]);
                    if (compCom == 6) {
                        com6();
                    } else {
                        comFun(compCom);
                    }
                } else {
                    display("*COMPUTER ACTIVE AND AWAITING COMMAND* ");
                }

            } else if (cmd.equals("com6_confirm")) {
                com6();

            } else {
                display("INVALID COMMAND - Do you want a list of commands? ");
            }

            // Post-command processing (from 2000-process)
            chkGalaxy();

            // Check win condition
            if (klingons < 1 && !gameOver) {
                gameOver = true;
                finishGame();
            }

            if (gameOver && !gameWon) {
                finishGame();
            }

            return flushOutput();
        }

        // ── Status (for differential testing) ────────────────────────────

        Map<String, String> getStatus() {
            Map<String, String> out = new LinkedHashMap<>();
            out.put("captain_name", captainName);
            out.put("skill_level", String.valueOf(skillLevel));
            out.put("fuel_count", String.valueOf(fuelCount));
            out.put("shield_cnt", String.valueOf(shieldCnt));
            out.put("damage_cnt", String.valueOf(damageCnt));
            out.put("torps", String.valueOf(torps));
            out.put("klingons", String.valueOf(klingons));
            out.put("klingons_initial", String.valueOf(kOr));
            out.put("klgns_in_quadrant", String.valueOf(klgns));
            out.put("romulons_in_quadrant", String.valueOf(romulons));
            out.put("base_cnt", String.valueOf(baseCnt));
            out.put("quadrant", "(" + q1 + ", " + q2 + ")");
            out.put("enterprise_pos", "(" + mrctr + ", " + mkctr + ")");
            out.put("hq_quadrant", "(" + hq1 + ", " + hq2 + ")");
            out.put("s_date", String.valueOf(sDate));
            out.put("ds_date", String.valueOf(dsDate));
            out.put("seed_x", String.format("%.12f", seedX));
            out.put("game_over", gameOver ? "True" : "False");
            out.put("game_won", gameWon ? "True" : "False");
            out.put("indicate_x", String.valueOf(indicateX));
            out.put("nx", String.valueOf(nx));
            out.put("var1", String.valueOf(var1));
            return out;
        }

        List<String> getInitialOutput() {
            return flushOutput();
        }

        // ── Fingerprint ──────────────────────────────────────────────────

        Map<String, String> galaxyFingerprint() {
            int countK = 0, countR = 0, countB = 0, countE = 0, countH = 0, countStar = 0;
            for (int r = 1; r <= 126; r++) {
                for (int c = 1; c <= 126; c++) {
                    switch (masterTbl[r][c]) {
                        case 'K': countK++; break;
                        case 'R': countR++; break;
                        case 'B': countB++; break;
                        case 'E': countE++; break;
                        case 'H': countH++; break;
                        case '*': countStar++; break;
                    }
                }
            }

            Map<String, String> out = new TreeMap<>(); // sorted for stability
            out.put("MRCTR", String.valueOf(mrctr));
            out.put("MKCTR", String.valueOf(mkctr));
            out.put("HQ1", String.valueOf(hq1));
            out.put("HQ2", String.valueOf(hq2));
            out.put("K_OR", String.valueOf(kOr));
            out.put("KLINGONS", String.valueOf(klingons));
            out.put("VAB1", String.valueOf(vab1));
            out.put("VAB2", String.valueOf(vab2));
            out.put("S_DATE", String.valueOf(sDate));
            out.put("DS_DATE", String.valueOf(dsDate));
            out.put("SEED_X", String.format("%.12f", seedX));
            out.put("FUEL", String.valueOf(fuelCount));
            out.put("TORPS", String.valueOf(torps));
            out.put("COUNT_K", String.valueOf(countK));
            out.put("COUNT_R", String.valueOf(countR));
            out.put("COUNT_B", String.valueOf(countB));
            out.put("COUNT_STAR", String.valueOf(countStar));
            out.put("COUNT_E", String.valueOf(countE));
            out.put("COUNT_H", String.valueOf(countH));
            return out;
        }

        private static int cobolRound(double value) {
            return (int) Math.floor(value + 0.5);
        }
    }
}

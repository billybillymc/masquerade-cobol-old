package com.modernization.masquerade.runner.programs;

import com.modernization.masquerade.runner.ProgramRunner;

import java.time.LocalDate;
import java.time.YearMonth;
import java.time.format.DateTimeFormatter;
import java.time.format.DateTimeParseException;
import java.util.*;

/**
 * Java reimplementation of CORPT00C — CardDemo Report Submission Screen.
 *
 * <p>Mirrors {@code pipeline/reimpl/corpt00c.py}. Python is the source of truth.
 *
 * <p>Structure: standalone {@link #processReportScreen} method + thin
 * {@link #runVector} adapter.
 *
 * <p>Uses a fixed "today" of 2025-06-15 to match the Python adapter's
 * deterministic output.
 */
public class Corpt00c implements ProgramRunner {

    private static final String CCDA_MSG_INVALID_KEY = "Invalid key pressed.                    ";

    // ── Inner data types ────────────────────────────────────────────────────

    static class JobRequest {
        String reportName = "";
        String startDate = "";
        String endDate = "";

        JobRequest(String reportName, String startDate, String endDate) {
            this.reportName = reportName;
            this.startDate = startDate;
            this.endDate = endDate;
        }
    }

    static class ReportResult {
        JobRequest jobRequest = null;
        String message = "";
        boolean error = false;
        String xctlProgram = "";
        boolean returnToPrev = false;
    }

    // ── Standalone business method ──────────────────────────────────────────

    /**
     * Process report submission screen — mirrors {@code process_report_screen} in
     * {@code pipeline/reimpl/corpt00c.py}.
     */
    ReportResult processReportScreen(
            int eibcalen, String eibaid, int pgmContext,
            String reportType,
            String startMm, String startDd, String startYyyy,
            String endMm, String endDd, String endYyyy,
            LocalDate today) {

        ReportResult result = new ReportResult();

        if (eibcalen == 0) {
            result.returnToPrev = true;
            result.xctlProgram = "COSGN00C";
            return result;
        }

        if (pgmContext == 0) {
            // First entry — show blank form
            return result;
        }

        if ("PF3".equals(eibaid)) {
            result.xctlProgram = "COMEN01C";
            result.returnToPrev = true;
            return result;
        }

        if (!"ENTER".equals(eibaid)) {
            result.error = true;
            result.message = CCDA_MSG_INVALID_KEY;
            return result;
        }

        String rt = reportType != null ? reportType.trim().toLowerCase() : "";

        if ("monthly".equals(rt)) {
            int yr = today.getYear();
            int mo = today.getMonthValue();
            String start = String.format("%04d-%02d-01", yr, mo);
            int lastDay = YearMonth.of(yr, mo).lengthOfMonth();
            String end = String.format("%04d-%02d-%02d", yr, mo, lastDay);
            return submitJob("Monthly", start, end, result);
        } else if ("yearly".equals(rt)) {
            int yr = today.getYear();
            String start = String.format("%04d-01-01", yr);
            String end = String.format("%04d-12-31", yr);
            return submitJob("Yearly", start, end, result);
        } else if ("custom".equals(rt)) {
            // Validate fields
            List<String> errors = new ArrayList<>();
            if (startMm == null || startMm.trim().isEmpty())
                errors.add("Start Date - Month can NOT be empty...");
            if (startDd == null || startDd.trim().isEmpty())
                errors.add("Start Date - Day can NOT be empty...");
            if (startYyyy == null || startYyyy.trim().isEmpty())
                errors.add("Start Date - Year can NOT be empty...");
            if (endMm == null || endMm.trim().isEmpty())
                errors.add("End Date - Month can NOT be empty...");
            if (endDd == null || endDd.trim().isEmpty())
                errors.add("End Date - Day can NOT be empty...");
            if (endYyyy == null || endYyyy.trim().isEmpty())
                errors.add("End Date - Year can NOT be empty...");

            if (!errors.isEmpty()) {
                result.error = true;
                result.message = errors.get(0);
                return result;
            }

            String start = startYyyy.trim() + "-"
                    + padLeft(startMm.trim(), 2) + "-"
                    + padLeft(startDd.trim(), 2);
            String end = endYyyy.trim() + "-"
                    + padLeft(endMm.trim(), 2) + "-"
                    + padLeft(endDd.trim(), 2);

            if (!isValidDate(start)) {
                result.error = true;
                result.message = "Start Date - Not a valid date...";
                return result;
            }
            if (!isValidDate(end)) {
                result.error = true;
                result.message = "End Date - Not a valid date...";
                return result;
            }

            return submitJob("Custom", start, end, result);
        } else {
            result.error = true;
            result.message = "Select a report type to print report...";
            return result;
        }
    }

    private ReportResult submitJob(String reportName, String startDate, String endDate, ReportResult result) {
        result.jobRequest = new JobRequest(reportName, startDate, endDate);
        result.message = reportName + " report job submitted";
        return result;
    }

    private static String padLeft(String s, int len) {
        while (s.length() < len) s = "0" + s;
        return s;
    }

    private static boolean isValidDate(String dateStr) {
        try {
            LocalDate.parse(dateStr, DateTimeFormatter.ISO_LOCAL_DATE);
            return true;
        } catch (DateTimeParseException e) {
            return false;
        }
    }

    // ── runVector adapter ───────────────────────────────────────────────────

    @Override
    public Map<String, String> runVector(Map<String, String> inputs) {
        String scenario = inputs.getOrDefault("SCENARIO", "FIRST_ENTRY");

        LocalDate fixedToday = LocalDate.of(2025, 6, 15);

        ReportResult result;

        switch (scenario) {
            case "FIRST_ENTRY":
                result = processReportScreen(100, "ENTER", 0,
                        "", "", "", "", "", "", "", fixedToday);
                break;
            case "MONTHLY_REPORT":
                result = processReportScreen(100, "ENTER", 1,
                        "monthly", "", "", "", "", "", "", fixedToday);
                break;
            case "YEARLY_REPORT":
                result = processReportScreen(100, "ENTER", 1,
                        "yearly", "", "", "", "", "", "", fixedToday);
                break;
            case "CUSTOM_REPORT":
                result = processReportScreen(100, "ENTER", 1,
                        "custom", "01", "01", "2025", "06", "30", "2025", fixedToday);
                break;
            case "INVALID_TYPE":
                result = processReportScreen(100, "ENTER", 1,
                        "", "", "", "", "", "", "", fixedToday);
                break;
            case "PF3_RETURN":
                result = processReportScreen(100, "PF3", 1,
                        "", "", "", "", "", "", "", fixedToday);
                break;
            default:
                result = processReportScreen(100, "ENTER", 0,
                        "", "", "", "", "", "", "", fixedToday);
                break;
        }

        String jobName = "";
        String startDate = "";
        String endDate = "";
        if (result.jobRequest != null) {
            jobName = result.jobRequest.reportName;
            startDate = result.jobRequest.startDate;
            endDate = result.jobRequest.endDate;
        }

        Map<String, String> out = new LinkedHashMap<>();
        out.put("ERROR", result.error ? "Y" : "N");
        out.put("MESSAGE", result.message);
        out.put("XCTL_PROGRAM", result.xctlProgram != null ? result.xctlProgram : "");
        out.put("RETURN_TO_PREV", result.returnToPrev ? "Y" : "N");
        out.put("JOB_NAME", jobName);
        out.put("START_DATE", startDate);
        out.put("END_DATE", endDate);
        return out;
    }
}

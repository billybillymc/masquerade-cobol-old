       IDENTIFICATION DIVISION.
       PROGRAM-ID. COBDATFT.
      ******************************************************************
      * Stub for COBDATFT assembler date formatting routine.
      * Converts dates between formats based on CODATECN-TYPE/OUTTYPE.
      *
      * Type 1: YYYYMMDD
      * Type 2: YYYY-MM-DD
      *
      * Input:  CODATECN-TYPE, CODATECN-INP-DATE
      * Output: CODATECN-OUTTYPE, CODATECN-0UT-DATE
      ******************************************************************
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  WS-TEMP-YYYY             PIC X(04).
       01  WS-TEMP-MM               PIC X(02).
       01  WS-TEMP-DD               PIC X(02).

       LINKAGE SECTION.
       COPY CODATECN.

       PROCEDURE DIVISION USING CODATECN-REC.
      *---------------------------------------------------------------*
      * Parse input date based on input type
      *---------------------------------------------------------------*
           EVALUATE CODATECN-TYPE
               WHEN '1'
      *            YYYYMMDD input
                   MOVE CODATECN-INP-DATE(1:4) TO WS-TEMP-YYYY
                   MOVE CODATECN-INP-DATE(5:2) TO WS-TEMP-MM
                   MOVE CODATECN-INP-DATE(7:2) TO WS-TEMP-DD
               WHEN '2'
      *            YYYY-MM-DD input
                   MOVE CODATECN-INP-DATE(1:4) TO WS-TEMP-YYYY
                   MOVE CODATECN-INP-DATE(6:2) TO WS-TEMP-MM
                   MOVE CODATECN-INP-DATE(9:2) TO WS-TEMP-DD
               WHEN OTHER
                   MOVE 'INVALID INPUT TYPE'
                       TO CODATECN-ERROR-MSG
                   GOBACK
           END-EVALUATE.

      *---------------------------------------------------------------*
      * Format output date based on output type
      *---------------------------------------------------------------*
           EVALUATE CODATECN-OUTTYPE
               WHEN '1'
      *            YYYY-MM-DD output
                   STRING WS-TEMP-YYYY DELIMITED SIZE
                          '-'          DELIMITED SIZE
                          WS-TEMP-MM   DELIMITED SIZE
                          '-'          DELIMITED SIZE
                          WS-TEMP-DD   DELIMITED SIZE
                       INTO CODATECN-0UT-DATE
                   END-STRING
               WHEN '2'
      *            YYYYMMDD output
                   STRING WS-TEMP-YYYY DELIMITED SIZE
                          WS-TEMP-MM   DELIMITED SIZE
                          WS-TEMP-DD   DELIMITED SIZE
                       INTO CODATECN-0UT-DATE
                   END-STRING
               WHEN OTHER
                   MOVE 'INVALID OUTPUT TYPE'
                       TO CODATECN-ERROR-MSG
           END-EVALUATE.

           MOVE SPACES TO CODATECN-ERROR-MSG.
           GOBACK.

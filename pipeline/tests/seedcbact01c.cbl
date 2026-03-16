       IDENTIFICATION DIVISION.
       PROGRAM-ID. SEEDFILE.
       ENVIRONMENT DIVISION.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
           SELECT ACCTFILE ASSIGN TO ACCTFILE
                  ORGANIZATION IS INDEXED
                  ACCESS MODE IS SEQUENTIAL
                  RECORD KEY IS FD-ACCT-ID
                  FILE STATUS IS WS-STATUS.
       DATA DIVISION.
       FILE SECTION.
       FD  ACCTFILE.
       01  FD-ACCTFILE-REC.
           05 FD-ACCT-ID                        PIC 9(11).
           05 FD-ACCT-DATA                      PIC X(289).
       WORKING-STORAGE SECTION.
       COPY CVACT01Y.
       01  WS-STATUS                PIC XX.
       PROCEDURE DIVISION.
           OPEN OUTPUT ACCTFILE.
           INITIALIZE ACCOUNT-RECORD.
           MOVE 12345678901       TO ACCT-ID.
           MOVE 'Y'              TO ACCT-ACTIVE-STATUS.
           MOVE 5000.00          TO ACCT-CURR-BAL.
           MOVE 10000.00         TO ACCT-CREDIT-LIMIT.
           MOVE 2000.00          TO ACCT-CASH-CREDIT-LIMIT.
           MOVE '2020-01-15'     TO ACCT-OPEN-DATE.
           MOVE '2026-01-15'     TO ACCT-EXPIRAION-DATE.
           MOVE '2024-06-01'     TO ACCT-REISSUE-DATE.
           MOVE 500.00           TO ACCT-CURR-CYC-CREDIT.
           MOVE 0.00             TO ACCT-CURR-CYC-DEBIT.
           MOVE '10001     '     TO ACCT-ADDR-ZIP.
           MOVE 'GRP001    '     TO ACCT-GROUP-ID.
           MOVE ACCOUNT-RECORD   TO FD-ACCTFILE-REC.
           WRITE FD-ACCTFILE-REC.
           CLOSE ACCTFILE.
           DISPLAY 'SEED DONE'.
           STOP RUN.

       IDENTIFICATION DIVISION.
       PROGRAM-ID. TAXEDRV2.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 COMBAT GLOBAL.
          COPY XCOMBAT  REPLACING 'X' BY COMBAT.
       01 RETOURB GLOBAL.
          COPY XRETB    REPLACING 'X' BY RETOURB.
       01 WS-COMBAT              PIC X(600).
       01 WS-RETOUR              PIC X(600).
       01 WS-CR                  PIC 9(2) VALUE 0.
       01 WS-RC                  PIC 9(2) VALUE 0.
       01 WS-PARM                PIC X VALUE 'B'.
       PROCEDURE DIVISION.
      * Use the actual copybook structure to set fields correctly
           INITIALIZE COMBAT.
           MOVE '2'    TO COMBAT-CCOBNB.
           MOVE '2018' TO COMBAT-DAN.
           MOVE '75'   TO COMBAT-CC2DEP.
           MOVE '1'    TO COMBAT-CCODIR.
           MOVE '056'  TO COMBAT-CCOCOM.
           MOVE 0      TO COMBAT-MBACOM.
           MOVE 0      TO COMBAT-MBADEP.
           MOVE 0      TO COMBAT-MBAREG.
           MOVE 0      TO COMBAT-MBASYN.
           MOVE 0      TO COMBAT-MBACU.
           MOVE 0      TO COMBAT-MBATSE.
           MOVE COMBAT TO WS-COMBAT.
           CALL 'EFITA3B8' USING
               WS-COMBAT WS-RETOUR WS-CR WS-RC WS-PARM.
           DISPLAY 'CR=' WS-CR.
           DISPLAY 'RC=' WS-RC.
           STOP RUN.

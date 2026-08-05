       IDENTIFICATION DIVISION.
       PROGRAM-ID. ORDERS.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       COPY CUSTREC.
       01  WS-AMOUNT        PIC S9(9)V99.
       PROCEDURE DIVISION.
       MAIN-PARA.
           PERFORM LOAD-CUSTOMER.
           PERFORM VALIDATE-ORDER.
           IF ACCOUNT-CLOSED
               PERFORM REJECT-ORDER
           ELSE
               CALL 'AUTHSVC'
           END-IF.
           STOP RUN.
       LOAD-CUSTOMER.
           EXEC SQL
               SELECT CUST-BALANCE INTO :WS-AMOUNT
               FROM CUSTOMER WHERE CUST-ID = :CUST-ID
           END-EXEC.
       VALIDATE-ORDER.
           IF WS-AMOUNT < 0
               GO TO REJECT-ORDER.
       REJECT-ORDER.
           EXEC SQL
               UPDATE ACCOUNT SET STATUS = 'C' WHERE ID = :CUST-ID
           END-EXEC.

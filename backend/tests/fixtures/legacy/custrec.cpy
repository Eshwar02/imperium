      * Customer record copybook
       01  CUSTOMER-RECORD.
           05  CUST-ID          PIC 9(6).
           05  CUST-NAME        PIC X(30).
           05  CUST-BALANCE     PIC S9(9)V99.
           05  CUST-STATUS      PIC X.
               88  ACCOUNT-ACTIVE   VALUE 'A'.
               88  ACCOUNT-CLOSED   VALUE 'C'.

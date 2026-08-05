"""COBOL business-rule candidate extraction (TDD)."""
from imperium.intelligence.business_rule_extractor import (
    RuleCandidate,
    _extract_cobol_candidates,
)

COBOL_SRC = """
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ACCTCHK.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01 ACCOUNT-STATUS PIC X.
          88 ACCOUNT-CLOSED VALUE 'C'.
          88 ACCOUNT-OPEN   VALUE 'O'.
       01 BALANCE PIC S9(9).
       PROCEDURE DIVISION.
       MAIN.
           IF BALANCE < 0
               MOVE 'C' TO ACCOUNT-STATUS
           END-IF.
           IF ACCOUNT-CLOSED THEN
               PERFORM REJECT
           END-IF.
"""


def test_88_level_condition_names_become_candidates():
    cands = _extract_cobol_candidates(COBOL_SRC, "acctchk.cbl")
    assert all(isinstance(c, RuleCandidate) for c in cands)
    closed = [c for c in cands if "ACCOUNT-CLOSED" in c.code_snippet]
    assert closed, "expected a candidate mentioning ACCOUNT-CLOSED"
    assert any(c.hint == "cobol_condition_name" for c in closed)
    c = closed[0]
    assert c.file_path == "acctchk.cbl"
    assert c.line >= 1


def test_if_statements_become_candidates():
    cands = _extract_cobol_candidates(COBOL_SRC, "acctchk.cbl")
    balance_guards = [
        c for c in cands
        if c.hint == "cobol_guard" and "BALANCE" in c.code_snippet
    ]
    assert balance_guards, "expected an IF guard candidate mentioning BALANCE"

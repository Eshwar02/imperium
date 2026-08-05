from imperium.intelligence.frontends import get_frontend
from imperium.intelligence.frontends.cobol import CobolFrontend, _detect_format, expand_copies

FIXED = (
    "000100 IDENTIFICATION DIVISION.\n"
    "000200 PROGRAM-ID. HELLO.\n"
    "000300*THIS IS A COMMENT\n"
    "000400 PROCEDURE DIVISION.\n"
)

PROG = (
    "PROGRAM-ID. ORDERS.\n"
    "PROCEDURE DIVISION.\n"
    "MAIN-PARA.\n"
    "    PERFORM VALIDATE-PARA.\n"
    "    CALL 'AUTHSVC'.\n"
    "VALIDATE-PARA.\n"
    "    IF AMT > 0 GO TO MAIN-PARA.\n"
)


def test_detect_fixed_format():
    assert _detect_format(FIXED) == "fixed"


def test_detect_free_format():
    assert _detect_format(PROG) == "free"


def test_preprocess_strips_seq_and_comments():
    out = CobolFrontend().preprocess("h.cbl", FIXED)
    assert "000100" not in out
    assert "IDENTIFICATION DIVISION." in out
    assert "THIS IS A COMMENT" not in out


def test_expand_copies_inlines_and_records():
    out, refs = expand_copies(" PROCEDURE DIVISION.\n COPY CUSTREC.\n",
                              {"CUSTREC": "01 CUST-ID PIC 9(5)."})
    assert "CUST-ID" in out
    assert refs == ["CUSTREC"]


def test_expand_copies_unresolved_still_recorded():
    out, refs = expand_copies(" COPY MISSING.\n", {})
    assert refs == ["MISSING"]


def test_structure_paragraphs_and_calls():
    root = CobolFrontend().structure("orders.cbl", PROG)
    assert root.kind == "module" and root.name == "ORDERS"
    paras = {c.name: c for c in root.children if c.kind == "function"}
    assert "MAIN-PARA" in paras and "VALIDATE-PARA" in paras
    main_calls = [c.name for c in paras["MAIN-PARA"].children if c.kind == "call"]
    assert "VALIDATE-PARA" in main_calls and "AUTHSVC" in main_calls
    val_calls = [c.name for c in paras["VALIDATE-PARA"].children if c.kind == "call"]
    assert "MAIN-PARA" in val_calls  # GO TO target


def test_edges_copies():
    fe = CobolFrontend()
    src = "PROGRAM-ID. P.\nPROCEDURE DIVISION.\n COPY CUSTREC.\n"
    edges = fe.edges("p.cbl", fe.structure("p.cbl", src), src)
    assert any(e["type"] == "COPIES" and e["target"] == "CUSTREC" for e in edges)


def test_data_items_88_level():
    items = CobolFrontend().data_items("p.cbl", "01 ACCT-STATUS PIC X.\n 88 IS-ACTIVE VALUE 'A'.\n")
    assert any(d["name"] == "IS-ACTIVE" and d["is_condition"] for d in items)
    assert any(d["name"] == "ACCT-STATUS" and d["pic"].startswith("X") for d in items)


def test_registered_via_get_frontend():
    assert isinstance(get_frontend("cobol"), CobolFrontend)

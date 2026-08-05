from imperium.intelligence.frontends.jcl import JclFrontend
from imperium.intelligence.frontends.mainframe_data import extract_cics, extract_sql_edges

JCL = (
    "//PAYJOB JOB (ACCT)\n"
    "//STEP1 EXEC PGM=PAYCALC\n"
    "//IN DD DSN=PROD.PAY.MASTER,DISP=SHR\n"
    "//STEP2 EXEC PGM=PAYRPT\n"
    "//OUT DD DSN=PROD.PAY.REPORT,DISP=(NEW)\n"
)


def test_jcl_structure_steps():
    root = JclFrontend().structure("pay.jcl", JCL)
    steps = {c.name for c in root.children if c.kind == "function"}
    assert root.name == "PAYJOB"
    assert steps == {"STEP1", "STEP2"}


def test_jcl_runs_and_dataset_edges():
    fe = JclFrontend()
    edges = fe.edges("pay.jcl", fe.structure("pay.jcl", JCL), JCL)
    assert any(e["type"] == "RUNS" and e["source"] == "STEP1" and e["target"] == "PAYCALC" for e in edges)
    assert any(e["type"] == "USES_DATASET" and e["target"] == "PROD.PAY.MASTER" for e in edges)


def test_exec_sql_read_write():
    src = ("EXEC SQL SELECT NAME FROM CUSTOMER WHERE ID = :X END-EXEC.\n"
           "EXEC SQL UPDATE ACCOUNT SET BAL = 0 END-EXEC.\n")
    edges = extract_sql_edges("ORDERS", src)
    assert any(e["type"] == "READS" and e["target"] == "CUSTOMER" for e in edges)
    assert any(e["type"] == "WRITES" and e["target"] == "ACCOUNT" for e in edges)


def test_exec_cics_txn():
    edges = extract_cics("ORDERS", "EXEC CICS RETURN TRANSID('PAY1') END-EXEC.\n")
    assert any(e["type"] == "EXPOSES" and e["target"] == "PAY1" for e in edges)

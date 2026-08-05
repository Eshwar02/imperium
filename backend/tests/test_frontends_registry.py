from imperium.intelligence.frontends import get_frontend, has_frontend
from imperium.intelligence.frontends.cobol import CobolFrontend
from imperium.intelligence.frontends.default import DefaultFrontend
from imperium.intelligence.frontends.jcl import JclFrontend


def test_unknown_language_returns_default():
    assert isinstance(get_frontend("python"), DefaultFrontend)


def test_cobol_and_jcl_registered():
    assert isinstance(get_frontend("cobol"), CobolFrontend)
    assert isinstance(get_frontend("jcl"), JclFrontend)
    assert has_frontend("cobol") and has_frontend("jcl")
    assert not has_frontend("python")


def test_default_structure_returns_module_ast(tmp_path):
    # DefaultFrontend delegates to the existing file-based parser, so give it a real file.
    f = tmp_path / "x.py"
    f.write_text("def foo():\n    bar()\n")
    root = get_frontend("python").structure(str(f), f.read_text())
    assert root.kind == "module"
    assert any(c.kind == "function" and c.name == "foo" for c in root.children)

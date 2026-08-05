"""Frontend registry — dispatch a language to its :class:`LanguageFrontend`.

Modern languages fall through to :class:`DefaultFrontend`. Legacy frontends register
themselves here so the orchestrator can build their graph/rules generically.
"""
from __future__ import annotations

from imperium.intelligence.frontends.base import LanguageFrontend
from imperium.intelligence.frontends.default import DefaultFrontend

_REGISTRY: dict[str, LanguageFrontend] = {}
_DEFAULT = DefaultFrontend()


def register(frontend: LanguageFrontend) -> None:
    for lang in frontend.languages:
        _REGISTRY[lang] = frontend


def get_frontend(language: str) -> LanguageFrontend:
    return _REGISTRY.get(language, _DEFAULT)


def has_frontend(language: str) -> bool:
    """True when a dedicated (non-default) frontend is registered for ``language``."""
    return language in _REGISTRY


# ── register legacy frontends ─────────────────────────────────────────────────
from imperium.intelligence.frontends.cobol import CobolFrontend  # noqa: E402
from imperium.intelligence.frontends.jcl import JclFrontend  # noqa: E402

register(CobolFrontend())
register(JclFrontend())

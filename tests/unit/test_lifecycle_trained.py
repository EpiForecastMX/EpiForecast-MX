"""C7.7 — Obesidad publicada DESDE su release, en canales exactos; F50 sigue invisible.

Antes (F2/C5.6) este archivo probaba que `trained` no publica. El 4-nov-2026 el autor dio el OK
formal y Obesidad pasó a `published`: lo que ahora se fija es CÓMO está publicada —sólo desde el
release sellado, sólo en web/epibot/reports, sin galería— y que el carril legacy no la absorba.
"""

from __future__ import annotations

from epiforecast import registry

_OBESIDAD = "obesidad"
_LEGACY = ["Depresión", "Parkinson", "Alzheimer", "Dengue"]


def test_obesidad_esta_published_desde_su_release():
    spec = registry.require(_OBESIDAD)
    assert spec.lifecycle == "published"
    assert spec.is_release_backed
    assert spec.artifact_source.release_id == "obesidad_release_2517e7858901"


def test_canales_exactos_sin_tableau_ni_galeria():
    spec = registry.require(_OBESIDAD)
    assert spec.channels == ("web", "epibot", "reports")
    assert spec.gallery_enabled is False
    for canal in ("web", "epibot", "reports"):
        assert _OBESIDAD in [n.lower() for n in registry.published_members(channel=canal)]
    assert _OBESIDAD not in [n.lower() for n in registry.published_members(channel="tableau")]


def test_el_carril_legacy_no_cambia():
    assert [d.data_name for d in registry.legacy_published()] == _LEGACY
    assert registry.production_cohort() == ["Depresión", "Parkinson", "Alzheimer"]
    assert registry.names(published_only=True) == [
        *_LEGACY,
        "Obesidad",
        "Diabetes tipo I",
        "Diabetes tipo II",
    ]


def test_f50_sigue_invisible():
    publicados = [n.lower() for n in registry.names(published_only=True)]
    assert "anorexia f50" not in publicados

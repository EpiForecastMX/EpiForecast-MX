"""F2/C5.6 — `trained` NO publica: Obesidad sigue invisible para todo consumidor published_only."""

from __future__ import annotations

from epiforecast import registry

_OBESIDAD = "obesidad"


def test_obesidad_esta_trained_no_published():
    spec = registry.require(_OBESIDAD)
    assert spec.lifecycle == "trained"  # C5 cerrado
    assert spec.lifecycle != "published"


def test_trained_sigue_invisible_para_published_only():
    assert _OBESIDAD not in [n.lower() for n in registry.names(published_only=True)]
    assert _OBESIDAD not in [n.lower() for n in registry.standalone_members(published_only=True)]
    assert _OBESIDAD not in [n.lower() for n in registry.published_members()]
    for canal in ("web", "epibot", "reports", "tableau"):
        assert _OBESIDAD not in [n.lower() for n in registry.published_members(channel=canal)]


def test_trained_sigue_declarado_para_quien_no_filtra():
    # Visible para el runner (que no filtra por lifecycle), invisible para los canales.
    assert _OBESIDAD in [n.lower() for n in registry.names()]


def test_la_cohorte_neuro_y_dengue_no_cambian():
    publicados = registry.names(published_only=True)
    assert publicados == ["Depresión", "Parkinson", "Alzheimer", "Dengue"]
    assert len(publicados) == 4  # el flip de Obesidad no añade nadie a los canales

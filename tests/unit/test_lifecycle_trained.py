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
        "Anorexia F50",
        "Diabetes tipo I",
        "Diabetes tipo II",
        "Hipertensión arterial",
        "Enfermedad isquémica del corazón",
        "Enfermedad cerebrovascular",
        "Infecciones intestinales por otros organismos y las mal definidas",
        "Infecciones respiratorias agudas",
        "Infección de vías urinarias",
        "Gingivitis y enfermedad periodontal",
        "Asma",
        "Úlceras, gastritis y duodenitis",
        "Tumor maligno de la mama",
        "Tumor maligno del cuello del útero",
        "Tumor maligno de la próstata",
        "Tumor maligno del cuerpo del útero",
        "Tumor maligno del ovario",
        "Tumor maligno de tráquea, bronquios y pulmón",
        "Tumor maligno del estómago",
        "Tumor maligno del colon y recto",
        "Tumor maligno del hígado y de las vías biliares intrahepáticas",
        "Linfoma de Hodgkin",
        "Linfoma no Hodgkin",
        "Leucemia",
        "Tumor maligno del esófago",
        "Tumor maligno del páncreas",
        "Tumores malignos del encéfalo y otras partes del sistema nervioso central",
        "Tumores malignos de los huesos y de los cartílagos articulares",
        "Tumor maligno del riñón",
        "Neumonías y bronconeumonías",
        "Otitis media aguda",
        "Conjuntivitis",
        "Amebiasis intestinal",
        "Accidente de transporte en vehículos con motor",
        "Edema, proteinuria y trastornos hipertensivos en el embarazo, parto y puerperio",
    ]


def test_covid_sigue_invisible():
    publicados = [n.lower() for n in registry.names(published_only=True)]
    assert "covid-19" not in publicados

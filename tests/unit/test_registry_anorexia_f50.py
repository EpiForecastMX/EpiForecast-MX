"""C6.1 — N+1: Anorexia F50 se registra por CONFIGURACIÓN y nace invisible."""

from __future__ import annotations

from epiforecast import registry
from epiforecast.data.extraction import cuadro_extractor

_F50 = "anorexia_f50"
_GRUPO = "trastornos_nutricion"


def test_identidad_declarada():
    spec = registry.require(_F50)
    assert spec.id == _F50 and spec.data_name == "Anorexia F50"
    assert spec.artifact_key == "Anorexia_F50" and spec.slug == _F50
    assert spec.cie_codes == ("F50",)
    assert spec.extraction_group == _GRUPO
    assert spec.exposure_source_id == "inegi_cpv2020_static"
    assert spec.selection_policy == "rolling_cv_v1"


def test_aliases_clinicos_resuelven():
    for alias in ("anorexia", "anorexia nerviosa", "tca", "bulimia", "trastornos alimentarios"):
        assert registry.require(alias).id == _F50


def test_perfil_de_baja_incidencia_sin_traits_legacy():
    perfil = registry.require(_F50).profile
    assert perfil.cohorte_id == "baja_incidencia"  # ni neuro, ni conteos, ni obesidad
    assert perfil.unidad == "conteos" and perfil.rate_scale == 100_000
    assert not any(perfil.motor_rate.values())  # ningún motor modela tasa hoy
    for atributo in ("fallback_regional", "excluir_outliers", "invert_log_predict"):
        assert getattr(perfil, atributo) is False, atributo
    # Traits por motor: TODOS apagados (nada de log1p, COVID, ENSO, clamp ni short_series).
    for motor, trait in (
        ("prophet", "log_transform"),
        ("prophet", "covid_holidays"),
        ("prophet", "cv_weights"),
        ("prophet", "enso"),
        ("ensemble", "covid_holidays"),
        ("ensemble", "clamp"),
        ("stacking", "clamp"),
        ("deepar", "short_series"),
        ("nbglm", "enso"),
    ):
        assert registry.trait("Anorexia F50", motor, trait, default=True) is False, (motor, trait)


def test_nace_configured_y_sin_motores_legacy():
    spec = registry.require(_F50)
    assert spec.lifecycle == "configured"
    assert spec.training_engines == () and spec.eligible_engines == ()
    assert spec.channels == () and spec.gallery_enabled is False


def test_invisible_en_todo_filtro_published_only():
    assert registry.names(published_only=True) == ["Depresión", "Parkinson", "Alzheimer", "Dengue"]
    for nombres in (
        registry.standalone_members(published_only=True),
        registry.published_members(),
        *[registry.published_members(channel=c) for c in ("web", "epibot", "reports", "tableau")],
    ):
        assert _F50 not in [n.lower() for n in nombres]


def test_doctor_sin_problemas():
    from epiforecast.registry_doctor import diagnose

    assert [p for p in diagnose(_F50) if p.severity == "error"] == []


def test_cuadro_compartido_emite_los_dos_bloques():
    grupo = cuadro_extractor.load_group(_GRUPO)
    por_id = {d["id"]: d for d in grupo["diseases"]}
    assert set(por_id) == {"obesidad", _F50}
    assert por_id["obesidad"]["block_index"] == 0 and por_id[_F50]["block_index"] == 1
    assert por_id[_F50]["onboard"] is True  # C6: deja de estar solo "extraíble"
    assert por_id[_F50]["keyword"] == "Anorexia_F50"
    assert grupo["observation_lag_weeks"] == 1 and grupo["n_states_expected"] == 32


def test_obesidad_no_cambia_con_el_alta_de_f50():
    obe = registry.require("obesidad")
    assert obe.lifecycle == "trained" and obe.profile_name == "obesidad_cronica"
    assert obe.training_engines == ("prophet", "deepar", "ensemble", "stacking")

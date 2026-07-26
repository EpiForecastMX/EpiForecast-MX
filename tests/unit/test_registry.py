"""E1: registry tipado. Paridad con el golden (neuro+Dengue byte-idénticos) + validación."""

from __future__ import annotations

import pytest

from epiforecast import registry
from epiforecast.registry import RegistryError, load_registry
from tests.unit.test_golden_cohortes import _NORMALIZAR_TASA_GLOBAL, GOLDEN

_REG_DISEASES = ("Depresión", "Parkinson", "Alzheimer", "Dengue")


def _registry_gate_signature(name: str) -> dict[str, bool]:
    """Reproduce la firma de gates del golden PERO computada desde el registry."""
    d = registry.require(name)
    neuro = d.profile.cohorte_id == "neuro"
    count_log = d.profile.cohorte_id == "conteos"

    def rt(engine: str, key: str) -> bool:
        return registry.trait(name, engine, key)

    return {
        "is_neuro": neuro,
        "is_count_log_cohort": count_log,
        "prophet_rate_normalized": _NORMALIZAR_TASA_GLOBAL and rt("prophet", "rate"),
        "deepar_rate_normalized": _NORMALIZAR_TASA_GLOBAL and rt("deepar", "rate"),
        "prophet_log_transform": rt("prophet", "log_transform"),
        "prophet_enso": rt("prophet", "enso"),
        "nbglm_enso": rt("nbglm", "enso"),
        "prophet_covid_holidays": rt("prophet", "covid_holidays"),
        "ensemble_covid_holidays": rt("ensemble", "covid_holidays"),
        "prophet_cv_weights": rt("prophet", "cv_weights"),
        "ensemble_clamp": rt("ensemble", "clamp"),
        "stacking_clamp": rt("stacking", "clamp"),
        "deepar_short_series": rt("deepar", "short_series"),
        "invert_log_predict": rt("prophet", "invert_log_predict"),
        "hybrid_fallback": rt("prophet", "fallback_regional"),
        "in_general_batch": d.batch == "General",
        "excluir_outliers": rt("prophet", "excluir_outliers"),
    }


@pytest.mark.parametrize("name", _REG_DISEASES)
def test_registry_reproduce_el_golden(name: str):
    assert _registry_gate_signature(name) == GOLDEN[name]


def test_registry_carga_y_valida():
    assert registry.validate_config() == []


def test_aliases_acento_case_cie():
    r = registry.get_registry()
    dep = r.get("Depresión")
    assert dep is not None
    for alias in ("Depresion", "depresion", "DEPRESIÓN", "F32", "episodio depresivo"):
        assert r.get(alias) is dep
    assert r.get("e66") is r.get("Obesidad")
    assert r.get("a97.1") is r.get("Dengue")


def test_none_y_desconocido_devuelven_none():
    assert registry.try_get(None) is None
    assert registry.try_get("futbol") is None
    with pytest.raises(RegistryError):
        registry.require("no_existe")


def test_cohortes_y_lote():
    assert set(registry.production_cohort()) == {"Depresión", "Parkinson", "Alzheimer"}
    assert "Dengue" in registry.standalone_members()
    # Obesidad registrada pero NO publicada -> invisible
    assert "Obesidad" not in registry.published_members()
    assert "Obesidad" not in registry.production_cohort()


def test_cie_map():
    assert registry.cie_map() == {
        "F32": "Depresión",
        "G20": "Parkinson",
        "G30": "Alzheimer",
        "A97": "Dengue",
        "E66": "Obesidad",
        "F50": "Anorexia F50",  # C6/N+1: co-ubicado con Obesidad en el cuadro 14.1
    }


def test_obesidad_configurada_perfil_propio():
    obe = registry.require("Obesidad")
    assert obe.lifecycle == "trained"  # C5 cerrado; NUNCA published (ver test_lifecycle_trained)
    assert obe.profile.cohorte_id == "obesidad"  # ni neuro ni conteos
    assert obe.batch == "standalone"
    # C7.1: el carril nuevo no entrena motores legacy, así que Obesidad no declara ninguno; su
    # backend de artefactos son los runs sellados del runner.
    assert obe.training_engines == () and obe.eligible_engines == ()
    assert obe.artifact_backend == registry.BACKEND_RUNNER_RELEASE  # C7.2-B: el bundle
    # perfil crónico: Prophet/DeepAR en tasa; Ensemble/Stacking conservan conteos.
    assert obe.profile.rate_scale == 100_000
    assert registry.trait("Obesidad", "prophet", "rate") is True
    assert registry.trait("Obesidad", "deepar", "rate") is True
    assert registry.trait("Obesidad", "ensemble", "rate") is False
    assert registry.trait("Obesidad", "stacking", "rate") is False
    assert registry.trait("Obesidad", "prophet", "enso") is False
    assert registry.trait("Obesidad", "deepar", "short_series") is False
    assert registry.trait("Obesidad", "prophet", "fallback_regional") is True


def test_dengue_deepar_conserva_tasa_prophet_no():
    # La divergencia per-motor clave.
    assert registry.trait("Dengue", "prophet", "rate") is False
    assert registry.trait("Dengue", "deepar", "rate") is True


def test_rechazo_id_duplicado(tmp_path):
    bad = tmp_path / "dup.yaml"
    bad.write_text(
        """
version: 1
perfiles:
  p: {cohorte_id: x, rate_scale: 100000, motor_rate: {prophet: true}}
padecimientos:
  - {id: a, data_name: A, artifact_key: A, slug: a, cie_codes: [X1], profile: p}
  - {id: a, data_name: B, artifact_key: B, slug: b, cie_codes: [X2], profile: p}
""",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="id duplicado"):
        load_registry(bad)


def test_rechazo_alias_duplicado(tmp_path):
    bad = tmp_path / "dupalias.yaml"
    bad.write_text(
        """
version: 1
perfiles:
  p: {cohorte_id: x, rate_scale: 100000, motor_rate: {prophet: true}}
padecimientos:
  - {id: a, data_name: A, artifact_key: A, slug: a, cie_codes: [X1], aliases: [comun], profile: p}
  - {id: b, data_name: B, artifact_key: B, slug: b, cie_codes: [X2], aliases: [comun], profile: p}
""",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="alias duplicado"):
        load_registry(bad)


def test_rechazo_clave_desconocida(tmp_path):
    bad = tmp_path / "badkey.yaml"
    bad.write_text(
        """
version: 1
perfiles:
  p: {cohorte_id: x, rate_scale: 100000, motor_rate: {prophet: true}, clave_rara: 1}
padecimientos:
  - {id: a, data_name: A, artifact_key: A, slug: a, cie_codes: [X1], profile: p}
""",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="desconocidas"):
        load_registry(bad)


def test_rechazo_tasa_sin_escala_explicita(tmp_path):
    bad = tmp_path / "rate_without_scale.yaml"
    bad.write_text(
        """
version: 1
perfiles:
  p: {cohorte_id: x, motor_rate: {prophet: true}}
padecimientos:
  - {id: a, data_name: A, artifact_key: A, slug: a, cie_codes: [X1], profile: p}
""",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match="rate_scale.*positivo"):
        load_registry(bad)


@pytest.mark.parametrize(
    ("profile_body", "message"),
    [
        (
            "{cohorte_id: x, rate_scale: 100000, motor_rate: {prophet: 'false'}}",
            "motor_rate debe usar booleanos",
        ),
        (
            "{cohorte_id: x, rate_scale: .nan, motor_rate: {prophet: true}}",
            "rate_scale debe ser finito",
        ),
        (
            "{cohorte_id: x, rate_scale: 100000, prophet_log_transform: 'false', "
            "motor_rate: {prophet: true}}",
            "traits booleanos",
        ),
    ],
)
def test_rechazo_tipos_ambiguos_en_contrato_de_transform(
    tmp_path, profile_body: str, message: str
):
    bad = tmp_path / "ambiguous_transform.yaml"
    bad.write_text(
        f"""
version: 1
perfiles:
  p: {profile_body}
padecimientos:
  - {{id: a, data_name: A, artifact_key: A, slug: a, cie_codes: [X1], profile: p}}
""",
        encoding="utf-8",
    )
    with pytest.raises(RegistryError, match=message):
        load_registry(bad)

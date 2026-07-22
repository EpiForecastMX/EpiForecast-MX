"""E0-S2: golden freeze del comportamiento de cohorte (red de seguridad de EPIC 1-2).

Congela la **firma disease-variante** de cada gate del pipeline para las 5 combinaciones
vigentes ``{None, Depresión, Parkinson, Alzheimer, Dengue}``. Cada gate deriva de dos
predicados de cohorte (``is_neuro``, ``is_count_log_cohort``) + la lista de exención de
outliers. La firma se computa llamando a los helpers REALES; así, cuando EPIC 1 los
respalde con el registry, este test prueba que el comportamiento no cambió (byte-idéntico
en la parte determinista). Referencias de código de cada gate en ``_gate_signature``.

También congela un hash de la selección productiva legacy (432 series) como red de
seguridad para el selector unificado de EPIC 3.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from epiforecast.utils.cohorts import is_count_log_cohort, is_neuro
from epiforecast.utils.config import conf

DISEASES: tuple[str | None, ...] = (None, "Depresión", "Parkinson", "Alzheimer", "Dengue")

# Exención de outliers epidémicos (config/features/feature_engineering.yaml: excluir_padecimientos).
# Baseline congelado; EPIC 1 lo deriva del perfil del registry.
_EXCLUIR_OUTLIERS: frozenset[str] = frozenset({"Dengue"})

# normalizar_tasa global (prophet.yaml:1 = true). DeepAR lo lee SIN gate de cohorte, así que
# DeepAR-Dengue conserva tasa/100k aunque Prophet-Dengue use conteos. Esta es la divergencia
# per-motor clave que E1-S2 codifica como trait(disease, engine, "rate").
_NORMALIZAR_TASA_GLOBAL: bool = (
    bool(conf.get("normalizar_tasa", True)) if hasattr(conf, "get") else True
)


def _gate_signature(pad: str | None) -> dict[str, bool]:
    """Firma **per-motor** de los gates, computada desde los helpers reales.

    Los gates son inherentemente por-motor (Prophet-Dengue=conteos vs DeepAR-Dengue=tasa),
    así que la firma los prefija con su motor. Cada entrada documenta su sitio de código.
    """
    neuro = is_neuro(pad)
    count_log = is_count_log_cohort(pad)
    return {
        "is_neuro": neuro,
        "is_count_log_cohort": count_log,
        # prophet/model.py:65-67  rate = normalizar_tasa AND not is_count_log_cohort
        "prophet_rate_normalized": _NORMALIZAR_TASA_GLOBAL and not count_log,
        # deepar/model.py:164  rate = normalizar_tasa (SIN gate de cohorte: Dengue conserva tasa)
        "deepar_rate_normalized": _NORMALIZAR_TASA_GLOBAL,
        # prophet/model.py:71-72  log = conf AND (is_neuro OR is_count_log_cohort)
        "prophet_log_transform": neuro or count_log,
        # prophet/model.py:80-82  enso = conf AND is_count_log_cohort
        "prophet_enso": count_log,
        # nbglm/model.py:63  enso = conf AND is_count_log_cohort
        "nbglm_enso": count_log,
        # prophet/data_prep.py:149  holidays COVID solo si is_neuro
        "prophet_covid_holidays": neuro,
        # ensemble/feature_builder.py:100  holidays incluidas si (pad is None) OR is_neuro
        "ensemble_covid_holidays": (pad is None) or neuro,
        # prophet/cross_validator.py:51-52  cv_weights None si not is_neuro
        "prophet_cv_weights": neuro,
        # ensemble/model.py:199  clamp estacional si is_count_log_cohort
        "ensemble_clamp": count_log,
        # stacking/model.py:164  clamp estacional si is_count_log_cohort
        "stacking_clamp": count_log,
        # deepar/model.py:175-179  short_series si (pad truthy) AND not is_neuro
        "deepar_short_series": (pad is not None) and not neuro,
        # predice.py:287  invertir log (expm1) si is_count_log_cohort
        "invert_log_predict": count_log,
        # entrena.py:284  fallback regional híbrido solo si is_neuro
        "hybrid_fallback": neuro,
        # entrena.py:208-213  lote "General" = cohorte neuro
        "in_general_batch": neuro,
        # feature_engineering.yaml excluir_padecimientos
        "excluir_outliers": pad in _EXCLUIR_OUTLIERS,
    }


# Golden congelado: la verdad vigente ANTES de la migración al registry.
_NEURO_SIG: dict[str, bool] = {
    "is_neuro": True,
    "is_count_log_cohort": False,
    "prophet_rate_normalized": True,
    "deepar_rate_normalized": True,
    "prophet_log_transform": True,
    "prophet_enso": False,
    "nbglm_enso": False,
    "prophet_covid_holidays": True,
    "ensemble_covid_holidays": True,
    "prophet_cv_weights": True,
    "ensemble_clamp": False,
    "stacking_clamp": False,
    "deepar_short_series": False,
    "invert_log_predict": False,
    "hybrid_fallback": True,
    "in_general_batch": True,
    "excluir_outliers": False,
}

GOLDEN: dict[str, dict[str, bool]] = {
    "None": {
        "is_neuro": False,
        "is_count_log_cohort": False,
        "prophet_rate_normalized": True,
        "deepar_rate_normalized": True,
        "prophet_log_transform": False,
        "prophet_enso": False,
        "nbglm_enso": False,
        "prophet_covid_holidays": False,
        "ensemble_covid_holidays": True,  # pad is None -> holidays incluidas
        "prophet_cv_weights": False,
        "ensemble_clamp": False,
        "stacking_clamp": False,
        "deepar_short_series": False,
        "invert_log_predict": False,
        "hybrid_fallback": False,
        "in_general_batch": False,
        "excluir_outliers": False,
    },
    "Depresión": _NEURO_SIG,
    "Parkinson": _NEURO_SIG,
    "Alzheimer": _NEURO_SIG,
    "Dengue": {
        "is_neuro": False,
        "is_count_log_cohort": True,
        "prophet_rate_normalized": False,  # conteos (no tasa) en Prophet
        "deepar_rate_normalized": True,  # PERO DeepAR-Dengue sí usa tasa/100k
        "prophet_log_transform": True,
        "prophet_enso": True,
        "nbglm_enso": True,
        "prophet_covid_holidays": False,
        "ensemble_covid_holidays": False,
        "prophet_cv_weights": False,
        "ensemble_clamp": True,
        "stacking_clamp": True,
        "deepar_short_series": True,
        "invert_log_predict": True,
        "hybrid_fallback": False,
        "in_general_batch": False,
        "excluir_outliers": True,
    },
}


@pytest.mark.parametrize("pad", DISEASES, ids=lambda p: str(p))
def test_gate_signature_congelada(pad: str | None):
    assert _gate_signature(pad) == GOLDEN[str(pad)]


def test_none_no_es_ninguna_cohorte():
    # Bordes de None preservados (7 call sites dependen de esto).
    assert is_neuro(None) is False
    assert is_count_log_cohort(None) is False


def test_excluir_outliers_yaml_incluye_dengue():
    """La exención real vive en el YAML; confirmamos que el baseline coincide."""
    fe = Path("config/features/feature_engineering.yaml")
    if not fe.exists():
        pytest.skip("config/features/feature_engineering.yaml ausente")
    data = yaml.safe_load(fe.read_text(encoding="utf-8"))
    # busca la clave excluir_padecimientos en cualquier nivel
    found: list[str] = []

    def _walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k == "excluir_padecimientos" and isinstance(v, list):
                    found.extend(v)
                _walk(v)
        elif isinstance(o, list):
            for x in o:
                _walk(x)

    _walk(data)
    assert set(found) == set(_EXCLUIR_OUTLIERS)


# ── Freeze de la selección productiva legacy (red de seguridad para EPIC 3) ──
_SELECCION_LEGACY_SHA256 = "4b92c0367846de1b2161edef2f49e3cc6fc96ce724fe3d976caad287cf03e309"


def test_seleccion_productiva_legacy_congelada():
    from epiforecast import catalog

    if not (catalog._neuro_table_path().exists() and catalog._dengue_table_path().exists()):
        pytest.skip("artefactos de producción ausentes (sin DVC pull)")
    df, _ = catalog.build_production_catalog()
    rows = sorted(
        (r.disease_id, r.entidad, r.sexo, r.motor_productivo) for r in df.itertuples(index=False)
    )
    blob = "\n".join("|".join(map(str, t)) for t in rows)
    assert hashlib.sha256(blob.encode()).hexdigest() == _SELECCION_LEGACY_SHA256

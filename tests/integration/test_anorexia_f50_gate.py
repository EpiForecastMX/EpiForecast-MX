"""C6.2 — gate N+1: Anorexia F50 recorre dataset y backtest por las MISMAS interfaces.

Demuestra reutilización funcional del runner con un padecimiento nuevo dado de alta solo por
configuración. NO evalúa calidad del modelo: no hay umbral de sMAPE. Requiere datos locales
(PDFs extraídos + INEGI); si faltan, se salta explícitamente.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from epiforecast import registry
from epiforecast.data import epi_dataset as ed
from epiforecast.runner import orchestrator as orch

pytestmark = pytest.mark.integration

_F50 = "Anorexia F50"
_ENGINE = "seasonal_naive_lag52"
_ROOT = ed._ROOT
_RAW = _ROOT / "data" / "raw" / "data_raw_Anorexia_F50.csv"
_RAW_OBESIDAD = _ROOT / "data" / "raw" / "data_raw_Obesidad.csv"
_INEGI = _ROOT / "data" / "utils" / "inegi.csv"


def _require_data() -> None:
    if not _RAW.exists() or not _INEGI.exists():
        pytest.skip("datos locales F50/INEGI no disponibles (extracción o DVC no restaurados)")


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    _require_data()
    return tmp_path_factory.mktemp("runs_f50")


@pytest.fixture(scope="module")
def dataset(root):
    return orch.validate_data(_F50, runs_root=root)


@pytest.fixture(scope="module")
def smoke(root, dataset):
    man = orch.run_command(_F50, "benchmark", stage="smoke", engines=[_ENGINE], runs_root=root)
    return man, root / man.run_id


def test_gate_f50_no_es_el_bloque_de_obesidad():
    # F50 y Obesidad salen del MISMO cuadro (block_index 1 vs 0): todos los conteos del gate
    # pasarían igual con el bloque equivocado. Esta es la única comprobación que lo detecta.
    _require_data()
    if not _RAW_OBESIDAD.exists():
        pytest.skip("raw de Obesidad no disponible para el contraste")
    key = ["Anio", "Semana", "Entidad"]
    f50 = pd.read_csv(_RAW, usecols=[*key, "Casos_semana", "Padecimiento"])
    obe = pd.read_csv(_RAW_OBESIDAD, usecols=[*key, "Casos_semana"])
    assert set(f50["Padecimiento"]) == {"Anorexia F50"}
    unidas = f50.merge(obe, on=key, suffixes=("_f50", "_obe"))
    iguales = (unidas["Casos_semana_f50"] == unidas["Casos_semana_obe"]).mean()
    assert iguales < 0.05  # coincidencias solo por azar en valores pequeños
    assert f50["Casos_semana"].sum() < obe["Casos_semana"].sum() / 10  # órdenes distintos


def test_gate_f50_dataset(dataset, root):
    assert dataset.disease_id == "anorexia_f50"
    assert dataset.counts == {"base": 64, "derived": 47, "products": 111}
    assert set(dataset.digests) == {"raw", "exposure", "config", "dataset"}
    dsdir = root / dataset.dataset_id
    base = pd.read_csv(dsdir / "epi_dataset_v2.csv", dtype={"cve_ent": str})
    assert len(base) == 41_792 and base.groupby(["cve_ent", "sexo"]).ngroups == 64
    assert set(base.groupby(["cve_ent", "sexo"]).size().unique()) == {653}
    periodos = sorted({(y, w) for y, w in zip(base.epi_year, base.epi_week, strict=True)})
    assert len(periodos) == 653 and periodos[0] == (2014, 1) and periodos[-1] == (2026, 26)
    assert set(base.groupby(["epi_year", "epi_week"]).cve_ent.nunique().unique()) == {32}
    assert not base.duplicated(["cve_ent", "sexo", "epi_year", "epi_week"]).any()
    # Un solo total estado-periodo imputado (Querétaro) → 2 filas base (hombres + mujeres).
    imputadas = base[~base.observed]
    assert len(imputadas) == 2 and set(imputadas.cve_ent) == {"22"}
    # Ceros de baja incidencia: son datos, no faltantes.
    assert (base.y_cases == 0).mean() > 0.4 and base.y_cases.notna().all()

    productos = pd.read_csv(dsdir / "products.csv", dtype={"geography_id": str})
    assert len(productos) == 72_483
    assert productos.groupby(["geography_level", "geography_id", "sex"]).ngroups == 111
    assert (productos.y_cases >= 0).all() and productos.y_cases.notna().all()
    piv = productos.pivot_table(
        index=["geography_level", "geography_id", "epi_year", "epi_week"],
        columns="sex",
        values="y_cases",
    )
    assert (piv["general"] == piv["hombres"] + piv["mujeres"]).all()
    estados = (
        productos[(productos.geography_level == "estado") & (productos.sex == "general")]
        .groupby(["epi_year", "epi_week"])
        .y_cases.sum()
    )
    nacional = (
        productos[(productos.geography_level == "nacional") & (productos.sex == "general")]
        .set_index(["epi_year", "epi_week"])
        .y_cases.reindex(estados.index)
    )
    assert (estados == nacional).all()


def test_gate_f50_smoke_por_las_mismas_interfaces(smoke, dataset):
    man, run_dir = smoke
    assert man.status == "succeeded" and man.exit_code == 0
    assert man.disease_id == "anorexia_f50" and man.dataset_id == dataset.dataset_id
    spec = json.loads((run_dir / "artifacts" / _ENGINE / "spec.json").read_text(encoding="utf-8"))
    assert spec["fold_ids"] == ["development_2024"]  # rolling_cv_v1 INTACTA
    assert spec["policy_name"] == "rolling_cv_v1"
    assert spec["n_series_modeled"] == 64  # cero modelos derivados
    assert spec["base_predictions"] == 3_328 and spec["derived_eval_rows"] == 5_772
    assert spec["n_fallback"] == 0 and spec["disease_id"] == "anorexia_f50"

    forecast = pd.read_csv(run_dir / "artifacts" / _ENGINE / "forecast.csv")
    metricas = pd.read_csv(run_dir / "artifacts" / _ENGINE / "metrics.csv")
    assert len(forecast) == 5_772 and len(metricas) == 111
    assert (forecast.y_pred_cases >= 0).all() and forecast.y_pred_cases.notna().all()
    assert set(forecast.disease_id) == set(metricas.disease_id) == {"anorexia_f50"}
    # C6 no fija umbral de sMAPE: demuestra reutilización, no calidad productiva.


def test_gate_f50_reproducible(smoke, tmp_path_factory):
    _require_data()
    otro = tmp_path_factory.mktemp("runs_f50_repro")
    man2 = orch.run_command(_F50, "benchmark", stage="smoke", engines=[_ENGINE], runs_root=otro)
    man1, _ = smoke
    assert man2.run_id == man1.run_id
    d1 = sorted((a.schema, a.digest) for a in man1.jobs[_ENGINE].artifacts)
    d2 = sorted((a.schema, a.digest) for a in man2.jobs[_ENGINE].artifacts)
    assert d1 == d2


def test_gate_f50_sigue_invisible():
    assert registry.require(_F50).lifecycle == "configured"
    assert "anorexia_f50" not in [n.lower() for n in registry.names(published_only=True)]

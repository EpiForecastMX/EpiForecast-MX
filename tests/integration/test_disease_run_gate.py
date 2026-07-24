"""F2/C3 — gate de INTEGRACIÓN E66: disease_run end-to-end (dataset_id vs run_id + benchmark OOS).

validate-data materializa runs/<dataset_id>/ (DatasetManifest, intacto). benchmark crea un dir
run_id DISTINTO y corre los 6 motores candidatos (5 estacionales + ETS) en subprocess limpio, cada
uno produciendo forecast/eval/metrics para los 111 productos modelando SOLO 64 bases. El ETS añade
fit_diagnostics.csv con un ajuste por serie/fold. Requiere datos gitignored.
"""

from __future__ import annotations

import json

import pandas as pd
import pytest

from epiforecast.data import epi_dataset as ed
from epiforecast.runner import orchestrator as orch
from epiforecast.runner.manifest import DATASET_MANIFEST_SCHEMA, DatasetManifest

pytestmark = pytest.mark.integration

_ROOT = ed._ROOT
_RAW = _ROOT / "data" / "raw" / "data_raw_Obesidad.csv"
_INEGI = _ROOT / "data" / "utils" / "inegi.csv"
_ENGINES = [
    "seasonal_naive_lag52",
    "seasonal_mean_3y",
    "seasonal_median_3y",
    "seasonal_mean_5y",
    "seasonal_median_5y",
    "ets_add_damped_log1p",
]
_ETS = "ets_add_damped_log1p"
_N_TRAIN_POR_FOLD = [366, 418, 470, 522]  # semanas previas de cada fold dev (2021-24)


def _require_data() -> None:
    if not _RAW.exists() or not _INEGI.exists():
        pytest.skip("datos locales E66/INEGI no disponibles (DVC no restaurado)")


@pytest.fixture(scope="module")
def root(tmp_path_factory):
    _require_data()
    return tmp_path_factory.mktemp("runs")


@pytest.fixture(scope="module")
def dataset(root):
    return orch.validate_data("Obesidad", runs_root=root)


@pytest.fixture(scope="module")
def bench_full(root, dataset):
    man = orch.run_command("Obesidad", "benchmark", stage="full", runs_root=root)
    return man, root / man.run_id


def _spec(run_dir, engine):
    return json.loads((run_dir / "artifacts" / engine / "spec.json").read_text(encoding="utf-8"))


def test_gate_dataset_manifest(dataset, root):
    assert dataset.schema == DATASET_MANIFEST_SCHEMA
    assert dataset.counts == {"base": 64, "derived": 47, "products": 111}
    dsdir = root / dataset.dataset_id
    assert len(pd.read_csv(dsdir / "products.csv")) == 72_483
    assert {a.schema for a in dataset.artifacts} == {"epi_dataset_v2", "products.v1", "lineage.v1"}


def test_gate_benchmark_6_motores_succeeded(bench_full, dataset):
    man, _ = bench_full
    assert man.run_id != dataset.dataset_id and man.dataset_id == dataset.dataset_id
    assert man.status == "succeeded" and man.exit_code == 0
    assert man.engines == _ENGINES  # candidatos de la política, no training_engines legacy
    assert set(man.input_digests) == {"raw", "exposure", "config", "dataset"}
    assert man.counts == {"base": 64, "derived": 47, "products": 111}
    for e in _ENGINES:
        assert man.jobs[e].is_complete()  # succeeded + artefactos verificados


@pytest.mark.parametrize("engine", _ENGINES)
def test_gate_cobertura_por_motor(bench_full, engine):
    _, run_dir = bench_full
    spec = _spec(run_dir, engine)
    assert spec["n_series_modeled"] == 64  # cero modelos para general/región/nacional
    assert spec["base_predictions"] == 13_312  # 64 × 208
    assert spec["derived_eval_rows"] == 23_088  # 111 × 208
    assert spec["n_fallback"] == 0  # en folds dev cada semana tiene su historial
    ad = run_dir / "artifacts" / engine
    assert len(pd.read_csv(ad / "forecast.csv")) == 23_088
    mt = pd.read_csv(ad / "metrics.csv")
    assert len(mt) == 444 and mt.groupby(["geography_level", "geography_id", "sex"]).ngroups == 111


def test_gate_diagnosticos_de_ajuste_solo_del_ets(bench_full):
    # Un ajuste por serie/fold (64×4) SOLO en el motor que entrena; los estacionales no ajustan.
    _, run_dir = bench_full
    for engine in _ENGINES:
        emits = engine == _ETS
        assert _spec(run_dir, engine)["n_diagnostics"] == (256 if emits else 0)
        assert (run_dir / "artifacts" / engine / "fit_diagnostics.csv").exists() is emits
        # La duración por serie es telemetría wall-clock: fuera de los artefactos con digest.
        assert (run_dir / "jobs" / f"{engine}.fit_timing.csv").exists()

    diag = pd.read_csv(run_dir / "artifacts" / _ETS / "fit_diagnostics.csv")
    assert len(diag) == 256 and diag.groupby(["geography_id", "sex"]).ngroups == 64
    assert sorted(diag["n_train"].unique()) == _N_TRAIN_POR_FOLD
    assert set(diag["variant"]) <= {"primary", "retry"}
    assert diag["transform_digest"].nunique() == 1 and diag["config_digest"].nunique() == 1
    spec = _spec(run_dir, _ETS)
    assert spec["transform"]["forward_steps"] == ["log1p"]  # inversa expm1 por contrato
    assert spec["transform"]["inverse_steps"] == ["expm1"]
    assert spec["transform_digest"] == diag["transform_digest"].iloc[0]
    assert spec["resource_limits"] == {"max_threads": 1}


def test_gate_reporte_comparativo(bench_full):
    _, run_dir = bench_full
    comp = pd.read_csv(run_dir / "comparison.csv")  # auto-generado en el run multi-motor
    assert set(comp["engine"]) == set(_ENGINES) and len(comp) == 6
    assert {"smape_bases", "smape_all", "smape_nacional_general", "runtime_s"} <= set(comp.columns)
    base = comp[comp["engine"] == "seasonal_naive_lag52"]["smape_all_impr_pct_vs_baseline"].iloc[0]
    assert base == 0.0  # el baseline no mejora sobre sí mismo (no se elige ganador)


def test_gate_validate_data_intacto_tras_benchmark(bench_full, dataset, root):
    back = DatasetManifest.read(root / dataset.dataset_id)
    assert back.counts == {"base": 64, "derived": 47, "products": 111}
    assert all(a.validated for a in back.artifacts)


def test_gate_reproducible(bench_full, tmp_path_factory):
    _require_data()
    root2 = tmp_path_factory.mktemp("runs2")
    man2 = orch.run_command("Obesidad", "benchmark", stage="full", runs_root=root2)
    man1 = bench_full[0]
    assert man2.run_id == man1.run_id
    for e in _ENGINES:
        d1 = sorted((a.schema, a.digest) for a in man1.jobs[e].artifacts)
        d2 = sorted((a.schema, a.digest) for a in man2.jobs[e].artifacts)
        assert d1 == d2

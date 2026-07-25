"""F2/C3 — gate de INTEGRACIÓN E66: disease_run end-to-end (dataset_id vs run_id + benchmark OOS).

validate-data materializa runs/<dataset_id>/ (DatasetManifest, intacto). benchmark crea un dir
run_id DISTINTO y corre los 9 motores candidatos (5 estacionales + ETS + Ridge armónico + los dos
perfiles Prophet) en subprocess limpio, cada uno produciendo forecast/eval/metrics para los 111
productos modelando SOLO 64 bases. Los cuatro motores que ajustan añaden fit_diagnostics.csv (una
fila por serie/fold). Requiere datos gitignored.
"""

from __future__ import annotations

import json
import shutil

import numpy as np
import pandas as pd
import pytest

from epiforecast.data import epi_dataset as ed
from epiforecast.runner import acceptance, final_models, selection
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
    "ridge_harmonic_log1p",
    "prophet_count_log1p",
    "prophet_rate_log1p",
]
_ETS = "ets_add_damped_log1p"
_RIDGE = "ridge_harmonic_log1p"
_PROPHET_COUNT = "prophet_count_log1p"
_PROPHET_RATE = "prophet_rate_log1p"
# Los que entrenan (y por tanto emiten un diagnóstico de ajuste por serie/fold).
_AJUSTAN = (_ETS, _RIDGE, _PROPHET_COUNT, _PROPHET_RATE)
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


@pytest.fixture(scope="module")
def selection_run(root, bench_full):
    man, _ = bench_full
    sel_man = orch.run_selection("Obesidad", man.run_id, runs_root=root)
    return sel_man, root / sel_man.run_id


def _spec(run_dir, engine):
    return json.loads((run_dir / "artifacts" / engine / "spec.json").read_text(encoding="utf-8"))


def test_gate_dataset_manifest(dataset, root):
    assert dataset.schema == DATASET_MANIFEST_SCHEMA
    assert dataset.counts == {"base": 64, "derived": 47, "products": 111}
    dsdir = root / dataset.dataset_id
    assert len(pd.read_csv(dsdir / "products.csv")) == 72_483
    assert {a.schema for a in dataset.artifacts} == {"epi_dataset_v2", "products.v1", "lineage.v1"}


def test_gate_benchmark_9_motores_succeeded(bench_full, dataset):
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


def _diagnostics(run_dir, engine):
    return pd.read_csv(run_dir / "artifacts" / engine / "fit_diagnostics.csv")


def test_gate_diagnosticos_solo_de_los_motores_que_ajustan(bench_full):
    # Un ajuste por serie/fold (64×4) SOLO en los motores que entrenan; los estacionales no ajustan.
    _, run_dir = bench_full
    for engine in _ENGINES:
        emits = engine in _AJUSTAN
        assert _spec(run_dir, engine)["n_diagnostics"] == (256 if emits else 0)
        assert (run_dir / "artifacts" / engine / "fit_diagnostics.csv").exists() is emits
        # La duración por serie es telemetría wall-clock: fuera de los artefactos con digest.
        assert (run_dir / "jobs" / f"{engine}.fit_timing.csv").exists()

    for engine in _AJUSTAN:
        diag = _diagnostics(run_dir, engine)
        spec = _spec(run_dir, engine)
        assert len(diag) == 256 and diag.groupby(["geography_id", "sex"]).ngroups == 64
        assert sorted(diag["n_train"].unique()) == _N_TRAIN_POR_FOLD
        assert diag["transform_digest"].nunique() == 1 and diag["config_digest"].nunique() == 1
        # expm1 gobernado por el contrato en TODOS los motores que transforman el objetivo.
        assert spec["transform"]["forward_steps"][-1] == "log1p"
        assert spec["transform"]["inverse_steps"][0] == "expm1"
        assert spec["transform_digest"] == diag["transform_digest"].iloc[0]
        assert spec["resource_limits"] == {"max_threads": 1}
    assert set(_diagnostics(run_dir, _ETS)["variant"]) <= {"primary", "retry"}


def test_gate_seleccion_interna_del_ridge(bench_full):
    # 256 refits exteriores × 9 candidatos = 2,304 ajustes internos (2,560 Ridge en total).
    _, run_dir = bench_full
    diag = _diagnostics(run_dir, _RIDGE)
    assert (diag["n_candidates"] == 9).all() and (diag["n_candidates_valid"] == 9).all()
    assert int(diag["n_candidates"].sum()) == 2_304
    assert (diag["n_inner_validation"] == 52).all()
    assert (diag["n_inner_train"] == diag["n_train"] - 52).all()  # el holdout nunca entra
    assert set(diag["fourier_order"]) <= {2, 4, 6} and set(diag["alpha"]) <= {0.1, 1.0, 10.0}
    assert diag["inner_smape"].between(0, 200).all()
    spec = _spec(run_dir, _RIDGE)
    assert spec["engine_params"]["solver"] == "svd"  # determinista
    assert spec["engine_params"]["sklearn_version"]  # versión efectiva registrada


def test_gate_perfiles_prophet_congelados_y_por_metadata(bench_full):
    # Los dos perfiles difieren SOLO en su TransformContract y usan la config congelada del tuning.
    _, run_dir = bench_full
    count, rate = _spec(run_dir, _PROPHET_COUNT), _spec(run_dir, _PROPHET_RATE)
    assert count["transform"]["forward_steps"] == ["log1p"]
    assert count["transform"]["rate_scale"] is None
    assert rate["transform"]["forward_steps"] == ["rate_per_exposure", "log1p"]
    assert rate["transform"]["inverse_steps"] == ["expm1", "rate_to_count"]
    assert rate["transform"]["rate_scale"] == 100_000.0  # del perfil del registry
    for spec in (count, rate):
        frozen = spec["engine_params"]["frozen"]
        assert set(frozen) == {
            "seasonality_mode",
            "changepoint_prior_scale",
            "seasonality_prior_scale",
            "fourier_order",
        }
        assert spec["engine_params"]["uncertainty_samples"] == 0  # MAP, sin intervalos
        assert spec["engine_params"]["mcmc_samples"] == 0
        assert spec["engine_params"]["yearly_seasonality"] is False  # nativas desactivadas
        assert spec["engine_params"]["prophet_version"]
    # Las diagnósticas registran la configuración efectiva, idéntica en las 256 serie/folds.
    diag = _diagnostics(run_dir, _PROPHET_RATE)
    assert diag["fourier_order"].nunique() == 1 and diag["seasonality_mode"].nunique() == 1


def test_gate_reporte_comparativo(bench_full):
    _, run_dir = bench_full
    comp = pd.read_csv(run_dir / "comparison.csv")  # auto-generado en el run multi-motor
    assert set(comp["engine"]) == set(_ENGINES) and len(comp) == 9
    assert {"smape_bases", "smape_all", "smape_nacional_general", "runtime_s"} <= set(comp.columns)
    base = comp[comp["engine"] == "seasonal_naive_lag52"]["smape_all_impr_pct_vs_baseline"].iloc[0]
    assert base == 0.0  # el baseline no mejora sobre sí mismo (no se elige ganador)


def test_gate_seleccion_congelada(selection_run):
    # Mapa serie→motor sobre development; los 47 derivados NUNCA eligen motor.
    man, sel_dir = selection_run
    sel = pd.read_csv(sel_dir / "selection.csv", dtype={"geography_id": str})
    assert len(sel) == 64 and not sel.duplicated(["geography_id", "sex"]).any()
    assert sel["selected_engine"].value_counts().to_dict() == {
        "seasonal_mean_5y": 16,
        "ets_add_damped_log1p": 16,
        "ridge_harmonic_log1p": 12,
        "seasonal_median_5y": 10,
        "prophet_rate_log1p": 5,
        "prophet_count_log1p": 5,
    }
    assert int((sel["tier"] == "challenger").sum()) == 10  # Prophet entra en 10/64
    challengers = sel[sel["tier"] == "challenger"]
    assert (challengers["challenger_improvement_pct"] >= 5.0).all()
    incumbents = sel[sel["tier"] == "incumbent"]
    assert (incumbents["challenger_improvement_pct"] < 5.0).all()
    assert man.input_digests["selection"]


def test_gate_portafolio_de_desarrollo(selection_run):
    _, sel_dir = selection_run
    manifest = json.loads((sel_dir / "selection_manifest.json").read_text(encoding="utf-8"))
    resumen = manifest["portfolio_development"]
    assert resumen["smape_bases"] == pytest.approx(26.07, abs=0.01)
    assert resumen["smape_all"] == pytest.approx(24.52, abs=0.01)
    assert resumen["smape_nacional_general"] == pytest.approx(14.40, abs=0.01)

    portfolio = pd.read_csv(sel_dir / "portfolio_development.csv", dtype={"geography_id": str})
    assert len(portfolio) == 444  # 111 productos × 4 folds
    assert portfolio.groupby(["geography_level", "geography_id", "sex"]).ngroups == 111
    assert set(portfolio["engine"]) == {"portfolio"}  # identidad del portafolio, no del donante
    assert manifest["selection_digest"] and manifest["rule"]["band_pct"] == 5.0


def test_gate_seleccion_cargable_y_sellada(selection_run, tmp_path):
    _, sel_dir = selection_run
    sel, manifest = selection.load_frozen_selection(sel_dir)
    assert len(sel) == 64 and manifest["counts"]["series"] == 64
    assert (sel_dir / "selection_report.md").read_text(encoding="utf-8").startswith("# Selección")
    # El manifiesto sella los otros tres artefactos: alterar uno invalida la carga. Se altera una
    # COPIA: la selección oficial queda intacta para el stage test.
    copia = tmp_path / "copia"
    shutil.copytree(sel_dir, copia)
    (copia / "selection_report.md").write_text("alterado", encoding="utf-8")
    with pytest.raises(selection.SelectionError, match="alterado"):
        selection.load_frozen_selection(copia)


@pytest.fixture(scope="module")
def test_stage(root, selection_run):
    sel_man, _ = selection_run
    man = orch.run_command(
        "Obesidad", "benchmark", stage="test", runs_root=root, selection_run_id=sel_man.run_id
    )
    return man, root / man.run_id


def test_gate_2025_solo_con_seleccion_congelada(test_stage, selection_run):
    # El stage test corre SOLO las familias seleccionadas + el control, y lleva el selection_digest.
    man, run_dir = test_stage
    sel_man, _ = selection_run
    assert man.status == "succeeded" and man.stage == "test"
    assert man.input_digests["selection"] == sel_man.input_digests["selection"]
    assert set(man.engines) == {
        "seasonal_mean_5y",
        "seasonal_median_5y",
        "ets_add_damped_log1p",
        "ridge_harmonic_log1p",
        "prophet_count_log1p",
        "prophet_rate_log1p",
        "seasonal_naive_lag52",  # control
    }
    job_ctx = json.loads((run_dir / "job_context.json").read_text(encoding="utf-8"))
    assert job_ctx["selection_digest"] == sel_man.input_digests["selection"]
    assert man.input_digests["selection"][:12] in man.run_id  # identidad del run

    for engine in man.engines:  # 2025 completo: 53 semanas, sin fallbacks
        spec = _spec(run_dir, engine)
        assert spec["fold_ids"] == ["test_2025"]
        assert spec["base_predictions"] == 64 * 53 == 3_392
        assert spec["derived_eval_rows"] == 111 * 53 == 5_883
        assert spec["n_fallback"] == 0


def test_gate_aceptacion_2025(test_stage):
    _, run_dir = test_stage
    acc = json.loads((run_dir / "acceptance.json").read_text(encoding="utf-8"))
    assert acc["accepted"] is True
    assert {c["scope"] for c in acc["checks"]} == {
        "smape_bases",
        "smape_all",
        "smape_nacional_general",
    }
    for check in acc["checks"]:  # el portafolio mejora al control en los tres ámbitos
        assert check["passed"] and check["worse_pct"] < 0

    portfolio = pd.read_csv(run_dir / "portfolio_test.csv", dtype={"geography_id": str})
    assert len(portfolio) == 111 and set(portfolio["split"]) == {"test"}
    assert portfolio.groupby(["geography_level", "geography_id", "sex"]).ngroups == 111

    final, _ = acceptance.load_accepted(run_dir)
    assert len(final) == 64 and set(final["source"]) == {"development_selection"}
    assert final["selected_engine"].value_counts().to_dict() == {
        "seasonal_mean_5y": 16,
        "ets_add_damped_log1p": 16,
        "ridge_harmonic_log1p": 12,
        "seasonal_median_5y": 10,
        "prophet_rate_log1p": 5,
        "prophet_count_log1p": 5,
    }  # el mapa de desarrollo queda aceptado SIN modificaciones


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


@pytest.fixture(scope="module")
def refit_run(root, test_stage):
    man, _ = test_stage
    refit = orch.run_command("Obesidad", "refit", runs_root=root, acceptance_run_id=man.run_id)
    return refit, root / refit.run_id


@pytest.fixture(scope="module")
def forecast_run(root, refit_run):
    man, _ = refit_run
    fc = orch.run_command(
        "Obesidad", "forecast", horizon=52, runs_root=root, refit_run_id=man.run_id
    )
    return fc, root / fc.run_id


def test_gate_refit_final(refit_run):
    # 64 modelos, uno por base seleccionada; cero para derivados; toda la historia.
    man, run_dir = refit_run
    assert man.status == "succeeded"
    summary = json.loads((run_dir / "refit_summary.json").read_text(encoding="utf-8"))
    assert summary["n_models"] == 64 and summary["final_refit"] is True
    assert summary["n_train_values"] == [653] and summary["train_end"] == [2026, 26]
    assert summary["distribution"] == {
        "seasonal_mean_5y": 16,
        "ets_add_damped_log1p": 16,
        "ridge_harmonic_log1p": 12,
        "seasonal_median_5y": 10,
        "prophet_rate_log1p": 5,
        "prophet_count_log1p": 5,
    }
    total = 0
    for engine in man.engines:  # todos los envelopes y estados deben cargar y verificar sello
        modelos = final_models.load_models(run_dir, engine)
        total += len(modelos)
        for envelope, _ in modelos:
            assert envelope["series_key"]["geography_level"] == "estado"
            assert envelope["final_refit"] and envelope["n_train"] == 653
    assert total == 64


def _consistencia(full: pd.DataFrame) -> None:
    piv = full.pivot_table(
        index=["geography_level", "geography_id", "epi_year", "epi_week"],
        columns="sex",
        values="y_pred_cases",
    )
    assert np.allclose(piv["general"], piv["hombres"] + piv["mujeres"], rtol=0, atol=1e-9)
    estados = full[(full.geography_level == "estado") & (full.sex == "general")]
    nacional = full[(full.geography_level == "nacional") & (full.sex == "general")]
    por_periodo = estados.groupby(["epi_year", "epi_week"])["y_pred_cases"].sum()
    nac = nacional.set_index(["epi_year", "epi_week"])["y_pred_cases"].reindex(por_periodo.index)
    assert np.allclose(por_periodo.to_numpy(), nac.to_numpy(), rtol=0, atol=1e-9)


def test_gate_forecast_preliminar(forecast_run):
    man, run_dir = forecast_run
    assert man.status == "succeeded"
    base = pd.read_csv(run_dir / "forecast_base.csv", dtype={"geography_id": str})
    full = pd.read_csv(run_dir / "forecast.csv", dtype={"geography_id": str})
    assert len(base) == 3_328 and len(full) == 5_772
    assert full.groupby(["geography_level", "geography_id", "sex"]).ngroups == 111
    periodos = sorted({(y, w) for y, w in zip(full.epi_year, full.epi_week, strict=True)})
    assert len(periodos) == 52 and periodos[0] == (2026, 27) and periodos[-1] == (2027, 26)
    assert not full.duplicated(
        ["geography_level", "geography_id", "sex", "epi_year", "epi_week"]
    ).any()
    assert full["y_pred_cases"].notna().all() and (full["y_pred_cases"] >= 0).all()
    assert np.isfinite(full["y_pred_cases"]).all()
    assert full["yhat_lower"].isna().all() and full["yhat_upper"].isna().all()  # point-only
    _consistencia(full)
    lineage = json.loads((run_dir / "lineage.json").read_text(encoding="utf-8"))
    assert lineage["refit_digest"] and lineage["products"] == 111


def test_gate_forecast_portable(forecast_run, refit_run, tmp_path_factory):
    # El refit copiado a otro runs_root pronostica lo MISMO, sin depender de rutas originales.
    _, refit_dir = refit_run
    _, original_dir = forecast_run
    otro = tmp_path_factory.mktemp("runs_portable")
    shutil.copytree(refit_dir, otro / refit_dir.name)
    orch.validate_data("Obesidad", runs_root=otro)
    portable = orch.run_command(
        "Obesidad", "forecast", horizon=52, runs_root=otro, refit_run_id=refit_dir.name
    )
    assert portable.status == "succeeded"
    cols = ["geography_level", "geography_id", "sex", "epi_year", "epi_week", "y_pred_cases"]
    izq = pd.read_csv(otro / portable.run_id / "forecast.csv", dtype={"geography_id": str})
    der = pd.read_csv(original_dir / "forecast.csv", dtype={"geography_id": str})
    assert (
        izq[cols]
        .sort_values(cols)
        .reset_index(drop=True)
        .equals(der[cols].sort_values(cols).reset_index(drop=True))
    )  # numéricamente idéntico


def test_gate_estado_retirado_deja_el_run_failed(refit_run, tmp_path_factory):
    _, refit_dir = refit_run
    roto = tmp_path_factory.mktemp("runs_roto")
    shutil.copytree(refit_dir, roto / refit_dir.name)
    orch.validate_data("Obesidad", runs_root=roto)
    estados = sorted((roto / refit_dir.name / "models" / "seasonal_mean_5y").glob("*.state.json"))
    estados[0].unlink()  # retirar un estado sellado
    with pytest.raises((final_models.FinalModelError, orch.RunnerError)):
        orch.run_command(
            "Obesidad", "forecast", horizon=52, runs_root=roto, refit_run_id=refit_dir.name
        )

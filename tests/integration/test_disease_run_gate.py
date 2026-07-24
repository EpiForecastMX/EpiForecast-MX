"""F2/C3 — gate de INTEGRACIÓN E66: disease_run end-to-end (dataset_id vs run_id + benchmark OOS).

validate-data materializa runs/<dataset_id>/ (DatasetManifest, intacto). benchmark crea un dir
run_id DISTINTO, corre seasonal_naive_lag52 en subprocess limpio y produce forecast/eval/metrics
para los 111 productos modelando SOLO 64 bases. Requiere datos gitignored (DVC); skip si faltan.
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


def _spec(run_dir):
    return json.loads(
        (run_dir / "artifacts" / "seasonal_naive_lag52" / "spec.json").read_text(encoding="utf-8")
    )


def test_gate_dataset_manifest(dataset, root):
    assert dataset.schema == DATASET_MANIFEST_SCHEMA
    assert dataset.counts == {"base": 64, "derived": 47, "products": 111}
    dsdir = root / dataset.dataset_id
    assert len(pd.read_csv(dsdir / "products.csv")) == 72_483
    assert {a.schema for a in dataset.artifacts} == {"epi_dataset_v2", "products.v1", "lineage.v1"}


def test_gate_benchmark_succeeded_dir_distinto(bench_full, dataset):
    man, _ = bench_full
    assert man.run_id != dataset.dataset_id and man.dataset_id == dataset.dataset_id
    assert man.stage == "full" and man.policy_digest and man.engines == ["seasonal_naive_lag52"]
    assert man.status == "succeeded" and man.exit_code == 0
    # Digests y conteos del DatasetManifest viajaron al RunManifest (C3a.1).
    assert set(man.input_digests) == {"raw", "exposure", "config", "dataset"}
    assert man.counts == {"base": 64, "derived": 47, "products": 111}
    job = man.jobs["seasonal_naive_lag52"]
    assert job.is_complete()  # succeeded + artefactos validados (digest re-verificado)
    assert {a.schema for a in job.artifacts} == {
        "forecast.v1",
        "evaluation.v1",
        "metrics.v1",
        "engine_spec.v1",
    }


def test_gate_cobertura_64_modeladas_111_evaluadas(bench_full):
    man, run_dir = bench_full
    spec = _spec(run_dir)
    assert spec["n_series_modeled"] == 64  # cero modelos para general/región/nacional
    assert spec["base_predictions"] == 13_312  # 64 × 208 (4 folds × 52)
    assert spec["derived_eval_rows"] == 23_088  # 111 × 208
    assert spec["fold_ids"] == [f"development_{y}" for y in (2021, 2022, 2023, 2024)]

    ad = run_dir / "artifacts" / "seasonal_naive_lag52"
    fc = pd.read_csv(ad / "forecast.csv")
    assert len(fc) == 23_088  # 111 productos × 208
    mt = pd.read_csv(ad / "metrics.csv")
    assert len(mt) == 444  # 111 × 4 folds
    assert mt.groupby(["geography_level", "geography_id", "sex"]).ngroups == 111


def test_gate_validate_data_intacto_tras_benchmark(bench_full, dataset, root):
    # El benchmark NO tocó el DatasetManifest de validate-data.
    back = DatasetManifest.read(root / dataset.dataset_id)
    assert back.counts == {"base": 64, "derived": 47, "products": 111}
    assert all(a.validated for a in back.artifacts)


def test_gate_run_id_distinto_por_stage(bench_full, root):
    smoke = orch.run_command("Obesidad", "benchmark", stage="smoke", runs_root=root)
    assert smoke.run_id != bench_full[0].run_id  # distinto stage → distinto run_id
    assert smoke.status == "succeeded"


def test_gate_reproducible(bench_full, tmp_path_factory):
    # Segundo run en otro runs_root: mismo run_id y mismos digests de artefactos.
    _require_data()
    root2 = tmp_path_factory.mktemp("runs2")
    man2 = orch.run_command("Obesidad", "benchmark", stage="full", runs_root=root2)
    man1 = bench_full[0]
    assert man2.run_id == man1.run_id
    d1 = sorted((a.schema, a.digest) for a in man1.jobs["seasonal_naive_lag52"].artifacts)
    d2 = sorted((a.schema, a.digest) for a in man2.jobs["seasonal_naive_lag52"].artifacts)
    assert d1 == d2

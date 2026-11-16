"""Guarda de integridad en ``orchestrator.run_selection``: ``bench.policy_digest`` == actual.

Pruebas 100% sintéticas y herméticas (``tmp_path`` + ``monkeypatch``, sin runs reales ni procesos
externos) que verifican:
1. Rechazo explícito con ``RunnerError`` accionable (incluyendo ``expected`` y ``actual`` completos)
   ANTES de cargar artefactos CSV o ejecutar ``selection.build_selection`` cuando ``policy_digest``
   del benchmark difiere del ``load_policy(declared_policy(...)).digest`` vigente o está ausente.
2. Preservación exacta del camino original cuando ``bench.policy_digest == policy.digest``.
3. Preservación de todas las guardas previas de ``run_selection``.
4. Constancia ejecutable de que la afirmación C5 de Opus es FALSA: bajo ``rolling_cv_v1`` (aun con
   ``policy_digest`` coincidente), un benchmark con sólo los 5 motores estacionales ya falla cerrado
   en ``selection.select_for_series`` por incumbents faltantes (``ETS`` y ``Ridge``).
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from epiforecast.runner import contracts as ct
from epiforecast.runner import orchestrator, selection
from epiforecast.runner.manifest import (
    STAGE_FULL,
    STATUS_FAILED,
    STATUS_SUCCEEDED,
    ArtifactRecord,
    DatasetManifest,
    JobRecord,
    RunManifest,
)
from epiforecast.runner.policy import load_policy

_DISEASE = "obesidad"
_DATASET_ID = "obesidad_sintetico_001"
_BENCH_RUN = "obesidad_benchmark_full_sintetico001"
_COMMIT_PIN = "373ea5f6833473f26f80bb998ed2ecbfe1da334f"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _install_hermetic_stubs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> DatasetManifest:
    """Aísla ``validate_data``, ``_git_commit`` y ``evaluate_portfolio`` sin tocar ``load_policy``."""
    dm = DatasetManifest(
        dataset_id=_DATASET_ID,
        disease_id=_DISEASE,
        code_commit=_COMMIT_PIN,
        digests={
            "raw": "a" * 64,
            "exposure": "b" * 64,
            "config": "c" * 64,
            "dataset": "d" * 64,
        },
        counts={"base": 64, "derived": 47, "products": 111},
    )
    ds_dir = tmp_path / _DATASET_ID
    ds_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(
        [
            {
                "geography_level": "nacional",
                "geography_id": "mx",
                "sex": "general",
                "epi_year": 2024,
                "epi_week": 1,
                "y_cases": 100.0,
            }
        ]
    ).to_csv(ds_dir / "products.csv", index=False)

    def _fake_evaluate_portfolio(
        base_forecast: pd.DataFrame,
        products: pd.DataFrame,
        policy: Any,
        split: str,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        assert split == ct.SPLIT_DEVELOPMENT
        assert len(base_forecast) == 64
        assert not products.empty and policy.digest
        portfolio_metrics = pd.DataFrame(
            [
                {
                    "engine": selection.PORTFOLIO_ENGINE,
                    "geography_level": "estado",
                    "geography_id": "01",
                    "sex": "hombres",
                    ct.COL_SMAPE: 18.5,
                    ct.COL_MASE: 0.75,
                },
                {
                    "engine": selection.PORTFOLIO_ENGINE,
                    "geography_level": "estado",
                    "geography_id": "01",
                    "sex": "mujeres",
                    ct.COL_SMAPE: 19.5,
                    ct.COL_MASE: 0.85,
                },
                {
                    "engine": selection.PORTFOLIO_ENGINE,
                    "geography_level": "nacional",
                    "geography_id": "mx",
                    "sex": "general",
                    ct.COL_SMAPE: 12.0,
                    ct.COL_MASE: 0.65,
                },
            ]
        )
        return pd.DataFrame(), portfolio_metrics

    monkeypatch.setattr(orchestrator, "validate_data", lambda *_a, **_k: dm)
    monkeypatch.setattr(orchestrator, "_git_commit", lambda: _COMMIT_PIN)
    monkeypatch.setattr(selection, "evaluate_portfolio", _fake_evaluate_portfolio)
    return dm


def _write_synthetic_benchmark(
    runs_root: Path,
    *,
    policy_digest_value: str | None,
    engines: tuple[str, ...] | None = None,
    dataset_id: str = _DATASET_ID,
    stage: str = STAGE_FULL,
    status: str = STATUS_SUCCEEDED,
    command: str = "benchmark",
    run_id: str = _BENCH_RUN,
) -> Path:
    """Escribe un benchmark sintético completo y sellado por SHA-256 bajo ``runs_root``."""
    if engines is None:
        rule = selection.SelectionRule.from_policy(load_policy("rolling_cv_v1"))
        engines = rule.incumbents

    bench_dir = runs_root / run_id
    bench_dir.mkdir(parents=True, exist_ok=True)
    jobs: dict[str, JobRecord] = {}

    for idx, engine in enumerate(engines):
        art_dir = bench_dir / "artifacts" / engine
        art_dir.mkdir(parents=True, exist_ok=True)

        metrics_rows = [
            {
                ct.COL_ENGINE: engine,
                ct.COL_FOLD: "development_2024",
                ct.COL_SPLIT: ct.SPLIT_DEVELOPMENT,
                "geography_level": "estado",
                "geography_id": f"{state_idx:02d}",
                "sex": sex,
                ct.COL_SMAPE: 20.0 + float(idx),
                ct.COL_MASE: 0.80 + 0.01 * float(idx),
                ct.COL_RMSE: 3.0 + 0.1 * float(idx),
            }
            for state_idx in range(1, 33)
            for sex in ("hombres", "mujeres")
        ]
        metrics_path = art_dir / "metrics.csv"
        pd.DataFrame(metrics_rows).to_csv(metrics_path, index=False)

        forecast_rows = [
            {
                ct.COL_RUN_ID: run_id,
                ct.COL_ENGINE: engine,
                ct.COL_FOLD: "development_2024",
                "geography_level": "estado",
                "geography_id": f"{state_idx:02d}",
                "sex": sex,
                "epi_year": 2024,
                "epi_week": 1,
                "y_pred_cases": 5.0,
            }
            for state_idx in range(1, 33)
            for sex in ("hombres", "mujeres")
        ]
        forecast_path = art_dir / "forecast.csv"
        pd.DataFrame(forecast_rows).to_csv(forecast_path, index=False)

        jobs[engine] = JobRecord(
            engine=engine,
            status=STATUS_SUCCEEDED,
            exit_code=0,
            artifacts=[
                ArtifactRecord(
                    path=str(metrics_path.relative_to(bench_dir)),
                    digest=_sha256(metrics_path),
                    schema="metrics.v1",
                    validated=True,
                ),
                ArtifactRecord(
                    path=str(forecast_path.relative_to(bench_dir)),
                    digest=_sha256(forecast_path),
                    schema="forecast.v1",
                    validated=True,
                ),
            ],
        )

    RunManifest(
        run_id=run_id,
        disease_id=_DISEASE,
        command=command,
        dataset_id=dataset_id,
        stage=stage,
        status=status,
        code_commit=_COMMIT_PIN,
        policy_digest=policy_digest_value,
        engines=list(engines),
        jobs=jobs,
    ).write(bench_dir)
    return bench_dir


def _spy_downstream_calls(monkeypatch: pytest.MonkeyPatch) -> dict[str, int]:
    """Cuenta lecturas CSV y llamadas a ``build_selection`` para probar rechazo previo."""
    counts = {"read_csv": 0, "build_selection": 0}
    real_read_csv = pd.read_csv
    real_build_selection = selection.build_selection

    def _counted_read_csv(*args: Any, **kwargs: Any) -> Any:
        counts["read_csv"] += 1
        return real_read_csv(*args, **kwargs)

    def _counted_build_selection(*args: Any, **kwargs: Any) -> pd.DataFrame:
        counts["build_selection"] += 1
        return real_build_selection(*args, **kwargs)

    monkeypatch.setattr(pd, "read_csv", _counted_read_csv)
    monkeypatch.setattr(selection, "build_selection", _counted_build_selection)
    return counts


def test_select_rechaza_policy_digest_de_otra_politica_antes_de_cargar_artefactos(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_hermetic_stubs(tmp_path, monkeypatch)
    expected_policy = load_policy("rolling_cv_v1")
    foreign_policy = load_policy("rolling_cv_baja_incidencia_v1")
    assert expected_policy.digest != foreign_policy.digest

    _write_synthetic_benchmark(tmp_path, policy_digest_value=foreign_policy.digest)
    calls = _spy_downstream_calls(monkeypatch)

    with pytest.raises(orchestrator.RunnerError) as exc_info:
        orchestrator.run_selection(_DISEASE, _BENCH_RUN, runs_root=tmp_path)

    msg = str(exc_info.value)
    assert _BENCH_RUN in msg
    assert "rolling_cv_v1" in msg
    assert expected_policy.digest in msg
    assert foreign_policy.digest in msg
    assert calls == {"read_csv": 0, "build_selection": 0}
    assert list(tmp_path.glob(f"{_DISEASE}_select_*")) == []


def test_select_rechaza_override_policy_name_con_digest_distinto(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_hermetic_stubs(tmp_path, monkeypatch)
    bench_policy = load_policy("rolling_cv_v1")
    target_policy = load_policy("rolling_cv_baja_incidencia_v1")

    _write_synthetic_benchmark(tmp_path, policy_digest_value=bench_policy.digest)
    calls = _spy_downstream_calls(monkeypatch)

    with pytest.raises(orchestrator.RunnerError) as exc_info:
        orchestrator.run_selection(
            _DISEASE,
            _BENCH_RUN,
            policy_name="rolling_cv_baja_incidencia_v1",
            runs_root=tmp_path,
        )

    msg = str(exc_info.value)
    assert "rolling_cv_baja_incidencia_v1" in msg
    assert target_policy.digest in msg
    assert bench_policy.digest in msg
    assert calls == {"read_csv": 0, "build_selection": 0}
    assert list(tmp_path.glob(f"{_DISEASE}_select_*")) == []


@pytest.mark.parametrize("missing_digest", [None, ""])
def test_select_rechaza_benchmark_sin_policy_digest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing_digest: str | None
) -> None:
    _install_hermetic_stubs(tmp_path, monkeypatch)
    expected_policy = load_policy("rolling_cv_v1")

    _write_synthetic_benchmark(tmp_path, policy_digest_value=missing_digest)
    calls = _spy_downstream_calls(monkeypatch)

    with pytest.raises(orchestrator.RunnerError) as exc_info:
        orchestrator.run_selection(_DISEASE, _BENCH_RUN, runs_root=tmp_path)

    msg = str(exc_info.value)
    assert expected_policy.digest in msg
    assert "<ausente>" in msg
    assert calls == {"read_csv": 0, "build_selection": 0}
    assert list(tmp_path.glob(f"{_DISEASE}_select_*")) == []


def test_select_misma_politica_sigue_camino_original(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install_hermetic_stubs(tmp_path, monkeypatch)
    expected_policy = load_policy("rolling_cv_v1")

    _write_synthetic_benchmark(tmp_path, policy_digest_value=expected_policy.digest)
    man = orchestrator.run_selection(_DISEASE, _BENCH_RUN, runs_root=tmp_path)

    assert man.status == STATUS_SUCCEEDED
    assert man.command == "select"
    assert man.policy_digest == expected_policy.digest
    sel_dir = tmp_path / man.run_id
    sel_df, sel_manifest = selection.load_frozen_selection(sel_dir)
    assert len(sel_df) == 64
    assert sel_manifest["provenance"]["policy_name"] == "rolling_cv_v1"
    assert sel_manifest["provenance"]["policy_digest"] == expected_policy.digest
    assert sel_manifest["provenance"]["benchmark_run_id"] == _BENCH_RUN


def test_select_preserva_guardas_previas(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_hermetic_stubs(tmp_path, monkeypatch)
    expected_policy = load_policy("rolling_cv_v1")

    monkeypatch.setattr(orchestrator, "_tracked_dirty", lambda: ["src/epiforecast/x.py"])
    with pytest.raises(orchestrator.RunnerError, match="selección oficial rechazada"):
        orchestrator.run_selection(_DISEASE, _BENCH_RUN, runs_root=tmp_path, require_clean=True)
    monkeypatch.setattr(orchestrator, "_tracked_dirty", lambda: [])

    with pytest.raises(orchestrator.RunnerError, match="no existe el benchmark"):
        orchestrator.run_selection(_DISEASE, "inexistente", runs_root=tmp_path)

    _write_synthetic_benchmark(
        tmp_path,
        policy_digest_value=expected_policy.digest,
        status=STATUS_FAILED,
        run_id="bench_failed",
    )
    with pytest.raises(orchestrator.RunnerError, match="no es un benchmark exitoso"):
        orchestrator.run_selection(_DISEASE, "bench_failed", runs_root=tmp_path)

    _write_synthetic_benchmark(
        tmp_path,
        policy_digest_value=expected_policy.digest,
        stage="smoke",
        run_id="bench_smoke",
    )
    with pytest.raises(orchestrator.RunnerError, match="exige un benchmark 'full'"):
        orchestrator.run_selection(_DISEASE, "bench_smoke", runs_root=tmp_path)

    _write_synthetic_benchmark(
        tmp_path,
        policy_digest_value=expected_policy.digest,
        dataset_id="otro_dataset",
        run_id="bench_other_ds",
    )
    with pytest.raises(orchestrator.RunnerError, match="dataset otro_dataset != actual"):
        orchestrator.run_selection(_DISEASE, "bench_other_ds", runs_root=tmp_path)

    bench_corrupt = _write_synthetic_benchmark(
        tmp_path,
        policy_digest_value=expected_policy.digest,
        run_id="bench_corrupt",
    )
    (bench_corrupt / "artifacts" / "seasonal_naive_lag52" / "metrics.csv").write_text(
        "corrupto\n", encoding="utf-8"
    )
    with pytest.raises(orchestrator.RunnerError, match="digest no coincide"):
        orchestrator.run_selection(_DISEASE, "bench_corrupt", runs_root=tmp_path)


def test_c5_opus_falso_rolling_cv_v1_con_5_estacionales_ya_rechaza_incumbents_faltantes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Constancia ejecutable C5=FALSE: ``select_for_series`` ya exige TODOS los incumbents."""
    _install_hermetic_stubs(tmp_path, monkeypatch)
    rolling_v1 = load_policy("rolling_cv_v1")
    cinco_estacionales = load_policy("rolling_cv_baja_incidencia_v1").candidate_engines
    assert len(cinco_estacionales) == 5

    _write_synthetic_benchmark(
        tmp_path,
        policy_digest_value=rolling_v1.digest,
        engines=cinco_estacionales,
        run_id="bench_subset_5",
    )
    with pytest.raises(
        selection.SelectionError,
        match=r"faltan incumbents en el benchmark: \['ets_add_damped_log1p', 'ridge_harmonic_log1p'\]",
    ):
        orchestrator.run_selection(_DISEASE, "bench_subset_5", runs_root=tmp_path)

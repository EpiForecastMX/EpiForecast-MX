"""Caída al control tras un rechazo: sólo autorizada, sólo limpia y sin depender de runs locales."""

from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from epiforecast import registry
from epiforecast.runner import acceptance, orchestrator
from epiforecast.runner.artifact_acceptance import validate_acceptance
from epiforecast.runner.artifact_identity import ArtifactValidationError
from epiforecast.runner.manifest import STATUS_SUCCEEDED, ArtifactRecord, JobRecord, RunManifest

_RUN = "x_benchmark_test_abc_def"
_CONTROL = "seasonal_naive_lag52"
_RULE = {
    "control_engine": _CONTROL,
    "fallback_engine": _CONTROL,
    "max_worse_pct": {"smape_all": 5.0, "smape_bases": 5.0, "smape_nacional_general": 10.0},
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _final(engine: str = _CONTROL) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "geography_id": f"{i:02d}",
                "sex": sexo,
                "selected_engine": engine,
                "source": acceptance.SOURCE_FALLBACK,
            }
            for i in range(1, 33)
            for sexo in ("hombres", "mujeres")
        ]
    )


def _run_rechazado(root: Path, final: pd.DataFrame) -> Path:
    """Run de test completo y coherente, con el veredicto de un rechazo real."""
    run_dir = root / _RUN
    metricas = run_dir / "artifacts" / _CONTROL / "metrics.csv"
    metricas.parent.mkdir(parents=True)
    metricas.write_text("x\n1\n", encoding="utf-8")
    arts = acceptance.write_acceptance(
        run_dir,
        pd.DataFrame({"x": [1]}),
        final,
        "reporte\n",
        {
            "accepted": False,
            "checks": [{"scope": "smape_nacional_general", "passed": False}],
            "rule": _RULE,
            "provenance": {
                "run_id": _RUN,
                "selection_digest": "sel",
                "selection_run_id": "seleccion",
            },
        },
    )
    job = JobRecord(
        engine=_CONTROL,
        status=STATUS_SUCCEEDED,
        exit_code=0,
        artifacts=[
            ArtifactRecord(
                str(metricas.relative_to(run_dir)), _sha(metricas), "metrics.v1", validated=True
            )
        ],
    )
    RunManifest(
        run_id=_RUN,
        disease_id="x",
        command="benchmark",
        dataset_id="d",
        stage="test",
        status=STATUS_SUCCEEDED,
        policy_digest="p",
        engines=[_CONTROL],
        jobs={_CONTROL: job},
        artifacts=arts,
    ).write(run_dir)
    return run_dir


def _valida(run_dir: Path, autorizado: str | None):
    return validate_acceptance(
        run_dir,
        run_id=_RUN,
        disease_id="x",
        dataset_id="d",
        policy_digest="p",
        acceptance_digest=_sha(run_dir / "acceptance.json"),
        selection_digest="sel",
        selection_run_id="seleccion",
        final_selection_digest=_sha(run_dir / "final_selection.csv"),
        authorized_fallback_run=autorizado,
    )


def test_un_rechazo_autorizado_valida_y_declara_el_control(tmp_path):
    resultado = _valida(_run_rechazado(tmp_path, _final()), _RUN)
    assert resultado.outcome == acceptance.OUTCOME_FALLBACK


@pytest.mark.parametrize("autorizado", [None, "otro_run"])
def test_un_rechazo_sin_autorizar_este_run_no_valida(tmp_path, autorizado):
    run_dir = _run_rechazado(tmp_path, _final())
    with pytest.raises(ArtifactValidationError, match="accepted=true"):
        _valida(run_dir, autorizado)


def test_autorizar_no_rescata_un_portafolio_mixto(tmp_path):
    final = _final()
    final.loc[0, "selected_engine"] = "seasonal_mean_5y"
    with pytest.raises(ArtifactValidationError, match="entera"):
        _valida(_run_rechazado(tmp_path, final), _RUN)


def _refit(root: Path, autorizado: str | None, monkeypatch):
    disease = SimpleNamespace(acceptance_fallback_run=autorizado)
    monkeypatch.setattr(registry, "require", lambda _: disease)
    dm = SimpleNamespace(dataset_id="d", disease_id="x")
    return orchestrator._refit_context(root, _RUN, dm, SimpleNamespace(digest="p"))


def test_refit_sin_autorizacion_se_niega(tmp_path, monkeypatch):
    _run_rechazado(tmp_path, _final())
    with pytest.raises(orchestrator.RunnerError, match="NEGATIVA.*sin autorización"):
        _refit(tmp_path, None, monkeypatch)


def test_refit_autorizado_usa_el_control(tmp_path, monkeypatch):
    _run_rechazado(tmp_path, _final())
    final, _, procedencia = _refit(tmp_path, _RUN, monkeypatch)
    assert set(final["selected_engine"]) == {_CONTROL}
    assert procedencia["acceptance_run_id"] == _RUN


def test_refit_autorizado_no_acepta_una_seleccion_mixta(tmp_path, monkeypatch):
    final = _final()
    final.loc[0, "selected_engine"] = "seasonal_mean_5y"
    _run_rechazado(tmp_path, final)
    with pytest.raises(orchestrator.RunnerError, match="NEGATIVA.*entera"):
        _refit(tmp_path, _RUN, monkeypatch)

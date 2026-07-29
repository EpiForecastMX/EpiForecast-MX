"""Carril semanal aislado: PDF explícito → raw temporal → dataset observado → gate, sin publicar."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from scripts import prospective_week as pw

from epiforecast.data.epi_geo_exposure import load_geo_catalog


def _rows(year: int, week: int, disease: str = "Obesidad") -> pd.DataFrame:
    catalog = load_geo_catalog()
    return pd.DataFrame(
        [
            {
                "Anio": year,
                "Semana": week,
                "Entidad": entity.nombre_canonico,
                "Padecimiento": disease,
                "Casos_semana": i,
                "Acumulado_hombres": i + 10,
                "Acumulado_mujeres": i + 20,
                "Acumulado_anio_anterior": i + 5,
            }
            for i, entity in enumerate(catalog.entities, start=1)
        ],
        columns=pw.RAW_COLUMNS,
    )


def _extract_result(frame: pd.DataFrame, year: int = 2026, week: int = 28) -> dict[str, object]:
    return {
        "valid": True,
        "df": frame,
        "year": year,
        "week": week,
        "n_states": len(frame),
        "reason": "ok",
    }


def test_extract_new_rows_valida_periodo_y_cobertura(monkeypatch, tmp_path):
    pdf = tmp_path / "2026_sem28.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(pw, "extract_cuadro_from_pdf", lambda *_: _extract_result(_rows(2026, 28)))

    result = pw.extract_new_rows("obesidad", [pdf])
    assert len(result) == 32
    assert result[["Anio", "Semana"]].drop_duplicates().values.tolist() == [[2026, 28]]
    assert result["Padecimiento"].unique().tolist() == ["Obesidad"]


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda frame: frame.iloc[:-1], "cobertura geográfica"),
        (
            lambda frame: frame.assign(Semana=[29, *([28] * 31)]),
            "periodo del filename",
        ),
        (lambda frame: frame.assign(Padecimiento="Otro"), "Padecimiento"),
        (
            lambda frame: pd.concat([frame.iloc[:-1], frame.iloc[[0]]], ignore_index=True),
            "duplicadas",
        ),
    ],
)
def test_extract_new_rows_falla_cerrado(monkeypatch, tmp_path, mutate, match):
    pdf = tmp_path / "2026_sem28.pdf"
    pdf.write_bytes(b"%PDF")
    frame = mutate(_rows(2026, 28))
    monkeypatch.setattr(pw, "extract_cuadro_from_pdf", lambda *_: _extract_result(frame))
    with pytest.raises(pw.ProspectiveWeekError, match=match):
        pw.extract_new_rows("obesidad", [pdf])


def test_merge_preserva_prefijo_y_acepta_periodo_posterior():
    baseline = _rows(2026, 27)
    new = _rows(2026, 28)
    merged = pw.merge_observation_raw(
        baseline, new, disease_name="Obesidad", catalog=load_geo_catalog()
    )
    assert len(merged) == 64
    prefix = merged[merged["Semana"] == 27].reset_index(drop=True)
    expected = baseline.sort_values(["Anio", "Semana", "Entidad"]).reset_index(drop=True)
    pd.testing.assert_frame_equal(prefix, expected)


@pytest.mark.parametrize("period", [(2026, 27), (2026, 26)])
def test_merge_rechaza_reemplazo_o_periodo_viejo(period):
    with pytest.raises(pw.ProspectiveWeekError, match="posteriores"):
        pw.merge_observation_raw(
            _rows(2026, 27),
            _rows(*period),
            disease_name="Obesidad",
            catalog=load_geo_catalog(),
        )


def test_run_week_es_determinista_y_pasa_raw_explicito(monkeypatch, tmp_path):
    baseline = tmp_path / "data_raw_Obesidad.csv"
    _rows(2026, 27).to_csv(baseline, index=False)
    pdf = tmp_path / "2026_sem28.pdf"
    pdf.write_bytes(b"%PDF")
    monkeypatch.setattr(pw, "extract_new_rows", lambda *_args, **_kwargs: _rows(2026, 28))

    captured: list[bytes] = []

    def fake_validate(disease, runs_root=None, *, raw_path=None):
        assert disease == "obesidad"
        assert runs_root == (tmp_path / "runs").resolve()
        assert isinstance(raw_path, Path)
        captured.append(raw_path.read_bytes())
        return SimpleNamespace(
            dataset_id="obesidad_observacion",
            digests={"dataset": "1" * 64},
        )

    evaluation = SimpleNamespace(
        observation_cutoff=(2026, 27),
        release_id="obesidad_release_x",
        gate_digest="2" * 64,
        candidate_digest="3" * 64,
        control_digest="4" * 64,
        skipped_weeks=(),
    )
    status = SimpleNamespace(
        weeks_required=4,
        weeks_available=1,
        completed_weeks=((2026, 27),),
        verdict="INCOMPLETE",
    )
    monkeypatch.setattr(pw.orchestrator, "validate_data", fake_validate)
    monkeypatch.setattr(pw, "derive_evaluation", lambda *_args, **_kwargs: (evaluation, status))

    first = pw.run_week("obesidad", [pdf], baseline_raw=baseline, runs_root=tmp_path / "runs")
    second = pw.run_week("obesidad", [pdf], baseline_raw=baseline, runs_root=tmp_path / "runs")
    assert first == second
    assert captured[0] == captured[1]
    assert first["source_periods"] == [[2026, 28]]
    assert first["observation_cutoff"] == [2026, 27]
    assert first["completed_weeks"] == [[2026, 27]]
    assert first["weeks_available"] == 1
    assert first["verdict"] == "INCOMPLETE"
    assert len(first["report_digest"]) == 64
    assert str(tmp_path) not in str(first)


def test_cli_dry_run_es_obligatorio():
    with pytest.raises(SystemExit):
        pw._parser().parse_args(["--disease", "obesidad", "--pdf", "x.pdf"])

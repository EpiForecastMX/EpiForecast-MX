"""Carril semanal aislado: PDF explícito → raw temporal → dataset observado → gate, sin publicar."""

from __future__ import annotations

import hashlib
import json
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


def test_merge_repetido_identico_es_idempotente():
    baseline = _rows(2026, 27)
    repeated = _rows(2026, 27)
    repeated["Semana"] = repeated["Semana"].astype(str)  # extractor entrega la semana como texto
    merged = pw.merge_observation_raw(
        baseline,
        repeated,
        disease_name="Obesidad",
        catalog=load_geo_catalog(),
    )
    pd.testing.assert_frame_equal(
        merged,
        baseline.sort_values(["Anio", "Semana", "Entidad"]).reset_index(drop=True),
    )


def test_merge_rechaza_periodo_viejo():
    with pytest.raises(pw.ProspectiveWeekError, match="posteriores"):
        pw.merge_observation_raw(
            _rows(2026, 27),
            _rows(2026, 26),
            disease_name="Obesidad",
            catalog=load_geo_catalog(),
        )


def test_merge_rechaza_revision_del_ultimo_periodo():
    revised = _rows(2026, 27)
    revised.loc[0, "Casos_semana"] += 1
    with pytest.raises(pw.ProspectiveWeekError, match="revisión rechazada"):
        pw.merge_observation_raw(
            _rows(2026, 27),
            revised,
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
        training_dataset_id="obesidad_entrenamiento",
        training_dataset_digest="0" * 64,
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
    assert first["source_pdfs"] == [
        {"name": pdf.name, "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest()}
    ]
    assert first["observation_cutoff"] == [2026, 27]
    assert first["training_dataset_id"] == "obesidad_entrenamiento"
    assert first["completed_weeks"] == [[2026, 27]]
    assert first["weeks_available"] == 1
    assert first["verdict"] == "INCOMPLETE"
    assert len(first["report_digest"]) == 64
    assert str(tmp_path) not in str(first)


def test_cli_dry_run_es_obligatorio():
    with pytest.raises(SystemExit):
        pw._parser().parse_args(["--disease", "obesidad", "--pdf", "x.pdf"])


def test_cli_write_rechaza_un_baseline_manual_antes_de_leerlo(tmp_path, capsys):
    """Un baseline arbitrario puede retroceder el estado; sólo se admite para inspección."""
    rc = pw.main(
        [
            "--disease",
            "obesidad",
            "--pdf",
            str(tmp_path / "no_se_debe_leer.pdf"),
            "--baseline-raw",
            str(tmp_path / "historia_vieja.csv"),
            "--write",
        ]
    )
    assert rc == 2
    assert "--baseline-raw es sólo para dry-run" in capsys.readouterr().err


def test_siguiente_semana_parte_del_ultimo_raw_declarado(monkeypatch, tmp_path):
    canonical = tmp_path / "canonical.csv"
    canonical.write_bytes(b"viejo")
    store_root = tmp_path / "store"
    dataset_id = "obesidad_observada"
    dataset = store_root / "obesidad" / dataset_id
    inputs = dataset / "inputs"
    inputs.mkdir(parents=True)
    observed = inputs / "raw.csv"
    observed.write_bytes(b"nuevo")
    raw_digest = hashlib.sha256(observed.read_bytes()).hexdigest()

    config = tmp_path / "publication"
    config.mkdir()
    status = config / "status.json"
    evaluation = config / "evaluation.json"
    status.write_text(json.dumps({"observation_dataset_id": dataset_id}), encoding="utf-8")
    evaluation.write_text(
        json.dumps({"observation_source_digests": {"raw": raw_digest}}), encoding="utf-8"
    )
    monkeypatch.setattr(
        pw,
        "declared_paths",
        lambda *_args, **_kwargs: {"status": status, "evaluation": evaluation},
    )

    result = pw._baseline_from_declared_state(
        "obesidad",
        canonical,
        runs_root=tmp_path / "runs",
        observation_store_root=store_root,
    )
    assert result == observed

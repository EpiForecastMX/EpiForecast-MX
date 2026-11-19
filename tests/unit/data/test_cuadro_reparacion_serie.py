"""Reparaciones declaradas de la serie (``sem_desde_delta_acumulado``) e ``inicio_serie``.

Herméticas: series sintéticas en memoria y un CLI con el extractor sustituido; sin PDFs.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
import scripts.extrae_cuadro as cli

from epiforecast.data.extraction import cuadro_extractor
from epiforecast.data.extraction.cuadro_reparacion_serie import (
    ReparacionError,
    aplica_reparaciones,
    exclusion_por_inicio,
)

pytestmark = pytest.mark.unit

_REGLA = {
    "tipo": "sem_desde_delta_acumulado",
    "diseases": ["x_t00"],
    "desde": "2024_sem02",
    "hasta": "2024_sem04",
    "motivo": "Sem. impreso con el acumulado H+M",
}


def _serie(acum: dict[tuple[int, int], tuple[int, int]], sem: int = 999) -> pd.DataFrame:
    """Dos entidades; ``acum[(año, semana)] = (H de A, H de B)`` con M = 1 en cada una."""
    filas = []
    for (anio, semana), (ha, hb) in sorted(acum.items()):
        for entidad, h in (("A", ha), ("B", hb)):
            filas.append(
                {
                    "Anio": anio,
                    "Semana": f"{semana:02d}",
                    "Entidad": entidad,
                    "Padecimiento": "X",
                    "Casos_semana": sem,
                    "Acumulado_hombres": h,
                    "Acumulado_mujeres": 1,
                    "Acumulado_anio_anterior": 0,
                }
            )
    return pd.DataFrame(filas)


def _spec(**extra: Any) -> dict[str, Any]:
    return {"observation_lag_weeks": 1, "reparaciones": [dict(_REGLA, **extra)]}


_ACUM = {(2024, 1): (50, 60), (2024, 2): (3, 4), (2024, 3): (5, 9), (2024, 4): (5, 12)}


def test_delta_del_acumulado_y_reinicio_anual() -> None:
    serie, registro, motivos = aplica_reparaciones(_serie(_ACUM), _spec(), "x_t00")
    sem = serie.set_index(["Anio", "Semana", "Entidad"])["Casos_semana"]
    # 2024_sem01 (fuera de rango) queda impreso; 2024_sem02 observa 2024-W01: reinicio, A(b).
    assert sem[(2024, "01", "A")] == 999
    assert sem[(2024, "02", "A")] == 4 and sem[(2024, "02", "B")] == 5
    assert sem[(2024, "03", "A")] == 2 and sem[(2024, "03", "B")] == 5
    assert sem[(2024, "04", "A")] == 0 and sem[(2024, "04", "B")] == 3
    assert len(registro) == 6
    assert set(registro["Regla"]) == {"reinicio_anual", "delta_acumulado"}
    assert (registro["Casos_semana_impreso"] == 999).all()
    assert motivos["2024_sem02.pdf"].endswith("(reinicio anual, Sem. = acumulado)")
    assert "respecto de 2024_sem03" in motivos["2024_sem04.pdf"]
    assert "2024_sem01.pdf" not in motivos


def test_sin_reinicio_usa_el_boletin_previo_fuera_del_rango() -> None:
    serie, _, _ = aplica_reparaciones(_serie(_ACUM), _spec(desde="2024_sem03"), "x_t00")
    sem = serie.set_index(["Anio", "Semana", "Entidad"])["Casos_semana"]
    assert sem[(2024, "02", "A")] == 999  # fuera del rango
    assert sem[(2024, "03", "A")] == 2


def test_falla_si_el_acumulado_baja() -> None:
    acum = {**_ACUM, (2024, 4): (4, 12)}
    with pytest.raises(ReparacionError, match=r"2024_sem04 A: el acumulado baja \(6 -> 5\)"):
        aplica_reparaciones(_serie(acum), _spec(), "x_t00")


def test_falla_si_falta_el_boletin_previo() -> None:
    acum = {k: v for k, v in _ACUM.items() if k != (2024, 2)}
    with pytest.raises(ReparacionError, match="2024_sem02: boletín del rango sin datos"):
        aplica_reparaciones(_serie(acum), _spec(), "x_t00")
    with pytest.raises(ReparacionError, match="falta el boletín previo 2024_sem02"):
        aplica_reparaciones(_serie(acum), _spec(desde="2024_sem03"), "x_t00")


def test_falla_si_falta_un_acumulado() -> None:
    serie = _serie(_ACUM)
    serie.loc[(serie["Semana"] == "03") & (serie["Entidad"] == "B"), "Acumulado_mujeres"] = None
    with pytest.raises(ReparacionError, match="2024_sem03 B: acumulado ausente"):
        aplica_reparaciones(serie, _spec(), "x_t00")


def test_sin_sexo_usa_el_acumulado_total() -> None:
    serie = _serie(_ACUM)
    serie["Acumulado_total"] = serie.pop("Acumulado_hombres") + serie.pop("Acumulado_mujeres")
    reparada, _, _ = aplica_reparaciones(serie, _spec(), "x_t00")
    sem = reparada.set_index(["Anio", "Semana", "Entidad"])["Casos_semana"]
    assert sem[(2024, "03", "B")] == 5


def test_opt_in_otro_padecimiento_y_grupo_sin_reparaciones_quedan_intactos() -> None:
    serie = _serie(_ACUM)
    for spec, disease in ((_spec(), "otro_t99"), ({"observation_lag_weeks": 1}, "x_t00")):
        mismo, registro, motivos = aplica_reparaciones(serie, spec, disease)
        assert mismo is serie and registro.empty and motivos == {}


@pytest.mark.parametrize(
    ("cambio", "mensaje"),
    [
        ({"tipo": "inventada"}, "tipo de reparación desconocido"),
        ({"motivo": " "}, "reparación sin motivo"),
        ({"desde": "2024_sem05"}, "rango de reparación vacío"),
        ({"hasta": "2024-04"}, "reparaciones.hasta inválido"),
    ],
)
def test_configuracion_invalida_falla(cambio: dict[str, str], mensaje: str) -> None:
    with pytest.raises(ReparacionError, match=mensaje):
        aplica_reparaciones(_serie(_ACUM), _spec(**cambio), "x_t00")


_INICIO = {"inicio_serie": [{"diseases": ["x_t00"], "desde": "2016_sem02", "motivo": "m"}]}


def test_inicio_serie_excluye_lo_anterior_sin_periodo_vacio() -> None:
    exc = exclusion_por_inicio(_INICIO, "2016_sem01.pdf", "x_t00")
    assert exc is not None and exc["keep_period"] is False
    assert exc["reason"] == "anterior al inicio declarado de la serie (2016_sem02): m"
    assert exclusion_por_inicio(_INICIO, "2016_sem02.pdf", "x_t00") is None
    assert exclusion_por_inicio(_INICIO, "2014_sem05.pdf", "otro_t99") is None
    with pytest.raises(ReparacionError, match="inicio_serie sin motivo"):
        exclusion_por_inicio(
            {"inicio_serie": [{"diseases": ["x_t00"], "desde": "2016_sem02"}]},
            "2015_sem01.pdf",
            "x_t00",
        )


def test_source_exclusion_del_extractor_aplica_inicio_serie() -> None:
    spec = dict(
        _INICIO,
        source_exclusions=[
            {
                "file": "2016_sem20.pdf",
                "diseases": ["x_t00"],
                "reason": "errata",
                "keep_period": True,
            }
        ],
    )
    assert cuadro_extractor.source_exclusion(spec, "2016_sem20.pdf", "x_t00")["reason"] == "errata"
    inicio = cuadro_extractor.source_exclusion(spec, "2015_sem30.pdf", "x_t00")
    assert inicio is not None and inicio["reason"].startswith("anterior al inicio declarado")
    assert cuadro_extractor.source_exclusion(spec, "2017_sem01.pdf", "x_t00") is None


def _cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, acum: dict[Any, Any]) -> int:
    """Corre el CLI sobre boletines sintéticos (sin PDFs) desde ``tmp_path``."""
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    resultados = []
    for (anio, semana), _ in sorted(acum.items()):
        (pdf_dir / f"{anio}_sem{semana:02d}.pdf").write_bytes(b"")
        df = _serie({(anio, semana): acum[(anio, semana)]})
        resultados.append(
            {
                "df": df,
                "year": anio,
                "week": semana,
                "page": 1,
                "layout": "4col_prev",
                "n_states": 2,
                "valid": True,
                "reason": "ok",
            }
        )
    d = SimpleNamespace(
        id="x_t00", data_name="X", slug="x_t00", extraction_group="g", sex_breakdown=True
    )
    monkeypatch.setattr(cli.registry, "require", lambda _: d)
    monkeypatch.setattr(cli, "_results", lambda tasks, jobs: iter(resultados))
    monkeypatch.setattr(cli, "load_group", lambda _: _spec())
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["extrae_cuadro", "--disease", "x", "--pdf-dir", str(pdf_dir)])
    return cli.main()


def test_cli_registra_la_reparacion_en_manifiesto_y_registro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    assert _cli(monkeypatch, tmp_path, _ACUM) == 0
    interim = tmp_path / "data" / "interim"
    serie = pd.read_csv(interim / "x_t00_boletin.csv", dtype={"Semana": str})
    assert (
        serie.loc[(serie["Semana"] == "03") & (serie["Entidad"] == "B"), "Casos_semana"].item()
        == 5
    )
    manifiesto = pd.read_csv(interim / "x_t00_extraccion_manifest.csv").set_index("file")
    assert manifiesto.loc["2024_sem01.pdf", "reason"] == "ok"
    assert "reparación sem_desde_delta_acumulado" in manifiesto.loc["2024_sem03.pdf", "reason"]
    assert len(pd.read_csv(interim / "x_t00_reparaciones.csv")) == 6


def test_cli_falla_cerrado_sin_escribir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    acum = {**_ACUM, (2024, 4): (4, 12)}
    assert _cli(monkeypatch, tmp_path, acum) == 2
    assert not (tmp_path / "data" / "interim" / "x_t00_boletin.csv").exists()
    assert not (tmp_path / "data" / "interim" / "x_t00_extraccion_manifest.csv").exists()

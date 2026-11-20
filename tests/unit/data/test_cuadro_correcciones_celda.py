"""Correcciones declaradas de celdas (``correcciones_celda``) y su paso por el CLI.

Herméticas: series sintéticas en memoria y un CLI con el extractor sustituido; sin PDFs.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pandas as pd
import pytest
import scripts.extrae_cuadro as cli

from epiforecast.data.extraction.cuadro_correcciones_celda import (
    CorreccionError,
    aplica_correcciones,
    celdas_casos,
)
from epiforecast.data.extraction.cuadro_reparacion_serie import (
    ReparacionError,
    aplica_reparaciones,
)

pytestmark = pytest.mark.unit

_FIJA = {
    "archivo": "2024_sem03.pdf",
    "diseases": ["x_t00"],
    "entidad": "B",
    "columna": "Casos_semana",
    "esperado": None,
    "valor": 0,
    "motivo": "la fuente imprime «- 1»",
    "autoridad": "decisión nominal de prueba",
}
_IMPUTA = {
    "archivo": "2024_sem04.pdf",
    "diseases": ["x_t00"],
    "entidad": "A",
    "columna": "Casos_semana",
    "esperado": 999,
    "imputar": True,
    "motivo": "el acumulado impreso baja",
    "autoridad": "decisión nominal de prueba",
}
_REPARA = {
    "tipo": "sem_desde_delta_acumulado",
    "diseases": ["x_t00"],
    "desde": "2024_sem02",
    "hasta": "2024_sem04",
    "motivo": "Sem. impreso con el acumulado H+M",
}
# acum[(año, semana)] = (H de A, H de B), M = 1; A baja en 2024_sem04 (5 -> 4).
_ACUM = {(2024, 1): (50, 60), (2024, 2): (3, 4), (2024, 3): (5, 9), (2024, 4): (4, 12)}


def _serie(acum: dict[tuple[int, int], tuple[int, int]]) -> pd.DataFrame:
    filas = []
    for (anio, semana), (ha, hb) in sorted(acum.items()):
        for entidad, h in (("A", ha), ("B", hb)):
            vacia = (anio, semana, entidad) == (2024, 3, "B")  # «- 1» leído como vacío
            filas.append(
                {
                    "Anio": anio,
                    "Semana": f"{semana:02d}",
                    "Entidad": entidad,
                    "Padecimiento": "X",
                    "Casos_semana": None if vacia else 999,
                    "Acumulado_hombres": h,
                    "Acumulado_mujeres": 1,
                    "Acumulado_anio_anterior": 0,
                }
            )
    df = pd.DataFrame(filas)
    # Como el extractor: columna object con enteros y vacíos (el CSV escribe «0», no «0.0»).
    df["Casos_semana"] = pd.Series([f["Casos_semana"] for f in filas], dtype=object)
    return df


def _celda(serie: pd.DataFrame, semana: int, entidad: str) -> object:
    fila = (serie["Semana"].astype(int) == semana) & (serie["Entidad"] == entidad)
    return serie.loc[fila, "Casos_semana"].item()


def test_fija_un_valor_y_lo_registra() -> None:
    serie, registro, notas = aplica_correcciones(
        _serie(_ACUM), {"correcciones_celda": [_FIJA]}, "x_t00"
    )
    assert _celda(serie, 3, "B") == 0
    assert _celda(serie, 3, "A") == 999
    assert registro.to_dict("records")[0]["Valor_extraido"] == ""
    assert registro.to_dict("records")[0]["Valor_corregido"] == 0
    assert notas == {"2024_sem03.pdf": "corrección de celda declarada: B Casos_semana vacía -> 0"}


def test_imputar_deja_la_celda_vacia_y_la_reparacion_no_la_recalcula() -> None:
    spec = {
        "observation_lag_weeks": 1,
        "reparaciones": [_REPARA],
        "correcciones_celda": [_IMPUTA],
    }
    with pytest.raises(ReparacionError, match="el acumulado baja"):
        aplica_reparaciones(_serie(_ACUM), spec, "x_t00")
    serie, registro, _ = aplica_correcciones(_serie(_ACUM), spec, "x_t00")
    omitir = frozenset(celdas_casos(spec, "x_t00"))
    reparada, reg_rep, _ = aplica_reparaciones(serie, spec, "x_t00", omitir)
    assert pd.isna(_celda(reparada, 4, "A"))
    assert _celda(reparada, 4, "B") == 3  # 13 - 10: las demás celdas sí se reparan
    assert registro.to_dict("records")[0]["Accion"] == "imputar"
    assert len(reg_rep) == 5


def test_sin_correcciones_devuelve_la_misma_serie() -> None:
    serie = _serie(_ACUM)
    otra = dict(_FIJA, diseases=["y_t00"])
    for spec in ({}, {"correcciones_celda": [otra]}):
        salida, registro, notas = aplica_correcciones(serie, spec, "x_t00")
        assert salida is serie and registro.empty and notas == {}


@pytest.mark.parametrize(
    ("cambio", "mensaje"),
    [
        ({"entidad": "Z"}, "la celda no existe"),
        ({"archivo": "2023_sem03.pdf"}, "la celda no existe"),
        ({"esperado": 1}, "extraído None, esperado 1.0"),
    ],
)
def test_falla_cerrado_si_la_celda_no_cuadra(cambio: dict[str, Any], mensaje: str) -> None:
    with pytest.raises(CorreccionError, match=mensaje):
        aplica_correcciones(
            _serie(_ACUM), {"correcciones_celda": [dict(_FIJA, **cambio)]}, "x_t00"
        )


@pytest.mark.parametrize(
    ("cambio", "quita", "mensaje"),
    [
        ({"imputar": True}, None, "exactamente uno"),
        ({}, "valor", "exactamente uno"),
        ({"columna": "Acumulado_hombres", "imputar": True}, "valor", "sólo vale para Casos"),
        ({"valor": -1}, None, "entero no negativo"),
        ({"columna": "Otra"}, None, "columna no admitida"),
        ({"archivo": "2024_sem3.pdf"}, None, "archivo inválido"),
        ({}, "esperado", "falta «esperado»"),
        ({}, "autoridad", "falta autoridad"),
        ({}, "motivo", "falta motivo"),
    ],
)
def test_configuracion_invalida_falla(
    cambio: dict[str, Any], quita: str | None, mensaje: str
) -> None:
    regla = {k: v for k, v in dict(_FIJA, **cambio).items() if k != quita}
    with pytest.raises(CorreccionError, match=mensaje):
        aplica_correcciones(_serie(_ACUM), {"correcciones_celda": [regla]}, "x_t00")


def test_duplicada_falla() -> None:
    with pytest.raises(CorreccionError, match="duplicada"):
        aplica_correcciones(_serie(_ACUM), {"correcciones_celda": [_FIJA, _FIJA]}, "x_t00")


def _cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, spec: dict[str, Any]) -> int:
    """Corre el CLI sobre boletines sintéticos (sin PDFs) desde ``tmp_path``."""
    pdf_dir = tmp_path / "pdfs"
    pdf_dir.mkdir()
    completa = _serie(_ACUM)
    resultados = []
    for anio, semana in sorted(_ACUM):
        (pdf_dir / f"{anio}_sem{semana:02d}.pdf").write_bytes(b"")
        df = completa[completa["Semana"] == f"{semana:02d}"].reset_index(drop=True)
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
    monkeypatch.setattr(cli, "load_group", lambda _: spec)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.argv", ["extrae_cuadro", "--disease", "x", "--pdf-dir", str(pdf_dir)])
    return cli.main()


def test_cli_registra_correcciones_en_manifiesto_y_registro(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    spec = {
        "observation_lag_weeks": 1,
        "reparaciones": [_REPARA],
        "correcciones_celda": [_FIJA, _IMPUTA],
    }
    assert _cli(monkeypatch, tmp_path, spec) == 0
    interim = tmp_path / "data" / "interim"
    texto = (interim / "x_t00_boletin.csv").read_text(encoding="utf-8")
    assert "2024,04,A,X,,4,1,0" in texto  # imputada: vacía, acumulados impresos intactos
    assert "2024,03,B,X,0,9,1,0" in texto  # fijada en 0 y no recalculada por la reparación
    manifiesto = pd.read_csv(interim / "x_t00_extraccion_manifest.csv").set_index("file")
    nota = manifiesto.loc["2024_sem04.pdf", "reason"]
    assert "reparación sem_desde_delta_acumulado" in nota
    assert nota.endswith("corrección de celda declarada: A Casos_semana 999 -> imputada")
    assert len(pd.read_csv(interim / "x_t00_correcciones.csv")) == 2


def test_cli_falla_cerrado_sin_escribir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    spec = {"observation_lag_weeks": 1, "correcciones_celda": [dict(_FIJA, esperado=3)]}
    assert _cli(monkeypatch, tmp_path, spec) == 2
    assert not (tmp_path / "data" / "interim" / "x_t00_boletin.csv").exists()
    assert not (tmp_path / "data" / "interim" / "x_t00_correcciones.csv").exists()

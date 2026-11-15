"""Paso semanal mixto: un publicado con rezago 0 y otro con rezago 1 en la MISMA semana fuente N.

La paridad del consolidado es de semana FUENTE (``Anio``/``Semana`` del boletín): ambos aportan sus
32 filas de N y la paridad pasa, aunque sus semanas objetivo (corte de vista) sean N y N-1. Si uno
va una semana fuente atrás, el paso falla cerrado. Sintético y hermético: ``consolida`` corre con
la ``revisa_consolidado`` real sobre un contrato de cobertura sintético (sin registry ni ``runs/``).
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pytest
from scripts import paso_semanal as ps

from epiforecast.data import epi_dataset as ed
from epiforecast.data.epi_geo_exposure import GeoCatalog, load_geo_catalog
import epiforecast.publication.contratos_datos as cd
from tests.unit.data import rezago_sintetico as syn

pytestmark = pytest.mark.unit

_COLUMNAS = list(syn.RAW_COLUMNS)
# id → (nombre del padecimiento en el boletín, rezago impreso de su cuadro)
_PADS = {"cero_x00": ("Sintético rezago cero", 0), "uno_x01": ("Sintético rezago uno", 1)}


@pytest.fixture(scope="module")
def catalog() -> GeoCatalog:
    return load_geo_catalog()


def _contrato(catalog: GeoCatalog) -> cd.ContratoCobertura:
    return cd.ContratoCobertura(
        neuro=(),
        conteo=(),
        entidades=tuple(cd.slug(e.nombre_canonico) for e in catalog.entities),
        alias={},
        regiones=(),
        release=tuple(cd.slug(nombre) for nombre, _ in _PADS.values()),
        profundidad_minima=4,
    )


def _escribe(frame: pd.DataFrame, ruta: Path) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(ruta, index=False, columns=_COLUMNAS, quoting=csv.QUOTE_MINIMAL)


@dataclass(frozen=True)
class _Escenario:
    root: Path
    base: Path
    legacy: Path
    raws: dict[str, pd.DataFrame]


def _escenario(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    catalog: GeoCatalog,
    n: tuple[int, int],
    fin_por_id: dict[str, tuple[int, int]],
) -> _Escenario:
    """Raw de observación por id (hasta su semana fuente final) y la base con las semanas < N."""
    root = tmp_path / "be"
    raws: dict[str, pd.DataFrame] = {}
    for d, (nombre, lag) in _PADS.items():
        raw = syn.raw_boletines(syn.source_periods(fin_por_id[d], 6), lag, catalog, nombre)
        raws[d] = raw
        _escribe(
            raw, root / "artifacts" / "observations" / d / "obs1" / "inputs" / f"data_raw_{d}.csv"
        )
    previas = pd.concat(
        [r[(r["Anio"] * 100 + r["Semana"]) < n[0] * 100 + n[1]] for r in raws.values()],
        ignore_index=True,
    )
    base = tmp_path / "base.csv"
    _escribe(previas, base)
    legacy = tmp_path / "legacy.csv"
    legacy.write_text(",".join(_COLUMNAS) + "\n", encoding="utf-8")
    monkeypatch.setattr(ps, "publicados", lambda: list(_PADS))
    monkeypatch.setattr(ps, "observacion_actual", lambda d, r=None: "obs1")
    monkeypatch.setattr(
        cd.ContratoCobertura, "canonico", classmethod(lambda cls: _contrato(catalog))
    )
    return _Escenario(root, base, legacy, raws)


def _consolida(e: _Escenario, n: tuple[int, int], out: Path) -> int:
    return ps.consolida(n[1], n[0], e.base, e.legacy, e.legacy, out, e.root)


@pytest.mark.parametrize("n", [(2026, 43), (2026, 1), (2025, 53), (2021, 1)])
def test_rezago_0_y_1_con_la_misma_semana_fuente_pasan_la_paridad(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, catalog: GeoCatalog, n: tuple[int, int]
) -> None:
    e = _escenario(tmp_path, monkeypatch, catalog, n, {d: n for d in _PADS})
    out = tmp_path / "out.csv"
    assert _consolida(e, n, out) == 0
    r = cd.revisa_consolidado(out, _contrato(catalog), _contrato(catalog).padecimientos)
    assert r.pasa, r.problemas
    # Corte del consolidado = semana FUENTE común para los dos.
    assert set(r.cifras["cortes"].values()) == {n}
    consolidado = pd.read_csv(out)
    for nombre, _ in _PADS.values():
        filas = consolidado[consolidado["Padecimiento"] == nombre]
        assert len(filas[(filas["Anio"] == n[0]) & (filas["Semana"] == n[1])]) == 32
    # Corte de vista (semana OBJETIVO) propio de cada id: N con rezago 0, N-1 con rezago 1.
    raws = e.raws
    cortes_objetivo = {}
    for d, (_, lag) in _PADS.items():
        prep = ed.build_prep(raws[d], catalog, lag)
        ultimo = prep.loc[prep["period_start"].idxmax()]
        cortes_objetivo[d] = (int(ultimo["epi_year"]), int(ultimo["epi_week"]))
    anterior = {
        (2026, 43): (2026, 42),
        (2026, 1): (2025, 53),
        (2025, 53): (2025, 52),
        (2021, 1): (2020, 53),
    }[n]
    assert cortes_objetivo == {"cero_x00": n, "uno_x01": anterior}


@pytest.mark.parametrize("atrasado", sorted(_PADS))
@pytest.mark.parametrize(("n", "previa"), [((2026, 43), (2026, 42)), ((2026, 1), (2025, 53))])
def test_un_publicado_una_semana_fuente_atras_falla(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    catalog: GeoCatalog,
    atrasado: str,
    n: tuple[int, int],
    previa: tuple[int, int],
) -> None:
    fines = {d: (previa if d == atrasado else n) for d in _PADS}
    e = _escenario(tmp_path, monkeypatch, catalog, n, fines)
    out = tmp_path / "out.csv"
    # El paso no puede consolidar N si un publicado no trae sus 32 filas de N.
    assert _consolida(e, n, out) == 2
    assert f"{atrasado}: 0 filas en {n[0]}-W{n[1]} (se esperan 32)" in capsys.readouterr().err
    assert not out.exists()
    # Y la paridad, sobre un consolidado que ya trae a uno atrasado, falla por corte dispar.
    raws = e.raws
    dispar = tmp_path / "dispar.csv"
    _escribe(pd.concat(list(raws.values()), ignore_index=True), dispar)
    r = cd.revisa_consolidado(dispar, _contrato(catalog), _contrato(catalog).padecimientos)
    assert not r.pasa
    assert any("corte dispar" in p for p in r.problemas)

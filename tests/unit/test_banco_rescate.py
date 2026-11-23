"""Rescate de controles: naive coherente, compuerta completa y motor fijo de la sombra v4."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from epiforecast.banco import coherente, rescate
from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner import sombra_v2 as sv

pytestmark = pytest.mark.unit
_ROOT = Path(__file__).resolve().parents[2]
CAT = load_geo_catalog()


def _historia(anios: int = 6, series: int = 64) -> tuple[np.ndarray, list[tuple[int, int]]]:
    periodos = [(a, w) for a in range(2018, 2018 + anios) for w in range(1, 53)]
    sem = np.array([w for _, w in periodos])
    rng = np.random.default_rng(1)
    medias = np.linspace(0.05, 30, series)[:, None] * (1 + 0.5 * np.sin(2 * np.pi * sem / 52))
    return rng.poisson(medias).astype(float), periodos


def test_redondeo_controlado_conserva_el_total_redondeado() -> None:
    pred = np.array([[0.4, 1.6, 0.0], [0.4, 0.2, 2.5], [0.3, 0.2, 0.0]])
    r = coherente.redondeo_controlado(pred)
    assert np.array_equal(r, np.round(r))
    assert list(r.sum(axis=0)) == [1.0, 2.0, 2.0]
    assert list(r[:, 0]) == [1.0, 0.0, 0.0]  # empate de residuos: gana la primera serie
    assert list(r[:, 2]) == [0.0, 2.0, 0.0]  # 2.5 redondea al par


def test_escala_semanal_conserva_los_ceros_y_acota() -> None:
    bases = np.array([[0.0, 2.0], [4.0, 0.0]])
    out = coherente.escala_semanal(bases, np.array([8.0, 100.0]))
    assert out[0, 0] == 0.0 and out[1, 1] == 0.0
    assert out[1, 0] == 8.0  # factor 2, en el límite
    assert out[0, 1] == 4.0  # factor 50 acotado a 2


def test_pronostico_coherente_suma_al_total_y_hereda_ceros() -> None:
    y, periodos = _historia()
    train, hold = periodos[:-52], periodos[-52:]
    pred, control = coherente.pronostico(y[:, :-52], train, hold, {}, "f4", True)
    assert pred.shape == control.shape == (64, 52)
    assert (pred[control == 0] == 0).all()
    assert np.array_equal(pred, np.round(pred)) and (pred >= 0).all()


def test_formas_comparten_nivel() -> None:
    m = {
        k: np.arange(1.0, 53.0) * (i + 1) for i, k in enumerate(["naive", "nxp", "ets", "media3"])
    }
    total = coherente.nacional("f4", m, nivel=520.0)
    assert total.sum() == pytest.approx(520.0)


def test_matriz_s_111_y_37_productos() -> None:
    claves = [(f"{i:02d}", s) for i in range(1, 33) for s in ("hombres", "mujeres")]
    s, nb = rescate.matriz_s(claves, CAT)
    assert (nb, s.shape) == (64, (111, 64))
    assert s[-1].sum() == 64 and s[64].sum() == 2
    s, nb = rescate.matriz_s([(f"{i:02d}", "general") for i in range(1, 33)], CAT)
    assert (nb, s.shape) == (32, (37, 32))


def test_compuerta_aplica_los_tres_limites() -> None:
    lim = {f"lim_{k}": v for k, v in zip(rescate.AMBITOS, (10.0, 5.0, 5.0), strict=True)}
    base = {"disease_id": "d", "anio": 2024} | lim
    df = pd.DataFrame(
        [
            base
            | {
                "motor": "control",
                "smape_nacional_general": 20.0,
                "smape_bases": 50.0,
                "smape_all": 40.0,
            },
            base
            | {
                "motor": "a",
                "smape_nacional_general": 18.0,
                "smape_bases": 52.0,
                "smape_all": 41.0,
            },
            base
            | {
                "motor": "b",
                "smape_nacional_general": 18.0,
                "smape_bases": 53.0,
                "smape_all": 41.0,
            },
        ]
    )
    g = rescate.compuerta(df).set_index("motor")
    assert g.loc["a", "positivo"] and not g.loc["b", "pasa"]
    cero = df.assign(smape_bases=0.0)  # control y variante en 0: el runner reprueba (inf)
    assert not rescate.compuerta(cero)["pasa"].any()


def test_motor_fijo_ignora_la_seleccion() -> None:
    reglas = sv.cargar_reglas(_ROOT / "config" / "sombra" / "sombra_v4.yaml")
    assert reglas.fijo == "naive_coherente_f4"
    met = pd.DataFrame(
        [
            {"engine": e, "fold": f, "smape_nacional_general": s, "smape_bases": 50.0}
            for e, s in (("naive_lag52", 10.0), ("naive_coherente_f4", 30.0))
            for f in "abcd"
        ]
    )
    assert sv.seleccionar(met, reglas)["engine"] == "naive_coherente_f4"
    sin = dataclasses.replace(reglas, fijo="")
    assert sv.seleccionar(met, sin)["engine"] == "naive_lag52"

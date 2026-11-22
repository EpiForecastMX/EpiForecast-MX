"""Banco ampliado: motores, LightGBM sin fuga, pliegues sólo de desarrollo y métricas."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from epiforecast.banco import flujo, global_ml, motores, reporte
from epiforecast.data.epi_calendar import weeks_in_year

pytestmark = pytest.mark.unit
CFG = flujo.cargar_config()
P = CFG["parametros"]


def _periodos(desde: int, hasta: int) -> list[tuple[int, int]]:
    return [(y, w) for y in range(desde, hasta + 1) for w in range(1, weeks_in_year(y) + 1)]


def _serie(periodos: list[tuple[int, int]], nivel: float = 10.0) -> np.ndarray:
    return np.array([nivel + 5 * np.sin(2 * np.pi * w / 52) for _, w in periodos])


def test_config_todos_los_motores_implementados() -> None:
    assert CFG["control"] in CFG["motores"]
    assert len(CFG["motores"]) == 30


@pytest.mark.parametrize("motor", [m for m in flujo.LOCALES if m != "prophet_log1p"])
def test_motores_locales_dan_pronostico_finito(motor: str) -> None:
    per = _periodos(2016, 2022)
    train, hold = per[:-52], per[-52:]
    y = _serie(train)
    v = flujo.LOCALES[motor](y, train, hold, P)
    assert v.shape == (52,) and np.isfinite(v).all()


def test_naive_repite_el_anio_previo() -> None:
    per = _periodos(2021, 2023)
    train, hold = per[:-52], per[-52:]
    y = np.arange(len(train), dtype=float)
    assert np.array_equal(motores.naive_lag52(y, train, hold, P), y[-52:])


def test_intermitentes_en_ceros_dan_cero() -> None:
    per = _periodos(2021, 2023)
    y = np.zeros(len(per) - 52)
    for m in (motores.croston_sba, motores.tsb, motores.poisson_fourier):
        assert (m(y, per[:-52], per[-52:], P) == 0).all()


def test_factor_de_nivel_acotado() -> None:
    y = np.r_[np.zeros(52), np.full(52, 100.0)]
    assert motores._factor_nivel(y, P) == P["nivel_limites"][1]


def test_ets_sin_dos_estaciones_falla() -> None:
    per = _periodos(2023, 2024)
    with pytest.raises(ValueError, match="estaciones"):
        motores.ets_amortiguado_log1p(np.ones(60), per[:60], per[60:70], P)


def test_lgbm_global_sin_fuga_y_finito() -> None:
    per = _periodos(2017, 2023)
    train, hold = per[:-52], per[-52:]
    series = {(g, "general"): _serie(train, 10 + i) for i, g in enumerate(("01", "02", "03"))}
    out = global_ml.lgbm_global_directo(series, train, hold, P)
    assert all(v.shape == (52,) and np.isfinite(v).all() for v in out.values())
    with pytest.raises(AssertionError):
        global_ml._rasgos(np.ones(300), 200, 105, 1)  # objetivo a 105 semanas: lag fuera


def _root_sintetico(tmp_path: Path, prueba: int) -> str:
    d, rel = "x_a00", "x_a00_release_1"
    pub = tmp_path / "config/publication" / d
    pub.mkdir(parents=True)
    (pub / "public_release_pointer.json").write_text(json.dumps({"release_id": rel}))
    (pub / "prospective_status.json").write_text(json.dumps({"observation_dataset_id": "obs"}))
    pol = tmp_path / "artifacts/releases" / d / rel / "policy"
    pol.mkdir(parents=True)
    (pol / "p.yaml").write_text(
        "folds:\n  development:\n    - {epi_year: 2022}\n    - {epi_year: 2023}\n"
        f"  test:\n    - {{epi_year: {prueba}}}\n"
    )
    obs = tmp_path / "artifacts/observations" / d / "obs"
    obs.mkdir(parents=True)
    per = _periodos(2016, 2025)
    pd.DataFrame(
        [
            {"cve_ent": c, "sexo": "general", "epi_year": y, "epi_week": w, "y_cases": 3.0}
            for c in ("01", "02")
            for y, w in per
        ]
    ).to_csv(obs / "epi_dataset_v2.csv", index=False)
    return d


def test_correr_usa_solo_desarrollo(tmp_path: Path) -> None:
    d = _root_sintetico(tmp_path, 2025)
    df, info = flujo.correr(d, "media_3y", CFG, tmp_path)
    assert set(df["epi_year"]) == {2022, 2023} and not info["fallos"]
    met = flujo.metricas(df, set(), info["series"])
    assert (met["smape_nacional"] == 0).all()


def test_traslape_desarrollo_prueba_falla(tmp_path: Path) -> None:
    d = _root_sintetico(tmp_path, 2023)
    with pytest.raises(flujo.BancoError, match="traslapan"):
        flujo.correr(d, "naive_lag52", CFG, tmp_path)


def test_pliegue_incompleto_queda_fuera_del_nacional() -> None:
    df = pd.DataFrame(
        {
            "fold": 2022,
            "geography_id": "01",
            "sex": "general",
            "epi_year": 2022,
            "epi_week": [1, 2],
            "y_true": [1.0, 2.0],
            "y_pred": [1.0, 2.0],
        }
    )
    met = flujo.metricas(df, set(), n_series=2)
    assert np.isnan(met["smape_nacional"].item())


def test_reporte_cuenta_victorias_sobre_el_naive() -> None:
    t = pd.DataFrame(
        {
            "naive_lag52": [10.0, 10.0],
            "ets_amortiguado_log1p": [8.0, 12.0],
            "media_5y": [9.0, 11.0],
        },
        index=["a", "b"],
    )
    fijo = reporte.motor_fijo(t, "naive_lag52", CFG["clase_de"]).set_index("engine")
    assert fijo.loc["ets_amortiguado_log1p", "gana_al_naive"] == 1
    assert fijo.loc["ets_amortiguado_log1p", "gana_al_mejor_simple"] == 1


def test_topdown_reparte_el_nacional_por_proporcion() -> None:
    per = _periodos(2017, 2023)
    train, hold = per[:-52], per[-52:]
    series = {("01", "general"): _serie(train, 10), ("02", "general"): _serie(train, 30)}
    out = flujo.GLOBALES["topdown_media52_nacional"](series, train, hold, P)
    total = sum(s[-52:].mean() for s in series.values())
    assert np.allclose(out[("01", "general")] + out[("02", "general")], total)
    assert out[("02", "general")][0] > out[("01", "general")][0]

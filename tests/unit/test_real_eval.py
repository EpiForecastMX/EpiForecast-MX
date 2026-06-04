"""Tests del módulo común de realidad/forecast para selección de motor (real_eval).

Compartido por produccion_dengue (Dengue) y reselect_motor_2026 (neuro).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from epiforecast.evaluation.real_eval import build_forecasts, build_real, eval_year, smape


def test_smape_cero_y_perfecto():
    assert np.isnan(smape([0.0], [0.0]))  # denom 0
    assert smape([100.0, 50.0], [100.0, 50.0]) == 0.0  # perfecto
    # acepta Series (no solo ndarray)
    assert smape(pd.Series([10.0]), pd.Series([10.0])) == 0.0


def _boletin_csv(path) -> None:
    # 2 padecimientos, 2 entidades, 3 semanas; acumulados crecientes por sexo.
    rows = []
    for pad in ["Dengue", "Parkinson"]:
        for ent in ["Veracruz", "Jalisco"]:
            ah = am = 0
            for sem in [1, 2, 3]:
                ch, cm = sem, sem * 2  # casos de la semana por sexo
                ah += ch
                am += cm
                rows.append(
                    {
                        "Padecimiento": pad,
                        "Entidad": ent,
                        "Anio": 2026,
                        "Semana": sem,
                        "Casos_semana": ch + cm,
                        "Acumulado_hombres": ah,
                        "Acumulado_mujeres": am,
                    }
                )
    # una fila de otro año para probar eval_year
    rows.append(
        {
            "Padecimiento": "Dengue",
            "Entidad": "Veracruz",
            "Anio": 2025,
            "Semana": 50,
            "Casos_semana": 1,
            "Acumulado_hombres": 1,
            "Acumulado_mujeres": 0,
        }
    )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_eval_year(tmp_path):
    bol = tmp_path / "bol.csv"
    _boletin_csv(bol)
    assert eval_year(bol, ["Dengue"]) == 2026
    assert eval_year(bol, ["Parkinson"]) == 2026


def test_build_real_general_y_sexo(tmp_path):
    bol = tmp_path / "bol.csv"
    _boletin_csv(bol)
    real = build_real(bol, ["Dengue"], 2026, weeks_limit=3)
    # general de Veracruz sem 2 = casos_semana = 2 + 4 = 6
    vg = real[(real.entidad == "Veracruz") & (real.sexo == "general") & (real.Semana == 2)]
    assert vg["real"].iloc[0] == 6.0
    # hombres Veracruz sem 2 = incremento de acumulado = 2 (casos H de la semana)
    vh = real[(real.entidad == "Veracruz") & (real.sexo == "hombres") & (real.Semana == 2)]
    assert vh["real"].iloc[0] == 2.0
    # Nacional general sem 1 = suma de las 2 entidades = (1+2)*2 = 6
    nac = real[(real.entidad == "Nacional") & (real.sexo == "general") & (real.Semana == 1)]
    assert nac["real"].iloc[0] == 6.0
    # solo cohorte pedida
    assert set(real["padecimiento"].unique()) == {"Dengue"}


def _forecast_csv(path) -> None:
    # forecast que ARRANCA en la semana ISO 2 (2026-01-05), no en la 1.
    ds = pd.to_datetime(["2026-01-05", "2026-01-12", "2026-01-19"])  # ISO sem 2,3,4
    rows = []
    for ent in ["Veracruz"]:
        for i, d in enumerate(ds):
            rows.append(
                {
                    "ds": d,
                    "yhat": 10.0 + i,
                    "smape_usado": 33.3,
                    "meta_padecimiento": "Dengue",
                    "meta_entidad": ent,
                    "meta_modo": "general",
                }
            )
    pd.DataFrame(rows).to_csv(path, index=False)


def test_build_forecasts_alinea_por_semana_iso(tmp_path):
    fpath = tmp_path / "fc.csv"
    _forecast_csv(fpath)
    fc, cv = build_forecasts({"Prophet": fpath}, ["Dengue"], 2026, weeks_limit=10)
    # La primera fila (2026-01-05) debe etiquetarse Semana 2 (ISO), NO 1 (cumcount).
    first = fc.sort_values("Semana").iloc[0]
    assert int(first["Semana"]) == 2
    assert first["yhat"] == 10.0
    # cv: smape_usado por serie
    assert cv["cv_smape"].iloc[0] == pytest.approx(33.3)
    assert set(fc.columns) >= {"motor", "padecimiento", "entidad", "sexo", "Semana", "yhat"}

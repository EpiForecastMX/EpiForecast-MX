"""Sensibilidad sin 2020–2021: recorte de la historia y referencia fija (sin Optuna)."""

from __future__ import annotations

import numpy as np
import pytest

from epiforecast.banco import ajuste_flujo, sensibilidad

pytestmark = pytest.mark.unit


def _padecimiento() -> ajuste_flujo.Padecimiento:
    anios = np.repeat(np.arange(2015, 2025), 52)
    sem = np.tile(np.arange(1, 53), 10)
    rng = np.random.default_rng(0)
    base = 20 + 5 * np.sin(2 * np.pi * sem / 52)
    y = np.vstack([rng.poisson(base * f) for f in (1.0, 2.0, 0.5)]).astype(float)
    y[:, anios == 2020] *= 0.3  # caída pandémica
    return ajuste_flujo.Padecimiento("demo", y, anios, sem, [2021, 2022, 2023, 2024])


def test_sin_anios_quita_semanas_y_pliegues() -> None:
    p = _padecimiento()
    q = sensibilidad.sin_anios(p, (2020, 2021))
    assert q.y.shape[1] == p.y.shape[1] - 104
    assert not set(q.anios) & {2020, 2021}
    assert q.desarrollo == [2022, 2023, 2024]
    assert sensibilidad.sin_anios(p, ()) is p
    assert p.y.shape[1] == 520  # el original no cambia


def test_referencia_fija_y_naive_sin_cambio_en_2023() -> None:
    p = _padecimiento()
    configs = sensibilidad.configuraciones({2023: {}, 2024: {}})
    configs["nivel_x_perfil_optuna"] = (
        "nivel_x_perfil",
        {a: sensibilidad.ajuste.ESPACIOS["nivel_x_perfil"][2] for a in (2023, 2024)},
    )
    filas = sensibilidad.filas(p, configs)
    ref = {a: ajuste_flujo.naive(p, a) for a in (2022, 2023, 2024)}
    for f in filas:
        assert f["naive_completa"] == ref[f["pliegue"]]
        if f["pliegue"] >= 2023:
            assert f["naive_variante"] == pytest.approx(f["naive_completa"])
    # el control dentro de la variante completa vale exactamente cero
    ctrl = [f for f in filas if f["config"] == "estacional_nivel" and f["variante"] == "completa"]
    assert all(f["log_ratio"] == 0 for f in ctrl)
    # la configuración optimizada sólo existe donde hubo estudio (2023 y 2024)
    opt = {f["pliegue"] for f in filas if f["config"] == "nivel_x_perfil_optuna"}
    assert opt == {2023, 2024}
    # el top-down tiene su ETS en cada variante (sin penalización por falta de precálculo)
    td = [f for f in filas if f["config"] == "topdown"]
    assert td and all(f["smape"] < ajuste_flujo.PENALIZACION for f in td)

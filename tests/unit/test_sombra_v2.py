"""Política v2 en sombra: selección, intervalos, pronóstico, evaluación y candado de prueba."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from epiforecast.data.epi_geo_exposure import load_geo_catalog
from epiforecast.runner import sombra_v2 as sv
from epiforecast.runner import sombra_v2_flujo as flujo

pytestmark = pytest.mark.unit
CAT = load_geo_catalog()
REGLAS = sv.cargar_reglas()


def _met(filas: list[tuple[str, str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"engine": e, "fold": f, "smape_nacional_general": s, "smape_bases": 50.0}
            for e, f, s in filas
        ]
    )


def test_config_declara_control_entre_candidatos() -> None:
    assert REGLAS.control in REGLAS.candidatos
    assert REGLAS.niveles == (80, 95)


def test_productos_suman_las_bases() -> None:
    base = pd.DataFrame(
        [
            {"geography_id": g, "sex": s, "epi_year": 2026, "epi_week": 1, "v": 1.0 + i}
            for i, (g, s) in enumerate(
                [("01", "hombres"), ("01", "mujeres"), ("02", "hombres"), ("02", "mujeres")]
            )
        ]
    )
    prod = sv.productos(base, CAT, ["v"])
    nac = prod[(prod["geography_level"] == "nacional") & (prod["sex"] == "general")]
    assert nac["v"].item() == 10.0
    est = prod[(prod["geography_level"] == "estado") & (prod["sex"] == "general")]
    assert sorted(est["v"]) == [3.0, 7.0]
    assert set(prod["geography_level"]) == {"estado", "region", "nacional"}


def test_productos_sin_desglose_por_sexo() -> None:
    base = pd.DataFrame(
        [
            {"geography_id": g, "sex": "general", "epi_year": 2026, "epi_week": 1, "v": 2.0}
            for g in ("01", "02")
        ]
    )
    prod = sv.productos(base, CAT, ["v"])
    assert set(prod["sex"]) == {"general"}
    assert prod[prod["geography_level"] == "nacional"]["v"].item() == 4.0


def test_control_se_queda_sin_mejora_material() -> None:
    met = _met(
        [("seasonal_naive_lag52", f, 20.0) for f in "abcd"]
        + [("seasonal_mean_5y", f, 19.5) for f in "abcd"]
    )  # 2.5 % < margen
    assert sv.seleccionar(met, REGLAS)["engine"] == "seasonal_naive_lag52"


def test_retador_gana_con_mejora_material_y_mayoritaria() -> None:
    met = _met(
        [("seasonal_naive_lag52", f, 20.0) for f in "abcd"]
        + [("seasonal_mean_5y", f, 15.0) for f in "abcd"]
    )
    sel = sv.seleccionar(met, REGLAS)
    assert sel["engine"] == "seasonal_mean_5y"
    assert sel["dev_vs_control_pct"] == pytest.approx(-25.0)


def test_retador_minoritario_no_desplaza_al_control() -> None:
    # Mejora media del 25 %, pero gana sólo un pliegue de cuatro.
    met = _met(
        [("seasonal_naive_lag52", f, 20.0) for f in "abcd"]
        + [("seasonal_mean_5y", "a", 0.0)]
        + [("seasonal_mean_5y", f, 20.0) for f in "bcd"]
    )
    assert sv.seleccionar(met, REGLAS)["engine"] == "seasonal_naive_lag52"
    sin_mayoria = dataclasses.replace(REGLAS, mayoria_pliegues=False)
    assert sv.seleccionar(met, sin_mayoria)["engine"] == "seasonal_mean_5y"


def _historia(
    anios: range, valor: float = 4.0
) -> dict[tuple[str, str], dict[tuple[int, int], float]]:
    from epiforecast.data.epi_calendar import weeks_in_year

    periodos = [(y, w) for y in anios for w in range(1, weeks_in_year(y) + 1)]
    return {
        (g, s): {p: valor for p in periodos} for g in ("01", "02") for s in ("hombres", "mujeres")
    }


def _ev_dev(error: float) -> pd.DataFrame:
    """Desarrollo sintético de un motor: verdad 4, predicción 4 + error alternado."""
    filas = []
    for g in ("01", "02"):
        for s in ("hombres", "mujeres"):
            for w in range(1, 53):
                filas.append(
                    {
                        "geography_id": g,
                        "sex": s,
                        "fold": "f",
                        "epi_year": 2024,
                        "epi_week": w,
                        "y_true_cases": 4.0,
                        "y_pred_cases": 4.0 + (error if w % 2 else -error),
                    }
                )
    return pd.DataFrame(filas)


def test_intervalos_contienen_el_punto_y_no_son_negativos() -> None:
    q = sv.cuantiles(_ev_dev(1.0), CAT, REGLAS)
    fc = sv.pronostico(_historia(range(2019, 2025)), "seasonal_naive_lag52", REGLAS, q, CAT)
    assert fc.attrs["origen"] == (2024, 52)
    assert len(fc) == 52 * 15  # 4 bases, 2 estatales, 4+2 regionales y 2+1 nacionales
    assert (fc["lower_95"] <= fc["lower_80"]).all() and (fc["upper_80"] <= fc["upper_95"]).all()
    assert (fc["lower_80"] <= fc["y_pred_cases"]).all() and (
        fc["y_pred_cases"] <= fc["upper_80"]
    ).all()
    assert (fc[["lower_80", "lower_95"]] >= 0).all().all()
    assert np.allclose(fc["y_pred_cases"], fc["control_cases"])


def test_pocos_residuos_falla_cerrado() -> None:
    corto = _ev_dev(1.0).query("epi_week <= 10")
    with pytest.raises(sv.SombraError, match="residuos"):
        sv.cuantiles(corto, CAT, REGLAS)


def test_evaluar_pronostico_perfecto() -> None:
    q = sv.cuantiles(_ev_dev(1.0), CAT, REGLAS)
    fc = sv.pronostico(_historia(range(2019, 2025)), "seasonal_mean_3y", REGLAS, q, CAT)
    llave = [*sv.LLAVE, *sv.PERIODO]
    verdad = fc[llave].assign(y_true_cases=fc["y_pred_cases"])
    pub = fc[llave].assign(y_pred_cases=fc["y_pred_cases"] * 2)
    out = sv.evaluar(fc, verdad, pub, REGLAS.niveles)
    assert out["semanas"] == 52
    assert out["smape_nacional_sombra"] == 0.0
    assert out["smape_nacional_publicado"] > 0.0
    assert out["cobertura_95_productos"] == 100.0


def test_desarrollo_rechaza_anios_de_prueba(tmp_path: Path) -> None:
    d, rel, bench = "x_a00", "x_a00_release_1", "x_a00_benchmark_full_1"
    (tmp_path / "config/publication" / d).mkdir(parents=True)
    (tmp_path / "config/publication" / d / "public_release_pointer.json").write_text(
        json.dumps({"release_id": rel})
    )
    rdir = tmp_path / "artifacts/releases" / d / rel
    (rdir / "policy").mkdir(parents=True)
    (rdir / "selection").mkdir()
    (rdir / "policy/p.yaml").write_text("folds:\n  test:\n    - {epi_year: 2025}\n")
    (rdir / "selection/acceptance.json").write_text(
        json.dumps({"provenance": {"benchmark_run_id": bench}})
    )
    edir = tmp_path / "runs" / bench / "artifacts" / "seasonal_naive_lag52"
    edir.mkdir(parents=True)
    ev = _ev_dev(0.0).assign(
        engine="seasonal_naive_lag52", split="development", geography_level="estado", epi_year=2025
    )
    ev.to_csv(edir / "evaluation.csv", index=False)
    with pytest.raises(sv.SombraError, match="prueba"):
        flujo.desarrollo(d, REGLAS, tmp_path)
    ev.assign(epi_year=2024).to_csv(edir / "evaluation.csv", index=False)
    assert len(flujo.desarrollo(d, REGLAS, tmp_path)) == len(ev)


def test_predicciones_banco_coinciden_con_el_runner_en_el_naive() -> None:
    from epiforecast.runner.sombra_predictores import predicciones_base

    trains = _historia(range(2019, 2025), valor=3.0)
    from epiforecast.runner.forecasting import horizon_periods

    periodos = horizon_periods((2024, 52), 10)
    a = predicciones_base(trains, "seasonal_naive_lag52", periodos, "benchmark")
    b = predicciones_base(trains, "naive_lag52", periodos, "banco")
    assert a == b


def test_cuantiles_ampliados_ensanchan_la_banda() -> None:
    ev = _ev_dev(1.0).assign(y_pred_cases=lambda d: d["y_pred_cases"] * (1 + d["epi_week"] / 100))
    amplio = dataclasses.replace(REGLAS, cuantil_de=(90.0, 99.0))
    q, qa = sv.cuantiles(ev, CAT, REGLAS), sv.cuantiles(ev, CAT, amplio)
    assert ((qa["q_hi_80"] - qa["q_lo_80"]) >= (q["q_hi_80"] - q["q_lo_80"])).all()


def test_desarrollo_banco_excluye_motores_con_fallos(tmp_path: Path) -> None:
    d, rel = "x_a00", "x_a00_release_1"
    (tmp_path / "config/publication" / d).mkdir(parents=True)
    (tmp_path / "config/publication" / d / "public_release_pointer.json").write_text(
        json.dumps({"release_id": rel})
    )
    pol = tmp_path / "artifacts/releases" / d / rel / "policy"
    pol.mkdir(parents=True)
    (pol / "p.yaml").write_text("folds:\n  test:\n    - {epi_year: 2025}\n")
    banco = tmp_path / "runs/banco_ampliado/v1/tareas"
    banco.mkdir(parents=True)
    df = _ev_dev(0.0).rename(columns={"y_true_cases": "y_true", "y_pred_cases": "y_pred"})
    df = df.assign(fold=2024)
    for motor, fallos in (("naive_lag52", []), ("tsb", [{"fold": 2024}])):
        df.to_csv(banco / f"{d}__{motor}.csv.gz", index=False)
        (banco / f"{d}__{motor}.json").write_text(json.dumps({"fallos": fallos}))
    v3 = sv.cargar_reglas(sv.CONFIG.parent / "sombra_v3.yaml")
    ev = flujo.desarrollo(d, v3, tmp_path)
    assert set(ev["engine"]) == {"naive_lag52"}
    assert set(ev["fold"]) == {"development_2024"}

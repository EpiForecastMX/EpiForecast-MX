"""Galería Dengue W37: sexo observado, motor de cada serie y sólo la banda propia del motor.

Antes, hombres y mujeres eran la serie general multiplicada por una proporción constante y con el
motor de la general, y el zoom y la vista de 5 años dibujaban una banda empírica de ±1.96σ como si
fuera la incertidumbre del motor. Rótulos aprobados: «media prevista» y «intervalo predictivo
central nominal del N %», con el N que declara el propio motor.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import pytest

from epiforecast.utils.semana_epi import ds_de_semana_boletin

pytestmark = pytest.mark.unit

ULTIMA = (2026, 20)  # última semana del boletín del fixture


@pytest.fixture
def galeria(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    cfg = sys.modules["epiforecast.utils.config"]
    monkeypatch.setitem(cfg.conf["paths"], "reports", str(tmp_path / "reports"))
    monkeypatch.delitem(sys.modules, "scripts.build_dengue_gallery", raising=False)
    return importlib.import_module("scripts.build_dengue_gallery")


# --- serie real por sexo ----------------------------------------------------------------------


def test_anio_que_empieza_a_mitad_no_vuelca_el_acumulado(galeria) -> None:
    """Dengue 2018 arranca en la W27: su primer acumulado suma 26 semanas y no es un incremento."""
    g = pd.DataFrame({"Anio": [2018] * 3, "Semana": [27, 28, 29], "a": [752, 760, 775]})
    estricto = galeria._incrementos_observados(g, "a", solo_semanales=True)
    assert pd.isna(estricto.iloc[0])
    assert estricto.iloc[1:].tolist() == [8.0, 15.0]
    # control: la regla de neuro (sin la opción) sí lo vuelca, que es el pico que se evita
    assert galeria._incrementos_observados(g, "a").iloc[0] == 752.0


def test_hueco_del_boletin_no_suma_varias_semanas(galeria) -> None:
    """Dengue 2020 salta de la W40 a la W45: ese incremento son cinco semanas, no una."""
    g = pd.DataFrame(
        {"Anio": [2020] * 4, "Semana": [39, 40, 45, 46], "a": [7000, 7563, 11049, 11585]}
    )
    estricto = galeria._incrementos_observados(g, "a", solo_semanales=True)
    assert pd.isna(estricto.iloc[2])
    assert estricto.iloc[[1, 3]].tolist() == [563.0, 536.0]
    assert galeria._incrementos_observados(g, "a").iloc[2] == 3486.0  # control: regla neuro


def test_reinicio_del_acumulado_en_la_semana_uno_dengue(galeria) -> None:
    """Dengue reinicia el acumulado en la semana 1: esa semana aporta su propio acumulado.

    2024 tiene 52 semanas del boletín, así que 2024-W52 → 2025-W1 son consecutivas (en 2025, con 53,
    la consecutiva de la W53 sería la 2026-W1).
    """
    g = pd.DataFrame(
        {"Anio": [2024, 2025, 2025, 2025], "Semana": [52, 1, 2, 3], "a": [9000, 6, 88, 193]}
    )
    assert galeria._incrementos_observados(g, "a", solo_semanales=True).tolist()[1:] == [
        6.0,
        82.0,
        105.0,
    ]


def test_semana_uno_sin_antecedente_queda_ausente(galeria) -> None:
    """Sin la semana previa no se sabe si el acumulado de la semana 1 ya se reinició."""
    g = pd.DataFrame({"Anio": [2026] * 3, "Semana": [1, 2, 3], "a": [6, 88, 193]})
    inc = galeria._incrementos_observados(g, "a", solo_semanales=True)
    assert pd.isna(inc.iloc[0]) and inc.iloc[1:].tolist() == [82.0, 105.0]


def test_neuro_reinicia_en_la_semana_dos_sin_pico_anual(galeria) -> None:
    """Depresión Nacional mujeres 2025: la semana 1 continúa el acumulado de 2024 y la 2 reinicia."""
    g = pd.DataFrame(
        {
            "Anio": [2024, 2024, 2025, 2025, 2025],
            "Semana": [51, 52, 1, 2, 3],
            "a": [108895, 110369, 111375, 963, 2693],
        }
    )
    inc = galeria._incrementos_observados(g, "a", solo_semanales=True).tolist()
    assert inc[1:] == [1474.0, 1006.0, 963.0, 1730.0]
    # control: agrupar por año tomaba el acumulado de la semana 1 (111,375) como incremento y la
    # reparación de la semana 2 promediaba con él: el pico anual de decenas de miles
    previa = g.groupby("Anio")["a"].diff()
    assert previa.where(previa.notna(), g["a"]).iloc[2] == 111375.0


def test_real_por_sexo_es_observado_y_descarta_lo_ausente(galeria) -> None:
    bol = pd.DataFrame(
        {
            "Anio": [2018, 2018, 2018],
            "Semana": [27, 28, 29],
            "Entidad": ["Colima"] * 3,
            "Casos_semana": [30, 30, 30],
            "Acumulado_hombres": [752, 760, 775],
            "Acumulado_mujeres": [800, 803, 810],
        }
    )
    h = galeria._real_sexo_dengue(bol, "hombres")
    m = galeria._real_sexo_dengue(bol, "mujeres")
    assert h["y"].tolist() == [8.0, 15.0]  # la W27 sin antecedente no aparece (ni como 0)
    assert m["y"].tolist() == [3.0, 7.0]
    assert h["ds"].tolist() == [ds_de_semana_boletin(2018, 28), ds_de_semana_boletin(2018, 29)]


# --- rótulos ----------------------------------------------------------------------------------


def test_rotulo_de_banda_usa_el_nivel_declarado(galeria) -> None:
    assert galeria.etiqueta_banda(0.9) == "Intervalo predictivo central nominal del 90 %"
    assert galeria.etiqueta_banda(0.8) == "Intervalo predictivo central nominal del 80 %"
    assert galeria.etiqueta_banda(None) is None


# --- main: motor y serie de cada fila ---------------------------------------------------------


def _boletin() -> pd.DataFrame:
    filas = []
    acum_h = acum_m = 0
    for s in range(2, ULTIMA[1] + 1):
        acum_h += 2
        acum_m += 5
        filas.append(
            {
                "Anio": 2026,
                "Semana": s,
                "Entidad": "Colima",
                "Padecimiento": "Dengue",
                "Casos_semana": 9,  # H + M = 7: el boletín no reconcilia
                "Acumulado_hombres": acum_h,
                "Acumulado_mujeres": acum_m,
            }
        )
    return pd.DataFrame(filas)


def _forecasts(galeria: Any) -> None:
    """DeepAR y Prophet con valores distintos por sexo y su nivel nominal declarado."""
    ds = pd.date_range(ds_de_semana_boletin(2026, 4), periods=70, freq="7D")
    for motor, nivel, base in (("deepar", 0.9, 100.0), ("prophet", 0.8, 200.0)):
        filas = []
        for k, sexo in enumerate(("general", "hombres", "mujeres")):
            yhat = base + 10 * k
            filas.append(
                pd.DataFrame(
                    {
                        "ds": ds.strftime("%Y-%m-%d"),
                        "yhat": yhat,
                        "yhat_lower": yhat - 3,
                        "yhat_upper": yhat + 3,
                        "intervalo_disponible": True,
                        "intervalo_nivel_nominal": nivel,
                        "meta_padecimiento": "Dengue",
                        "meta_entidad": "Colima",
                        "meta_modo": sexo,
                    }
                )
            )
        p = galeria.FC_BASE / motor / f"all_forecast_{motor}.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        pd.concat(filas).to_csv(p, index=False)


@pytest.fixture
def corrida(galeria, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, list[Any]]:
    prod = pd.DataFrame(
        {
            "entidad": ["Colima"] * 3,
            "sexo": ["general", "hombres", "mujeres"],
            "motor_productivo": ["DeepAR", "Prophet", "DeepAR"],
        }
    )
    galeria.PROD.parent.mkdir(parents=True, exist_ok=True)
    prod.to_csv(galeria.PROD, index=False)
    _forecasts(galeria)
    llamadas: dict[str, list[Any]] = {"zoom": [], "chart": [], "extra": [], "payload": []}
    monkeypatch.setattr(galeria, "cargar_boletin_dengue", _boletin)
    monkeypatch.setattr(galeria, "_chart", lambda *a, **k: llamadas["chart"].append((a, k)))
    monkeypatch.setattr(galeria, "_chart_zoom", lambda *a, **k: llamadas["zoom"].append((a, k)))
    monkeypatch.setattr(
        galeria, "render_extra_views", lambda *a, **k: llamadas["extra"].append((a, k))
    )
    monkeypatch.setattr(galeria, "_dengue_regiones", lambda *a, **k: 0)
    out = tmp_path / "web" / "dengue"
    out.mkdir(parents=True)
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(out)])
    assert galeria.main() == 0
    return llamadas


def test_cada_sexo_usa_su_motor_y_su_pronostico(corrida) -> None:
    motores = [a[2] for a, _ in corrida["zoom"]]
    assert motores == ["DeepAR", "Prophet", "DeepAR"]
    # el pronóstico de hombres es el de Prophet-hombres (210), sin multiplicar por proporción
    fc_h = corrida["zoom"][1][0][1]
    assert set(fc_h["yhat"].round(6)) == {210.0}
    fc_m = corrida["zoom"][2][0][1]
    assert set(fc_m["yhat"].round(6)) == {120.0}


def test_real_de_cada_sexo_es_el_incremento_observado(corrida) -> None:
    real_h = corrida["zoom"][1][0][0]
    real_m = corrida["zoom"][2][0][0]
    assert set(real_h["y"]) == {2.0}  # acumulado de hombres sube 2 por semana
    assert set(real_m["y"]) == {5.0}
    real_g = corrida["zoom"][0][0][0]
    assert set(real_g["y"]) == {9.0}  # la general es Casos_semana, no H + M


def test_banda_nativa_solo_sobre_el_futuro_con_rotulos_aprobados(corrida) -> None:
    for (args, kw), nivel in zip(corrida["zoom"], (90, 80, 90), strict=True):
        real, fc = args[0], args[1]
        ultima = real["ds"].max()
        obs = fc[fc["ds"] <= ultima]
        fut = fc[fc["ds"] > ultima]
        assert obs["yhat_lower"].isna().all() and obs["yhat_upper"].isna().all()
        assert ((fut["yhat_upper"] - fut["yhat_lower"]).round(6) == 6.0).all()  # la nativa (±3)
        assert kw["etiqueta_linea"] == f"Media prevista ({args[2]})"
        assert kw["etiqueta_banda"] == f"Intervalo predictivo central nominal del {nivel} %"


def test_vistas_extra_piden_el_sexo_a_su_motor(corrida) -> None:
    for (args, kw), sexo in zip(corrida["extra"], ("general", "hombres", "mujeres"), strict=True):
        assert args[3] == sexo  # fetch_sexo
        assert args[4] == 1.0  # sin proporción
        assert kw["etiqueta_banda"].startswith("Intervalo predictivo central nominal")


# --- vista de 5 años --------------------------------------------------------------------------


def test_vista_5_anios_no_fabrica_banda(galeria, tmp_path, monkeypatch) -> None:
    """Ensemble no produce intervalo: la vista de 5 años no debe dibujarle ±1.96σ."""
    ds = pd.date_range("2025-01-06", periods=90, freq="7D")
    fc = pd.DataFrame({"ds": ds, "yhat": 50.0, "yhat_lower": 50.0, "yhat_upper": 50.0})
    real = pd.DataFrame({"ds": ds[:70], "y": [40.0, 60.0] * 35})
    capt: list[pd.DataFrame] = []
    monkeypatch.setattr(galeria, "forecast_window", lambda *a, **k: fc)
    monkeypatch.setattr(galeria, "_chart_zoom", lambda r, f, *a, **k: capt.append(f))
    monkeypatch.setattr(galeria, "_chart_compare", lambda *a, **k: None)
    galeria.render_extra_views(
        real,
        "Depresión",
        "Colima",
        "general",
        1.0,
        real["ds"].max(),
        ds.max(),
        "Ensemble",
        tmp_path / "x.png",
        "t",
        enso=False,
        motores_comparacion={"Ensemble": "Ensemble"},
    )
    fut = capt[0][capt[0]["ds"] > real["ds"].max()]
    assert ((fut["yhat_upper"] - fut["yhat_lower"]).abs() < 1e-9).all()


def test_sin_regiones_no_genera_las_regiones(galeria, tmp_path, monkeypatch) -> None:
    """Las 4 regiones no son parte de las 99 series de la asignación: la opción las omite."""
    prod = pd.DataFrame(
        {"entidad": ["Colima"], "sexo": ["general"], "motor_productivo": ["DeepAR"]}
    )
    galeria.PROD.parent.mkdir(parents=True, exist_ok=True)
    prod.to_csv(galeria.PROD, index=False)
    _forecasts(galeria)
    monkeypatch.setattr(galeria, "cargar_boletin_dengue", _boletin)
    for f in ("_chart", "_chart_zoom", "render_extra_views"):
        monkeypatch.setattr(galeria, f, lambda *a, **k: None)

    def _no(*a: Any, **k: Any) -> int:
        raise AssertionError("no debía generar regiones")

    monkeypatch.setattr(galeria, "_dengue_regiones", _no)
    out = tmp_path / "web" / "dengue"
    out.mkdir(parents=True)
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(out), "--sin-regiones"])
    assert galeria.main() == 0
    items = json.loads((out / "_gallery_items.json").read_text(encoding="utf-8"))
    assert items and not any("Region" in json.dumps(i) for i in items)


def test_revision_negativa_de_la_fuente_queda_ausente(galeria) -> None:
    """Neuro 2016-W20: la fuente infla el acumulado y lo corrige en la W21. La W21 no se imputa."""
    g = pd.DataFrame(
        {"Anio": [2016] * 5, "Semana": [18, 19, 20, 21, 22], "a": [1325, 1406, 28124, 1575, 1661]}
    )
    inc = galeria._incrementos_observados(g, "a", solo_semanales=True)
    assert inc.iloc[1] == 81.0 and inc.iloc[2] == 26718.0  # el dato publicado se conserva
    assert pd.isna(inc.iloc[3]) and inc.iloc[4] == 86.0
    # control: la regla sin estricta imputa la W21 con la media que incluye el error (pico doble)
    assert galeria._incrementos_observados(g, "a").iloc[3] > 8000

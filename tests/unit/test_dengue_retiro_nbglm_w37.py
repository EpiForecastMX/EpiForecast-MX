"""Retiro de NBGLM de las superficies públicas de Dengue (ENMIENDA_DENGUE_NBGLM_W37, 13-oct-2026).

NBGLM queda suspendido por su predicción recursiva: ni la proyección a 5 años ni el escenario
El Niño (ambos lo reajustan durante el build) llegan al producto, la comparación de la galería
no lo muestra y los motores productivos se derivan de la asignación congelada, nunca de una
lista escrita a mano.
"""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd
import pytest

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]


def _importa(nombre: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    cfg = sys.modules["epiforecast.utils.config"]
    monkeypatch.setitem(cfg.conf["paths"], "reports", str(tmp_path / "reports"))
    monkeypatch.setitem(cfg.conf["paths"], "interim", str(tmp_path / "interim"))
    monkeypatch.delitem(sys.modules, nombre, raising=False)
    return importlib.import_module(nombre)


def _asignacion(nacional: str = "DeepAR") -> pd.DataFrame:
    filas = [("Nacional", "general", nacional), ("Nacional", "hombres", "Prophet")]
    filas += [("Colima", s, "DeepAR") for s in ("general", "hombres", "mujeres")]
    return pd.DataFrame(filas, columns=["entidad", "sexo", "motor_productivo"])


# --- dengue_forecast.json: sin capa de proyección -------------------------------------------


def _forecast_nacional(n: int, ultima: pd.Timestamp) -> pd.DataFrame:
    ds = pd.date_range(ultima + pd.Timedelta(days=7), periods=n, freq="7D")
    return pd.DataFrame(
        {
            "ds": ds.strftime("%Y-%m-%d"),
            "yhat": 10.0,
            "yhat_lower": 5.0,
            "yhat_upper": 20.0,
            "meta_padecimiento": "Dengue",
            "meta_entidad": "Nacional",
            "meta_modo": "general",
        }
    )


@pytest.fixture
def web(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    mod = _importa("scripts.build_dengue_forecast_web", tmp_path, monkeypatch)
    ultima = pd.Timestamp("2026-08-31")
    serie = pd.DataFrame({"ds": pd.date_range("2025-01-06", ultima, freq="7D"), "y": 3.0})
    monkeypatch.setattr(mod, "serie_nacional", lambda: serie)
    monkeypatch.setattr(mod, "serie_contexto_a9091", lambda: pd.DataFrame(columns=["ds", "y"]))
    prod = tmp_path / "reports" / "ProdDetails" / "produccion_dengue.csv"
    prod.parent.mkdir(parents=True)
    _asignacion().to_csv(prod, index=False)
    monkeypatch.setattr(mod, "PROD", prod)
    mod._ultima = ultima
    return mod


def _escribe_fc(mod: Any, tmp_path: Path, motor: str, n: int) -> None:
    p = tmp_path / "reports" / "forecasts" / motor.lower() / f"all_forecast_{motor.lower()}.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    _forecast_nacional(n, mod._ultima).to_csv(p, index=False)


def _corre(mod: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    out = tmp_path / "web"
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(out), "--generado", "2026-10-13"])
    assert mod.main() == 0
    return json.loads((out / "dengue_forecast.json").read_text(encoding="utf-8"))


def test_json_sin_proyeccion_ni_motor_de_proyeccion(web, tmp_path, monkeypatch) -> None:
    _escribe_fc(web, tmp_path, "DeepAR", 52)
    data = _corre(web, tmp_path, monkeypatch)
    assert "proyeccion" not in data
    assert "motor_proyeccion" not in data["meta"]
    assert "anios_proyeccion" not in data["meta"]
    assert data["meta"]["horizonte_semanas"] == 52
    assert len(data["pronostico"]) == 52
    assert data["meta"]["distribucion"] == {"DeepAR": 4, "Prophet": 1}


def test_el_build_no_ajusta_nbglm(web, tmp_path, monkeypatch) -> None:
    """Si el build volviera a importar el predictor suspendido, esta prueba lo detecta."""
    import epiforecast.models.nbglm.model as nb

    def _prohibido(*_a: object, **_k: object) -> None:
        raise AssertionError("el build de la página no debe ajustar NBGLM")

    monkeypatch.setattr(nb.NBGLMForecaster, "fit", _prohibido)
    monkeypatch.setattr(nb.NBGLMForecaster, "predict", _prohibido)
    _escribe_fc(web, tmp_path, "DeepAR", 52)
    _corre(web, tmp_path, monkeypatch)
    assert not hasattr(web, "proyeccion_nbglm")


def test_pronostico_de_mas_de_52_semanas_aborta(web, tmp_path, monkeypatch) -> None:
    _escribe_fc(web, tmp_path, "DeepAR", 53)
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(tmp_path / "w"), "--generado", "x"])
    with pytest.raises(SystemExit, match="53 semanas"):
        web.main()


def test_motor_nacional_sin_archivo_no_cae_a_otro(web, tmp_path, monkeypatch) -> None:
    """Antes, un motor fuera de la lista fija caía en silencio a Prophet y meta.motor_nacional mentía."""
    _escribe_fc(web, tmp_path, "Prophet", 52)  # existe Prophet, pero el nacional es otro motor
    _asignacion(nacional="LightGBM").to_csv(web.PROD, index=False)
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(tmp_path / "w"), "--generado", "x"])
    with pytest.raises(FileNotFoundError, match="all_forecast_lightgbm"):
        web.main()


# --- Escenario El Niño: fuera del build ------------------------------------------------------


def test_escenario_nino_se_niega_sin_bandera(tmp_path, monkeypatch) -> None:
    mod = _importa("scripts.dengue_pronostico_nino", tmp_path, monkeypatch)
    out = tmp_path / "nino"
    monkeypatch.setattr(sys, "argv", ["x", "--out", str(out)])
    assert mod.main() == 2
    assert not out.exists()


def test_make_dengue_web_no_invoca_el_escenario() -> None:
    mk = (ROOT / "Makefile").read_text(encoding="utf-8")
    i = mk.index("\ndengue-web:")
    receta = mk[i : mk.index("\n\n", i)]
    assert "build_dengue_forecast_web" in receta  # control positivo: es la receta correcta
    assert "dengue_pronostico_nino" not in receta


# --- Galería: comparación sin NBGLM ----------------------------------------------------------


def test_comparacion_dengue_deriva_de_la_asignacion(tmp_path, monkeypatch) -> None:
    gal = _importa("scripts.build_dengue_gallery", tmp_path, monkeypatch)
    cmp_ = gal.compare_motors(_asignacion())
    assert list(cmp_) == ["DeepAR", "Prophet", "Ensemble", "Stacking"]
    assert "NBGLM" not in cmp_
    assert cmp_["DeepAR"] == "DeepAR"
    assert "no elegible" in cmp_["Ensemble"] and "no elegible" in cmp_["Stacking"]


def test_nbglm_con_series_si_se_compara(tmp_path, monkeypatch) -> None:
    """La exclusión sale de la asignación: si algún día NBGLM tiene series, aparece."""
    gal = _importa("scripts.build_dengue_gallery", tmp_path, monkeypatch)
    prod = _asignacion()
    prod.loc[0, "motor_productivo"] = "NBGLM"
    assert "NBGLM" in gal.compare_motors(prod)


def test_vistas_extra_exigen_motores_de_comparacion(tmp_path, monkeypatch) -> None:
    gal = _importa("scripts.build_dengue_gallery", tmp_path, monkeypatch)
    real = pd.DataFrame({"ds": pd.date_range("2025-01-06", periods=60, freq="7D"), "y": 1.0})
    monkeypatch.setattr(gal, "_chart_zoom", lambda *a, **k: None)
    monkeypatch.setattr(gal, "forecast_window", lambda *a, **k: pd.DataFrame())
    with pytest.raises(ValueError, match="sin motores"):
        gal.render_extra_views(
            real,
            "Dengue",
            "Colima",
            "general",
            1.0,
            real["ds"].max(),
            real["ds"].max(),
            "DeepAR",
            tmp_path / "x.png",
            "t",
            enso=True,
        )


def test_comparacion_neuro_conserva_sus_cuatro_motores(tmp_path, monkeypatch) -> None:
    neuro = _importa("scripts.build_neuro_gallery", tmp_path, monkeypatch)
    assert {m: m for m in ("Prophet", "DeepAR", "Ensemble", "Stacking")} == neuro.COMPARE_NEURO


# --- EpiBot y reporte: motores productivos derivados -----------------------------------------


def test_knowledge_deriva_motores_productivos(tmp_path, monkeypatch) -> None:
    kb = _importa("scripts.build_web_knowledge", tmp_path, monkeypatch)
    assert kb._motores_productivos_dengue(_asignacion()) == ["DeepAR", "Prophet"]
    src = (ROOT / "scripts" / "build_web_knowledge.py").read_text(encoding="utf-8")
    assert '"proyeccion_anios"' not in src
    assert '"motores_productivos": ["DeepAR", "Prophet", "NBGLM"]' not in src


def test_reporte_marca_en_produccion_segun_la_asignacion(tmp_path, monkeypatch) -> None:
    rep = _importa("scripts.genera_reporte", tmp_path, monkeypatch)
    prod = _asignacion().assign(smape_ganador=10.0, total_real=5, n_semanas_real=30)
    p = tmp_path / "prod.csv"
    prod.to_csv(p, index=False)
    monkeypatch.setattr(rep, "PROD_DENGUE", p)
    tabla = {m["motor"]: m for m in rep.compute_dengue_stats()["motor_table"]}
    assert tabla["DeepAR"]["en_produccion"] and tabla["Prophet"]["en_produccion"]
    assert not tabla["NB-GLM"]["en_produccion"]
    assert tabla["NB-GLM"]["nota"].startswith("Suspendido")
    assert not tabla["Ensemble"]["en_produccion"] and "No elegible" in tabla["Ensemble"]["nota"]

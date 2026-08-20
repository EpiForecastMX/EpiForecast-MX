"""Guardas del paquete histórico del paper MICAI 2026.

El paquete de datos (~500 MB) no se versiona; estas pruebas se saltan solas si no está
materializado. Lo que sí se versiona —código, MANIFEST, raíz de confianza y resultados—
se verifica siempre.

Materializar el paquete:  python scripts/paper_micai_2026/sella_bundle.py
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPTS = RAIZ / "scripts/paper_micai_2026"
REPORTES = RAIZ / "reports/paper_micai_2026"
sys.path.insert(0, str(SCRIPTS))


def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _bundle():
    """Importa bundle o salta la prueba si el paquete no está materializado."""
    try:
        import bundle as b
    except (FileNotFoundError, ImportError) as e:
        pytest.skip(f"paquete no materializado: {e}")
    if not (b.BASE / "MANIFEST.json").exists():
        pytest.skip("paquete no materializado")
    return b


# --------------------------------------------------------------- raíz de confianza
def test_raiz_de_confianza_coincide_con_el_manifest():
    """El SHA-256 registrado en Git debe describir al MANIFEST versionado."""
    esperado = (REPORTES / "RAIZ_SHA256.txt").read_text().split()[0]
    assert _sha256(REPORTES / "MANIFEST.json") == esperado


def test_el_manifest_nombra_los_commits_del_paper():
    m = json.loads((REPORTES / "MANIFEST.json").read_text())
    assert m["commit_modelos"] == "c13e7163"
    assert m["commit_observaciones"] == "b43ebdf2"
    assert len(m["piezas"]) == 7


# --------------------------------------------------------------- resultados versionados
def test_los_resultados_coinciden_con_sus_hashes():
    d = REPORTES / "resultados"
    registrados = json.loads((d / "HASHES.json").read_text())["archivos"]
    for nombre, sha in registrados.items():
        assert _sha256(d / nombre) == sha, f"{nombre} cambió sin actualizar HASHES.json"


def test_la_particion_regional_es_la_del_contrato():
    m = pd.read_csv(REPORTES / "resultados/region_membership.csv")
    assert len(m) == 32
    assert not m.entidad.duplicated().any()
    assert m.region.value_counts().to_dict() == {
        "Urbana media": 15,
        "Rural / dispersa": 7,
        "Sur-Sureste vulnerable": 6,
        "Metropolitana alta": 4,
    }


# --------------------------------------------------------------- guardas del paquete
def test_las_siete_piezas_verifican():
    b = _bundle()
    fallan = [n for n, ok in b.verifica_todo() if not ok]
    assert not fallan, f"piezas con SHA-256 distinto: {fallan}"


@pytest.mark.parametrize(
    "viva",
    [
        "data/processed/tableau.csv",
        "data/processed/dataset_boletin_epidemiologico.csv",
        "reports/ProdDetails/tabla_333_modelos_produccion.xlsx",
        "reports/forecasts/deepar/all_forecast_deepar.csv",
    ],
)
def test_las_rutas_vivas_estan_prohibidas(viva):
    """Las cifras del paper no pueden salir del árbol de trabajo: hoy dan otros números."""
    b = _bundle()
    with pytest.raises(b.FueraDelPaqueteError):
        b.prohibe_rutas_vivas(RAIZ / viva)


def test_una_pieza_inexistente_no_se_sirve():
    b = _bundle()
    with pytest.raises(b.FueraDelPaqueteError):
        b.ruta("no_existe.csv")


# --------------------------------------------------------------- reproducción mínima
def test_la_tabla_2_publicada_reproduce():
    """sMAPE 6,63 % y desviación +4,40 % — lo impreso en el paper, sin corregir."""
    b = _bundle()
    import numpy as np

    obs = b.observado()
    obs = obs[(obs.Padecimiento == "Depresión") & (obs.Anio == 2026)]
    y_s = obs.groupby("Semana")["Casos_semana"].sum()

    t = b.tableau()
    d = t[
        (t.padecimiento == "Depresión") & (t.meta_modo == "general") & (t.entidad == "Nacional")
    ].copy()
    d["ds"] = pd.to_datetime(d.ds)
    d = d[d.ds.dt.isocalendar().year == 2026]
    d["w"] = d.ds.dt.isocalendar().week.astype(int)
    f_s = d.set_index("w")["yhat_ensemble"]

    W = [w for w in range(2, 19) if w in y_s.index and w in f_s.index]
    y, f = y_s[W].values.astype(float), f_s[W].values.astype(float)
    smape = 100 * np.mean(np.abs(y - f) / ((np.abs(y) + np.abs(f)) / 2))
    assert round(smape, 2) == 6.63
    assert round(100 * (f.sum() - y.sum()) / y.sum(), 2) == 4.40
    assert y.sum() == 48300


def test_el_desfase_de_semana_esta_confirmado():
    """incrementos_total(ds=w) sigue al boletín de w+1, no al de w."""
    b = _bundle()
    t = b.tableau()
    d = t[
        (t.padecimiento == "Depresión") & (t.meta_modo == "general") & (t.entidad == "Jalisco")
    ].copy()
    d["ds"] = pd.to_datetime(d.ds)
    d = d[d.ds.dt.isocalendar().year == 2025]
    d["w"] = d.ds.dt.isocalendar().week.astype(int)
    modelo = d.set_index("w")["incrementos_total"]

    o = b.observado()
    o = o[(o.Padecimiento == "Depresión") & (o.Anio == 2025)]
    o["Entidad"] = o["Entidad"].replace({"Distrito Federal": "Ciudad de México"})
    bol = o[o.Entidad == "Jalisco"].set_index("Semana")["Casos_semana"]

    ws = [w for w in range(2, 50) if w in modelo.index and w in bol.index and w + 1 in bol.index]
    con_w = sum(abs(modelo[w] - bol[w]) < 0.5 for w in ws)
    con_w1 = sum(abs(modelo[w] - bol[w + 1]) < 0.5 for w in ws)
    assert con_w1 > 5 * max(con_w, 1), f"coincidencias w={con_w} w+1={con_w1}"

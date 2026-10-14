"""Seguimiento posterior al corte (campos de validación v2): misma semana a ambos lados.

Origen: en la tabla W37 `pron_sem_previa` era el pronóstico de la W38 y `realidad_sem_previa` la
realidad de la W39. Estas pruebas fijan que el par se forma por (serie, semana del boletín, ds),
que nada se desplaza y que un lado faltante declara el par ausente.
"""

from __future__ import annotations

import importlib
from pathlib import Path
import sys
from typing import Any

from openpyxl import Workbook, load_workbook
import pandas as pd
import pytest
from scripts import genera_validacion_semanal as gvs

from epiforecast.utils.semana_epi import ds_de_semana_boletin

pytestmark = pytest.mark.unit


@pytest.fixture
def seg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """El módulo, importado con ``conf["paths"]["reports"]`` apuntando a un directorio temporal."""
    cfg = sys.modules["epiforecast.utils.config"]
    monkeypatch.setitem(cfg.conf["paths"], "reports", str(tmp_path / "reports"))
    for m in ("scripts.genera_seguimiento_post_corte", "scripts.build_dengue_gallery"):
        monkeypatch.delitem(sys.modules, m, raising=False)
    return importlib.import_module("scripts.genera_seguimiento_post_corte")


CORTE = (2026, 37)
SERIE = {
    "cohorte": "neuro",
    "padecimiento": "Depresion",
    "entidad": "Nacional",
    "sexo": "general",
    "motor": "Prophet",
}


def test_semanas_objetivo_cruzan_el_anio_con_la_53(seg: Any) -> None:
    assert seg.semanas_objetivo((2025, 51), (2026, 2)) == [
        (2025, 52),
        (2025, 53),
        (2026, 1),
        (2026, 2),
    ]
    assert seg.semanas_objetivo((2026, 51), (2027, 1)) == [(2026, 52), (2027, 1)]  # 2026 tiene 52
    assert seg.semanas_objetivo(CORTE, (2026, 39)) == [(2026, 38), (2026, 39)]
    assert seg.semanas_objetivo(CORTE, CORTE) == []


def test_el_paso_sin_semana_del_boletin_se_declara_fuera(seg: Any) -> None:
    fc = pd.DataFrame({"ds": pd.to_datetime(["2026-12-21", "2026-12-28", "2027-01-04"])})
    fuera = seg.pasos_sin_semana(fc, pd.Timestamp("2026-12-14"), pd.Timestamp("2027-01-04"))
    assert fuera == ["2026-12-28"]


def _fc(filas: list[tuple[int, int, float]], corte: tuple[int, int] = CORTE) -> pd.DataFrame:
    """Pronóstico sintético de la SERIE: (año, semana del boletín, yhat), con su paso."""
    out = []
    for i, (a, s, y) in enumerate(filas, start=1):
        out.append(
            {
                "ds": ds_de_semana_boletin(a, s),
                "yhat": y,
                "meta_padecimiento": "Depresión",
                "meta_entidad": None,  # el nacional viaja sin entidad
                "meta_modo": "general",
                "anio_boletin_corte": corte[0],
                "semana_boletin_corte": corte[1],
                "fase_modelo": "pronostico",
                "adelanto_semanas": i,
            }
        )
    return pd.DataFrame(out)


class _Obs:
    """Observado sintético: {(año, semana): valor}; ausente si no está."""

    def __init__(self, valores: dict[tuple[int, int], float], ultima: tuple[int, int]) -> None:
        self.valores, self.ultima = valores, ultima

    def ultima_semana(self, cohorte: str) -> tuple[int, int]:
        return self.ultima

    def valor(self, fila, anio, semana, ds):  # noqa: ANN001, ANN201
        v = self.valores.get((anio, semana))
        return (v, "") if v is not None else (None, "observación no desagregable")


def _corre(seg: Any, monkeypatch, fc: pd.DataFrame, obs: _Obs) -> pd.DataFrame:  # noqa: ANN001
    monkeypatch.setattr(seg, "asignacion", lambda: [dict(SERIE)])
    monkeypatch.setattr(seg, "Observado", lambda: obs)
    monkeypatch.setattr(seg, "_load_fc", lambda motor: fc)
    monkeypatch.setattr(seg, "_sha", lambda p: "x")
    tabla, resumen = seg.construye(CORTE)
    assert resumen["semanas_evaluadas"] == len(tabla)
    return tabla.set_index("semana_objetivo")


def test_cada_semana_se_empareja_consigo_misma(seg: Any, monkeypatch) -> None:  # noqa: ANN001
    t = _corre(
        seg,
        monkeypatch,
        _fc([(2026, 38, 100.0), (2026, 39, 200.0)]),
        _Obs({(2026, 38): 110, (2026, 39): 190}, (2026, 39)),
    )
    assert t.loc["2026-W38", ["pronostico", "real", "horizonte", "corte"]].tolist() == [
        100,
        110,
        1,
        "2026-W37",
    ]
    assert t.loc["2026-W39", ["pronostico", "real", "horizonte"]].tolist() == [200, 190, 2]
    assert t.loc["2026-W39", "ds_objetivo"] == "2026-09-14"
    assert (t["estado"] == "par").all()


def test_sin_pronostico_de_la_semana_no_se_usa_el_de_la_anterior(seg: Any, monkeypatch) -> None:  # noqa: ANN001
    """El error de la tabla W37: realidad W39 junto al pronóstico W38. Aquí debe quedar ausente."""
    t = _corre(
        seg,
        monkeypatch,
        _fc([(2026, 38, 100.0)]),
        _Obs({(2026, 38): 110, (2026, 39): 190}, (2026, 39)),
    )
    w39 = t.loc["2026-W39"]
    assert w39["estado"] == "ausente" and "sin pronóstico guardado" in w39["motivo"]
    assert pd.isna(w39["pronostico"]) and pd.isna(w39["error_abs"])
    assert w39["real"] == 190  # lo observado se conserva, sin pareja


def test_sin_observacion_el_par_queda_ausente(seg: Any, monkeypatch) -> None:  # noqa: ANN001
    t = _corre(
        seg,
        monkeypatch,
        _fc([(2026, 38, 100.0), (2026, 39, 200.0)]),
        _Obs({(2026, 39): 190}, (2026, 39)),
    )
    assert t.loc["2026-W38", "estado"] == "ausente"
    assert pd.isna(t.loc["2026-W38", "real"]) and t.loc["2026-W38", "pronostico"] == 100


def test_un_pronostico_de_otro_corte_no_entra(seg: Any, monkeypatch) -> None:  # noqa: ANN001
    t = _corre(
        seg,
        monkeypatch,
        _fc([(2026, 38, 100.0), (2026, 39, 200.0)], corte=(2026, 33)),
        _Obs({(2026, 38): 1, (2026, 39): 1}, (2026, 39)),
    )
    assert set(t["motivo"]) == {"pronóstico de otro corte"}


def test_paso_del_modelo_distinto_del_horizonte_no_se_empareja(seg: Any, monkeypatch) -> None:  # noqa: ANN001
    fc = _fc([(2026, 38, 100.0), (2026, 39, 200.0)])
    fc.loc[fc["ds"] == ds_de_semana_boletin(2026, 39), "adelanto_semanas"] = 3
    t = _corre(seg, monkeypatch, fc, _Obs({(2026, 38): 1, (2026, 39): 1}, (2026, 39)))
    assert "paso 3 del pronóstico ≠ horizonte 2" in t.loc["2026-W39", "motivo"]


def test_la_tabla_lleva_ambos_lados_de_la_misma_semana(tmp_path: Path) -> None:
    ruta = tmp_path / "tabla.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "Produccion"
    ws.append(["padecimiento", "entidad", "sexo", "pron_sem_previa", "realidad_sem_previa"])
    ws.append(["Depresion", "Nacional", "general", 999, None])  # 999: el pronóstico de la W38
    ws.append(["Depresion", "Ciudad de México", "mujeres", 999, None])
    ws.append(["Dengue", "Nacional", "general", None, None])
    wb.save(ruta)
    base = {
        "cohorte": "neuro",
        "padecimiento": "Depresion",
        "corte": "2026-W37",
        "semana_objetivo": "2026-W39",
        "horizonte": 2,
    }
    ultima = pd.DataFrame(
        [
            {
                **base,
                "entidad": "Nacional",
                "sexo": "general",
                "pronostico": 3136,
                "real": 3332,
                "estado": "par",
                "motivo": "",
            },
            {
                **base,
                "entidad": "Ciudad de México",
                "sexo": "mujeres",
                "pronostico": 50,
                "real": None,
                "estado": "ausente",
                "motivo": "revisión",
            },
        ]
    )

    ultima["definicion_real"] = [
        "casos de la semana (Casos_semana)",
        "incremento del acumulado por sexo de la entidad",
    ]
    assert gvs._update_excel(ultima, ruta) == 2

    ws = load_workbook(ruta)["Produccion"]
    filas = [[c.value for c in fila] for fila in ws.iter_rows(min_row=1)]
    assert filas[0][-5:] == list(gvs.COLUMNAS_VALIDACION)
    assert filas[1][3:] == [
        3136,
        3332,
        "2026-W39",
        "2026-W37",
        2,
        "par",
        "casos de la semana (Casos_semana)",
    ]
    assert filas[2][3:5] == [None, None]  # ausente: ni el 999 de otra semana ni medio par
    assert filas[2][-2] == "ausente: revisión"
    assert filas[3][3:5] == [None, None] and filas[3][5] is None  # Dengue no está en esta tabla


def test_la_tabla_rechaza_mezclar_semanas(tmp_path: Path) -> None:
    dos = pd.DataFrame({"semana_objetivo": ["2026-W38", "2026-W39"], "cohorte": ["neuro"] * 2})
    with pytest.raises(ValueError, match="UNA semana"):
        gvs._update_excel(dos, tmp_path / "x.xlsx")


# ── el knowledge del EpiBot ────────────────────────────────────────────────────


def _resumen(tmp_path: Path, ultima: str = "2026-W39") -> Path:
    import json

    r = {"semanas_evaluadas": 2, "semanas": [{"etiqueta": "2026-W38"}, {"etiqueta": ultima}]}
    ruta = tmp_path / "seguimiento_post_corte.json"
    ruta.write_text(json.dumps(r), "utf-8")
    return ruta


def test_knowledge_exige_que_tabla_y_resumen_hablen_de_la_misma_semana(tmp_path: Path) -> None:
    from scripts.build_web_knowledge import carga_seguimiento

    ok = [{"semana_validacion": "2026-W39"}] * 3
    assert carga_seguimiento(_resumen(tmp_path), ok)["semanas_evaluadas"] == 2
    with pytest.raises(SystemExit, match="2026-W38"):
        carga_seguimiento(_resumen(tmp_path), [{"semana_validacion": "2026-W38"}])
    with pytest.raises(SystemExit, match="la tabla declara"):
        carga_seguimiento(_resumen(tmp_path), [{"semana_validacion": None}])


def test_tabla_v1_sin_semana_declarada_no_publica_el_par(tmp_path: Path) -> None:
    from types import SimpleNamespace

    from scripts.build_web_knowledge import build_prod_models

    v1 = pd.DataFrame(
        [
            {
                "padecimiento": "Depresion",
                "entidad": "Nacional",
                "sexo": "general",
                "modelo_produccion": "Prophet",
                "pron_sem_previa": 3118,
                "realidad_sem_previa": 3332,
            }
        ]
    )
    fila = build_prod_models(SimpleNamespace(prod_models=v1))[0]
    assert "pron_sem_previa" not in fila and "realidad_sem_previa" not in fila

    v2 = v1.assign(
        semana_validacion="2026-W39", corte_validacion="2026-W37", horizonte_validacion=2
    )
    fila = build_prod_models(SimpleNamespace(prod_models=v2))[0]
    assert (fila["pron_sem_previa"], fila["realidad_sem_previa"]) == (3118, 3332)
    assert (fila["semana_validacion"], fila["horizonte_validacion"]) == ("2026-W39", 2)


# ── ronda W37, decisiones del 14-oct-2026: tabla del EpiBot y nacional por sexo ─────────────


def test_la_semana_previa_cruza_el_anio(seg: Any) -> None:
    assert seg.semana_previa(2026, 1) == (2025, 53)  # 2025 tiene 53 semanas del boletín
    assert seg.semana_previa(2026, 39) == (2026, 38)


def test_cada_valor_observado_lleva_su_definicion(seg: Any) -> None:
    base = {"cohorte": "neuro", "padecimiento": "Parkinson", "motor": "Prophet"}
    assert (
        seg.definicion_real({**base, "entidad": "Nacional", "sexo": "general"}) == seg.DEF_GENERAL
    )
    assert (
        seg.definicion_real({**base, "entidad": "Nacional", "sexo": "hombres"})
        == "incremento neto del acumulado por sexo, sujeto a revisiones"
    )
    assert (
        seg.definicion_real({**base, "entidad": "region_Urbana media", "sexo": "mujeres"})
        == seg.DEF_SEXO_AGREGADO
    )
    assert seg.definicion_real({**base, "entidad": "Jalisco", "sexo": "mujeres"}) == (
        seg.DEF_SEXO_ESTATAL
    )


def _obs_sintetico(seg: Any, filas: list[tuple[str, int, int, int, int, int]]) -> Any:
    """Observado con un boletín neuro de juguete: (entidad, año, semana, casos, ac_h, ac_m)."""
    obs = object.__new__(seg.Observado)
    obs.neuro = pd.DataFrame(
        filas,
        columns=[
            "Entidad",
            "Anio",
            "Semana",
            "Casos_semana",
            "Acumulado_hombres",
            "Acumulado_mujeres",
        ],
    ).assign(Padecimiento="Parkinson")
    obs.dengue = pd.DataFrame()
    obs._cache = {}
    return obs


PARK_H = {
    "cohorte": "neuro",
    "padecimiento": "Parkinson",
    "entidad": "Nacional",
    "sexo": "hombres",
    "motor": "Ensemble",
}


def test_sin_cobertura_en_la_semana_previa_el_incremento_por_sexo_queda_ausente(
    seg: Any, monkeypatch
) -> None:  # noqa: ANN001
    monkeypatch.setattr(seg, "N_ENTIDADES", 2)
    obs = _obs_sintetico(
        seg,
        [
            ("A", 2026, 38, 9, 100, 50),  # en la W38 sólo publicó A
            ("A", 2026, 39, 9, 110, 55),
            ("B", 2026, 39, 9, 300, 70),
        ],
    )
    real, motivo = obs.valor(PARK_H, 2026, 39, ds_de_semana_boletin(2026, 39))
    assert real is None
    assert motivo == "boletín incompleto en la semana previa (1/2 entidades)"


def test_el_nacional_por_sexo_es_el_neto_del_acumulado_y_no_la_suma_recortada(
    seg: Any, monkeypatch
) -> None:  # noqa: ANN001
    """El caso de Parkinson hombres W39: un estado revisa a la baja; el neto lo incluye (85) y la
    suma estatal recortada a cero (87, la página anterior) queda documentada, no publicada."""
    monkeypatch.setattr(seg, "N_ENTIDADES", 2)
    obs = _obs_sintetico(
        seg,
        [
            ("Tamaulipas", 2026, 38, 0, 148, 0),
            ("Resto", 2026, 38, 0, 1000, 0),
            ("Tamaulipas", 2026, 39, 0, 146, 0),  # revisión: −2
            ("Resto", 2026, 39, 0, 1087, 0),  # +87
        ],
    )
    tabla = pd.DataFrame(
        [
            {
                **PARK_H,
                "nivel": "nacional",
                "semana_objetivo": "2026-W39",
                "ds_objetivo": "2026-09-14",
                "real": 85,
                "definicion_real": seg.DEF_SEXO_AGREGADO,
            }
        ]
    )
    (a,) = seg._agregacion_sexo(tabla, obs, [])
    assert (a["neto"], a["real_publicado"], a["suma_estatal_recortada"]) == (85, 85, 87)
    assert a["entidades_con_revision_negativa"] == {"Tamaulipas": -2}
    assert (a["entidades_semana"], a["entidades_semana_previa"]) == (2, 2)
    assert a["semanas_consecutivas"] is True
    assert a["definicion_real"] == "incremento neto del acumulado por sexo, sujeto a revisiones"


def test_un_ausente_conserva_su_motivo_y_el_acumulado_de_la_fuente(seg: Any) -> None:
    obs = _obs_sintetico(
        seg,
        [("Tamaulipas", 2026, 38, 0, 148, 0), ("Tamaulipas", 2026, 39, 0, 146, 0)],
    )
    tabla = pd.DataFrame(
        [
            {
                **PARK_H,
                "entidad": "Tamaulipas",
                "nivel": "estatal",
                "semana_objetivo": "2026-W39",
                "ds_objetivo": "2026-09-14",
                "horizonte": 2,
                "pronostico": 5,
                "real": None,
                "estado": "ausente",
                "motivo": "revisión negativa del acumulado por sexo (148 → 146)",
            }
        ]
    )
    (a,) = seg._ausentes(tabla, obs, [])
    assert a["real"] is None and a["pronostico"] == 5  # ausente: nunca cero
    assert (a["acumulado_semana_previa"], a["acumulado_semana"]) == (148, 146)
    assert a["motivo"].startswith("revisión negativa")


class _ObsGeneral:
    def general_semana(self, fila, anio, semana):  # noqa: ANN001, ANN201
        return 1000 + semana, ""


def test_la_tabla_semanal_no_publica_el_ajuste_dentro_de_muestra(seg: Any, monkeypatch) -> None:  # noqa: ANN001
    """Antes del corte sólo lo observado; los pares del seguimiento salen de la tabla; después,
    el pronóstico guardado con su horizonte; cada semana con el periodo oficial del boletín."""
    serie = {**SERIE, "motor": "Prophet"}
    monkeypatch.setattr(seg, "asignacion", lambda: [serie])
    fc = _fc([(2026, s, 100.0 + s) for s in range(38, 53)])
    monkeypatch.setattr(seg, "_load_fc", lambda motor: fc)
    tabla = pd.DataFrame(
        [
            {
                **SERIE,
                "nivel": "nacional",
                "corte": "2026-W37",
                "semana_objetivo": f"2026-W{s}",
                "horizonte": s - 37,
                "pronostico": 100 + s,
                "real": 1000 + s if s == 38 else None,
                "estado": "par" if s == 38 else "ausente",
                "motivo": "" if s == 38 else "revisión",
                "error_abs": 862 if s == 38 else None,
            }
            for s in (38, 39)
        ]
    )
    out = seg.semanal_nacional(tabla, _ObsGeneral(), CORTE, (2026, 39))
    info = out["Depresion"]
    assert info["titulo"] == "Seguimiento del pronóstico con corte W37"
    sem = {w["semana"]: w for w in info["semanas"]}
    assert len(sem) == 52 and sem[1]["fase"] == "observado"
    assert sem[37] == {
        "anio": 2026,
        "semana": 37,
        "etiqueta": "2026-W37",
        "periodo_inicio": "2026-09-13",
        "periodo_fin": "2026-09-19",
        "fase": "observado",
        "real": 1037,
    }  # ni pronóstico ni motores: el ajuste dentro de muestra no viaja
    assert sem[38]["fase"] == "seguimiento" and sem[38]["periodo_inicio"] == "2026-09-20"
    assert (sem[38]["pronostico"], sem[38]["real"], sem[38]["diferencia"]) == (138, 1038, -900)
    assert sem[39]["estado"] == "ausente" and sem[39]["real"] is None  # ausente, no cero
    assert "diferencia" not in sem[39] and "error_abs" not in sem[39]
    assert (sem[40]["fase"], sem[40]["horizonte"], sem[40]["pronostico"]) == ("pronostico", 3, 140)
    assert all("fecha" not in w and "error_pct" not in w for w in info["semanas"])
    assert info["semanas_seguimiento"] == 2 and info["semanas_pronostico"] == 13


def test_una_revision_negativa_queda_ausente_con_el_acumulado_en_el_motivo(
    seg: Any, monkeypatch
) -> None:  # noqa: ANN001
    obs = _obs_sintetico(
        seg, [("Tamaulipas", 2026, 38, 0, 148, 0), ("Tamaulipas", 2026, 39, 0, 146, 0)]
    )
    monkeypatch.setattr(obs, "serie", lambda fila: pd.DataFrame({"ds": [], "y": []}))
    fila = {**PARK_H, "entidad": "Tamaulipas"}
    real, motivo = obs.valor(fila, 2026, 39, ds_de_semana_boletin(2026, 39))
    assert real is None
    assert motivo.startswith("revisión negativa del acumulado por sexo (148 → 146)")


# ── consumidores: knowledge, zoom del EpiBot y página de validación ───────────────────────────


def _resumen_v2() -> dict[str, Any]:
    return {
        "corte": {"etiqueta": "2026-W37"},
        "ultima_semana_observada": {"etiqueta": "2026-W39"},
        "semanas": [
            {
                "etiqueta": "2026-W38",
                "cohortes": {
                    "neuro": {
                        "nacional": [
                            {
                                "padecimiento": "Depresion",
                                "sexo": "general",
                                "pronostico": 3118,
                                "real": 2748,
                            }
                        ]
                    }
                },
            }
        ],
    }


def _semanal_v2(**cambio: Any) -> dict[str, Any]:
    w38 = {
        "etiqueta": "2026-W38",
        "fase": "seguimiento",
        "estado": "par",
        "pronostico": 3118,
        "real": 2748,
    }
    w37 = {"etiqueta": "2026-W37", "fase": "observado", "real": 3181}
    w37.update(cambio)
    return {
        "Depresion": {
            "corte": "2026-W37",
            "ultima_semana_observada": "2026-W39",
            "semanas": [w37, w38],
        }
    }


def test_el_knowledge_rechaza_el_ajuste_dentro_de_muestra_y_pares_ajenos(tmp_path: Path) -> None:
    import json

    from scripts.build_web_knowledge import carga_semanal

    ruta = tmp_path / "seguimiento_semanal_nacional.json"
    ruta.write_text(json.dumps(_semanal_v2()), "utf-8")
    assert carga_semanal(ruta, _resumen_v2())["Depresion"]["corte"] == "2026-W37"
    for cambio, msg in (
        ({"pronostico": 3175}, "ajuste dentro de muestra"),
        ({"fecha": "2026-08-31"}, "tabla anterior"),
    ):
        ruta.write_text(json.dumps(_semanal_v2(**cambio)), "utf-8")
        with pytest.raises(SystemExit, match=msg):
            carga_semanal(ruta, _resumen_v2())
    otro = _semanal_v2()
    otro["Depresion"]["semanas"][1]["pronostico"] = 3136  # el de la W39
    ruta.write_text(json.dumps(otro), "utf-8")
    with pytest.raises(SystemExit, match="no es el par del seguimiento"):
        carga_semanal(ruta, _resumen_v2())
    with pytest.raises(SystemExit, match="falta"):
        carga_semanal(tmp_path / "no.json", _resumen_v2())


def test_el_zoom_del_epibot_lleva_los_pares_y_falla_si_falta_uno(
    tmp_path: Path, monkeypatch
) -> None:  # noqa: ANN001
    import json

    from scripts import build_epibot_zoom as z

    reports, out = tmp_path / "Reports", tmp_path / "epibot"
    reports.mkdir()
    out.mkdir()
    clave = "Parkinson/Nacional/Parkinson_Nacional_hombres.png"
    (reports / "zoom_data_neuro.json").write_text(
        json.dumps({clave: {"motor": "Ensemble", "d": ["2026-09-07"], "r": [92], "y": [86]}}),
        "utf-8",
    )
    csv = tmp_path / "seguimiento_post_corte.csv"
    cols = "cohorte,padecimiento,entidad,sexo,semana_objetivo,inicio_semana,fin_semana,corte,horizonte,pronostico,real,error_abs,estado,motivo,definicion_real"
    # La definición lleva coma: se escribe con pandas, que la entrecomilla como el CSV real.
    pd.DataFrame(
        [
            dict(
                zip(
                    cols.split(","),
                    [
                        "neuro",
                        "Parkinson",
                        "Nacional",
                        "hombres",
                        "2026-W38",
                        "2026-09-20",
                        "2026-09-26",
                        "2026-W37",
                        1,
                        86,
                        92,
                        6,
                        "par",
                        "",
                        "incremento neto del acumulado por sexo, sujeto a revisiones",
                    ],
                    strict=True,
                )
            )
        ]
    ).to_csv(csv, index=False)
    monkeypatch.setattr(
        sys, "argv", ["z", "--reports", str(reports), "--out", str(out), "--seguimiento", str(csv)]
    )
    assert z.main() == 0
    serie = json.loads((out / "zoom_series.json").read_text("utf-8"))["parkinson|nacional|hombres"]
    assert serie["ds_corte"] == "2026-08-31" and serie["corte"] == "2026-W37"
    assert serie["definicion_real"].startswith("incremento neto del acumulado por sexo")
    assert serie["seguimiento"] == [
        {
            "etiqueta": "2026-W38",
            "periodo_inicio": "2026-09-20",
            "periodo_fin": "2026-09-26",
            "corte": "2026-W37",
            "estado": "par",
            "motivo": "",
            "horizonte": 1,
            "pronostico": 86,
            "real": 92,
            "error_abs": 6,
        }
    ]
    (reports / "zoom_data_neuro.json").write_text(
        json.dumps({clave.replace("hombres", "mujeres"): {"motor": "Prophet"}}), "utf-8"
    )
    with pytest.raises(SystemExit, match="no tiene seguimiento"):
        z.main()


def test_la_pagina_no_califica_ni_convierte_ausentes_en_cero() -> None:
    base = {
        "cohorte": "neuro",
        "padecimiento": "Parkinson",
        "corte": "2026-W37",
        "semana_objetivo": "2026-W39",
        "horizonte": 2,
        "motor": "Ensemble",
    }
    seg_df = pd.DataFrame(
        [
            {
                **base,
                "entidad": "Nacional",
                "nivel": "nacional",
                "sexo": "hombres",
                "pronostico": 88,
                "real": 85,
                "estado": "par",
                "motivo": "",
                "definicion_real": "x",
            },
            {
                **base,
                "entidad": "Tamaulipas",
                "nivel": "estatal",
                "sexo": "general",
                "pronostico": 5,
                "real": None,
                "estado": "ausente",
                "motivo": "revisión negativa",
                "definicion_real": "x",
            },
            {
                **base,
                "entidad": "Jalisco",
                "nivel": "estatal",
                "sexo": "general",
                "pronostico": 9,
                "real": 7,
                "estado": "par",
                "motivo": "",
                "definicion_real": "x",
            },
        ]
    )
    resumen = {
        "ausentes": [
            {
                "semana_objetivo": "2026-W39",
                "horizonte": 2,
                "padecimiento": "Parkinson",
                "entidad": "Tamaulipas",
                "sexo": "hombres",
                "motor": "Stacking",
                "pronostico": 5,
                "motivo": "revisión negativa del acumulado por sexo (148 → 146)",
                "acumulado_semana_previa": 148,
                "acumulado_semana": 146,
            }
        ],
        "agregacion_sexo": [
            {
                "semana_objetivo": "2026-W39",
                "padecimiento": "Parkinson",
                "sexo": "hombres",
                "neto": 85,
                "real_publicado": 85,
                "suma_estatal_recortada": 87,
                "entidades_con_revision_negativa": {"Tamaulipas": -2},
                "entidades_semana": 32,
                "entidades_semana_previa": 32,
                "semanas_consecutivas": True,
            }
        ],
    }
    html = gvs._generate_html(seg_df, CORTE, resumen)
    for calificacion in ("EXCELENTE", "BUENO", "REGULAR", "FALLO", "Semaforo", "SMAPE", "N/A"):
        assert calificacion not in html
    assert "incremento neto del acumulado por sexo, sujeto a revisiones" in html
    assert "Pares ausentes y sus motivos" in html and "148 &rarr; 146" in html
    assert "Parkinson (G20) hombres semana 39: 85 (con la definicion anterior, 87)" in html
    # El ausente no entra en la suma de las entidades: 1 par (Jalisco), observado 7.
    assert "1 entidades con par: observado 7 / pronostico 9; 1 ausente(s) fuera de la suma" in html


# ── indicador «Notificaciones previstas · agregado estatal neuro» (14-oct-2026) ────────────────


def _agregado(seg: Any, monkeypatch, cambia=None):  # noqa: ANN001, ANN202
    """3 padecimientos × 2 estados × 3 sexos (N_ENTIDADES=2), 52 pasos de 0.3 por serie, más un
    nacional y una región que NO deben entrar, y filas de otro corte que tampoco."""
    monkeypatch.setattr(seg, "N_ENTIDADES", 2)
    filas, fc = [], []
    for pad in ("Alzheimer", "Depresion", "Parkinson"):
        for ent in ("Jalisco", "Nacional", "region_Urbana media", "Puebla"):
            for sexo in ("general", "hombres", "mujeres"):
                filas.append(
                    {
                        "cohorte": "neuro",
                        "padecimiento": pad,
                        "entidad": ent,
                        "sexo": sexo,
                        "motor": "Prophet",
                    }
                )
                for paso in range(1, 53):
                    base = {
                        "meta_padecimiento": seg.NEURO[pad],
                        "meta_entidad": None
                        if ent == "Nacional"
                        else seg._entidad_forecast({"cohorte": "neuro", "entidad": ent}),
                        "meta_modo": sexo,
                        "ds": pd.Timestamp("2026-09-07") + pd.Timedelta(weeks=paso - 1),
                        "fase_modelo": "pronostico",
                        "adelanto_semanas": paso,
                    }
                    fc.append(
                        {
                            **base,
                            "yhat": 0.3,
                            "anio_boletin_corte": 2026,
                            "semana_boletin_corte": 37,
                        }
                    )
                    fc.append(
                        {
                            **base,
                            "yhat": 999.0,
                            "anio_boletin_corte": 2026,
                            "semana_boletin_corte": 33,
                        }
                    )
    df = pd.DataFrame(fc)
    if cambia is not None:
        df = cambia(df)
    monkeypatch.setattr(seg, "asignacion", lambda: filas)
    monkeypatch.setattr(seg, "_load_fc", lambda motor: df)
    monkeypatch.setattr(seg, "_sha", lambda p: "x")
    return seg.agregado_estatal_neuro(CORTE)


def test_el_agregado_suma_los_yhat_originales_y_redondea_una_vez(seg: Any, monkeypatch) -> None:  # noqa: ANN001
    ag = _agregado(seg, monkeypatch)
    # 6 series estatales (2 estados × 3) × 52 pasos × 0.3 = 93.6 → 94; redondear cada serie
    # (15.6 → 16) y sumar daría 96. El nacional, la región y el corte W33 no entran.
    assert (ag["series_incluidas"], ag["valores"]) == (6, 312)
    assert ag["suma_original"] == pytest.approx(93.6)
    assert ag["valor_mostrado"] == 94
    assert ag["por_sexo"]["general"]["suma_de_totales_redondeados_por_serie"] == 96
    assert {s["entidad"] for s in ag["por_sexo"]["general"]["series_incluidas"]} == {
        "Jalisco",
        "Puebla",
    }
    assert ag["rotulo"] == "Notificaciones previstas · agregado estatal neuro"
    assert ag["corte"] == "2026-W37" and ag["horizonte"]["pasos"] == 52
    assert ag["horizonte"]["ds_primero"] == "2026-09-07"
    assert ag["por_sexo"]["general"]["por_padecimiento"]["Depresion"]["series"] == 2


def test_una_serie_ausente_no_vale_cero(seg: Any, monkeypatch) -> None:  # noqa: ANN001
    def sin_puebla(df: pd.DataFrame) -> pd.DataFrame:
        return df[~((df["meta_entidad"] == "Puebla") & (df["meta_padecimiento"] == "Parkinson"))]

    with pytest.raises(SystemExit, match="pasos"):
        _agregado(seg, monkeypatch, sin_puebla)


def test_un_horizonte_incompleto_o_un_valor_invalido_aborta(seg: Any, monkeypatch) -> None:  # noqa: ANN001
    def corto(df: pd.DataFrame) -> pd.DataFrame:
        return df[df["adelanto_semanas"] <= 51]

    with pytest.raises(SystemExit, match="no 1..52"):
        _agregado(seg, monkeypatch, corto)

    def nan(df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df.loc[(df["meta_entidad"] == "Jalisco") & (df["adelanto_semanas"] == 7), "yhat"] = float(
            "nan"
        )
        return df

    with pytest.raises(SystemExit, match="no finitos o negativos"):
        _agregado(seg, monkeypatch, nan)


def test_el_knowledge_toma_el_agregado_y_rechaza_otro_denominador(tmp_path: Path) -> None:
    import json

    from scripts.build_web_knowledge import aplica_agregado, carga_agregado

    pp = {
        p: {"series": 32, "suma_original": v, "valor_mostrado": round(v)}
        for p, v in (("Alzheimer", 1899.4), ("Depresion", 161887.1), ("Parkinson", 7737.54))
    }
    ag = {
        "corte": "2026-W37",
        "series_incluidas": 96,
        "valores": 4992,
        "suma_original": 171524.0401,
        "valor_mostrado": 171524,
        "por_sexo": {"general": {"por_padecimiento": pp}, "hombres": {"por_padecimiento": pp}},
    }
    ruta = tmp_path / "agregado_estatal_neuro.json"
    ruta.write_text(json.dumps(ag), "utf-8")
    resumen = {"corte": {"etiqueta": "2026-W37"}}
    assert carga_agregado(ruta, resumen)["valor_mostrado"] == 171524
    stats = {
        "pronostico_total": 171525,
        "por_pad": {
            "Depresion": {
                "casos_futuro_total": 161888,
                "por_sexo": {"hombres": {"n": 37, "casos_total": 127000}},
            }
        },
    }
    aplica_agregado(stats, carga_agregado(ruta, resumen))
    assert stats["pronostico_total"] == 171524
    assert stats["por_pad"]["Depresion"]["casos_futuro_total"] == 161887
    assert (
        stats["por_pad"]["Depresion"]["por_sexo"]["hombres"]["casos_total"] == 161887
    )  # 32 estados, no 37 geografías
    assert stats["por_pad"]["Depresion"]["por_sexo"]["hombres"]["n_estados"] == 32
    for cambio, msg in (
        ({"valor_mostrado": 171525}, "redondeada una vez"),
        ({"series_incluidas": 95}, "95 series"),
        ({"corte": "2026-W33"}, "corte"),
    ):
        ruta.write_text(json.dumps({**ag, **cambio}), "utf-8")
        with pytest.raises(SystemExit, match=msg):
            carga_agregado(ruta, resumen)

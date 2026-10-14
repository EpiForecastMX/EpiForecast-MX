"""Seguimiento diagnóstico posterior al corte: pronóstico guardado contra lo observado, misma semana.

Versión 2 de los campos de validación (ronda con corte de modelos W37). La versión 1 eran las
columnas ``pron_sem_previa``/``realidad_sem_previa`` de la tabla de producción, que en W37
quedaron de semanas distintas (pronóstico de la W38, realidad de la W39): no se comparaban.

Para cada serie de la ASIGNACIÓN CONGELADA (neuro: tabla de producción; Dengue:
``produccion_dengue.csv``) y para cada semana del boletín posterior al corte que ya tenga
observación, se empareja por ``(padecimiento, entidad, sexo, semana del boletín, ds)``:

* el pronóstico GUARDADO por el motor asignado, en el ``ds`` legado de esa semana, que debe ser
  una fila ``fase_modelo == "pronostico"`` emitida desde el corte (``anio/semana_boletin_corte``);
* lo observado esa misma semana, con la regla de la galería: general = ``Casos_semana``; hombres y
  mujeres = incremento del acumulado por sexo sólo entre semanas consecutivas del boletín; nacional
  y regiones = suma de sus entidades, exigiendo que todas hayan publicado ESA semana y, para el
  incremento por sexo, también la semana previa.

Nacional y regiones por sexo (decisión del autor, 14-oct-2026): es la diferencia del acumulado
AGREGADO entre semanas consecutivas, incluidas las revisiones negativas que publiquen los estados.
Se rotula «incremento neto del acumulado por sexo, sujeto a revisiones»: no es un número demostrado
de casos nuevos. No se reconstruye sumando incrementos estatales recortados a cero (la página del
candidato anterior lo hacía: Parkinson hombres W39 daba 87; la diferencia del acumulado da 85).
Los ausentes estatales y sus motivos se conservan aparte. ``Casos_semana`` (general) es otra
cantidad y no se fuerza a coincidir con hombres + mujeres.

Nunca se desplaza un valor ni se empareja el pronóstico de una semana con la realidad de otra. Si
falta cualquiera de los dos lados, el par se declara AUSENTE con su motivo. El paso del horizonte
cuyo ``ds`` no tiene semana del boletín (2026-12-28) no es una semana objetivo: queda fuera y se
declara. La semana 1 del boletín tampoco es evaluable (colisión del calendario legado).

Rótulo: seguimiento diagnóstico posterior al corte, con el número de semanas evaluadas. No es una
evaluación independiente ni sustituye la del artículo.

Salidas (en ``--out``):
  * ``seguimiento_post_corte.csv``  una fila por (serie, semana objetivo), pares y ausentes
  * ``seguimiento_post_corte.json`` resumen por semana y cohorte, definiciones, ausentes y la
    agregación nacional por sexo (neto frente a la suma estatal recortada)
  * ``agregado_estatal_neuro.json`` el indicador «Notificaciones previstas · agregado estatal neuro»:
    suma de los ``yhat`` ORIGINALES de las 96 series de los 32 estados (Alzheimer, Depresión y
    Parkinson, modo general; motor asignado), 52 pasos desde el corte, redondeada UNA vez. Lleva
    procedencia, corte, horizonte, series incluidas y suma original, y el mismo cálculo por sexo
    (32 estados). No sustituye a los modelos nacionales, que conservan su pronóstico propio.
  * ``seguimiento_semanal_nacional.json`` la tabla semanal del EpiBot (nacional, general) por
    padecimiento: fase observado (hasta el corte, sólo lo observado), seguimiento (pares
    posteriores al corte) y pronóstico (semanas aún sin dato), con el periodo oficial del boletín

Uso:
    python scripts/genera_seguimiento_post_corte.py --out reports/ProdDetails
"""

from __future__ import annotations

import argparse
from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
import hashlib
import json
import math
from pathlib import Path
import sys
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.build_dengue_gallery import (  # noqa: E402
    PROD,
    _boletin_neuro,
    _load_fc,
    _real_general,
    _real_sexo_dengue,
    _region_members,
    boletin_real,
)

from epiforecast.constants import ENTIDAD_DISPLAY  # noqa: E402
from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402
from epiforecast.utils.config import conf  # noqa: E402
from epiforecast.utils.semana_epi import (  # noqa: E402
    DsSinSemanaBoletinError,
    SemanaUnoLegacyError,
    ds_de_semana_boletin,
    fin_semana_boletin,
    inicio_semana_boletin,
    semana_boletin_de_ds,
    semanas_del_anio_boletin,
)

VERSION = 2
ROTULO = "seguimiento diagnóstico posterior al corte; no evaluación independiente"
ROTULO_SEMANAL = (
    "comparaciones sólo en las semanas posteriores al corte (seguimiento diagnóstico, no desempeño "
    "general del modelo); antes del corte se muestra únicamente lo observado: el ajuste dentro de "
    "muestra no se presenta como validación"
)
DEF_GENERAL = "casos de la semana (Casos_semana)"
DEF_SEXO_AGREGADO = "incremento neto del acumulado por sexo, sujeto a revisiones"
DEF_SEXO_ESTATAL = "incremento del acumulado por sexo de la entidad"
MOTORES_NEURO = ("Prophet", "DeepAR", "Ensemble", "Stacking")
COL_ACUM = {"hombres": "Acumulado_hombres", "mujeres": "Acumulado_mujeres"}
TABLA = Path(conf["paths"]["reports"]) / "ProdDetails" / "tabla_333_modelos_produccion.xlsx"
NEURO = {"Depresion": "Depresión", "Parkinson": "Parkinson", "Alzheimer": "Alzheimer"}
SEXOS = ("general", "hombres", "mujeres")
N_ENTIDADES = 32
COLUMNAS = [
    "cohorte",
    "padecimiento",
    "entidad",
    "sexo",
    "nivel",
    "motor",
    "corte",
    "semana_objetivo",
    "ds_objetivo",
    "inicio_semana",
    "fin_semana",
    "horizonte",
    "yhat",
    "pronostico",
    "real",
    "error_abs",
    "estado",
    "motivo",
    "definicion_real",
]


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _etiqueta(anio: int, semana: int) -> str:
    return f"{anio}-W{semana:02d}"


def siguiente_semana(anio: int, semana: int) -> tuple[int, int]:
    """La semana del boletín que sigue, incluido el paso de la 52/53 a la 1."""
    if semana >= semanas_del_anio_boletin(anio):
        return anio + 1, 1
    return anio, semana + 1


def semana_previa(anio: int, semana: int) -> tuple[int, int]:
    """La semana del boletín anterior, incluido el paso de la 1 a la 52/53 del año previo."""
    if semana <= 1:
        return anio - 1, semanas_del_anio_boletin(anio - 1)
    return anio, semana - 1


def definicion_real(fila: dict[str, str]) -> str:
    """Qué cantidad es «lo observado» de la serie (rótulo que viaja con cada valor)."""
    if fila["sexo"] == "general":
        return DEF_GENERAL
    return DEF_SEXO_ESTATAL if _nivel(fila["entidad"]) == "estatal" else DEF_SEXO_AGREGADO


def semanas_objetivo(corte: tuple[int, int], ultima: tuple[int, int]) -> list[tuple[int, int]]:
    """Semanas del boletín estrictamente posteriores al corte y hasta la última observada."""
    out: list[tuple[int, int]] = []
    s = siguiente_semana(*corte)
    while s <= ultima:
        out.append(s)
        s = siguiente_semana(*s)
    return out


def pasos_sin_semana(
    fc: pd.DataFrame, ds_corte: pd.Timestamp, ds_ultima: pd.Timestamp
) -> list[str]:
    """``ds`` del pronóstico entre el corte y la última semana observada sin semana del boletín."""
    ds = sorted(set(fc.loc[(fc["ds"] > ds_corte) & (fc["ds"] <= ds_ultima), "ds"]))
    fuera = []
    for d in ds:
        try:
            semana_boletin_de_ds(d)
        except DsSinSemanaBoletinError:
            fuera.append(pd.Timestamp(d).date().isoformat())
    return fuera


# --- asignación congelada -------------------------------------------------------------------


def asignacion() -> list[dict[str, str]]:
    """Las 432 series con su motor: 333 neuro de la tabla y 99 Dengue de produccion_dengue.csv."""
    tabla = pd.read_excel(TABLA, sheet_name="Produccion")
    filas: list[dict[str, str]] = []
    for r in tabla[tabla["padecimiento"].isin(NEURO)].itertuples(index=False):
        filas.append(
            {
                "cohorte": "neuro",
                "padecimiento": str(r.padecimiento),
                "entidad": str(r.entidad),
                "sexo": str(r.sexo),
                "motor": str(r.modelo_produccion),
            }
        )
    for r in pd.read_csv(PROD).itertuples(index=False):
        filas.append(
            {
                "cohorte": "dengue",
                "padecimiento": "Dengue",
                "entidad": str(r.entidad),
                "sexo": str(r.sexo),
                "motor": str(r.motor_productivo),
            }
        )
    claves = [(f["padecimiento"], f["entidad"], f["sexo"]) for f in filas]
    if len(set(claves)) != len(claves):
        raise ValueError("la asignación repite una serie")
    return filas


def _nivel(entidad: str) -> str:
    if entidad == "Nacional":
        return "nacional"
    return "regional" if entidad.lower().startswith("region") else "estatal"


def _entidad_forecast(fila: dict[str, str]) -> str:
    """``meta_entidad`` del pronóstico: la tabla escribe ``region_X`` y el pronóstico ``Region X``."""
    e = fila["entidad"]
    if fila["cohorte"] == "neuro" and e.startswith("region_"):
        return "Region " + e[len("region_") :]
    return e


# --- observado --------------------------------------------------------------------------------


class Observado:
    """Lo observado por semana del boletín, con la misma regla que la galería."""

    def __init__(self) -> None:
        self.neuro = _boletin_neuro()
        bol = cargar_boletin_dengue()
        bol["Entidad"] = bol["Entidad"].replace(ENTIDAD_DISPLAY)
        self.dengue = bol
        self._cache: dict[tuple[str, str, str], pd.DataFrame] = {}

    def ultima_semana(self, cohorte: str) -> tuple[int, int]:
        """La última semana en la que TODOS los padecimientos de la cohorte tienen 32 entidades."""
        df = self.dengue if cohorte == "dengue" else self.neuro
        if cohorte == "neuro":
            df = df[df["Padecimiento"].isin(NEURO.values())]
        n = df.groupby(["Padecimiento", "Anio", "Semana"])["Entidad"].nunique().reset_index()
        completas = n[n["Entidad"] >= N_ENTIDADES]
        por_pad: list[tuple[int, int]] = []
        for _, g in completas.groupby("Padecimiento"):
            semanas = zip(g["Anio"].to_numpy(), g["Semana"].to_numpy(), strict=True)
            por_pad.append(max((int(a), int(s)) for a, s in semanas))
        return min(por_pad)

    def _miembros(self, fila: dict[str, str]) -> tuple[pd.DataFrame, int]:
        """Filas del boletín de la serie y cuántas entidades deben haber publicado."""
        if fila["cohorte"] == "dengue":
            ent = fila["entidad"]
            if ent == "Nacional":
                return self.dengue, N_ENTIDADES
            return self.dengue[self.dengue["Entidad"] == ENTIDAD_DISPLAY.get(ent, ent)], 1
        df = self.neuro[self.neuro["Padecimiento"] == NEURO[fila["padecimiento"]]]
        e = _entidad_forecast(fila)
        if e == "Nacional":
            return df, N_ENTIDADES
        if e.startswith("Region "):
            miembros = _region_members(e[len("Region ") :])
            return df[df["Entidad"].isin(miembros)], len(miembros)
        return df[df["Entidad"] == e], 1

    def serie(self, fila: dict[str, str]) -> pd.DataFrame:
        clave = (fila["padecimiento"], fila["entidad"], fila["sexo"])
        if clave not in self._cache:
            if fila["cohorte"] == "dengue":
                sub, _ = self._miembros(fila)
                real = (
                    _real_general(sub)
                    if fila["sexo"] == "general"
                    else _real_sexo_dengue(sub, fila["sexo"])
                )
            else:
                e = _entidad_forecast(fila)
                region = e[len("Region ") :] if e.startswith("Region ") else None
                real = boletin_real(NEURO[fila["padecimiento"]], e, fila["sexo"], region)
            self._cache[clave] = real
        return self._cache[clave]

    def valor(
        self, fila: dict[str, str], anio: int, semana: int, ds: pd.Timestamp
    ) -> tuple[float | None, str]:
        """(valor observado, motivo si falta) de la serie en esa semana del boletín."""
        sub, esperadas = self._miembros(fila)
        publicaron = sub[(sub["Anio"] == anio) & (sub["Semana"] == semana)]["Entidad"].nunique()
        if publicaron < esperadas:
            return None, f"boletín incompleto ({publicaron}/{esperadas} entidades)"
        if fila["sexo"] != "general":
            # El incremento por sexo resta el acumulado de la semana previa: si en ella faltó una
            # entidad, la diferencia le atribuiría a esta semana todo su acumulado.
            pa, ps = semana_previa(anio, semana)
            previa = sub[(sub["Anio"] == pa) & (sub["Semana"] == ps)]["Entidad"].nunique()
            if previa < esperadas:
                return (
                    None,
                    f"boletín incompleto en la semana previa ({previa}/{esperadas} entidades)",
                )
        real = self.serie(fila)
        v = real.loc[pd.to_datetime(real["ds"]) == ds, "y"]
        if v.empty:
            if fila["sexo"] != "general":
                antes, _ = self.acumulado(fila, *semana_previa(anio, semana))
                ahora, _ = self.acumulado(fila, anio, semana)
                if antes is not None and ahora is not None and ahora < antes:
                    return None, (
                        f"revisión negativa del acumulado por sexo ({int(antes)} → {int(ahora)}): "
                        "no es la observación de una semana"
                    )
            return None, "observación no desagregable (sin semana previa consecutiva o revisión)"
        if len(v) > 1:
            return None, "observación duplicada en el ds"
        return float(v.iloc[0]), ""

    def general_semana(
        self, fila: dict[str, str], anio: int, semana: int
    ) -> tuple[int | None, str]:
        """``Casos_semana`` agregado de la serie en una semana del boletín (sin pasar por el ds)."""
        sub, esperadas = self._miembros(fila)
        s = sub[(sub["Anio"] == anio) & (sub["Semana"] == semana)]
        if s["Entidad"].nunique() < esperadas:
            return None, f"boletín incompleto ({s['Entidad'].nunique()}/{esperadas} entidades)"
        v = s["Casos_semana"].sum(min_count=1)
        return (None, "sin Casos_semana") if pd.isna(v) else (int(v), "")

    def acumulado(self, fila: dict[str, str], anio: int, semana: int) -> tuple[float | None, int]:
        """Acumulado por sexo de la serie (suma de sus entidades) y cuántas entidades publicaron."""
        sub, _ = self._miembros(fila)
        s = sub[(sub["Anio"] == anio) & (sub["Semana"] == semana)]
        v = s[COL_ACUM[fila["sexo"]]].sum(min_count=1)
        return (None if pd.isna(v) else float(v)), int(s["Entidad"].nunique())

    def por_entidad(self, fila: dict[str, str], anio: int, semana: int) -> pd.Series:
        """Incremento del acumulado por sexo de cada entidad de la serie (NaN si falta un lado)."""
        sub, _ = self._miembros(fila)
        col = COL_ACUM[fila["sexo"]]
        pa, ps = semana_previa(anio, semana)
        ahora = (
            sub[(sub["Anio"] == anio) & (sub["Semana"] == semana)].groupby("Entidad")[col].sum()
        )
        antes = sub[(sub["Anio"] == pa) & (sub["Semana"] == ps)].groupby("Entidad")[col].sum()
        return ahora.sub(antes)


# --- pronóstico ------------------------------------------------------------------------------


def pronostico(
    fila: dict[str, str], ds: pd.Timestamp, corte: tuple[int, int]
) -> tuple[float | None, int | None, str]:
    """(yhat, paso del pronóstico, motivo si falta) del motor asignado en ese ``ds``."""
    fc = _load_fc(fila["motor"])
    if fc.empty:
        return None, None, f"sin archivo de pronóstico de {fila['motor']}"
    pad = NEURO.get(fila["padecimiento"], fila["padecimiento"])
    d = fc[
        (fc["meta_padecimiento"] == pad)
        & (fc["meta_entidad"].fillna("Nacional") == _entidad_forecast(fila))
        & (fc["meta_modo"] == fila["sexo"])
        & (fc["ds"] == ds)
    ]
    if d.empty:
        return None, None, "sin pronóstico guardado en el ds"
    if len(d) > 1:
        return None, None, "pronóstico duplicado en el ds"
    r = d.iloc[0]
    if (int(r["anio_boletin_corte"]), int(r["semana_boletin_corte"])) != corte:
        return None, None, "pronóstico de otro corte"
    if str(r.get("fase_modelo", "pronostico")) != "pronostico":
        return None, None, "fila de ajuste, no de pronóstico"
    yhat = float(r["yhat"])
    if not math.isfinite(yhat):
        return None, None, "pronóstico no finito"
    paso = r.get("adelanto_semanas")
    return yhat, (int(paso) if pd.notna(paso) else None), ""


# --- construcción ------------------------------------------------------------------------------


def construye(
    corte: tuple[int, int], obs: Observado | None = None
) -> tuple[pd.DataFrame, dict[str, Any]]:
    obs = Observado() if obs is None else obs
    filas = asignacion()
    ultima = min(obs.ultima_semana("neuro"), obs.ultima_semana("dengue"))
    objetivos = semanas_objetivo(corte, ultima)
    ds_corte = ds_de_semana_boletin(*corte)

    registros: list[dict[str, Any]] = []
    for h, (anio, semana) in enumerate(objetivos, start=1):
        base = {
            "corte": _etiqueta(*corte),
            "semana_objetivo": _etiqueta(anio, semana),
            "inicio_semana": inicio_semana_boletin(anio, semana).isoformat(),
            "fin_semana": fin_semana_boletin(anio, semana).isoformat(),
            "horizonte": h,
        }
        try:
            ds = ds_de_semana_boletin(anio, semana)
        except SemanaUnoLegacyError:
            for f in filas:
                registros.append(
                    {
                        **f,
                        **base,
                        "nivel": _nivel(f["entidad"]),
                        "ds_objetivo": None,
                        "estado": "ausente",
                        "motivo": "semana 1 del boletín: no evaluable",
                        "definicion_real": definicion_real(f),
                    }
                )
            continue
        for f in filas:
            reg: dict[str, Any] = {
                **f,
                **base,
                "nivel": _nivel(f["entidad"]),
                "ds_objetivo": ds.date().isoformat(),
                "definicion_real": definicion_real(f),
            }
            yhat, paso, motivo_fc = pronostico(f, ds, corte)
            real, motivo_obs = obs.valor(f, anio, semana, ds)
            if paso is not None and paso != h:
                # El paso del modelo y la distancia en semanas del boletín sólo difieren si entre
                # el corte y la semana objetivo hubo un ds sin semana: entonces no es la misma.
                yhat, motivo_fc = None, f"paso {paso} del pronóstico ≠ horizonte {h} del boletín"
            motivos = [m for m in (motivo_fc, motivo_obs) if m]
            reg["yhat"] = None if yhat is None else round(yhat, 4)
            reg["pronostico"] = None if yhat is None else int(round(max(yhat, 0.0)))
            reg["real"] = None if real is None else int(round(real))
            if motivos:
                reg["estado"], reg["motivo"], reg["error_abs"] = (
                    "ausente",
                    "; ".join(motivos),
                    None,
                )
            else:
                reg["estado"], reg["motivo"] = "par", ""
                reg["error_abs"] = abs(reg["pronostico"] - reg["real"])
            registros.append(reg)

    tabla = pd.DataFrame(registros)[COLUMNAS]
    for col in ("pronostico", "real", "error_abs", "horizonte"):
        tabla[col] = tabla[col].astype("Int64")  # conteos: enteros, con ausente explícito
    fc_ref = _load_fc("prophet")
    semanas: list[dict[str, Any]] = []
    resumen: dict[str, Any] = {
        "version": VERSION,
        "rotulo": ROTULO,
        "corte": {
            "etiqueta": _etiqueta(*corte),
            "anio": corte[0],
            "semana": corte[1],
            "ds": ds_corte.date().isoformat(),
        },
        "ultima_semana_observada": {
            "etiqueta": _etiqueta(*ultima),
            "anio": ultima[0],
            "semana": ultima[1],
        },
        "semanas_evaluadas": len(objetivos),
        "pasos_sin_semana_excluidos": pasos_sin_semana(
            fc_ref, ds_corte, ds_de_semana_boletin(*ultima) if ultima[1] != 1 else ds_corte
        ),
        "asignacion": {
            "neuro": {"archivo": TABLA.name, "sha256": _sha(TABLA)},
            "dengue": {"archivo": PROD.name, "sha256": _sha(PROD)},
        },
        "reglas": [
            "misma clave (padecimiento, entidad, sexo, semana del boletín, ds) a ambos lados",
            "pronóstico guardado del motor asignado, emitido desde el corte (fase pronóstico)",
            "observado con la regla de la galería; nacional y regiones exigen todas sus entidades",
            "sin desplazar valores; un lado faltante declara el par ausente",
            "el paso del horizonte sin semana del boletín queda fuera de las comparaciones",
        ],
        "definiciones": {
            "general": DEF_GENERAL,
            "sexo_agregado": DEF_SEXO_AGREGADO,
            "sexo_estatal": DEF_SEXO_ESTATAL,
            "notas": [
                "nacional y regiones por sexo: diferencia entre semanas consecutivas del acumulado "
                "agregado (suma de sus entidades, todas publicadas en ambas semanas); incluye las "
                "revisiones negativas de los estados, así que es un incremento neto y no un número "
                "demostrado de casos nuevos",
                "el agregado no se reconstruye sumando incrementos estatales recortados a cero",
                "una entidad cuyo acumulado por sexo disminuye queda ausente en su serie estatal, "
                "con su motivo; no se imputa ni se convierte en cero",
                "Casos_semana (general) es otra cantidad del boletín: no se fuerza a coincidir con "
                "hombres + mujeres",
                "cambio de definición respecto de la página del candidato anterior (f60f6b22), que "
                "sumaba los incrementos estatales recortados a cero: ver agregacion_sexo",
            ],
        },
        "semanas": semanas,
        "ausentes": _ausentes(tabla, obs, filas),
        "agregacion_sexo": _agregacion_sexo(tabla, obs, filas),
    }
    for etiqueta, g in tabla.groupby("semana_objetivo", sort=True):
        sem: dict[str, Any] = {
            "etiqueta": etiqueta,
            "ds": g["ds_objetivo"].iloc[0],
            "inicio": g["inicio_semana"].iloc[0],
            "fin": g["fin_semana"].iloc[0],
            "horizonte": int(g["horizonte"].iloc[0]),
            "cohortes": {},
        }
        for cohorte, c in g.groupby("cohorte", sort=True):
            pares = c[c["estado"] == "par"]
            err = pares["error_abs"].astype(float)
            nac = pares[pares["nivel"] == "nacional"]
            sem["cohortes"][cohorte] = {
                "series": int(len(c)),
                "pares": int(len(pares)),
                "ausentes": int((c["estado"] == "ausente").sum()),
                "motivos_ausencia": dict(Counter(c.loc[c["estado"] == "ausente", "motivo"])),
                "error_abs_medio": round(float(err.mean()), 2) if len(err) else None,
                "error_abs_mediano": round(float(err.median()), 2) if len(err) else None,
                "nacional": [
                    {
                        "padecimiento": str(r["padecimiento"]),
                        "sexo": str(r["sexo"]),
                        "motor": str(r["motor"]),
                        "pronostico": int(r["pronostico"]),
                        "real": int(r["real"]),
                        "definicion_real": str(r["definicion_real"]),
                    }
                    for r in _registros(nac)
                ],
            }
        semanas.append(sem)
    return tabla, resumen


def _registros(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(k): v for k, v in fila.items()} for fila in df.to_dict("records")]


def _int(v: Any) -> int | None:
    return None if v is None or pd.isna(v) else int(v)


def _fila(r: dict[str, Any]) -> dict[str, str]:
    return {k: str(r[k]) for k in ("cohorte", "padecimiento", "entidad", "sexo", "motor")}


def _ausentes(
    tabla: pd.DataFrame, obs: Observado, filas: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Cada par ausente con su motivo y, si es una serie por sexo, el acumulado de ambas semanas."""
    out: list[dict[str, Any]] = []
    for r in _registros(tabla[tabla["estado"] == "ausente"]):
        reg: dict[str, Any] = {
            k: r[k]
            for k in ("semana_objetivo", "horizonte", "cohorte", "padecimiento", "entidad", "sexo")
        }
        reg.update(
            nivel=r["nivel"],
            motor=r["motor"],
            pronostico=_int(r["pronostico"]),
            real=_int(r["real"]),
            motivo=r["motivo"],
        )
        if r["sexo"] != "general" and r["ds_objetivo"] is not None:
            anio, semana = (int(x) for x in str(r["semana_objetivo"]).split("-W"))
            antes, _ = obs.acumulado(_fila(r), *semana_previa(anio, semana))
            ahora, _ = obs.acumulado(_fila(r), anio, semana)
            reg["acumulado_semana_previa"] = _int(antes)
            reg["acumulado_semana"] = _int(ahora)
        out.append(reg)
    return out


def _agregacion_sexo(
    tabla: pd.DataFrame, obs: Observado, filas: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Nacional por sexo: incremento neto del acumulado frente a la suma estatal recortada a cero.

    Documenta el cambio de definición: el valor publicado es ``neto`` (diferencia del acumulado
    nacional, con las revisiones negativas de los estados); ``suma_estatal_recortada`` es lo que
    mostraba la página anterior y NO se publica como observado.
    """
    out: list[dict[str, Any]] = []
    nac = tabla[(tabla["nivel"] == "nacional") & (tabla["sexo"] != "general")]
    for r in _registros(nac):
        if r["ds_objetivo"] is None:
            continue
        f = _fila(r)
        anio, semana = (int(x) for x in str(r["semana_objetivo"]).split("-W"))
        previa = semana_previa(anio, semana)
        antes, n_antes = obs.acumulado(f, *previa)
        ahora, n_ahora = obs.acumulado(f, anio, semana)
        inc = obs.por_entidad(f, anio, semana)
        revisiones = inc[inc < 0]
        neto = None if antes is None or ahora is None else int(ahora - antes)
        out.append(
            {
                "semana_objetivo": r["semana_objetivo"],
                "semana_previa": _etiqueta(*previa),
                "cohorte": r["cohorte"],
                "padecimiento": r["padecimiento"],
                "sexo": r["sexo"],
                "definicion_real": r["definicion_real"],
                "entidades_semana": n_ahora,
                "entidades_semana_previa": n_antes,
                "semanas_consecutivas": siguiente_semana(*previa) == (anio, semana),
                "acumulado_semana_previa": _int(antes),
                "acumulado_semana": _int(ahora),
                "neto": neto,
                "real_publicado": _int(r["real"]),
                "suma_estatal_recortada": int(inc.clip(lower=0).sum()),
                "entidades_con_revision_negativa": {
                    str(e): int(v) for e, v in revisiones.sort_index().items()
                },
            }
        )
    return out


def _clave_wc(padecimiento: str) -> str:
    """Clave de ``weekly_comparison`` (la del knowledge): sin tildes, como antes."""
    return {"Depresión": "Depresion"}.get(padecimiento, padecimiento)


def _pronostico_motor(
    fila: dict[str, str], motor: str, ds: pd.Timestamp, corte: tuple[int, int], h: int
) -> tuple[int | None, str]:
    yhat, paso, motivo = pronostico({**fila, "motor": motor}, ds, corte)
    if yhat is not None and paso is not None and paso != h:
        return None, f"paso {paso} del pronóstico ≠ horizonte {h} del boletín"
    return (None, motivo) if yhat is None else (int(round(max(yhat, 0.0))), "")


def total_52_pasos(fila: dict[str, str], corte: tuple[int, int]) -> int | None:
    """Suma de los 52 pasos semanales del pronóstico emitido desde el corte (motor asignado)."""
    fc = _load_fc(fila["motor"])
    if fc.empty:
        return None
    pad = NEURO.get(fila["padecimiento"], fila["padecimiento"])
    d = fc[
        (fc["meta_padecimiento"] == pad)
        & (fc["meta_entidad"].fillna("Nacional") == _entidad_forecast(fila))
        & (fc["meta_modo"] == fila["sexo"])
        & (fc["fase_modelo"].fillna("pronostico") == "pronostico")
        & (fc["anio_boletin_corte"] == corte[0])
        & (fc["semana_boletin_corte"] == corte[1])
    ]
    pasos = sorted(int(x) for x in d["adelanto_semanas"])
    if pasos != list(range(1, 53)):
        return None
    return max(redondea(float(d["yhat"].sum())), 0)  # redondeo único, mitad hacia arriba


def semanal_nacional(
    tabla: pd.DataFrame, obs: Observado, corte: tuple[int, int], ultima: tuple[int, int]
) -> dict[str, Any]:
    """Tabla semanal del EpiBot (nacional, general) del año de la última semana observada.

    * ``observado``  semanas hasta el corte: SÓLO lo observado (el ajuste dentro de muestra del
      motor no viaja: no se presenta como validación);
    * ``seguimiento`` semanas posteriores al corte ya observadas: el par del seguimiento, copiado
      de la misma tabla (semana, corte, horizonte, estado y motivo); un ausente sigue ausente;
    * ``pronostico`` semanas aún sin dato: el pronóstico guardado desde el corte (y, en neuro, el de
      cada motor con el mismo corte y paso, para el corredor).

    Cada semana lleva el periodo OFICIAL del boletín; el ``ds`` legado no se publica.
    """
    anio = ultima[0]
    nac = tabla[(tabla["nivel"] == "nacional") & (tabla["sexo"] == "general")]
    pares = {(r["padecimiento"], r["semana_objetivo"]): r for r in _registros(nac)}
    out: dict[str, Any] = {}
    for f in asignacion():
        if f["entidad"] != "Nacional" or f["sexo"] != "general":
            continue
        semanas: list[dict[str, Any]] = []
        for s in range(1, semanas_del_anio_boletin(anio) + 1):
            e: dict[str, Any] = {
                "anio": anio,
                "semana": s,
                "etiqueta": _etiqueta(anio, s),
                "periodo_inicio": inicio_semana_boletin(anio, s).isoformat(),
                "periodo_fin": fin_semana_boletin(anio, s).isoformat(),
            }
            if (anio, s) <= corte:
                real, motivo = obs.general_semana(f, anio, s)
                e.update(fase="observado", real=real)
                if motivo:
                    e["motivo_observado"] = motivo
            elif (anio, s) <= ultima:
                r = pares[(f["padecimiento"], _etiqueta(anio, s))]
                p, re_ = _int(r["pronostico"]), _int(r["real"])
                e.update(
                    fase="seguimiento",
                    corte=r["corte"],
                    horizonte=int(r["horizonte"]),
                    pronostico=p,
                    real=re_,
                    estado=r["estado"],
                    motivo=r["motivo"],
                )
                if r["estado"] == "par":
                    e.update(error_abs=_int(r["error_abs"]), diferencia=p - re_)  # type: ignore[operator]
            else:
                h = len(semanas_objetivo(corte, (anio, s)))
                ds = ds_de_semana_boletin(anio, s)
                p_, motivo = _pronostico_motor(f, f["motor"], ds, corte, h)
                e.update(
                    fase="pronostico",
                    corte=_etiqueta(*corte),
                    horizonte=h,
                    pronostico=p_,
                    real=None,
                )
                if motivo:
                    e["motivo"] = motivo
                if f["cohorte"] == "neuro":
                    for m in MOTORES_NEURO:
                        v, _ = _pronostico_motor(f, m, ds, corte, h)
                        if v is not None:
                            e[m.lower()] = v
            semanas.append(e)
        out[_clave_wc(NEURO.get(f["padecimiento"], f["padecimiento"]))] = {
            "version": 2,
            "titulo": f"Seguimiento del pronóstico con corte W{corte[1]}",
            "rotulo": ROTULO_SEMANAL,
            "entidad": "Nacional",
            "sexo": "general",
            "definicion_real": DEF_GENERAL,
            "modelo_productivo": f["motor"].lower(),
            "motor": f["motor"],
            "anio": anio,
            "corte": _etiqueta(*corte),
            "ultima_semana_observada": _etiqueta(*ultima),
            "semanas_seguimiento": sum(1 for x in semanas if x["fase"] == "seguimiento"),
            "semanas_reales": sum(1 for x in semanas if x["real"] is not None),
            "semanas_pronostico": sum(1 for x in semanas if x["fase"] == "pronostico"),
            "pronostico_52_pasos": total_52_pasos(f, corte),
            "semanas": semanas,
        }
    return out


def escribe(
    tabla: pd.DataFrame,
    resumen: dict[str, Any],
    out: Path,
    semanal: dict[str, Any] | None = None,
) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    csv = out / "seguimiento_post_corte.csv"
    js = out / "seguimiento_post_corte.json"
    tabla.to_csv(csv, index=False, lineterminator="\n")
    js.write_text(json.dumps(resumen, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if semanal is not None:
        (out / "seguimiento_semanal_nacional.json").write_text(
            json.dumps(semanal, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    return csv, js


ROTULO_AGREGADO = "Notificaciones previstas · agregado estatal neuro"
PASOS = 52


def redondea(x: float) -> int:
    """Redondeo único al mostrar (mitad hacia arriba, sin sesgo de banca)."""
    return int(Decimal(repr(x)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _pasos_serie(fila: dict[str, str], corte: tuple[int, int]) -> pd.DataFrame:
    """Las 52 filas de pronóstico guardadas desde el corte para la serie, o falla en seco."""
    fc = _load_fc(fila["motor"])
    pad = NEURO.get(fila["padecimiento"], fila["padecimiento"])
    clave = f"{fila['padecimiento']} · {fila['entidad']} · {fila['sexo']} ({fila['motor']})"
    if fc.empty:
        raise SystemExit(f"agregado estatal: sin pronósticos de {fila['motor']} para {clave}")
    d = fc[
        (fc["meta_padecimiento"] == pad)
        & (fc["meta_entidad"].fillna("Nacional") == fila["entidad"])
        & (fc["meta_modo"] == fila["sexo"])
        & (fc["fase_modelo"].fillna("pronostico") == "pronostico")
        & (fc["anio_boletin_corte"] == corte[0])
        & (fc["semana_boletin_corte"] == corte[1])
    ].sort_values("adelanto_semanas")
    pasos = [int(x) for x in d["adelanto_semanas"]]
    if pasos != list(range(1, PASOS + 1)) or d["ds"].duplicated().any():
        raise SystemExit(
            f"agregado estatal: {clave} tiene pasos {pasos[:3]}… ({len(pasos)}), no 1..{PASOS}"
        )
    y = d["yhat"].astype(float)
    if not y.map(math.isfinite).all() or (y < 0).any():
        raise SystemExit(f"agregado estatal: {clave} con valores no finitos o negativos")
    return d


def agregado_estatal_neuro(corte: tuple[int, int]) -> dict[str, Any]:
    """El indicador canónico y su detalle; una serie ausente o inválida aborta (no vale cero)."""
    estados = [
        f for f in asignacion() if f["cohorte"] == "neuro" and _nivel(f["entidad"]) == "estatal"
    ]
    out: dict[str, Any] = {
        "version": 1,
        "rotulo": ROTULO_AGREGADO,
        "definicion": (
            "suma de los pronósticos guardados (yhat sin redondear) de las series de los 32 "
            "estados de Alzheimer, Depresión y Parkinson, modo general, con el motor asignado, "
            "52 pasos desde el corte; redondeada una sola vez al mostrar. No es el pronóstico de "
            "los modelos nacionales (que conservan el suyo) ni incluye regiones ni Dengue"
        ),
        "corte": _etiqueta(*corte),
        "procedencia": {
            "asignacion": {"archivo": TABLA.name, "sha256": _sha(TABLA)},
            "forecasts": {},
        },
    }
    por_sexo: dict[str, Any] = {}
    horizonte: dict[str, Any] | None = None
    for sexo in SEXOS:
        filas = [f for f in estados if f["sexo"] == sexo]
        series: list[dict[str, Any]] = []
        por_pad: dict[str, dict[str, Any]] = {}
        for f in filas:
            d = _pasos_serie(f, corte)
            suma = float(d["yhat"].astype(float).sum())
            series.append(
                {
                    "padecimiento": f["padecimiento"],
                    "entidad": f["entidad"],
                    "motor": f["motor"],
                    "pasos": len(d),
                    "suma_original": suma,
                }
            )
            pp = por_pad.setdefault(f["padecimiento"], {"series": 0, "suma_original": 0.0})
            pp["series"] += 1
            pp["suma_original"] += suma
            if horizonte is None:
                ds = [pd.Timestamp(x) for x in d["ds"]]
                horizonte = {
                    "pasos": PASOS,
                    "ds_primero": ds[0].date().isoformat(),
                    "ds_ultimo": ds[-1].date().isoformat(),
                    "pasos_sin_semana_del_boletin": pasos_sin_semana(
                        d, ds[0] - pd.Timedelta(days=1), ds[-1]
                    ),
                }
                semanas = []
                for x in ds:
                    try:
                        semanas.append(_etiqueta(*semana_boletin_de_ds(x)))
                    except DsSinSemanaBoletinError:
                        continue
                horizonte["semanas_del_boletin"] = (
                    f"{semanas[0]} a {semanas[-1]} ({len(semanas)} semanas)"
                )
        n_pad = {p: v["series"] for p, v in por_pad.items()}
        ents = {(s_["padecimiento"], s_["entidad"]) for s_ in series}
        if (
            set(n_pad) != set(NEURO)
            or set(n_pad.values()) != {N_ENTIDADES}
            or len(ents) != len(series)
        ):
            raise SystemExit(
                f"agregado estatal {sexo}: cobertura {n_pad} (se exigen 32 estados × 3)"
            )
        total = sum(s_["suma_original"] for s_ in series)
        por_sexo[sexo] = {
            "series": len(series),
            "valores": len(series) * PASOS,
            "suma_original": total,
            "valor_mostrado": redondea(total),
            "suma_de_totales_redondeados_por_serie": sum(
                redondea(s_["suma_original"]) for s_ in series
            ),
            "por_padecimiento": {
                p: {**v, "valor_mostrado": redondea(v["suma_original"])}
                for p, v in sorted(por_pad.items())
            },
            "series_incluidas": series,
        }
    for motor in sorted({f["motor"] for f in estados}):
        ruta = (
            Path(conf["paths"]["reports"])
            / "forecasts"
            / motor.lower()
            / f"all_forecast_{motor.lower()}.csv"
        )
        out["procedencia"]["forecasts"][motor] = {"archivo": str(ruta), "sha256": _sha(ruta)}
    gen = por_sexo["general"]
    out.update(
        horizonte=horizonte,
        series_incluidas=gen["series"],
        valores=gen["valores"],
        suma_original=gen["suma_original"],
        valor_mostrado=gen["valor_mostrado"],
        denominador=(
            f"{gen['series']} series: 32 estados × 3 padecimientos (Alzheimer, Depresión, "
            f"Parkinson), modo general · {PASOS} pasos desde el corte W{corte[1]}"
        ),
        por_sexo=por_sexo,
    )
    return out


def corte_declarado() -> tuple[int, int]:
    """El corte que declaran los pronósticos de los motores asignados (debe ser uno solo)."""
    cortes: set[tuple[int, int]] = set()
    for motor in {f["motor"] for f in asignacion()}:
        fc = _load_fc(motor)
        if fc.empty or "anio_boletin_corte" not in fc.columns:
            continue
        pron = fc[fc["fase_modelo"].fillna("pronostico") == "pronostico"]
        for a, s in (
            pron[["anio_boletin_corte", "semana_boletin_corte"]]
            .dropna()
            .drop_duplicates()
            .itertuples(index=False)
        ):
            cortes.add((int(a), int(s)))
    if len(cortes) != 1:
        raise SystemExit(
            f"los pronósticos asignados declaran {len(cortes)} cortes: {sorted(cortes)}"
        )
    return next(iter(cortes))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument(
        "--corte",
        default=None,
        help="semana del boletín del corte (AAAA-Wss); por defecto, la que declaran los pronósticos",
    )
    a = ap.parse_args(argv)
    if a.corte is None:
        corte = corte_declarado()
    else:
        anio, semana = a.corte.split("-W")
        corte = (int(anio), int(semana))
    obs = Observado()
    tabla, resumen = construye(corte, obs)
    ultima = (
        resumen["ultima_semana_observada"]["anio"],
        resumen["ultima_semana_observada"]["semana"],
    )
    semanal = semanal_nacional(tabla, obs, corte, ultima)
    csv, js = escribe(tabla, resumen, a.out, semanal)
    agregado = agregado_estatal_neuro(corte)
    (a.out / "agregado_estatal_neuro.json").write_text(
        json.dumps(agregado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(
        f"  {ROTULO_AGREGADO}: {agregado['valor_mostrado']:,} "
        f"(suma original {agregado['suma_original']:.4f}; {agregado['denominador']})"
    )
    print(
        f"  seguimiento post-corte {resumen['corte']['etiqueta']}: {resumen['semanas_evaluadas']} semana(s)"
    )
    for s in resumen["semanas"]:
        for c, v in s["cohortes"].items():
            print(
                f"    {s['etiqueta']} h={s['horizonte']} {c}: {v['pares']}/{v['series']} pares, {v['ausentes']} ausentes"
            )
    print(f"  -> {csv}\n  -> {js}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

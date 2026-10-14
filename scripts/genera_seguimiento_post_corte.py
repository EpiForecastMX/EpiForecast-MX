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
  y regiones = suma de sus entidades, exigiendo que todas hayan publicado.

Nunca se desplaza un valor ni se empareja el pronóstico de una semana con la realidad de otra. Si
falta cualquiera de los dos lados, el par se declara AUSENTE con su motivo. El paso del horizonte
cuyo ``ds`` no tiene semana del boletín (2026-12-28) no es una semana objetivo: queda fuera y se
declara. La semana 1 del boletín tampoco es evaluable (colisión del calendario legado).

Rótulo: seguimiento diagnóstico posterior al corte, con el número de semanas evaluadas. No es una
evaluación independiente ni sustituye la del artículo.

Salidas (en ``--out``):
  * ``seguimiento_post_corte.csv``  una fila por (serie, semana objetivo), pares y ausentes
  * ``seguimiento_post_corte.json`` resumen por semana y cohorte

Uso:
    python scripts/genera_seguimiento_post_corte.py --out reports/ProdDetails
"""

from __future__ import annotations

import argparse
from collections import Counter
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
        real = self.serie(fila)
        v = real.loc[pd.to_datetime(real["ds"]) == ds, "y"]
        if v.empty:
            return None, "observación no desagregable (sin semana previa consecutiva o revisión)"
        if len(v) > 1:
            return None, "observación duplicada en el ds"
        return float(v.iloc[0]), ""


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


def construye(corte: tuple[int, int]) -> tuple[pd.DataFrame, dict[str, Any]]:
    obs = Observado()
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
                    }
                )
            continue
        for f in filas:
            reg: dict[str, Any] = {
                **f,
                **base,
                "nivel": _nivel(f["entidad"]),
                "ds_objetivo": ds.date().isoformat(),
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
        "semanas": semanas,
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
                    }
                    for r in _registros(nac)
                ],
            }
        semanas.append(sem)
    return tabla, resumen


def _registros(df: pd.DataFrame) -> list[dict[str, Any]]:
    return [{str(k): v for k, v in fila.items()} for fila in df.to_dict("records")]


def escribe(tabla: pd.DataFrame, resumen: dict[str, Any], out: Path) -> tuple[Path, Path]:
    out.mkdir(parents=True, exist_ok=True)
    csv = out / "seguimiento_post_corte.csv"
    js = out / "seguimiento_post_corte.json"
    tabla.to_csv(csv, index=False, lineterminator="\n")
    js.write_text(json.dumps(resumen, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return csv, js


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--corte", default="2026-W37", help="semana del boletín del corte (AAAA-Wss)")
    a = ap.parse_args(argv)
    anio, semana = a.corte.split("-W")
    tabla, resumen = construye((int(anio), int(semana)))
    csv, js = escribe(tabla, resumen, a.out)
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

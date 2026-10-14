"""Genera knowledge.json para el sitio web estatico de EpiForecast-MX.

Reutiliza ProjectDataCache y KnowledgeBase del proyecto para exportar
todos los datos necesarios a un JSON consumible por el frontend.

Uso:
    python scripts/build_web_knowledge.py
"""

import argparse
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
import json
import math
from pathlib import Path
import sys
from typing import Any
import unicodedata

import pandas as pd


def strip_accents(text: str) -> str:
    """Remueve acentos de un string (á→a, é→e, etc.)."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c))


# Agregar src/ al path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from epi_modules.features.data_cache import ProjectDataCache  # noqa: E402
from epi_modules.features.knowledge_base import KnowledgeBase  # noqa: E402

from epiforecast.constants import ENTIDAD_DISPLAY  # noqa: E402
from epiforecast.data.boletin import cargar_boletin_dengue  # noqa: E402
from epiforecast.publication.metricas_seleccion import ROTULO, separa_metricas  # noqa: E402
from epiforecast.utils.cohorts import filter_neuro  # noqa: E402
from epiforecast.utils.config import conf  # noqa: E402
from epiforecast.utils.semana_epi import (  # noqa: E402
    ds_de_semana_boletin,
    fin_semana_boletin,
    inicio_semana_boletin,
)

# Salida por defecto (flujo legacy). El refresh sellado pasa `--out` y escribe en el
# staging: un generador que sólo sabe escribir en el árbol real es lo que lo ensucia.
OUTPUT = Path("web_dashboard/knowledge.json")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Genera knowledge.json del EpiBot.")
    parser.add_argument(
        "--out",
        type=Path,
        default=OUTPUT,
        help=f"archivo de salida (por defecto {OUTPUT}); el refresh sellado apunta al staging",
    )
    parser.add_argument(
        "--evidencia-metricas",
        type=Path,
        default=None,
        help=(
            "JSON de revisión con las métricas de selección retiradas del knowledge público "
            f"(rotuladas «{ROTULO}»); nunca se publica"
        ),
    )
    parser.add_argument(
        "--seguimiento",
        type=Path,
        default=None,
        help=(
            "seguimiento_post_corte.json (genera_seguimiento_post_corte.py): resumen de las "
            "semanas evaluadas después del corte, que el EpiBot presenta como seguimiento"
        ),
    )
    return parser.parse_args(argv)


def carga_seguimiento(ruta: Path, prod_models: list[dict[str, Any]]) -> dict[str, Any]:
    """El resumen del seguimiento, comprobado contra los campos por serie de la tabla.

    Los dos caminos deben hablar de la misma semana: la última evaluada del resumen es la que
    declara cada fila de la tabla (`semana_validacion`). Si no, el EpiBot diría una semana en el
    resumen y otra en el gráfico de calibración.
    """
    resumen: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    if not resumen.get("semanas"):
        raise SystemExit(f"{ruta}: seguimiento sin semanas evaluadas")
    ultima = resumen["semanas"][-1]["etiqueta"]
    declaradas = {m.get("semana_validacion") for m in prod_models}
    if declaradas != {ultima}:
        raise SystemExit(
            f"la tabla declara las semanas {sorted(map(str, declaradas))} y el seguimiento "
            f"termina en {ultima}: regenera la tabla con genera_validacion_semanal.py"
        )
    if resumen.get("semanas_evaluadas") != len(resumen["semanas"]):
        raise SystemExit(f"{ruta}: semanas_evaluadas no coincide con las semanas listadas")
    return resumen


def carga_agregado(ruta: Path, resumen: dict[str, Any]) -> dict[str, Any]:
    """El indicador «Notificaciones previstas · agregado estatal neuro», calculado en el backend.

    Lo escribe ``genera_seguimiento_post_corte.py`` desde los ``yhat`` originales (suma sin
    redondear, redondeo único). Antes ``stats.pronostico_total`` sumaba los totales por serie ya
    redondeados (171,525 en vez de 171,524) y el EpiBot lo recalculaba igual y lo llamaba
    «Pronóstico Nacional». Falla en seco si falta, si habla de otro corte o si no cubre 96 series.
    """
    if not ruta.is_file():
        raise SystemExit(f"falta {ruta} (lo escribe genera_seguimiento_post_corte.py)")
    ag: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    if ag.get("corte") != resumen["corte"]["etiqueta"]:
        raise SystemExit(f"{ruta}: corte {ag.get('corte')} ≠ {resumen['corte']['etiqueta']}")
    if (ag.get("series_incluidas"), ag.get("valores")) != (96, 96 * 52):
        raise SystemExit(
            f"{ruta}: {ag.get('series_incluidas')} series / {ag.get('valores')} valores"
        )
    una_vez = Decimal(repr(ag["suma_original"])).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    if ag.get("valor_mostrado") != int(una_vez):
        raise SystemExit(f"{ruta}: valor_mostrado no es la suma original redondeada una vez")
    return ag


def aplica_agregado(stats: dict[str, Any], ag: dict[str, Any]) -> None:
    """Los totales por padecimiento y por sexo pasan a ser los del agregado estatal canónico.

    ``por_sexo.*.casos_total`` sumaba las 37 geografías (Nacional + 4 regiones + 32 estados: el
    mismo caso contado hasta tres veces); ahora es la suma de los 32 estados. Los modelos
    nacionales conservan su pronóstico propio en ``casos_nacional``.
    """
    stats["pronostico_total"] = ag["valor_mostrado"]
    for pad, ps in stats.get("por_pad", {}).items():
        gen = ag["por_sexo"]["general"]["por_padecimiento"].get(pad)
        if gen is None:
            continue
        ps["casos_futuro_total"] = gen["valor_mostrado"]
        ps["casos_futuro_total_definicion"] = "agregado estatal (32 estados, modo general)"
        for sx, info in ps.get("por_sexo", {}).items():
            sxa = ag["por_sexo"].get(sx, {}).get("por_padecimiento", {}).get(pad)
            if sxa is not None:
                info["casos_total"] = sxa["valor_mostrado"]
                info["casos_total_definicion"] = "agregado estatal (32 estados)"
                info["n_estados"] = sxa["series"]


def carga_semanal(ruta: Path, resumen: dict[str, Any]) -> dict[str, Any]:
    """La tabla semanal del EpiBot (``seguimiento_semanal_nacional.json``), contrastada con el resumen.

    Sustituye a la «Real vs Pronóstico 2026», que alineaba lo observado con TODAS las filas del
    pronóstico del año (el ajuste dentro de muestra W2–W37 incluido) y rotulaba el ``ds`` legado
    como inicio de la semana. Aquí: las comparaciones son sólo los pares posteriores al corte, que
    deben ser los del resumen; antes del corte sólo viaja lo observado; cada semana lleva el
    periodo oficial del boletín. Falla en seco si algo no cuadra.
    """
    if not ruta.is_file():
        raise SystemExit(f"falta {ruta} (lo escribe genera_seguimiento_post_corte.py)")
    semanal: dict[str, Any] = json.loads(ruta.read_text(encoding="utf-8"))
    corte, ultima = resumen["corte"]["etiqueta"], resumen["ultima_semana_observada"]["etiqueta"]
    pares = {
        (strip_accents(n["padecimiento"]), s["etiqueta"]): n
        for s in resumen["semanas"]
        for c in s["cohortes"].values()
        for n in c["nacional"]
        if n["sexo"] == "general"
    }
    for pad, info in semanal.items():
        if (info.get("corte"), info.get("ultima_semana_observada")) != (corte, ultima):
            raise SystemExit(f"{ruta}: {pad} habla de otro corte o de otra semana observada")
        for w in info["semanas"]:
            if "fecha" in w or "error_pct" in w:
                raise SystemExit(f"{ruta}: {pad} {w['etiqueta']} trae campos de la tabla anterior")
            if w["fase"] == "observado" and set(w) & {
                "pronostico",
                "prophet",
                "deepar",
                "ensemble",
                "stacking",
            }:
                raise SystemExit(
                    f"{ruta}: {pad} {w['etiqueta']} publica el ajuste dentro de muestra"
                )
            if w["fase"] == "seguimiento" and w["estado"] == "par":
                n = pares.get((strip_accents(pad), w["etiqueta"]))
                if n is None or (n["pronostico"], n["real"]) != (w["pronostico"], w["real"]):
                    raise SystemExit(f"{ruta}: {pad} {w['etiqueta']} no es el par del seguimiento")
    return semanal


def _sin_nan(valor: Any) -> Any:
    """NaN -> None, recursivo.

    El `JSONEncoder.default` que había aquí nunca se ejecutaba para NaN: `json` sabe
    serializar un float NaN por sí mismo (como el token `NaN`, que no es JSON válido y que
    `JSON.parse` del navegador rechaza). Se sustituye antes de serializar y se serializa
    con `allow_nan=False`, para que un NaN que se escape sea un error y no un sitio roto.
    """
    if isinstance(valor, float) and pd.isna(valor):
        return None
    if isinstance(valor, dict):
        return {clave: _sin_nan(v) for clave, v in valor.items()}
    if isinstance(valor, list | tuple):
        return [_sin_nan(v) for v in valor]
    return valor


def escribe_evidencia(retiradas: dict[str, Any], destino: Path) -> None:
    """Escribe las métricas retiradas (evidencia de revisión, no publicable)."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(_sin_nan(retiradas), f, ensure_ascii=False, indent=1, allow_nan=False)


def escribe_knowledge(knowledge: dict[str, Any], destino: Path) -> None:
    """Serializa con NaN -> null en `destino`, creando su directorio si falta."""
    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "w", encoding="utf-8") as f:
        json.dump(_sin_nan(knowledge), f, ensure_ascii=False, indent=None, allow_nan=False)


def _safe_int(v: Any) -> int | None:
    """Convierte a int si es numerico, None si no."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return int(v)
    except (ValueError, TypeError):
        return None


def _safe_float(v: Any, decimals: int = 2) -> float | None:
    """Convierte a float redondeado si es numerico, None si no."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        return round(float(v), decimals)
    except (ValueError, TypeError):
        return None


def _safe_str(v: Any) -> str | None:
    """Convierte a str sin acentos, None si NaN."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    return strip_accents(str(v))


def _normalize_keys(obj: Any) -> Any:
    """Recursivamente normaliza claves de dicts (strip acentos)."""
    if isinstance(obj, dict):
        return {strip_accents(str(k)): _normalize_keys(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize_keys(item) for item in obj]
    if isinstance(obj, str):
        return strip_accents(obj)
    return obj


def build_prod_models(cache: ProjectDataCache) -> list[dict]:
    """Exporta las 333 series neuro de producción como lista de dicts.

    El filtro por cohorte faltaba: el docstring prometía 333 y se exportaban las **435**
    filas del workbook, incluidas las 102 de Dengue —con 3 nacionales duplicados y 13
    selecciones de Ensemble/Stacking que Dengue no admite—. Ese es el `dengue n=102` que
    llegó al `knowledge.json` publicado. Dengue viaja en su propia sección
    (`build_dengue_section`), con su selector y sus motores.
    Ver docs/CONTRATO_VOCABULARIO_CIFRAS.md.
    """
    prod = cache.prod_models
    if prod is None or prod.empty:
        return []
    prod = filter_neuro(prod)
    if prod.empty:
        return []

    cols = [
        "padecimiento",
        "entidad",
        "sexo",
        "modelo_produccion",
        "smape_prod",
        "mase_prod",
        "rmse_prod",
        "mae_prod",
        "casos_52_semanas_futuro",
        "overfitting",
        "leakage",
        "tipo_modelo",
        "pron_sem_previa",
        "realidad_sem_previa",
        "semana_validacion",
        "corte_validacion",
        "horizonte_validacion",
        "definicion_realidad_validacion",
        "precision_historica",
    ]
    available = [c for c in cols if c in prod.columns]
    if "semana_validacion" not in available:
        # Tabla v1: el pronóstico y la realidad de la «semana previa» no declaran su semana y en
        # la ronda W37 eran de semanas distintas (W38 y W39). Sin la declaración no se publican.
        available = [c for c in available if c not in ("pron_sem_previa", "realidad_sem_previa")]
    rows = []
    for _, r in prod[available].iterrows():
        row = {}
        for c in available:
            v = r[c]
            if c in ("smape_prod", "mase_prod", "rmse_prod", "mae_prod"):
                row[c] = _safe_float(v)
            elif c in (
                "casos_52_semanas_futuro",
                "pron_sem_previa",
                "realidad_sem_previa",
                "horizonte_validacion",
            ):
                row[c] = _safe_int(v)
            elif c == "precision_historica":
                row[c] = _safe_str(v)
            else:
                row[c] = _safe_str(v)
        rows.append(row)
    return rows


def build_boletin(cache: ProjectDataCache) -> dict:
    """Pre-agrega datos del boletin para el frontend."""
    df = cache.boletin
    # Guard: el EpiBot público solo conoce la cohorte neuro de producción.
    # Excluye Dengue (en el consolidado pero sin respuestas/forecasts en el bot).
    if df is not None:
        df = filter_neuro(df)
    if df is None or df.empty:
        return {}

    result: dict[str, Any] = {}

    # Meta
    result["meta"] = {
        "total_registros": len(df),
        "min_anio": int(df["Anio"].min()),
        "max_anio": int(df["Anio"].max()),
        "max_semana": int(df[df["Anio"] == df["Anio"].max()]["Semana"].max()),
        "entidades": sorted(df["Entidad"].dropna().unique().tolist()),
        "padecimientos": sorted(df["Padecimiento"].dropna().unique().tolist()),
    }

    # Anual por padecimiento
    anual_pad: dict[str, dict[str, int]] = {}
    for pad in df["Padecimiento"].dropna().unique():
        sub = df[df["Padecimiento"] == pad]
        by_year = sub.groupby("Anio")["Casos_semana"].sum()
        anual_pad[str(pad)] = {str(int(y)): int(c) for y, c in by_year.items() if not pd.isna(c)}
    result["anual_por_pad"] = anual_pad

    # Anual por estado y padecimiento (top 10 estados por total)
    top_estados = (
        df.groupby("Entidad")["Casos_semana"]
        .sum()
        .sort_values(ascending=False)
        .head(15)
        .index.tolist()
    )
    anual_est: dict[str, dict[str, dict[str, int]]] = {}
    for est in top_estados:
        sub = df[df["Entidad"] == est]
        anual_est[str(est)] = {}
        for pad in sub["Padecimiento"].dropna().unique():
            pad_sub = sub[sub["Padecimiento"] == pad]
            by_year = pad_sub.groupby("Anio")["Casos_semana"].sum()
            anual_est[str(est)][str(pad)] = {
                str(int(y)): int(c) for y, c in by_year.items() if not pd.isna(c)
            }
    result["anual_por_estado_pad"] = anual_est

    # Ultima semana
    max_year = int(df["Anio"].max())
    max_week = int(df[df["Anio"] == max_year]["Semana"].max())
    latest = df[(df["Anio"] == max_year) & (df["Semana"] == max_week)]
    if not latest.empty:
        by_pad = latest.groupby("Padecimiento")["Casos_semana"].sum()
        result["ultima_semana"] = {
            "anio": max_year,
            "semana": max_week,
            "total": int(latest["Casos_semana"].sum()),
            "por_padecimiento": {str(p): int(c) for p, c in by_pad.items() if not pd.isna(c)},
        }

    # Ranking entidades (total historico)
    ranking = df.groupby("Entidad")["Casos_semana"].sum().sort_values(ascending=False)
    result["ranking_entidades"] = [
        {"entidad": str(e), "casos": int(c)} for e, c in ranking.head(20).items() if not pd.isna(c)
    ]

    # Semanal reciente (ultimas 12 semanas agregadas por padecimiento)
    recent = df[df["Anio"] == max_year].sort_values("Semana")
    last_weeks = sorted(recent["Semana"].unique())[-12:]
    semanal: list[dict] = []
    for w in last_weeks:
        w_data = recent[recent["Semana"] == w]
        entry: dict[str, Any] = {"semana": int(w), "total": int(w_data["Casos_semana"].sum())}
        for pad in df["Padecimiento"].dropna().unique():
            p_sub = w_data[w_data["Padecimiento"] == pad]
            entry[str(pad)] = int(p_sub["Casos_semana"].sum()) if not p_sub.empty else 0
        semanal.append(entry)
    result["semanal"] = semanal

    return result


_MOTORES_ENTRENADOS_DENGUE = ("Prophet", "DeepAR", "Ensemble", "Stacking", "NBGLM")


def _motores_productivos_dengue(prod: pd.DataFrame) -> list[str]:
    """Motores con al menos una serie en la asignación congelada, por número de series.

    Es la única fuente de los motores que se muestran: un motor entrenado pero sin series
    asignadas (Ensemble/Stacking no elegibles, NBGLM suspendido en W37) no aparece.
    """
    vc = prod["motor_productivo"].dropna().astype(str).value_counts()
    return sorted(vc.index, key=lambda m: (-int(vc[m]), m))


def build_dengue_section() -> dict[str, Any]:
    """Sección de Dengue para el EpiBot, derivada de los artefactos de producción.

    Dengue es el 4.o padecimiento con pipeline propio (cohorte de conteos-log, no neuro):
    sus métricas y selección de motor NO comparten estructura con la neuro (333 modelos por
    tasa). Por eso se expone en su propia sección y NO se mezcla en ``stats.por_pad`` (evita
    que los handlers de comparación neuro la incluyan con métricas incompatibles).
    Fuente: ``produccion_dengue.csv`` (selector DeepAR/Prophet) + boletín consolidado + forecast.
    """
    reports = Path(conf["paths"]["reports"])
    prod_path = reports / "ProdDetails" / "produccion_dengue.csv"
    if not prod_path.exists():
        return {}
    prod = pd.read_csv(prod_path)
    dist = {str(k): int(v) for k, v in prod["motor_productivo"].value_counts().items()}
    productivos = _motores_productivos_dengue(prod)
    nac = prod[(prod["entidad"] == "Nacional") & (prod["sexo"] == "general")]
    motor_nac = str(nac["motor_productivo"].iloc[0]) if len(nac) else "Prophet"
    # smape_ganador puede ser NaN si la serie cayó al criterio mae_real_casi_cero (imposible
    # para Nacional, pero el guard evita un TypeError si algún día ocurre).
    smape_nac = (
        round(float(nac["smape_ganador"].iloc[0]), 2)
        if len(nac) and pd.notna(nac["smape_ganador"].iloc[0])
        else None
    )

    df = cargar_boletin_dengue()
    ann = df.groupby("Anio")["Casos_semana"].sum()
    anual = {str(int(y)): int(c) for y, c in ann.items()}
    # Contexto 2014-2017 (esquema viejo A90/A91) para la gráfica de evolución del EpiBot:
    # prepende los años previos a la serie de modelado (otra clasificación, solo display).
    a9091 = Path(conf["paths"]["interim"]) / "dengue_a90a91_nacional.csv"
    if a9091.exists():
        old = pd.read_csv(a9091)
        old["tot"] = old["Acumulado_hombres"] + old["Acumulado_mujeres"]
        for y, c in old.groupby("Anio")["tot"].max().items():
            anual.setdefault(str(int(y)), int(c))
        anual = {y: anual[y] for y in sorted(anual)}
    pico_anio, pico_casos = int(ann.idxmax()), int(ann.max())
    total = df.groupby("Entidad")["Casos_semana"].sum().sort_values(ascending=False)
    top_ent = [
        {"entidad": ENTIDAD_DISPLAY.get(str(e), str(e)), "casos": int(c)}
        for e, c in total.head(6).items()
        if c > 0
    ]
    sin_casos = [ENTIDAD_DISPLAY.get(str(e), str(e)) for e, c in total.items() if c == 0]

    # Última semana real + pronóstico productivo nacional a 52 sem (motor productivo nacional).
    last = df[df["Anio"] == df["Anio"].max()]
    last_sem = int(last["Semana"].astype(int).max())
    last_real = ds_de_semana_boletin(int(df["Anio"].max()), last_sem)

    # Forecast CSV por motor (cache) -> pronóstico 52 sem de una serie (entidad, general).
    _fc_cache: dict[str, pd.DataFrame] = {}

    def _fc_52sem(entidad: str, motor: str) -> int:
        key = motor.lower()
        if key not in _fc_cache:
            p = reports / "forecasts" / key / f"all_forecast_{key}.csv"
            _fc_cache[key] = pd.read_csv(p, low_memory=False) if p.exists() else pd.DataFrame()
        fc = _fc_cache[key]
        if fc.empty:
            return 0
        # Los 52 pasos del pronóstico emitido desde el corte (fase pronóstico), sumados sin
        # redondear y redondeados una vez, como el agregado estatal neuro. Antes se sumaban los
        # pasos posteriores a la última semana observada (50 tras W39) y se rotulaban «52 sem».
        d = fc[
            (fc["meta_padecimiento"] == "Dengue")
            & (fc["meta_entidad"] == entidad)
            & (fc["meta_modo"] == "general")
            & (fc["fase_modelo"].fillna("pronostico") == "pronostico")
        ]
        cortes = d[["anio_boletin_corte", "semana_boletin_corte"]].drop_duplicates()
        pasos = sorted(int(x) for x in d["adelanto_semanas"])
        if (
            len(cortes) != 1
            or pasos != list(range(1, 53))
            or not d["yhat"].map(math.isfinite).all()
        ):
            raise SystemExit(
                f"Dengue {entidad} ({motor}): {len(pasos)} pasos y {len(cortes)} cortes; se exigen 52 y 1"
            )
        total = Decimal(repr(float(d["yhat"].astype(float).sum())))
        return max(int(total.quantize(Decimal("1"), rounding=ROUND_HALF_UP)), 0)

    casos_fut: int | None = _fc_52sem("Nacional", motor_nac) or None

    # Pronóstico 52 sem POR ENTIDAD (motor productivo de cada serie general) — consistente con
    # el mapa neuro, que muestra casos pronosticados a 52 sem (no histórico).
    prod_gen = prod[
        (prod["sexo"] == "general")
        & (~prod["entidad"].isin(["Nacional"]))
        & (~prod["entidad"].astype(str).str.startswith("Region"))
    ]
    por_entidad_fc: dict[str, int] = {}
    for _, r in prod_gen.iterrows():
        ent_raw = str(r["entidad"])
        val = _fc_52sem(ent_raw, str(r["motor_productivo"]))
        if val > 0:
            por_entidad_fc[ENTIDAD_DISPLAY.get(ent_raw, ent_raw)] = val

    return {
        "cie": "A97",
        "cobertura": f"{int(df['Anio'].min())}-{int(df['Anio'].max())}",
        "n_boletines": int(df.groupby(["Anio", "Semana"]).ngroups),
        "n_entidades": int(df["Entidad"].nunique()),
        "n_series": int(len(prod)),
        "horizonte_semanas": 52,
        "motores_entrenados": list(_MOTORES_ENTRENADOS_DENGUE),
        # Derivado de la asignación congelada: un motor sin series asignadas no es productivo.
        "motores_productivos": productivos,
        "dist_motor": dist,
        "motor_nacional": motor_nac,
        "smape_nacional": smape_nac,
        "casos_futuro_nacional_52sem": casos_fut,
        "casos_futuro_definicion": "52 pasos semanales del modelo nacional desde el corte",
        "ultima_real": last_real.strftime("%Y-%m-%d"),  # ds legado (no es la fecha del boletín)
        "ultima_semana_boletin": {
            "anio": int(df["Anio"].max()),
            "semana": last_sem,
            "inicio": inicio_semana_boletin(int(df["Anio"].max()), last_sem).isoformat(),
            "fin": fin_semana_boletin(int(df["Anio"].max()), last_sem).isoformat(),
        },
        "anual": anual,
        "anio_pico": pico_anio,
        "casos_pico": pico_casos,
        "anios_epidemicos": [2014, 2019, 2024],
        "ciclo_anios": "cuatro a cinco",
        "top_entidades": top_ent,
        "sin_casos": sin_casos,
        # Pronóstico 52 sem por entidad (motor productivo) para el mapa coroplético del EpiBot,
        # consistente con el mapa neuro (casos pronosticados a 52 sem, NO histórico).
        "por_entidad": por_entidad_fc,
        "unidad": "conteos absolutos (no tasa por 100 mil)",
        "notas": [
            "Serie de producción 2018-2026 (Cuadro 7.2 SINAVE, dengue confirmado A97.x agregado).",
            "La serie histórica 2014-2017 (taxonomía vieja A90/A91) es solo contexto/EDA, no entrena.",
            f"{len(_MOTORES_ENTRENADOS_DENGUE)} motores entrenados; productivos "
            f"{' y '.join(productivos)} según la asignación por serie. Ensemble y Stacking no "
            "son elegibles: los árboles no extrapolan la dinámica epidémica.",
            *(
                []
                if "NBGLM" in productivos
                else [
                    "NBGLM está suspendido en esta ronda por inestabilidad de su predicción "
                    "recursiva; sus modelos se conservan como evidencia, pero no se publica "
                    "ningún pronóstico suyo."
                ]
            ),
            "Pronóstico a 1 año (52 semanas). No se publica ninguna proyección multi-año.",
            "Los picos (2014, 2019, 2024) coinciden con años de El Niño; 2024 fue la mayor "
            "epidemia de dengue registrada en las Américas.",
        ],
    }


# MASE por encima de esto = denominador naive degenerado (serie casi-cero que diverge); se
# excluye del resumen. El máximo legítimo observado es ~6 (neuro); en Dengue año-bajo una
# serie casi-cero puede disparar el MASE a miles y contaminar el promedio.
_MASE_CAP = 20.0


def _metric_summary(sm: pd.Series, ma: pd.Series) -> dict[str, Any]:
    """Resumen mediana/promedio de SMAPE y MASE, robusto a MASE degenerado (> ``_MASE_CAP``)."""
    inf = float("inf")
    sm = pd.to_numeric(sm, errors="coerce").replace([inf, -inf], float("nan")).dropna()
    ma = pd.to_numeric(ma, errors="coerce").replace([inf, -inf], float("nan")).dropna()
    ma = ma[ma <= _MASE_CAP]
    return {
        "smape_med": _safe_float(sm.median()) if len(sm) else None,
        "smape_prom": _safe_float(sm.mean()) if len(sm) else None,
        "mase_med": _safe_float(ma.median()) if len(ma) else None,
        "mase_prom": _safe_float(ma.mean()) if len(ma) else None,
    }


def _rendimiento_dengue() -> dict[str, Any]:
    """Rendimiento 2026 de Dengue por motor productivo (cohorte propia; motores de la asignación).

    Fuente: ``produccion_dengue.csv`` (``smape_real_<motor>`` + ``mase_real_<motor>`` +
    ``motor_productivo``). Dengue 2026 es un año bajo: casi todas las series estatales son
    casi-cero, así que el SMAPE satura ~200% y la selección usa el MAE ("si es 0, es 0"); la
    señal informativa es la nacional. El MASE mediano (~0.03) muestra que los motores superan
    de sobra al naive estacional. Solo se muestran los motores elegibles/productivos.
    """
    reports = Path(conf["paths"]["reports"])
    prod_path = reports / "ProdDetails" / "produccion_dengue.csv"
    if not prod_path.exists():
        return {}
    df = pd.read_csv(prod_path)
    motores = _motores_productivos_dengue(df)
    smape_cols = [f"smape_real_{m.lower()}" for m in motores]
    if not all(c in df.columns for c in smape_cols):
        return {}
    have_mase = all(f"mase_real_{m.lower()}" in df.columns for m in motores)

    def _deployed(prefix: str) -> pd.Series:
        vals = []
        for _, row in df.iterrows():
            motor = row.get("motor_productivo")
            if pd.notna(motor):
                vals.append(row.get(f"{prefix}_{str(motor).lower()}"))
        return pd.Series(vals, dtype="float64") if vals else pd.Series(dtype="float64")

    motores_out: dict[str, Any] = {}
    for m in motores:
        sc = f"smape_real_{m.lower()}"
        mc = f"mase_real_{m.lower()}"
        motores_out[m] = _metric_summary(
            df[sc], df[mc] if (have_mase and mc in df.columns) else pd.Series(dtype=float)
        )
    motores_out["Productivo"] = _metric_summary(
        _deployed("smape_real"), _deployed("mase_real") if have_mase else pd.Series(dtype=float)
    )

    nac = df[(df["entidad"] == "Nacional") & (df["sexo"] == "general")]
    nacional: dict[str, Any] = {}
    if len(nac):
        r0 = nac.iloc[0]
        nacional = {
            "motor": _safe_str(r0.get("motor_productivo")),
            "smape": {m: _safe_float(r0.get(f"smape_real_{m.lower()}")) for m in motores},
        }

    out: dict[str, Any] = {
        "n": int(df[smape_cols].notna().any(axis=1).sum()),
        "orden_motores": motores,
        "tiene_mase": bool(have_mase),
        "motores": motores_out,
        "nacional": nacional,
        "nota": (
            "Dengue 2026 es un año bajo: la mayoría de las series estatales son casi-cero, "
            "por eso el SMAPE satura ~200% y la selección usa el MAE. El MASE mediano (~0.03) "
            "indica que los motores superan de sobra al naive estacional. La señal fiable es "
            "la nacional."
        ),
    }
    nsem = pd.to_numeric(df.get("n_semanas_real"), errors="coerce").dropna()
    if len(nsem):
        out["n_semanas"] = int(nsem.max())
    return out


def build_rendimiento_2026() -> dict[str, Any]:
    """Rendimiento 2026 por padecimiento y motor: SMAPE y MASE (mediana y promedio) de
    los motores + el motor productivo desplegado por serie.

    Neuro (Alzheimer/Depresion/Parkinson): fuente ``auditoria_motores_2026.xlsx`` (generado
    por ``reselect_motor_2026.py``). Dengue (cohorte propia): ``_rendimiento_dengue`` desde
    ``produccion_dengue.csv``. Alimenta el handler ``answerRendimientoPorPadecimiento`` del
    EpiBot. ``n`` = series con al menos un motor con dato 2026.
    """
    reports = Path(conf["paths"]["reports"])
    audit_path = reports / "ProdDetails" / "auditoria_motores_2026.xlsx"
    if not audit_path.exists():
        return {}
    df = pd.read_excel(audit_path)
    motores = ["DeepAR", "Prophet", "Stacking", "Ensemble"]
    smape_cols = [f"smape_2026_{m.lower()}" for m in motores]
    if not all(c in df.columns for c in smape_cols):
        return {}
    have_mase = all(f"mase_2026_{m.lower()}" in df.columns for m in motores)

    def _deployed(sub: pd.DataFrame, prefix: str) -> pd.Series:
        vals = []
        for _, row in sub.iterrows():
            motor = row.get("modelo_produccion")
            if pd.notna(motor):
                vals.append(row.get(f"{prefix}_{str(motor).lower()}"))
        return pd.Series(vals, dtype="float64") if vals else pd.Series(dtype="float64")

    def _agg(sub: pd.DataFrame) -> dict[str, Any]:
        n = int(sub[smape_cols].notna().any(axis=1).sum())
        motores_out: dict[str, Any] = {}
        for m in motores:
            sc = f"smape_2026_{m.lower()}"
            mc = f"mase_2026_{m.lower()}"
            motores_out[m] = _metric_summary(
                sub[sc], sub[mc] if (have_mase and mc in sub.columns) else pd.Series(dtype=float)
            )
        motores_out["Productivo"] = _metric_summary(
            _deployed(sub, "smape_2026"),
            _deployed(sub, "mase_2026") if have_mase else pd.Series(dtype=float),
        )
        return {"n": n, "motores": motores_out}

    pads = ["Alzheimer", "Depresion", "Parkinson"]
    neuro = df[df["padecimiento"].isin(pads)]
    por_pad = {
        pad: _agg(neuro[neuro["padecimiento"] == pad])
        for pad in pads
        if (neuro["padecimiento"] == pad).any()
    }
    result: dict[str, Any] = {
        "anio": 2026,
        "orden_motores": motores,
        "tiene_mase": bool(have_mase),
        "por_pad": por_pad,
        "global": _agg(neuro),
    }
    nsem = pd.to_numeric(neuro.get("n_semanas_real_2026"), errors="coerce").dropna()
    if len(nsem):
        result["n_semanas"] = int(nsem.max())
    dengue = _rendimiento_dengue()
    if dengue:
        result["dengue"] = dengue
    return result


def build_static_data() -> dict[str, Any]:
    """Datos estaticos del proyecto."""
    equipo = [
        {
            "nombre": "Javier Augusto Rebull Saucedo",
            "apodo": "JARS",
            "matricula": "A01795838",
            "rol": "Líder técnico y arquitecto principal del pipeline MLOps",
            "empleo": "Senior Associate Developer en Santander Bank US",
            "commits": 820,
            "aliases": [
                "javier",
                "javi",
                "jar",
                "jars",
                "rebull",
                "rebull saucedo",
                "javier rebull",
                "javier augusto",
            ],
        },
        {
            "nombre": "Juan Carlos Perez Nava",
            "apodo": "Jarcos",
            "matricula": "A01795941",
            "rol": "EDA, feature engineering y modelo Prophet base",
            "empleo": "Jefe de Área en el Instituto Mexicano del Seguro Social (IMSS)",
            "commits": 288,
            "aliases": [
                "juan",
                "juan carlos",
                "jarcos",
                "perez nava",
                "perez",
                "nava",
                "juan perez",
            ],
        },
        {
            "nombre": "Luis Gerardo Sanchez Salazar",
            "apodo": "Jerry",
            "matricula": "A01232963",
            "rol": "Diseño, desarrollo y optimización del dashboard",
            "empleo": "Senior Controls Engineer en Tesla",
            "commits": 201,
            "aliases": [
                "luis",
                "luis gerardo",
                "jerry",
                "sanchez salazar",
                "sanchez",
                "salazar",
                "luis sanchez",
                "gerardo",
            ],
        },
    ]

    padecimiento_info = {
        "Depresion": {
            "cie": "F32",
            "nombre_completo": "Episodio depresivo",
            "descripcion": (
                "Trastorno del estado de ánimo caracterizado por tristeza persistente, "
                "pérdida de interés, fatiga y alteraciones del sueño. Principal causa "
                "de discapacidad a nivel mundial según la OMS."
            ),
            "efectos": [
                "Deterioro cognitivo",
                "Alteraciones del apetito",
                "Insomnio o hipersomnia",
                "Mayor riesgo cardiovascular",
                "Debilitamiento del sistema inmunológico",
            ],
            "nota_mexico": (
                "Padecimiento con mayor incidencia de los tres. Afecta predominantemente "
                "a mujeres (proporción ~3:1) con estacionalidad marcada post-vacacional."
            ),
        },
        "Parkinson": {
            "cie": "G20",
            "nombre_completo": "Enfermedad de Parkinson",
            "descripcion": (
                "Trastorno neurodegenerativo progresivo por pérdida de neuronas "
                "dopaminérgicas. Temblor en reposo, rigidez muscular, bradicinesia "
                "e inestabilidad postural."
            ),
            "efectos": [
                "Temblores involuntarios",
                "Rigidez muscular",
                "Dificultad para caminar",
                "Problemas de deglución",
                "Trastornos del sueño",
                "Deterioro cognitivo avanzado",
            ],
            "nota_mexico": (
                "Incidencia moderada. Afecta ligeramente más a hombres, prevalencia "
                "crece con la edad. Estados del norte con tasas más elevadas."
            ),
        },
        "Alzheimer": {
            "cie": "G30",
            "nombre_completo": "Enfermedad de Alzheimer",
            "descripcion": (
                "Forma más común de demencia. Enfermedad neurodegenerativa progresiva que "
                "destruye neuronas, afectando memoria, pensamiento y comportamiento."
            ),
            "efectos": [
                "Pérdida progresiva de memoria",
                "Desorientación temporal y espacial",
                "Dificultad para planificar",
                "Cambios de personalidad",
                "Pérdida de autonomía",
                "Deterioro del lenguaje",
            ],
            "nota_mexico": (
                "Menor incidencia de los tres, tendencia creciente por envejecimiento "
                "poblacional. Jalisco, Chihuahua y Sinaloa con tasas más altas. "
                "La baja frecuencia hace que una diferencia de pocos casos pese mucho en el "
                "error porcentual."
            ),
        },
        "Dengue": {
            "cie": "A97",
            "nombre_completo": "Dengue",
            "descripcion": (
                "Arbovirosis transmitida por el mosquito Aedes aegypti, con estacionalidad "
                "climática anual (la carga vive en las semanas 27-52, época de lluvias) y "
                "grandes brotes epidémicos cada cuatro a cinco años. Puede evolucionar a "
                "dengue grave (hemorrágico)."
            ),
            "efectos": [
                "Fiebre alta súbita",
                "Dolor articular y muscular intenso",
                "Cefalea y dolor retroocular",
                "Erupción cutánea",
                "Hemorragias y choque en el dengue grave",
            ],
            "nota_mexico": (
                "Endémico en el sureste tropical y las costas (Jalisco, Veracruz, Chiapas y "
                "Guerrero concentran la carga); el centro-altiplano (Ciudad de México, Tlaxcala) "
                "no registra transmisión confirmada. 2024 fue la mayor epidemia en las Américas. "
                "Se modela como conteos absolutos (no tasa), con DeepAR y Prophet en producción."
            ),
        },
    }

    training_config = {
        "fecha_corte": "2025-01-01",
        "horizonte": 52,
        "series_totales": 333,
        "geografias": 37,
        "modelos": {
            "Prophet": {
                "cv_folds": 4,
                "test_size": 53,
                "cv_weights": [0.5, 0.75, 1.0, 1.25],
                "estacionalidad": "multiplicativa (Depresion, Parkinson), aditiva (Alzheimer)",
                "grid": {
                    "Depresion": "changepoint_prior_scale=[0.05,0.1,0.5], seasonality_prior_scale=[1,5,10]",
                    "Parkinson": "changepoint_prior_scale=[0.01,0.05,0.1], seasonality_prior_scale=[0.5,1,5]",
                    "Alzheimer": "changepoint_prior_scale=[0.01,0.05,0.1], seasonality_prior_scale=[0.5,1,5]",
                },
            },
            "DeepAR": {
                "context_length": 104,
                "prediction_length": 52,
                "epochs": 300,
                "early_stopping_patience": 15,
                "capas": "2 LSTM, 40 celdas",
                "dropout": 0.1,
                "learning_rate": 0.001,
                "batch_size": 32,
            },
            "Ensemble": {
                "componentes": "Prophet + XGBoost",
                "oof_cutoff": "2024-01-01",
                "xgb_cv_splits": 4,
                "xgb_test_size": 26,
                "xgb_params": "n_estimators=500, max_depth=4, lr=0.05, subsample=0.8",
            },
            "Stacking": {
                "componentes": "Prophet + ETS + LightGBM + Ridge",
                "oof_cutoff": "2024-01-01",
                "oof_folds": 4,
                "min_train": 104,
                "meta_learner": "Ridge con pesos no negativos",
                "expertos": ["ProphetExpert", "ETSExpert", "LGBMExpert"],
            },
        },
        "eventos": {
            "covid": {
                "inicio": "2020-03-23",
                "fin": "2022-09-22",
                "duracion_semanas": 130,
            },
            "tabasco_regimen": {
                "fecha": "2023-01-09",
                "duracion_dias": 365,
                "padecimiento": "Depresion",
            },
        },
    }

    definiciones = {
        "SMAPE": "Symmetric Mean Absolute Percentage Error. Métrica primaria de selección (0-200%). Menor es mejor.",
        "MASE": "Mean Absolute Scaled Error. Métrica de desempate (umbral 5%). Menor es mejor. <1 supera naive.",
        "RMSE": "Root Mean Squared Error. Segundo desempate. Sensible a errores grandes.",
        "MAE": "Mean Absolute Error. Error promedio absoluto en unidades de casos.",
        "Overfitting": "Ratio smape_test/smape_train. Alto (>2×), Moderado (>1.3×), OK.",
        "Leakage": "smape_train < 0.5% indica posible fuga de datos del test al train.",
        "Fallback regional": "Serie con incidencia insuficiente (<5 casos/52sem) usa el modelo de su región INEGI.",
        "Cross Validation": "Validación cruzada temporal con ventanas deslizantes (time series split).",
        "Horizonte": "Período de pronóstico: 52 semanas hacia adelante desde la fecha de corte.",
        "CIE-10": "Clasificación Internacional de Enfermedades, 10a revisión (OMS).",
    }

    regiones = {
        "Metropolitana alta": [
            "Ciudad de México",
            "Jalisco",
            "México",
            "Nuevo León",
        ],
        "Urbana media": [
            "Aguascalientes",
            "Baja California",
            "Baja California Sur",
            "Chihuahua",
            "Coahuila",
            "Colima",
            "Durango",
            "Guanajuato",
            "Morelos",
            "Querétaro",
            "San Luis Potosí",
            "Sinaloa",
            "Sonora",
            "Tamaulipas",
            "Zacatecas",
        ],
        "Rural / dispersa": [
            "Guerrero",
            "Hidalgo",
            "Michoacán",
            "Nayarit",
            "Puebla",
            "Tlaxcala",
            "Veracruz",
        ],
        "Sur-Sureste vulnerable": [
            "Campeche",
            "Chiapas",
            "Oaxaca",
            "Quintana Roo",
            "Tabasco",
            "Yucatán",
        ],
    }

    infra = {
        "tests": 855,
        "lineas_codigo": 13000,
        "cobertura": 92,
        "archivos_test": 46,
        "evaluaciones_totales": 1332,
        "ci_cd": "GitHub Actions (lint + typecheck + tests)",
        "sagemaker": "ml.g4dn.xlarge (NVIDIA T4), cuenta 564141855321",
        "bucket_s3": "s3://epiforecast-mx-data",
    }

    return {
        "equipo": equipo,
        "padecimiento_info": padecimiento_info,
        "training_config": training_config,
        "definiciones": definiciones,
        "regiones": regiones,
        "infra": infra,
    }


def _fill_horizon_dates(knowledge: dict[str, Any], cache: ProjectDataCache) -> None:
    """Rellena horizonte_inicio/horizonte_fin/ultimo_entrenamiento en training_config.

    kb.js (forecastDateRange) los lee para mostrar las fechas reales del
    horizonte de pronostico; sin ellos el bot degrada a "52 semanas" sin fechas.
    """
    tc = knowledge.get("training_config")
    if not isinstance(tc, dict):
        return
    p = Path("reports/forecasts/prophet/all_forecast_prophet.csv")
    if not p.exists():
        return
    df = pd.read_csv(p, usecols=["ds"], low_memory=False)
    df["ds"] = pd.to_datetime(df["ds"])
    fin = df["ds"].max()
    inicio = None
    bol = cache.boletin
    if bol is not None and not bol.empty:
        bol = filter_neuro(bol)
        anio = int(bol["Anio"].max())
        sem = int(bol.loc[bol["Anio"] == anio, "Semana"].max())
        last_real = ds_de_semana_boletin(anio, sem)
        fut = df.loc[df["ds"] > last_real, "ds"]
        if not fut.empty:
            inicio = fut.min()
    if inicio is not None:
        tc["horizonte_inicio"] = inicio.date().isoformat()
    if pd.notna(fin):
        tc["horizonte_fin"] = fin.date().isoformat()
    tc["ultimo_entrenamiento"] = datetime.fromtimestamp(p.stat().st_mtime).date().isoformat()


def build_padecimientos() -> dict[str, Any]:
    """Manifiesto de roster para el front-end (EPIC 4), desde el registry central.

    Solo emite padecimientos ``lifecycle=published`` (Obesidad ``configured`` queda
    invisible). Los conteos salen del **catálogo canónico** (432, no el 435 inflado).
    El JS construirá roster/colores/aliases/conteos desde aquí (refactor JS = gate de
    deploy con verificación visual). Es aditivo: no cambia las secciones existentes.
    """
    from epiforecast import registry
    from epiforecast.catalog import build_production_catalog

    df, counts = build_production_catalog()
    if counts.gallery_item_count is None:
        # Sin galería no hay conteo de gráficos: se cuenta en lo publicado, nunca se supone.
        raise SystemExit(
            "rosters.gallery_items: no se encontró la galería (Reports/index.html). Apunta "
            "EPIFORECAST_DASHBOARD al dashboard generado antes de construir el knowledge."
        )
    by_id = df.groupby("disease_id").size().to_dict()

    pads: list[dict[str, Any]] = []
    for d in registry.get_registry().diseases:
        if d.lifecycle != "published":
            continue
        pads.append(
            {
                "id": d.id,
                "pad_ascii": d.artifact_key,
                "pad_display": d.display_name,
                "cie": d.cie_codes[0] if d.cie_codes else None,
                "color": d.web.get("color"),
                "label": d.web.get("label"),
                "cohorte": d.profile.cohorte_id,
                "aggregate_national": d.aggregate_national,
                "aliases": list(d.aliases),
                "n_models": int(by_id.get(d.id, 0)),
                "nombre_completo": d.web.get("nombre_completo"),
            }
        )
    return {
        "padecimientos": pads,
        "rosters": {
            "total_series": counts.production_series_count,
            "gallery_items": counts.gallery_item_count,
            "por_cohorte": counts.por_cohorte,
            "national_aggregators": sum(p["n_models"] for p in pads if p["aggregate_national"]),
            "n_padecimientos": len(pads),
        },
    }


def main(argv: list[str] | None = None) -> None:
    """Entry point: genera knowledge.json (en `--out`, o en la ruta legacy)."""
    args = _parse_args(argv)
    destino = args.out
    print("Cargando datos del proyecto...")
    cache = ProjectDataCache()
    kb = KnowledgeBase(cache)

    # Forzar calculo de stats
    stats = kb._ensure_stats()
    # La validación semanal ya no se resume desde la tabla: viene del seguimiento posterior al
    # corte (misma semana a ambos lados), en su propia sección.
    stats.pop("validacion_semanal", None)
    prod_models = _normalize_keys(build_prod_models(cache))

    knowledge: dict[str, Any] = {
        "_generated": datetime.now().isoformat(),
        "_version": "1.0",
        "stats": _normalize_keys(stats),
        "prod_models": prod_models,
        "boletin": _normalize_keys(build_boletin(cache)),
        # Dengue: sección propia SIN normalizar (preserva tildes/eñes en estados y notas).
        "dengue": build_dengue_section(),
        # Rendimiento 2026 por padecimiento × motor (SMAPE + MASE). Claves ASCII, sin normalizar.
        # En la ronda W37 son métricas de selección: `separa_metricas` lo retira del público.
        "rendimiento_2026": build_rendimiento_2026(),
        # Manifiesto de roster data-driven (EPIC 4): solo published, conteos canónicos.
        **build_padecimientos(),
        **build_static_data(),
    }
    if args.seguimiento is not None:
        knowledge["seguimiento_post_corte"] = carga_seguimiento(args.seguimiento, prod_models)
        # Tabla semanal del EpiBot («Seguimiento del pronóstico con corte W37»). Sin el
        # seguimiento no se publica: la tabla anterior mezclaba ajuste y seguimiento.
        knowledge["weekly_comparison"] = carga_semanal(
            args.seguimiento.parent / "seguimiento_semanal_nacional.json",
            knowledge["seguimiento_post_corte"],
        )
        # Indicador canónico «Notificaciones previstas · agregado estatal neuro» (sin
        # normalizar: conserva tildes); stats lleva sólo los valores que ya mostraba.
        ag = carga_agregado(
            args.seguimiento.parent / "agregado_estatal_neuro.json",
            knowledge["seguimiento_post_corte"],
        )
        aplica_agregado(knowledge["stats"], ag)
        knowledge["agregado_estatal_neuro"] = {k: v for k, v in ag.items() if k != "por_sexo"} | {
            "por_padecimiento": ag["por_sexo"]["general"]["por_padecimiento"],
            "series": ag["por_sexo"]["general"]["series_incluidas"],
            "suma_de_totales_redondeados_por_serie": ag["por_sexo"]["general"][
                "suma_de_totales_redondeados_por_serie"
            ],
            "por_sexo": {
                sx: {k: v for k, v in d.items() if k != "series_incluidas"}
                for sx, d in ag["por_sexo"].items()
            },
        }
    _fill_horizon_dates(knowledge, cache)

    # Ronda W37: las métricas por serie y motor son el error de la ventana de selección W28–W37.
    # Salen del knowledge público y quedan sólo en la evidencia de revisión, rotuladas.
    knowledge, retiradas = separa_metricas(knowledge)
    if args.evidencia_metricas is not None:
        escribe_evidencia(retiradas, args.evidencia_metricas)
    escribe_knowledge(knowledge, destino)

    size_kb = destino.stat().st_size / 1024
    print(f"Generado: {destino} ({size_kb:.0f} KB)")
    print(f"  - {len(knowledge.get('prod_models', []))} modelos de produccion")
    print(f"  - Stats: {len(stats)} claves")
    print(f"  - Boletin: {len(knowledge.get('boletin', {}))} secciones")


if __name__ == "__main__":
    main()

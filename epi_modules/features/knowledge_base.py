"""Base de conocimiento del proyecto EpiForecast-MX.

Pre-computa estadisticas profundas desde los datos reales del proyecto
y responde preguntas con precision sin necesidad de IA externa.
"""

import contextlib
import logging
import re
from typing import Any

from .data_cache import ProjectDataCache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalizacion de texto
# ---------------------------------------------------------------------------

_ACCENT_MAP = str.maketrans(
    "aeiouAEIOUNn",
    "aeiouAEIOUNn",
    "",
)

# Map accented -> unaccented for matching
_STRIP_ACCENTS = str.maketrans(
    {
        "\u00e1": "a",
        "\u00e9": "e",
        "\u00ed": "i",
        "\u00f3": "o",
        "\u00fa": "u",
        "\u00c1": "A",
        "\u00c9": "E",
        "\u00cd": "I",
        "\u00d3": "O",
        "\u00da": "U",
        "\u00f1": "n",
        "\u00d1": "N",
    }
)


def _norm(text: str) -> str:
    """Normaliza texto: minusculas, sin acentos, sin puntuacion."""
    t = text.lower().translate(_STRIP_ACCENTS)
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


# ---------------------------------------------------------------------------
# Deteccion de entidades en la pregunta
# ---------------------------------------------------------------------------

_ESTADOS_ALIAS: dict[str, str] = {
    "cdmx": "Ciudad de Mexico",
    "ciudad de mexico": "Ciudad de Mexico",
    "edomex": "Mexico",
    "estado de mexico": "Mexico",
    "nuevo leon": "Nuevo Leon",
    "san luis potosi": "San Luis Potosi",
    "baja california sur": "Baja California Sur",
    "baja california": "Baja California",
    "quintana roo": "Quintana Roo",
    # Regiones
    "region metropolitana alta": "Region Metropolitana alta",
    "metropolitana alta": "Region Metropolitana alta",
    "metropolitana": "Region Metropolitana alta",
    "region rural dispersa": "Region Rural - dispersa",
    "region rural": "Region Rural - dispersa",
    "rural dispersa": "Region Rural - dispersa",
    "region sur sureste vulnerable": "Region Sur-Sureste vulnerable",
    "region sur sureste": "Region Sur-Sureste vulnerable",
    "region sur": "Region Sur-Sureste vulnerable",
    "sur sureste": "Region Sur-Sureste vulnerable",
    "sureste vulnerable": "Region Sur-Sureste vulnerable",
    "region urbana media": "Region Urbana media",
    "urbana media": "Region Urbana media",
}

_PADECIMIENTO_ALIAS: dict[str, str] = {
    "depresion": "Depresion",
    "depression": "Depresion",
    "f32": "Depresion",
    "parkinson": "Parkinson",
    "g20": "Parkinson",
    "alzheimer": "Alzheimer",
    "g30": "Alzheimer",
}

_SEXO_ALIAS: dict[str, str] = {
    "hombres": "hombres",
    "hombre": "hombres",
    "masculino": "hombres",
    "mujeres": "mujeres",
    "mujer": "mujeres",
    "femenino": "mujeres",
    "general": "general",
}

_MODELO_ALIAS: dict[str, str] = {
    "prophet": "Prophet",
    "deepar": "DeepAR",
    "deep ar": "DeepAR",
    "ensemble": "Ensemble",
    "stacking": "Stacking",
    "xgboost": "Ensemble",
    "lightgbm": "Stacking",
}


def _match_entidad(search: str, entidad: str) -> bool:
    """Compara search normalizado contra entidad del DataFrame (con acentos)."""
    return _norm(search) in _norm(entidad)


def _extract_years(q: str) -> list[int]:
    """Extrae anos mencionados en la pregunta (2014-2026)."""
    return sorted({int(m) for m in re.findall(r"\b(20[12]\d)\b", q) if 2014 <= int(m) <= 2026})


def _extract_weeks(q: str) -> list[int]:
    """Extrae semanas epidemiologicas (1-53) mencionadas en la pregunta."""
    weeks: list[int] = []
    for m in re.finditer(r"semana\s+(\d{1,2})", q):
        w = int(m.group(1))
        if 1 <= w <= 53:
            weeks.append(w)
    return sorted(set(weeks))


def _detect_entities(q: str) -> dict[str, str | None]:
    """Detecta padecimiento, estado, sexo y modelo en la pregunta."""
    qn = _norm(q)
    result: dict[str, str | None] = {
        "padecimiento": None,
        "estado": None,
        "sexo": None,
        "modelo": None,
    }
    result["_years"] = _extract_years(qn)  # type: ignore[assignment]
    result["_weeks"] = _extract_weeks(qn)  # type: ignore[assignment]
    for alias, canon in _PADECIMIENTO_ALIAS.items():
        if alias in qn:
            result["padecimiento"] = canon
            break
    for alias, canon in sorted(_ESTADOS_ALIAS.items(), key=lambda x: -len(x[0])):
        if alias in qn:
            result["estado"] = canon
            break
    if result["estado"] is None:
        # Intenta buscar cualquier nombre de estado
        estados_32 = [
            "aguascalientes",
            "baja california",
            "campeche",
            "chiapas",
            "chihuahua",
            "coahuila",
            "colima",
            "durango",
            "guanajuato",
            "guerrero",
            "hidalgo",
            "jalisco",
            "michoacan",
            "morelos",
            "nayarit",
            "oaxaca",
            "puebla",
            "queretaro",
            "sinaloa",
            "sonora",
            "tabasco",
            "tamaulipas",
            "tlaxcala",
            "veracruz",
            "yucatan",
            "zacatecas",
        ]
        for est in estados_32:
            if est in qn:
                result["estado"] = est.title()
                break
    if result["estado"] is None and "nacional" in qn:
        result["estado"] = "Nacional"
    for alias, canon in _SEXO_ALIAS.items():
        if alias in qn:
            result["sexo"] = canon
            break
    for alias, canon in _MODELO_ALIAS.items():
        if alias in qn:
            result["modelo"] = canon
            break
    return result


# ---------------------------------------------------------------------------
# KnowledgeBase: cerebro del proyecto
# ---------------------------------------------------------------------------


class KnowledgeBase:
    """Computa y cachea estadisticas profundas del proyecto."""

    def __init__(self, cache: ProjectDataCache) -> None:
        self.cache = cache
        self._stats: dict[str, Any] | None = None

    def _ensure_stats(self) -> dict[str, Any]:
        """Computa todas las estadisticas si no estan cacheadas."""
        if self._stats is not None:
            return self._stats

        stats: dict[str, Any] = {}
        prod = self.cache.prod_models

        if prod is None or prod.empty:
            self._stats = stats
            return stats

        df = prod.copy()

        # --- GLOBAL ---
        stats["total_modelos"] = len(df)
        stats["modelo_activo"] = self.cache.modelo_activo

        # Distribucion por motor
        if "modelo_produccion" in df.columns:
            mc = df["modelo_produccion"].value_counts()
            stats["dist_motor"] = {str(k): int(v) for k, v in mc.items()}
            stats["motor_ganador"] = str(mc.index[0])
            stats["motor_ganador_n"] = int(mc.iloc[0])
            stats["motor_ganador_pct"] = round(mc.iloc[0] / len(df) * 100, 1)

        # Metricas globales
        for met in ("smape_prod", "mase_prod", "rmse_prod", "mae_prod"):
            if met in df.columns:
                col = df[met].dropna()
                if not col.empty:
                    stats[f"{met}_mean"] = round(col.mean(), 2)
                    stats[f"{met}_median"] = round(col.median(), 2)
                    stats[f"{met}_min"] = round(col.min(), 2)
                    stats[f"{met}_max"] = round(col.max(), 2)
                    stats[f"{met}_std"] = round(col.std(), 2)

        # --- POR PADECIMIENTO ---
        stats["por_pad"] = {}
        if "padecimiento" in df.columns:
            for pad in df["padecimiento"].unique():
                sub = df[df["padecimiento"] == pad]
                ps: dict[str, Any] = {"n": len(sub)}
                for met in ("smape_prod", "mase_prod", "rmse_prod", "mae_prod"):
                    if met in sub.columns:
                        col = sub[met].dropna()
                        if not col.empty:
                            ps[f"{met}_mean"] = round(col.mean(), 2)
                            ps[f"{met}_median"] = round(col.median(), 2)
                if "modelo_produccion" in sub.columns:
                    mc = sub["modelo_produccion"].value_counts()
                    ps["dist_motor"] = {str(k): int(v) for k, v in mc.items()}
                    ps["motor_ganador"] = str(mc.index[0])
                    ps["motor_ganador_n"] = int(mc.iloc[0])
                if "casos_52_semanas_futuro" in sub.columns:
                    # Solo sumar 32 estados con sexo=general (sin Nacional ni regiones)
                    _gen = sub[(sub["sexo"] == "general") & (sub["entidad"] != "Nacional")]
                    if "entidad" in sub.columns:
                        _gen = _gen[
                            ~_gen["entidad"].str.startswith("Region", na=False)
                            & ~_gen["entidad"].str.startswith("region", na=False)
                        ]
                    ps["casos_futuro_total"] = (
                        int(_gen["casos_52_semanas_futuro"].sum()) if not _gen.empty else 0
                    )
                # Desglose por sexo dentro del padecimiento
                if "sexo" in sub.columns and "casos_52_semanas_futuro" in sub.columns:
                    pad_sexo: dict[str, Any] = {}
                    for sx in ("general", "hombres", "mujeres"):
                        sx_sub = sub[sub["sexo"] == sx]
                        if sx_sub.empty:
                            continue
                        sx_info: dict[str, Any] = {"n": len(sx_sub)}
                        sx_info["casos_total"] = int(sx_sub["casos_52_semanas_futuro"].sum())
                        # Casos a nivel nacional (la serie mas representativa)
                        nac = sx_sub[sx_sub["entidad"] == "Nacional"]
                        if not nac.empty:
                            sx_info["casos_nacional"] = int(nac["casos_52_semanas_futuro"].iloc[0])
                        for met in ("smape_prod", "mase_prod"):
                            if met in sx_sub.columns:
                                col = sx_sub[met].dropna()
                                if not col.empty:
                                    sx_info[f"{met}_mean"] = round(col.mean(), 2)
                                    sx_info[f"{met}_median"] = round(col.median(), 2)
                        pad_sexo[sx] = sx_info
                    if pad_sexo:
                        ps["por_sexo"] = pad_sexo

                stats["por_pad"][str(pad)] = ps

        # --- POR ESTADO ---
        stats["por_estado"] = {}
        if "entidad" in df.columns:
            for ent in df["entidad"].unique():
                sub = df[df["entidad"] == ent]
                es: dict[str, Any] = {"n": len(sub)}
                for met in ("smape_prod", "mase_prod"):
                    if met in sub.columns:
                        col = sub[met].dropna()
                        if not col.empty:
                            es[f"{met}_mean"] = round(col.mean(), 2)
                if "modelo_produccion" in sub.columns:
                    mc = sub["modelo_produccion"].value_counts()
                    es["dist_motor"] = {str(k): int(v) for k, v in mc.items()}
                if "casos_52_semanas_futuro" in sub.columns:
                    es["casos_futuro"] = int(sub["casos_52_semanas_futuro"].sum())
                stats["por_estado"][str(ent)] = es

        # --- DIAGNOSTICOS ---
        if "overfitting" in df.columns:
            ov = df["overfitting"].astype(str)
            stats["overfitting_ok"] = int(ov.str.startswith("OK").sum())
            stats["overfitting_moderado"] = int(ov.str.contains("Moderado", na=False).sum())
            stats["overfitting_alto"] = int(ov.str.contains("Alto", na=False).sum())
            stats["overfitting_nd"] = int(ov.str.contains("N/D|nan", na=False).sum())
        if "leakage" in df.columns:
            lk = df["leakage"].astype(str)
            stats["leakage_ok"] = int(lk.str.startswith("OK").sum())
            stats["leakage_sospechoso"] = int(lk.str.contains("Sospechoso", na=False).sum())

        # --- FALLBACK REGIONAL ---
        if "tipo_modelo" in df.columns:
            fb = df[df["tipo_modelo"] != "propio"]
            stats["fallback_n"] = len(fb)
            if not fb.empty:
                stats["fallback_detalles"] = [
                    f"{r['padecimiento']} - {r['entidad']} ({r.get('sexo', '?')})"
                    for _, r in fb.iterrows()
                ]

        # --- TOP / BOTTOM SMAPE ---
        if "smape_prod" in df.columns and "entidad" in df.columns:
            # Mejor SMAPE por serie
            sorted_df = df.sort_values("smape_prod")
            stats["top5_smape"] = [
                {
                    "entidad": str(r["entidad"]),
                    "padecimiento": str(r.get("padecimiento", "?")),
                    "sexo": str(r.get("sexo", "?")),
                    "smape": round(r["smape_prod"], 2),
                    "motor": str(r.get("modelo_produccion", "?")),
                }
                for _, r in sorted_df.head(5).iterrows()
            ]
            stats["bottom5_smape"] = [
                {
                    "entidad": str(r["entidad"]),
                    "padecimiento": str(r.get("padecimiento", "?")),
                    "sexo": str(r.get("sexo", "?")),
                    "smape": round(r["smape_prod"], 2),
                    "motor": str(r.get("modelo_produccion", "?")),
                }
                for _, r in sorted_df.tail(5).iterrows()
            ]

        # --- POR SEXO ---
        stats["por_sexo"] = {}
        if "sexo" in df.columns:
            for sx in df["sexo"].unique():
                sub = df[df["sexo"] == sx]
                ss: dict[str, Any] = {"n": len(sub)}
                if "smape_prod" in sub.columns:
                    ss["smape_mean"] = round(sub["smape_prod"].mean(), 2)
                    ss["smape_median"] = round(sub["smape_prod"].median(), 2)
                if "mase_prod" in sub.columns:
                    ss["mase_mean"] = round(sub["mase_prod"].mean(), 2)
                stats["por_sexo"][str(sx)] = ss

        # --- METRICAS POR MOTOR (comparativa completa) ---
        stats["por_motor"] = {}
        for motor_prefix in ("prophet", "deepar", "ensemble", "stacking"):
            sm_col = f"{motor_prefix}_smape"
            ms_col = f"{motor_prefix}_mase"
            rm_col = f"{motor_prefix}_rmse"
            ma_col = f"{motor_prefix}_mae"
            ms_data: dict[str, Any] = {}
            for col_name, label in [
                (sm_col, "smape"),
                (ms_col, "mase"),
                (rm_col, "rmse"),
                (ma_col, "mae"),
            ]:
                if col_name in df.columns:
                    col = df[col_name].dropna()
                    if not col.empty:
                        ms_data[f"{label}_mean"] = round(col.mean(), 2)
                        ms_data[f"{label}_median"] = round(col.median(), 2)
            if ms_data:
                stats["por_motor"][motor_prefix.title()] = ms_data
                if motor_prefix == "deepar":
                    stats["por_motor"]["DeepAR"] = ms_data
                    del stats["por_motor"]["Deepar"]

        # --- VALIDACION SEMANAL ---
        if "pron_sem_previa" in df.columns and "realidad_sem_previa" in df.columns:
            pron = df["pron_sem_previa"].dropna()
            real = df["realidad_sem_previa"].dropna()
            if not pron.empty and not real.empty:
                err_abs = (pron - real).abs()
                stats["validacion_semanal"] = {
                    "error_abs_medio": round(err_abs.mean(), 2),
                    "error_abs_mediano": round(err_abs.median(), 2),
                }

        # --- PRECISION HISTORICA ---
        if "precision_historica" in df.columns:
            try:
                prec = df["precision_historica"].astype(str).str.rstrip("%").astype(float)
                stats["precision_historica_mean"] = round(prec.mean(), 1)
                stats["precision_historica_median"] = round(prec.median(), 1)
            except Exception:
                pass

        # --- PRONOSTICO ACUMULADO ---
        if "casos_52_semanas_futuro" in df.columns:
            # Solo sumar 32 estados con sexo=general (sin Nacional ni regiones)
            _gen = df[(df["sexo"] == "general") & (df["entidad"] != "Nacional")]
            if "entidad" in df.columns:
                _gen = _gen[
                    ~_gen["entidad"].str.startswith("Region", na=False)
                    & ~_gen["entidad"].str.startswith("region", na=False)
                ]
            stats["pronostico_total"] = (
                int(_gen["casos_52_semanas_futuro"].sum()) if not _gen.empty else 0
            )

        # --- DEMOGRAFICA HISTORICA (boletin) ---
        bol = self.cache.boletin
        if bol is not None and not bol.empty:
            demo_hist: dict[str, dict[str, Any]] = {}
            pad_col = "Padecimiento" if "Padecimiento" in bol.columns else None
            ah_col = "Acumulado_hombres" if "Acumulado_hombres" in bol.columns else None
            am_col = "Acumulado_mujeres" if "Acumulado_mujeres" in bol.columns else None
            if pad_col and ah_col and am_col:
                for pad in bol[pad_col].dropna().unique():
                    sub = bol[bol[pad_col] == pad]
                    if sub.empty:
                        continue
                    idx = sub.groupby(["Anio", "Entidad"])["Semana"].idxmax()
                    last = sub.loc[idx]
                    h_total = int(last[ah_col].sum())
                    m_total = int(last[am_col].sum())
                    total = h_total + m_total
                    if total > 0:
                        demo_hist[str(pad)] = {
                            "hombres": h_total,
                            "mujeres": m_total,
                            "total": total,
                            "pct_h": round(h_total / total * 100, 1),
                            "pct_m": round(m_total / total * 100, 1),
                            "ratio_mh": round(m_total / h_total, 2) if h_total > 0 else 0,
                        }
            stats["demo_historica"] = demo_hist

        # --- INFRAESTRUCTURA ---
        stats["tests"] = 855
        stats["lineas_codigo"] = 13000
        stats["cobertura"] = 92
        stats["archivos_test"] = 46
        stats["horizonte"] = 52
        stats["evaluaciones_totales"] = 1332

        self._stats = stats
        return stats

    def invalidate(self) -> None:
        """Fuerza re-calculo de stats."""
        self._stats = None

    # ------------------------------------------------------------------
    # Motor de respuesta inteligente
    # ------------------------------------------------------------------

    def answer(self, query: str) -> str | None:
        """Intenta responder la pregunta con datos reales del proyecto."""
        s = self._ensure_stats()
        if not s:
            return None

        q = _norm(query)
        entities = _detect_entities(query)

        # Intentar cada handler en orden de especificidad
        handlers: list[tuple[str, ...]] = [
            # Equipo / integrantes del proyecto
            ("_answer_equipo",),
            # Contexto temporal (fecha, semana epi, cobertura datos)
            ("_answer_temporal",),
            # Meta del proyecto (padecimientos, regiones, franja COVID, alcance)
            ("_answer_proyecto_meta",),
            # Configuracion de entrenamiento, hiperparametros, fechas de corte
            ("_answer_training_config",),
            # Semana actual / siguiente / casos nuevos
            ("_answer_semana_actual",),
            # Que es un padecimiento (descripcion medica)
            ("_answer_que_es_padecimiento",),
            # Consultas historicas al boletin epidemiologico
            ("_answer_boletin",),
            # Consultas especificas (padecimiento + estado + metrica)
            ("_answer_specific_series",),
            # Consultas por estado
            ("_answer_estado",),
            # Consultas por padecimiento
            ("_answer_padecimiento",),
            # Consultas por modelo/motor
            ("_answer_motor",),
            # Composicion demografica por padecimiento
            ("_answer_demografica",),
            # Consultas por sexo/genero
            ("_answer_sexo",),
            # Metricas globales
            ("_answer_metrica_global",),
            # Rankings
            ("_answer_ranking",),
            # Diagnosticos
            ("_answer_diagnosticos",),
            # Validacion
            ("_answer_validacion",),
            # Infraestructura
            ("_answer_infra",),
            # Conteos y distribucion
            ("_answer_conteo",),
            # Pronostico acumulado
            ("_answer_pronostico",),
            # Definiciones
            ("_answer_definicion",),
        ]

        for (method_name,) in handlers:
            method = getattr(self, method_name)
            result = method(q, entities, s)
            if result:
                return result

        return None

    # ------------------------------------------------------------------
    # Handlers individuales
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # Equipo / integrantes del proyecto
    # ------------------------------------------------------------------

    _EQUIPO = {
        "javier": {
            "nombre": "Javier Augusto Rebull Saucedo",
            "apodo": "JARS",
            "matricula": "A01795838",
            "rol": "Líder técnico y arquitecto principal del pipeline MLOps",
            "empleo": "Senior Associate Developer en Santander Bank US",
            "commits": 820,
            "desc": (
                "Diseñó la arquitectura completa del proyecto: factory de modelos, "
                "configuración dinámica con OmegaConf, pipeline de datos, sistema de "
                "evaluación multi-métrica y la consola interactiva EPI. Responsable "
                "de la integración de Prophet, DeepAR, Ensemble y Stacking."
            ),
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
        "juan": {
            "nombre": "Juan Carlos Pérez Nava",
            "apodo": "Jarcos",
            "matricula": "A01795941",
            "rol": "EDA, feature engineering y modelo Prophet base",
            "empleo": "Jefe de Área en el Instituto Mexicano del Seguro Social (IMSS)",
            "commits": 288,
            "desc": (
                "Responsable del análisis exploratorio de datos (EDA), feature "
                "engineering y el modelo Prophet base. Su conocimiento institucional "
                "del IMSS fue clave para el diseño del pipeline de extracción, las "
                "reglas de negocio y la validación del boletín epidemiológico."
            ),
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
        "luis": {
            "nombre": "Luis Gerardo Sánchez Salazar",
            "apodo": "Jerry",
            "matricula": "A01232963",
            "rol": "Diseño, desarrollo y optimización del dashboard",
            "empleo": "Senior Controls Engineer en Tesla",
            "commits": 201,
            "desc": (
                "Responsable del diseño, desarrollo y optimización del dashboard "
                "interactivo (EpiForecast-IMSS-Dashboard). Modelado y transformación "
                "de datos para visualización en el dashboard. Su experiencia en "
                "ingeniería de control aportó rigor analítico al diseño de las "
                "visualizaciones y la presentación de resultados."
            ),
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
    }

    def _answer_equipo(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre los integrantes del equipo EpiForecast-MX."""
        # Preguntar por el equipo completo
        equipo_triggers = [
            "equipo",
            "integrantes",
            "miembros",
            "quienes son",
            "quienes hicieron",
            "quienes crearon",
            "quienes desarrollaron",
            "autores",
            "creadores",
        ]
        if any(t in q for t in equipo_triggers):
            lines = [
                "**Equipo EpiForecast-MX (Equipo 01)**\n",
                "Maestría en Inteligencia Artificial Aplicada · Tecnológico de Monterrey\n",
            ]
            for info in self._EQUIPO.values():
                lines.append(
                    f"- **{info['nombre']}** ({info['apodo']}) · {info['matricula']}\n"
                    f"  {info['rol']} · {info['empleo']}\n"
                    f"  {info['commits']} commits"
                )
            lines.append(
                "\nProyecto integrador para el IMSS: pronóstico epidemiológico "
                "multi-modelo de Depresión (F32), Parkinson (G20) y Alzheimer (G30)."
            )
            return "\n".join(lines)

        # Preguntar por un integrante específico
        person_triggers = [
            "quien es",
            "quien fue",
            "que hace",
            "que hizo",
            "conoces a",
            "dime de",
            "dime sobre",
            "hablame de",
            "cuentame de",
            "cuentame sobre",
        ]
        is_person_q = any(t in q for t in person_triggers)

        # También detectar nombre/apodo directo en preguntas cortas
        if not is_person_q and len(q.split()) > 3:
            return None

        # Buscar el match más largo para evitar colisiones (ej: "jar" vs "jarcos")
        best_info = None
        best_len = 0
        for info in self._EQUIPO.values():
            for alias in info["aliases"]:
                if alias in q and len(alias) > best_len:
                    best_len = len(alias)
                    best_info = info

        if best_info:
            info = best_info
            return (
                f"**{info['nombre']}**\n\n"
                f"- **Apodo:** {info['apodo']}\n"
                f"- **Matrícula:** {info['matricula']}\n"
                f"- **Rol:** {info['rol']}\n"
                f"- **Empleo actual:** {info['empleo']}\n"
                f"- **Commits:** {info['commits']}\n\n"
                f"{info['desc']}"
            )

        return None

    # ------------------------------------------------------------------
    # Contexto temporal (fecha, semana epi, cobertura de datos)
    # ------------------------------------------------------------------

    def _answer_temporal(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde preguntas sobre fecha, semana epidemiologica y cobertura temporal."""
        triggers = [
            "que dia",
            "que fecha",
            "fecha de hoy",
            "dia de hoy",
            "fecha actual",
            "semana epidemiologica",
            "semana epi",
            "en que semana",
            "que semana es",
            "que semana estamos",
            "semana estamos",
            "ultima semana",
            "ultimo dato",
            "hasta cuando",
            "hasta que fecha",
            "hasta que semana",
            "cobertura temporal",
            "rango de fecha",
            "periodo de dato",
            "desde cuando",
            "cuando inicia",
            "cuando empieza",
            "horizonte",
        ]
        if not any(t in q for t in triggers):
            return None

        from datetime import datetime, timedelta

        now = datetime.now()
        today = now.date()

        # Calcular semana epidemiologica (ISO week ~= epi week para Mexico)
        iso_year, iso_week, _ = today.isocalendar()

        lines: list[str] = []

        # --- Fecha actual ---
        is_date_q = any(
            t in q for t in ["que dia", "que fecha", "fecha de hoy", "dia de hoy", "fecha actual"]
        )
        if is_date_q:
            dias = [
                "lunes",
                "martes",
                "miércoles",
                "jueves",
                "viernes",
                "sábado",
                "domingo",
            ]
            meses = [
                "enero",
                "febrero",
                "marzo",
                "abril",
                "mayo",
                "junio",
                "julio",
                "agosto",
                "septiembre",
                "octubre",
                "noviembre",
                "diciembre",
            ]
            dia_sem = dias[today.weekday()]
            mes = meses[today.month - 1]
            lines.append(f"Hoy es **{dia_sem} {today.day} de {mes} de {today.year}**")
            lines.append(f"Semana epidemiológica: **{iso_week}** de {iso_year}")

        # --- Semana epidemiologica ---
        is_week_q = any(
            t in q
            for t in [
                "semana epidemiologica",
                "semana epi",
                "en que semana",
                "que semana es",
                "que semana estamos",
                "semana estamos",
            ]
        )
        if is_week_q and not is_date_q:
            lines.append(f"Estamos en la **semana epidemiológica {iso_week}** de {iso_year}")
            # Rango de la semana (lunes a domingo)
            lunes = today - timedelta(days=today.weekday())
            domingo = lunes + timedelta(days=6)
            lines.append(f"Del {lunes.strftime('%d/%m/%Y')} al {domingo.strftime('%d/%m/%Y')}")

        # --- Cobertura temporal de los datos ---
        is_coverage_q = any(
            t in q
            for t in [
                "ultima semana",
                "ultimo dato",
                "hasta cuando",
                "hasta que fecha",
                "hasta que semana",
                "cobertura temporal",
                "rango de fecha",
                "periodo de dato",
                "desde cuando",
                "cuando inicia",
                "cuando empieza",
            ]
        )
        if is_coverage_q:
            df_bol = self.cache.boletin
            if df_bol is not None and not df_bol.empty:
                min_year = int(df_bol["Anio"].min())
                max_year = int(df_bol["Anio"].max())
                max_week = int(df_bol[df_bol["Anio"] == max_year]["Semana"].max())
                min_week = int(df_bol[df_bol["Anio"] == min_year]["Semana"].min())
                total_rows = len(df_bol)

                if lines:
                    lines.append("")
                lines.append("**Cobertura del boletín epidemiológico**:")
                lines.append(f"- Desde: semana {min_week} de {min_year}")
                lines.append(f"- Hasta: **semana {max_week} de {max_year}**")
                lines.append(f"- Registros totales: {total_rows:,}")
                lines.append("- Padecimientos: Depresión (F32), Parkinson (G20), Alzheimer (G30)")
                lines.append("- Entidades: 32 estados + Nacional")

                # Rezago
                rezago = (
                    iso_week - max_week if max_year == iso_year else iso_week + (52 - max_week)
                )
                if rezago > 0:
                    lines.append(
                        f"- Rezago: ~{rezago} semana(s) respecto a la semana actual ({iso_week})"
                    )

            # Horizonte de pronostico
            tab = self.cache.tableau
            if tab is not None:
                import pandas as pd

                tab_ds = pd.to_datetime(tab["ds"])
                min_ds = tab_ds.min()
                max_ds = tab_ds.max()
                lines.append("\n**Cobertura del pronóstico (tableau)**:")
                lines.append(f"- Desde: {min_ds.strftime('%d/%m/%Y')}")
                lines.append(f"- Hasta: {max_ds.strftime('%d/%m/%Y')}")
                lines.append("- Horizonte: 52 semanas hacia adelante")
                lines.append("- Series: 333 (37 geo x 3 pad x 3 sexo)")

        # --- Horizonte ---
        if "horizonte" in q and not lines:
            lines.append(
                f"El horizonte de pronóstico es de **52 semanas** "
                f"(hasta enero {iso_year + 1} aproximadamente)."
            )

        # Siempre agregar contexto de semana epi si hay cualquier respuesta
        if lines and not is_date_q and not is_week_q:
            lines.insert(
                0,
                f"Fecha actual: {today.strftime('%d/%m/%Y')} (semana epidemiológica {iso_week})\n",
            )

        return "\n".join(lines) if lines else None

    # ------------------------------------------------------------------
    # Meta del proyecto: padecimientos, regiones, franja COVID, alcance
    # ------------------------------------------------------------------

    def _answer_proyecto_meta(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre alcance del proyecto: padecimientos, regiones, COVID."""
        # --- Padecimientos ---
        pad_triggers = [
            "que padecimiento",
            "cuales padecimiento",
            "de que padecimiento",
            "padecimiento sabes",
            "padecimiento manejas",
            "padecimiento modela",
            "padecimiento pronostic",
            "padecimiento cubre",
            "padecimiento tiene",
            "que enfermedad",
            "cuales enfermedad",
            "enfermedad modela",
            "enfermedad cubre",
            "que diagnostico",
            "que cie",
            "codigos cie",
            "clasificacion internacional",
        ]
        if any(t in q for t in pad_triggers):
            por_pad = s.get("por_pad", {})
            lines = [
                "**EpiForecast-MX modela 3 padecimientos** de la "
                "Clasificación Internacional de Enfermedades (CIE-10):\n"
            ]
            pads = [
                ("Depresión", "F32", "Depresión"),
                ("Parkinson", "G20", "Parkinson"),
                ("Alzheimer", "G30", "Alzheimer"),
            ]
            for nombre, cie, key in pads:
                ps = por_pad.get(key, {})
                sm = ps.get("smape_prod_median")
                motor = ps.get("motor_ganador")
                extra = ""
                if sm is not None:
                    extra += f" | SMAPE mediano: {sm}%"
                if motor:
                    extra += f" | Motor ganador: {motor}"
                lines.append(f"- **{nombre} ({cie})**{extra}")
            lines.append(
                f"\nCada padecimiento genera **111 modelos** "
                f"(37 geografías x 3 modos de sexo) = **{s.get('total_modelos', 333)} "
                f"modelos totales**."
            )
            return "\n".join(lines)

        # --- Regiones ---
        region_triggers = [
            "region",
            "macroregion",
            "macro region",
            "zona geografica",
            "zonas del pais",
            "division geografica",
            "cuantas region",
            "cuales region",
            "que region",
            "las region",
        ]
        if any(t in q for t in region_triggers):
            lines = [
                "**EpiForecast-MX usa 4 macrorregiones INEGI** "
                "de salud mental como geografías adicionales:\n"
            ]
            # Regiones INEGI de salud mental (usadas en los modelos)
            regiones_inegi = {
                "Metropolitana alta": [
                    "CDMX",
                    "Jalisco",
                    "México",
                    "Nuevo León",
                    "Guanajuato",
                    "Veracruz",
                    "Puebla",
                    "Chihuahua",
                    "Tamaulipas",
                    "Baja California",
                ],
                "Urbana media": [
                    "Coahuila",
                    "Sonora",
                    "San Luis Potosí",
                    "Michoacán",
                    "Sinaloa",
                    "Hidalgo",
                    "Querétaro",
                    "Morelos",
                    "Aguascalientes",
                    "Durango",
                    "Colima",
                    "Tlaxcala",
                    "Nayarit",
                ],
                "Rural / dispersa": [
                    "Tabasco",
                    "Yucatán",
                    "Quintana Roo",
                    "Zacatecas",
                    "Baja California Sur",
                ],
                "Sur-Sureste vulnerable": [
                    "Oaxaca",
                    "Chiapas",
                    "Guerrero",
                    "Campeche",
                ],
            }
            for nombre, estados in regiones_inegi.items():
                lines.append(f"- **{nombre}** ({len(estados)} entidades): {', '.join(estados)}")
            lines.append(
                "\nEstas regiones se modelan como series independientes "
                "y sirven de **fallback** para entidades con incidencia "
                f"insuficiente ({s.get('fallback_n', 8)} series usan fallback)."
            )
            lines.append(
                "\n**37 geografías totales**: 32 entidades + 4 regiones INEGI + Nacional."
            )
            return "\n".join(lines)

        # --- Franja COVID ---
        covid_triggers = [
            "covid",
            "pandemia",
            "franja covid",
            "periodo covid",
            "periodo pandem",
            "confinamiento",
            "cuarentena",
            "cambio estructural",
        ]
        if any(t in q for t in covid_triggers):
            from epiforecast.constants import (
                COVID_END,
                COVID_START,
            )

            return (
                f"**Periodo COVID-19 en EpiForecast-MX**:\n\n"
                f"- **Inicio**: {COVID_START} (15 de marzo de 2020)\n"
                f"- **Fin**: {COVID_END} (22 de septiembre de 2022)\n"
                f"- **Duración**: ~2.5 años (130 semanas)\n\n"
                f"Definido en `src/epiforecast/constants.py`. "
                f"Esta franja se usa en todas las visualizaciones del proyecto "
                f"(sombreado rojo) y en los changepoints de Prophet.\n\n"
                f"**Impacto por padecimiento**:\n"
                f"- **Depresión**: caída abrupta en 2020 seguida de rebote "
                f"sostenido post-pandemia (superó niveles pre-COVID)\n"
                f"- **Parkinson**: reducción moderada por caída en consultas "
                f"presenciales, recuperación gradual en 2022\n"
                f"- **Alzheimer**: impacto similar a Parkinson, con potencial "
                f"subdiagnóstico durante el confinamiento"
            )

        # --- Alcance general ---
        alcance_triggers = [
            "que sabe",
            "que puede",
            "de que sabe",
            "que conoce",
            "que informacion tiene",
            "que datos tiene",
            "que cubre",
            "alcance",
            "capacidad",
            "sobre que me puede",
        ]
        if any(t in q for t in alcance_triggers):
            return (
                "**Puedo responder sobre el proyecto EpiForecast-MX**:\n\n"
                "- **Padecimientos**: Depresión (F32), Parkinson (G20), "
                "Alzheimer (G30)\n"
                "- **Geografías**: 32 entidades + 4 regiones INEGI + Nacional\n"
                "- **Modelos**: Prophet, DeepAR, Ensemble, Stacking "
                f"({s.get('total_modelos', 333)} en producción)\n"
                "- **Métricas**: SMAPE, MASE, RMSE, MAE por serie\n"
                "- **Boletín epidemiológico**: datos históricos 2014-2026\n"
                "- **Equipo**: integrantes, roles, contribuciones\n"
                "- **Infraestructura**: tests, CI/CD, SageMaker, costos\n"
                "- **Franja COVID**: periodo, impacto, changepoints\n"
                "- **Pronósticos**: acumulados a 52 semanas por serie\n\n"
                "Pregúntame lo que quieras sobre cualquiera de estos temas."
            )

        return None

    # ------------------------------------------------------------------
    # Configuracion de entrenamiento, hiperparametros, fechas de corte
    # ------------------------------------------------------------------

    def _answer_training_config(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre fechas de corte, hiperparametros, CV y eventos especiales."""
        triggers = [
            "fecha de corte",
            "fechas de corte",
            "fecha corte",
            "fechas corte",
            "corte de entrenamiento",
            "corte del entrenamiento",
            "corte entrenamiento",
            "fecha de entrenamiento",
            "fechas de entrenamiento",
            "fecha del entrenamiento",
            "fechas del entrenamiento",
            "cuando se entreno",
            "cuando se entrenaron",
            "cuando entrenaron",
            "cuando entrenamos",
            "train test",
            "train/test",
            "hiperparametro",
            "hiperparametros",
            "hyperparametr",
            "hiper parametro",
            "hiper parametros",
            "cross validation",
            "validacion cruzada",
            "cv fold",
            "fold",
            "test size",
            "tamano de test",
            "tamano de prueba",
            "tamano test",
            "tamano prueba",
            "periodo de prueba",
            "oof",
            "out of fold",
            "ventana covid",
            "ventana de covid",
            "impacto covid",
            "covid en el modelo",
            "covid modelo",
            "regimen",
            "cambio de regimen",
            "change point",
            "changepoint",
            "epoch",
            "learning rate",
            "tasa de aprendizaje",
            "capas",
            "layers",
            "dropout",
            "context length",
            "prediction length",
            "early stopping",
            "patience",
            "configuracion del modelo",
            "configuracion de entrenamiento",
            "config del modelo",
            "config entrenamiento",
            "parametros del modelo",
            "parametros de entrenamiento",
            "como se entreno",
            "como se entrenaron",
            "con que parametros",
            "con que configuracion",
            "grid search",
            "busqueda de hiperparametro",
            "xgboost parametro",
            "lightgbm parametro",
            "prophet parametro",
            "deepar parametro",
            "stacking parametro",
            "ensemble parametro",
            "meta learner",
            "metalearner",
            "ridge",
            "elasticnet",
            "peso",
            "weight",
            "cv_weight",
            "estacionalidad",
            "seasonality",
        ]
        # Tambien activar si mencionan un modelo + palabra de config
        _config_words = (
            "configuracion",
            "config",
            "parametro",
            "parametros",
            "hiperparametro",
            "como se entreno",
            "como entrena",
            "como funciona",
        )
        _model_words = (
            "prophet",
            "deepar",
            "deep ar",
            "ensemble",
            "stacking",
            "xgboost",
            "lightgbm",
        )
        has_model_config = any(m in q for m in _model_words) and any(c in q for c in _config_words)

        if not any(t in q for t in triggers) and not has_model_config:
            return None

        modelo = ent.get("modelo")
        lines: list[str] = []

        # --- Fechas de corte (siempre mostrar si preguntan por corte/train/test) ---
        corte_kw = any(
            t in q
            for t in [
                "fecha de corte",
                "fecha corte",
                "corte de entrenamiento",
                "corte entrenamiento",
                "train test",
                "train/test",
                "como se entreno",
                "como se entrenaron",
            ]
        )
        if corte_kw or not modelo:
            lines.append("**Fechas de corte de entrenamiento**\n")
            lines.append("Todos los modelos usan la misma fecha de corte:")
            lines.append("- **FECHA_CORTE_ENTRENAMIENTO: 2025-01-01**")
            lines.append("- Datos de entrenamiento: semana 1/2014 hasta semana 52/2024")
            lines.append("- Datos de prueba (CV): semana 1/2025 en adelante")
            lines.append("- Horizonte de pronóstico: **52 semanas** (hasta enero 2027)")
            lines.append("")

        # --- Prophet ---
        show_prophet = modelo == "Prophet" or (
            not modelo
            and any(
                t in q
                for t in [
                    "prophet",
                    "fold",
                    "cv_weight",
                    "peso",
                    "weight",
                    "estacionalidad",
                    "seasonality",
                    "changepoint",
                    "change point",
                    "grid",
                ]
            )
        )
        if show_prophet or (corte_kw and not modelo):
            lines.append("**Prophet**")
            lines.append("- Validación cruzada: **4 folds** (TS_SPLITS)")
            lines.append("- Tamaño de prueba por fold: **53 semanas** (TEST_SIZE)")
            lines.append("- Pesos de CV: [0.5, 0.75, 1.0, 1.25] (más peso a folds recientes)")
            lines.append(
                "- Estacionalidad: multiplicativa (Depresión, Parkinson), aditiva (Alzheimer)"
            )
            lines.append("- Grid de hiperparámetros por padecimiento:")
            lines.append(
                "  - Depresión: changepoint_prior_scale=[0.05, 0.1, 0.5], "
                "seasonality_prior_scale=[1, 5, 10]"
            )
            lines.append(
                "  - Parkinson: changepoint_prior_scale=[0.01, 0.05, 0.1], "
                "seasonality_prior_scale=[0.5, 1, 5]"
            )
            lines.append(
                "  - Alzheimer: changepoint_prior_scale=[0.01, 0.05, 0.1], "
                "seasonality_prior_scale=[0.5, 1, 5]"
            )
            lines.append("")

        # --- Ensemble ---
        show_ensemble = modelo == "Ensemble" or (
            not modelo
            and any(
                t in q
                for t in [
                    "ensemble",
                    "xgboost",
                    "oof",
                    "out of fold",
                ]
            )
        )
        if show_ensemble or (corte_kw and not modelo):
            lines.append("**Ensemble (Prophet + XGBoost)**")
            lines.append("- Horizonte: **52 semanas** (HORIZON_ENSEMBLE)")
            lines.append("- OOF cutoff: **2024-01-01** (parallel_oof_cutoff)")
            lines.append("- XGBoost CV: **4 splits**, test_size=**26 semanas**")
            lines.append(
                "- XGBoost hiperparámetros: n_estimators=500, max_depth=4, "
                "learning_rate=0.05, subsample=0.8, colsample_bytree=0.8"
            )
            lines.append(
                "- Features: Prophet yhat, residuos, mes, semana, rolling means (4/12/26 sem)"
            )
            lines.append("")

        # --- Stacking ---
        show_stacking = modelo == "Stacking" or (
            not modelo
            and any(
                t in q
                for t in [
                    "stacking",
                    "lightgbm",
                    "meta learner",
                    "metalearner",
                    "ridge",
                    "elasticnet",
                    "ets",
                ]
            )
        )
        if show_stacking or (corte_kw and not modelo):
            lines.append("**Stacking (Prophet + ETS + LightGBM + Ridge)**")
            lines.append("- Horizonte: **52 semanas** (HORIZON_STACKING)")
            lines.append("- OOF cutoff: **2024-01-01**")
            lines.append("- OOF folds: **4**, mínimo de entrenamiento: **104 semanas** (2 años)")
            lines.append("- Meta-learner: Ridge con pesos no negativos")
            lines.append("- Expertos: ProphetExpert, ETSExpert, LGBMExpert")
            lines.append("")

        # --- DeepAR ---
        show_deepar = modelo == "DeepAR" or (
            not modelo
            and any(
                t in q
                for t in [
                    "deepar",
                    "deep ar",
                    "epoch",
                    "capas",
                    "layers",
                    "dropout",
                    "context length",
                    "prediction length",
                    "early stopping",
                    "patience",
                    "learning rate",
                    "tasa de aprendizaje",
                ]
            )
        )
        if show_deepar or (corte_kw and not modelo):
            lines.append("**DeepAR (GluonTS + PyTorch)**")
            lines.append("- Context length: **104 semanas** (2 años de historia)")
            lines.append("- Prediction length: **52 semanas**")
            lines.append("- Epochs: **300** (max)")
            lines.append("- Early stopping patience: **15 epochs**")
            lines.append("- Arquitectura: 2 capas LSTM, 40 celdas, dropout=0.1")
            lines.append("- Learning rate: 1e-3")
            lines.append("- Batch size: 32")
            lines.append("- Entrenamiento: CPU local o GPU en AWS SageMaker (ml.g4dn.xlarge)")
            lines.append("")

        # --- Eventos especiales (COVID, cambios de regimen) ---
        event_kw = any(
            t in q
            for t in [
                "covid",
                "pandemia",
                "regimen",
                "cambio de regimen",
                "change point",
                "changepoint",
                "evento especial",
                "tabasco",
            ]
        )
        if event_kw:
            lines.append("**Eventos especiales en el modelado**\n")
            lines.append("*COVID-19 (afecta los 3 padecimientos):*")
            lines.append("- Fecha de inicio: **2020-03-23** (semana epidemiológica 13/2020)")
            lines.append("- Ventana de impacto: **913 días** (~2.5 años, hasta sep 2022)")
            lines.append(
                "- Tratamiento: Prophet usa changepoint + holiday effect; "
                "Ensemble y Stacking capturan el efecto vía features temporales"
            )
            lines.append("")
            lines.append("*Cambio de régimen — Tabasco (solo Depresión):*")
            lines.append("- Fecha: **2023-01-09** (semana 2/2023)")
            lines.append("- Ventana: **365 días** (1 año)")
            lines.append(
                "- Motivo: cambio abrupto en el patrón de reporte de Depresión en Tabasco"
            )

        # Si no se activó ninguna sección específica, dar resumen general
        if not lines:
            lines.append("**Configuración general de entrenamiento**\n")
            lines.append("- Fecha de corte: **2025-01-01** (todos los modelos)")
            lines.append("- Horizonte: **52 semanas**")
            lines.append("- Modelos: Prophet, DeepAR, Ensemble, Stacking")
            lines.append("- Series: 333 (3 padecimientos x 37 geo x 3 sexo)")
            lines.append(
                "- Selección de producción: SMAPE primario, MASE desempate (5%), "
                "RMSE segundo desempate"
            )
            lines.append(
                "\nPregunta por un modelo específico para ver sus hiperparámetros: "
                '"hiperparámetros de Prophet", "configuración de DeepAR", etc.'
            )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Semana actual / siguiente / casos nuevos
    # ------------------------------------------------------------------

    def _answer_semana_actual(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde preguntas sobre la semana actual, siguiente o casos recientes."""
        triggers = [
            "esta semana",
            "semana actual",
            "semana pasada",
            "semana anterior",
            "semana previa",
            "semana siguiente",
            "proxima semana",
            "siguiente semana",
            "casos nuevos",
            "llegaron caso",
            "nuevos caso",
            "ultimo dato",
            "ultimos dato",
            "dato reciente",
            "datos reciente",
            "dato mas reciente",
            "ultimo reporte",
            "ultimo boletin",
            "mas reciente",
            "hoy",
            "proyectado",
            "proyeccion semana",
            "pronostico semana",
            "cuantos caso.*semana",
        ]
        if not any(t in q for t in triggers) and not re.search(r"cuantos?\s+caso.*semana", q):
            return None

        import pandas as pd

        pad = ent.get("padecimiento")
        estado = ent.get("estado")
        sexo = ent.get("sexo")

        lines: list[str] = []

        # --- Parte 1: Datos reales mas recientes (boletin) ---
        is_past = any(
            t in q
            for t in [
                "esta semana",
                "semana actual",
                "semana pasada",
                "semana anterior",
                "semana previa",
                "casos nuevos",
                "llegaron caso",
                "nuevos caso",
                "ultimo dato",
                "ultimos dato",
                "dato reciente",
                "datos reciente",
                "dato mas reciente",
                "mas reciente",
                "ultimo reporte",
                "ultimo boletin",
                "hoy",
            ]
        )

        if is_past:
            df_bol = self.cache.boletin
            if df_bol is not None and not df_bol.empty:
                latest_year = int(df_bol["Anio"].max())
                latest_week = int(df_bol[df_bol["Anio"] == latest_year]["Semana"].max())
                latest = df_bol[
                    (df_bol["Anio"] == latest_year) & (df_bol["Semana"] == latest_week)
                ]

                lines.append(
                    f"**Último boletín disponible: semana epidemiológica "
                    f"{latest_week} de {latest_year}**\n"
                )

                # Filtrar por padecimiento si se especifica
                sub = latest
                if pad:
                    pad_n = _norm(pad)
                    sub = sub[sub["Padecimiento"].apply(lambda x: _norm(str(x)) == pad_n)]
                if estado:
                    est_n = _norm(estado)
                    if est_n in (
                        "ciudad de mexico",
                        "distrito federal",
                        "cdmx",
                    ):
                        sub = sub[
                            sub["Entidad"].apply(
                                lambda x: _norm(str(x))
                                in (
                                    "ciudad de mexico",
                                    "distrito federal",
                                )
                            )
                        ]
                    else:
                        sub = sub[sub["Entidad"].apply(lambda x: est_n in _norm(str(x)))]

                if sub.empty:
                    lines.append("No se encontraron datos con esos filtros.")
                else:
                    total = int(sub["Casos_semana"].sum())
                    lines.append(f"Casos reportados en semana {latest_week}: **{total:,}**\n")

                    by_pad = (
                        sub.groupby("Padecimiento")["Casos_semana"]
                        .sum()
                        .sort_values(ascending=False)
                    )
                    for p, c in by_pad.items():
                        if not pd.isna(c):
                            lines.append(f"- {p}: {int(c):,}")

                    # Top 5 estados si no se filtro por estado
                    if not estado and len(sub["Entidad"].unique()) > 5:
                        top5 = (
                            sub.groupby("Entidad")["Casos_semana"]
                            .sum()
                            .sort_values(ascending=False)
                            .head(5)
                        )
                        lines.append("\nTop 5 entidades esta semana:")
                        for e, c in top5.items():
                            if not pd.isna(c):
                                lines.append(f"  - {e}: {int(c):,}")

                # Comparar con semana anterior
                prev_week = latest_week - 1
                prev_year = latest_year
                if prev_week < 1:
                    prev_week = 52
                    prev_year -= 1
                prev = df_bol[(df_bol["Anio"] == prev_year) & (df_bol["Semana"] == prev_week)]
                if not prev.empty:
                    prev_total = int(prev["Casos_semana"].sum())
                    curr_total = int(latest["Casos_semana"].sum())
                    if prev_total > 0:
                        cambio = (curr_total - prev_total) / prev_total * 100
                        arrow = "+" if cambio >= 0 else ""
                        lines.append(
                            f"\nCambio vs semana {prev_week}: "
                            f"{arrow}{cambio:.1f}% ({prev_total:,} -> {curr_total:,})"
                        )

        # --- Parte 2: Proyeccion de la semana siguiente (tableau) ---
        is_future = any(
            t in q
            for t in [
                "semana siguiente",
                "proxima semana",
                "siguiente semana",
                "proyectado",
                "proyeccion semana",
                "pronostico semana",
            ]
        ) or re.search(r"cuantos?\s+caso.*semana\s+siguiente", q)

        if is_future or (sexo and any(t in q for t in ["semana", "proyectado"])):
            tab = self.cache.tableau
            if tab is not None:
                tab_df = tab.copy()
                tab_df["ds"] = pd.to_datetime(tab_df["ds"])

                # Encontrar la semana mas cercana al futuro inmediato
                from datetime import datetime, timedelta

                today = datetime.now().date()
                # Buscar lunes de la proxima semana
                days_to_monday = (7 - today.weekday()) % 7
                if days_to_monday == 0:
                    days_to_monday = 7
                next_monday = today + timedelta(days=days_to_monday)

                # Buscar la fecha mas cercana en tableau
                all_dates = sorted(tab_df["ds"].unique())
                target_ts = pd.Timestamp(next_monday)
                closest = min(all_dates, key=lambda d: abs(d - target_ts))

                week_data = tab_df[tab_df["ds"] == closest]
                if not week_data.empty:
                    if lines:
                        lines.append("")
                    lines.append(
                        f"**Proyección para semana del {closest.strftime('%d/%m/%Y')}**\n"
                    )

                    sub_w = week_data
                    if pad:
                        pad_n = _norm(pad)
                        sub_w = sub_w[
                            sub_w["padecimiento"].apply(lambda x: _norm(str(x)) == pad_n)
                        ]
                    if estado and estado != "Nacional":
                        est_n = _norm(estado)
                        sub_w = sub_w[sub_w["entidad"].apply(lambda x: est_n in _norm(str(x)))]
                    if sexo and "meta_modo" in sub_w.columns:
                        sub_w = sub_w[sub_w["meta_modo"] == sexo]

                    if sub_w.empty:
                        lines.append("No se encontraron proyecciones con esos filtros.")
                    else:
                        total_yhat = int(sub_w["yhat"].sum())
                        lines.append(f"Casos proyectados: **{total_yhat:,}**\n")

                        # Desglose por padecimiento
                        by_p = (
                            sub_w.groupby("padecimiento")["yhat"]
                            .sum()
                            .sort_values(ascending=False)
                        )
                        for p, c in by_p.items():
                            lines.append(f"- {p}: {int(c):,}")

                        # Desglose por sexo si no se filtro
                        if not sexo and "meta_modo" in sub_w.columns:
                            lines.append("\nPor grupo:")
                            by_modo = (
                                sub_w.groupby("meta_modo")["yhat"]
                                .sum()
                                .sort_values(ascending=False)
                            )
                            for m, c in by_modo.items():
                                lines.append(f"  - {m}: {int(c):,}")

        # --- Parte 3: Validacion semana previa (prod_models) ---
        if is_past and not lines:
            # Fallback: usar pron_sem_previa y realidad_sem_previa
            prod = self.cache.prod_models
            if prod is not None:
                sub_p = prod
                if pad:
                    pad_n = _norm(pad)
                    sub_p = sub_p[sub_p["padecimiento"].apply(lambda x: _norm(str(x)) == pad_n)]
                if sexo:
                    sub_p = sub_p[sub_p["sexo"].str.lower() == sexo.lower()]

                pron = int(sub_p["pron_sem_previa"].sum())
                real = int(sub_p["realidad_sem_previa"].sum())
                lines.append("**Validación de la semana previa**:\n")
                lines.append(f"- Casos pronosticados: {pron:,}")
                lines.append(f"- Casos reales: {real:,}")
                if pron > 0:
                    error_pct = abs(real - pron) / real * 100 if real > 0 else 0
                    lines.append(f"- Error: {error_pct:.1f}%")

        return "\n".join(lines) if lines else None

    # ------------------------------------------------------------------
    # Descripcion medica de padecimientos
    # ------------------------------------------------------------------

    _PADECIMIENTO_INFO: dict[str, str] = {
        "depresion": (
            "**Depresión (CIE-10: F32)**\n\n"
            "La depresión es un trastorno del estado de ánimo caracterizado por "
            "tristeza persistente, pérdida de interés en actividades cotidianas, "
            "fatiga, alteraciones del sueño y dificultad para concentrarse. Es una "
            "de las principales causas de discapacidad a nivel mundial según la OMS.\n\n"
            "**Efectos en la salud**:\n"
            "- Deterioro cognitivo y dificultad para tomar decisiones\n"
            "- Alteraciones del apetito y peso corporal\n"
            "- Insomnio o hipersomnia crónica\n"
            "- Mayor riesgo cardiovascular\n"
            "- Debilitamiento del sistema inmunológico\n"
            "- Aislamiento social y deterioro de relaciones\n"
            "- Reducción significativa de la productividad laboral\n\n"
            "**En México (IMSS)**: es el padecimiento con mayor incidencia de los "
            "tres que monitoreamos. Afecta predominantemente a mujeres (proporción "
            "~3:1) y presenta estacionalidad marcada con picos en periodos post-vacacionales.\n\n"
            "*Esta información es de carácter general y no constituye consejo médico.*"
        ),
        "parkinson": (
            "**Enfermedad de Parkinson (CIE-10: G20)**\n\n"
            "El Parkinson es un trastorno neurodegenerativo progresivo que afecta "
            "el sistema nervioso central, causado por la pérdida de neuronas "
            "dopaminérgicas en la sustancia negra del cerebro. Se manifiesta "
            "principalmente con temblor en reposo, rigidez muscular, lentitud "
            "de movimiento (bradicinesia) e inestabilidad postural.\n\n"
            "**Efectos en la salud**:\n"
            "- Temblores involuntarios que dificultan actividades diarias\n"
            "- Rigidez muscular y dolor articular\n"
            "- Dificultad progresiva para caminar y mantener el equilibrio\n"
            "- Problemas de deglución y habla\n"
            "- Trastornos del sueño (movimientos oculares rápidos)\n"
            "- Deterioro cognitivo en etapas avanzadas\n"
            "- Depresión y ansiedad como comorbilidades frecuentes\n\n"
            "**En México (IMSS)**: la incidencia es moderada comparada con la "
            "depresión. Afecta ligeramente más a hombres y su prevalencia crece "
            "con la edad. Los estados del norte presentan tasas más elevadas.\n\n"
            "*Esta información es de carácter general y no constituye consejo médico.*"
        ),
        "alzheimer": (
            "**Enfermedad de Alzheimer (CIE-10: G30)**\n\n"
            "El Alzheimer es la forma más común de demencia. Es una enfermedad "
            "neurodegenerativa progresiva que destruye neuronas y conexiones "
            "cerebrales, afectando memoria, pensamiento y comportamiento. "
            "Comienza con olvidos leves y progresa hasta la pérdida de capacidad "
            "para conversar y responder al entorno.\n\n"
            "**Efectos en la salud**:\n"
            "- Pérdida progresiva de memoria (primero reciente, luego remota)\n"
            "- Desorientación temporal y espacial\n"
            "- Dificultad para planificar y resolver problemas\n"
            "- Cambios de personalidad y comportamiento\n"
            "- Pérdida de autonomía para actividades básicas\n"
            "- Deterioro del lenguaje y la comunicación\n"
            "- Carga significativa para cuidadores y familiares\n\n"
            "**En México (IMSS)**: es el padecimiento con menor incidencia de los "
            "tres, pero con tendencia creciente vinculada al envejecimiento "
            "poblacional. Jalisco, Chihuahua y Sinaloa reportan las tasas más altas. "
            "Su SMAPE de predicción es el más elevado (>100%) debido a la baja "
            "frecuencia y alta variabilidad entre entidades.\n\n"
            "*Esta información es de carácter general y no constituye consejo médico.*"
        ),
    }

    def _answer_que_es_padecimiento(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde que es un padecimiento con descripcion medica general."""
        # Triggers exactos con word boundary para evitar false positives
        regex_triggers = [
            r"\bque es\b",
            r"\bque significa\b",
            r"\bdime sobre\b",
            r"\bcuentame sobre\b",
            r"\bexplicame\b",
            r"\binformacion sobre\b",
            r"\bhablame de\b",
            r"\bdescribe\b",
            r"\bsintoma",
            r"\befecto",
            r"\bconsecuencia",
            r"\bcausa\b",
            r"\briesgo",
            r"\bimpacto en la salud\b",
            r"\bafecta\b",
            r"\bprovoca\b",
            r"\benfermedad\b",
            r"\btrastorno\b",
            r"padecimiento.*\bes\b",
        ]
        has_trigger = any(re.search(pat, q) for pat in regex_triggers)
        if not has_trigger:
            return None

        pad = ent.get("padecimiento")
        if not pad:
            # Intentar detectar sin alias standard
            if any(t in q for t in ["los tres", "los 3", "tres padecimiento"]):
                # Devolver los tres
                parts = []
                for key in ["depresion", "parkinson", "alzheimer"]:
                    parts.append(self._PADECIMIENTO_INFO[key])
                return "\n\n---\n\n".join(parts)
            return None

        key = _norm(pad)
        info = self._PADECIMIENTO_INFO.get(key)
        if not info:
            return None

        # Agregar datos del proyecto si estan disponibles
        pad_stats = s.get("por_pad", {}).get(pad)
        if pad_stats:
            cas = pad_stats.get("casos_futuro_total")
            sm = pad_stats.get("smape_prod_mean")
            extra = "\n\n**Datos del proyecto EpiForecast-MX**:\n"
            if cas:
                extra += f"- Pronóstico 52 semanas: {cas:,} casos\n"
            if sm:
                extra += f"- SMAPE promedio: {sm}%\n"
            ganador = pad_stats.get("motor_ganador")
            if ganador:
                extra += f"- Motor ganador: {ganador}\n"
            n = pad_stats.get("n")
            if n:
                extra += f"- Modelos de producción: {n}"
            info += extra

        return info

    # ------------------------------------------------------------------
    # Boletin epidemiologico (datos historicos 2014-2026)
    # ------------------------------------------------------------------

    def _query_boletin(
        self,
        padecimiento: str | None = None,
        estado: str | None = None,
        years: list[int] | None = None,
        weeks: list[int] | None = None,
    ):
        """Filtra el boletin epidemiologico y retorna el subset."""
        df = self.cache.boletin
        if df is None or df.empty:
            return None

        if padecimiento:
            pad_n = _norm(padecimiento)
            df = df[df["Padecimiento"].apply(lambda x: _norm(str(x)) == pad_n)]
        if estado:
            est_n = _norm(estado)
            # Manejo especial: "Ciudad de Mexico" y "Distrito Federal" son la misma entidad
            if est_n in ("ciudad de mexico", "distrito federal", "cdmx"):
                df = df[
                    df["Entidad"].apply(
                        lambda x: _norm(str(x)) in ("ciudad de mexico", "distrito federal")
                    )
                ]
            else:
                df = df[df["Entidad"].apply(lambda x: est_n in _norm(str(x)))]
        if years:
            df = df[df["Anio"].isin(years)]
        if weeks:
            df = df[df["Semana"].isin(weeks)]
        return df if not df.empty else None

    def _answer_boletin(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde preguntas sobre datos historicos del boletin epidemiologico."""
        years: list[int] = ent.get("_years", [])  # type: ignore[assignment]
        weeks: list[int] = ent.get("_weeks", [])  # type: ignore[assignment]

        # Trigger: necesita al menos un ano, o keywords de datos historicos
        hist_triggers = [
            "caso",
            "incidencia",
            "registro",
            "hubo",
            "reporto",
            "reportaron",
            "historico",
            "historica",
            "tendencia",
            "evolucion",
            "serie de tiempo",
            "serie temporal",
            "boletin",
            "sinave",
            "acumulado",
            "anual",
            "semanal",
            "covid",
            "pandemia",
            "comparar ano",
            "comparar anio",
            "crecio",
            "crecimiento",
            "bajo",
            "subio",
            "aumento",
            "disminuyo",
            "maximo",
            "minimo",
            "pico",
            "record",
        ]
        has_year = bool(years)
        has_hist_trigger = any(t in q for t in hist_triggers)
        ranking_kw = [
            "mas caso",
            "mas incidencia",
            "ranking",
            "top ",
            "mayor incidencia",
            "mas reporta",
            "menos caso",
            "menor incidencia",
            "que entidad",
            "que estado",
            "donde hay mas",
            "cual tiene mas",
        ]
        is_ranking_q = any(t in q for t in ranking_kw)

        if not has_year and not has_hist_trigger and not is_ranking_q:
            return None

        # Si la pregunta es sobre proyecciones futuras, dejar para _answer_pronostico
        future_kw = [
            "proyect",
            "pronostic",
            "forecast",
            "prediccion",
            "predice",
            "predecir",
            "futuro",
            "se espera",
        ]
        if any(t in q for t in future_kw) and not has_year:
            return None

        import pandas as pd

        pad = ent.get("padecimiento")
        estado = ent.get("estado")

        # --- Caso 1: Consulta muy especifica (ano + estado + padecimiento) ---
        if years and (pad or estado):
            sub = self._query_boletin(pad, estado, years, weeks)
            if sub is None or sub.empty:
                return None

            total_casos = sub["Casos_semana"].sum()
            lines = []

            # Titulo
            parts_title = []
            if pad:
                parts_title.append(f"**{pad}**")
            if estado:
                parts_title.append(f"en **{estado}**")
            yr_str = ", ".join(str(y) for y in years)
            parts_title.append(f"({yr_str})")
            if weeks:
                wk_str = ", ".join(str(w) for w in weeks)
                parts_title.append(f"semana(s) {wk_str}")
            lines.append(" ".join(parts_title) + ":\n")

            if not pd.isna(total_casos):
                lines.append(f"- **Casos totales: {int(total_casos):,}**")

            # Desglose por ano si multiples
            if len(years) > 1:
                lines.append("\nPor ano:")
                for y in years:
                    yr_sub = sub[sub["Anio"] == y]
                    c = yr_sub["Casos_semana"].sum()
                    if not pd.isna(c):
                        lines.append(f"  - {y}: {int(c):,} casos")

            # Si hay multiples entidades (estado no especificado)
            if not estado and "Entidad" in sub.columns:
                top_ent = sub.groupby("Entidad")["Casos_semana"].sum().sort_values(ascending=False)
                if len(top_ent) > 1:
                    lines.append("\nTop 10 entidades:")
                    for e, c in top_ent.head(10).items():
                        if not pd.isna(c):
                            lines.append(f"  - {e}: {int(c):,}")

            # Si hay estado pero no padecimiento, desglosar por padecimiento
            if estado and not pad and "Padecimiento" in sub.columns:
                by_pad = sub.groupby("Padecimiento")["Casos_semana"].sum()
                lines.append("\nPor padecimiento:")
                for p, c in by_pad.sort_values(ascending=False).items():
                    if not pd.isna(c):
                        lines.append(f"  - {p}: {int(c):,} casos")

            # Acumulados hombre/mujer si disponibles
            if estado and pad and len(years) == 1:
                last_week = sub.sort_values("Semana").iloc[-1]
                h = last_week.get("Acumulado_hombres")
                m = last_week.get("Acumulado_mujeres")
                if pd.notna(h) and pd.notna(m):
                    lines.append(
                        f"\nAcumulado {years[0]} (hasta semana {int(last_week['Semana'])}):"
                    )
                    lines.append(f"  - Hombres: {int(h):,}")
                    lines.append(f"  - Mujeres: {int(m):,}")
                    lines.append(f"  - Total: {int(h + m):,}")

            return "\n".join(lines) if len(lines) > 1 else None

        # --- Caso 2: Solo ano (resumen anual completo) ---
        if years and not pad and not estado:
            sub = self._query_boletin(years=years)
            if sub is None:
                return None
            yr_str = ", ".join(str(y) for y in years)
            lines = [f"**Resumen epidemiológico {yr_str}**:\n"]
            for y in years:
                yr_sub = sub[sub["Anio"] == y]
                total = yr_sub["Casos_semana"].sum()
                lines.append(f"**{y}**: {int(total):,} casos totales")
                by_pad = yr_sub.groupby("Padecimiento")["Casos_semana"].sum()
                for p, c in by_pad.sort_values(ascending=False).items():
                    if not pd.isna(c):
                        lines.append(f"  - {p}: {int(c):,}")
                if len(years) > 1:
                    lines.append("")
            return "\n".join(lines)

        # --- Caso 3: Ranking de entidades por casos (sin ano especifico) ---
        if is_ranking_q:
            df = self.cache.boletin
            if df is None:
                return None
            sub = df.copy()
            if pad:
                pad_n = _norm(pad)
                sub = sub[sub["Padecimiento"].apply(lambda x: _norm(str(x)) == pad_n)]
            top_ent = sub.groupby("Entidad")["Casos_semana"].sum().sort_values(ascending=False)
            pad_label = f" de {pad}" if pad else ""
            lines = [f"**Top entidades por incidencia{pad_label}** (2014-2026):\n"]
            for i, (e, c) in enumerate(top_ent.head(15).items(), 1):
                if not pd.isna(c):
                    lines.append(f"{i}. {e}: {int(c):,} casos")
            return "\n".join(lines)

        # --- Caso 4: Padecimiento (+ estado opcional) con trigger historico ---
        if pad and not years and has_hist_trigger:
            sub = self._query_boletin(padecimiento=pad, estado=estado)
            if sub is None:
                return None

            by_year = sub.groupby("Anio")["Casos_semana"].sum().sort_index()
            loc_label = f" en {estado}" if estado else ""
            lines = [f"**{pad}{loc_label} - Evolución histórica** (2014-2026):\n"]
            prev = None
            for y, c in by_year.items():
                if pd.isna(c):
                    continue
                c_int = int(c)
                change = ""
                if prev is not None and prev > 0:
                    pct = (c_int - prev) / prev * 100
                    arrow = "+" if pct >= 0 else ""
                    change = f" ({arrow}{pct:.1f}%)"
                lines.append(f"  - {y}: {c_int:,} casos{change}")
                prev = c_int

            # Pico y valle
            max_y = by_year.idxmax()
            min_y = by_year.idxmin()
            lines.append(f"\nPico: {max_y} ({int(by_year[max_y]):,} casos)")
            lines.append(f"Valle: {min_y} ({int(by_year[min_y]):,} casos)")

            return "\n".join(lines)

        # --- Caso 5: Solo estado con trigger historico (resumen por estado) ---
        if estado and not years and has_hist_trigger:
            df = self.cache.boletin
            if df is None:
                return None
            est_n = _norm(estado)
            if est_n in ("ciudad de mexico", "distrito federal", "cdmx"):
                sub = df[
                    df["Entidad"].apply(
                        lambda x: _norm(str(x)) in ("ciudad de mexico", "distrito federal")
                    )
                ]
            else:
                sub = df[df["Entidad"].apply(lambda x: est_n in _norm(str(x)))]
            if sub.empty:
                return None

            by_year = sub.groupby("Anio")["Casos_semana"].sum().sort_index()
            lines = [f"**{estado} - Evolución histórica**:\n"]
            lines.append(f"Total histórico: {int(by_year.sum()):,} casos\n")
            for y, c in by_year.items():
                if not pd.isna(c):
                    lines.append(f"  - {y}: {int(c):,}")

            # Desglose por padecimiento
            by_pad = sub.groupby("Padecimiento")["Casos_semana"].sum()
            lines.append("\nPor padecimiento (histórico total):")
            for p, c in by_pad.sort_values(ascending=False).items():
                if not pd.isna(c):
                    lines.append(f"  - {p}: {int(c):,}")

            return "\n".join(lines)

        # --- Caso 6: Preguntas sobre COVID / pandemia ---
        if any(t in q for t in ["covid", "pandemia"]):
            df = self.cache.boletin
            if df is None:
                return None
            lines = ["**Impacto COVID-19 en la incidencia**:\n"]
            for pad_name in ["Depresión", "Parkinson", "Alzheimer"]:
                pad_n = _norm(pad_name)
                p_sub = df[df["Padecimiento"].apply(lambda x, pn=pad_n: _norm(str(x)) == pn)]
                c19 = int(p_sub[p_sub["Anio"] == 2019]["Casos_semana"].sum())
                c20 = int(p_sub[p_sub["Anio"] == 2020]["Casos_semana"].sum())
                c21 = int(p_sub[p_sub["Anio"] == 2021]["Casos_semana"].sum())
                drop = round((c20 - c19) / c19 * 100, 1) if c19 > 0 else 0
                recov = round((c21 - c20) / c20 * 100, 1) if c20 > 0 else 0
                lines.append(f"**{pad_name}**:")
                lines.append(f"  - 2019 (pre-COVID): {c19:,}")
                lines.append(f"  - 2020 (pandemia): {c20:,} ({drop:+.1f}%)")
                lines.append(f"  - 2021 (recuperación): {c21:,} ({recov:+.1f}%)")
                lines.append("")
            return "\n".join(lines)

        return None

    def _answer_specific_series(
        self,
        q: str,
        ent: dict,
        s: dict,
    ) -> str | None:
        """Responde sobre una serie especifica (pad + estado)."""
        pad = ent.get("padecimiento")
        estado = ent.get("estado")
        if not (pad and estado):
            return None

        prod = self.cache.prod_models
        if prod is None:
            return None

        pad_norm = _norm(pad)
        est_norm = _norm(estado)
        mask = (prod["padecimiento"].apply(lambda x: _norm(str(x)) == pad_norm)) & (
            prod["entidad"].apply(lambda x: est_norm in _norm(str(x)))
        )
        sexo = ent.get("sexo")
        if sexo:
            mask = mask & (prod["sexo"].str.lower() == sexo.lower())

        sub = prod[mask]
        if sub.empty:
            return None

        titulo = f"## {pad} en {estado}" + (f" ({sexo})" if sexo else "")
        lines = [titulo, ""]

        total_casos = 0
        for i, (_, r) in enumerate(sub.iterrows()):
            sex_label = str(r.get("sexo", "")).capitalize()
            motor = r.get("modelo_produccion", "?")
            smape = r.get("smape_prod", 0)
            mase = r.get("mase_prod", 0)
            rmse = r.get("rmse_prod", 0)
            casos = int(r.get("casos_52_semanas_futuro", 0) or 0)
            total_casos += casos
            ov = r.get("overfitting", "?")
            just = r.get("justificacion", "")
            pron = r.get("pron_sem_previa")
            real = r.get("realidad_sem_previa")

            if i > 0:
                lines.append("---")
                lines.append("")

            lines.append(f"### {sex_label} — {motor}")
            lines.append("")
            lines.append(
                f"- SMAPE: **{smape:.1f}%** | MASE: **{mase:.2f}** | RMSE: **{rmse:.1f}**"
            )
            lines.append(f"- Casos proyectados (52 sem): **{casos:,}**")
            lines.append(f"- Overfitting: {ov}")
            if pron is not None and real is not None:
                with contextlib.suppress(ValueError, TypeError):
                    lines.append(
                        f"- Semana previa: pronostico **{int(pron)}** vs real **{int(real)}**"
                    )
            if just:
                lines.append(f"\n> {just}")
            lines.append("")

        if len(sub) > 1 and total_casos > 0:
            lines.append(f"**Total proyectado 52 semanas: {total_casos:,} casos**")

        return "\n".join(lines)

    def _answer_estado(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre un estado especifico."""
        estado = ent.get("estado")
        if not estado:
            return None
        # Si tambien hay padecimiento, _answer_specific_series ya lo manejo
        if ent.get("padecimiento"):
            return None

        info = None
        est_norm = _norm(estado)
        for key, val in s.get("por_estado", {}).items():
            if _norm(key) == est_norm or est_norm in _norm(key):
                info = val
                estado = key
                break
        if not info:
            return None

        lines = [f"**{estado}** ({info['n']} modelos de producción):\n"]
        sm = info.get("smape_prod_mean")
        ms = info.get("mase_prod_mean")
        if sm:
            lines.append(f"- SMAPE promedio: {sm}%")
        if ms:
            lines.append(f"- MASE promedio: {ms}")
        dist = info.get("dist_motor", {})
        if dist:
            lines.append("- Motores seleccionados:")
            for m, c in sorted(dist.items(), key=lambda x: -x[1]):
                lines.append(f"  - {m}: {c}")
        cas = info.get("casos_futuro")
        if cas:
            lines.append(f"- Pronóstico total 52 sem: {cas:,} casos")

        # Agregar detalle por padecimiento desde datos originales
        prod = self.cache.prod_models
        if prod is not None:
            sub = prod[prod["entidad"].apply(lambda x: est_norm in _norm(str(x)))]
            if not sub.empty and "padecimiento" in sub.columns:
                lines.append("\nPor padecimiento:")
                for pad in sub["padecimiento"].unique():
                    ps = sub[sub["padecimiento"] == pad]
                    sm_val = ps["smape_prod"].mean() if "smape_prod" in ps.columns else 0
                    motor = (
                        ps["modelo_produccion"].mode().iloc[0]
                        if "modelo_produccion" in ps.columns
                        else "?"
                    )
                    lines.append(f"  - {pad}: SMAPE={sm_val:.1f}%, motor predominante={motor}")

        return "\n".join(lines)

    def _answer_padecimiento(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre un padecimiento."""
        pad = ent.get("padecimiento")
        if not pad:
            return None
        info = s.get("por_pad", {}).get(pad)
        if not info:
            return None

        lines = [f"**{pad}** ({info['n']} modelos de producción):\n"]
        for met, label in [
            ("smape_prod_mean", "SMAPE medio"),
            ("smape_prod_median", "SMAPE mediano"),
            ("mase_prod_mean", "MASE medio"),
            ("mase_prod_median", "MASE mediano"),
        ]:
            val = info.get(met)
            if val is not None:
                unit = "%" if "smape" in met else ""
                lines.append(f"- {label}: {val}{unit}")

        ganador = info.get("motor_ganador")
        ganador_n = info.get("motor_ganador_n")
        if ganador:
            lines.append(f"- Motor ganador: **{ganador}** ({ganador_n} series)")

        dist = info.get("dist_motor", {})
        if dist and len(dist) > 1:
            lines.append("- Distribución de motores:")
            for m, c in sorted(dist.items(), key=lambda x: -x[1]):
                pct = round(c / info["n"] * 100, 1)
                lines.append(f"  - {m}: {c} ({pct}%)")

        cas = info.get("casos_futuro_total")
        if cas:
            lines.append(f"- Pronóstico acumulado 52 sem: **{cas:,} casos**")

        return "\n".join(lines)

    def _answer_motor(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre un motor/modelo especifico."""
        modelo = ent.get("modelo")

        # Preguntas conceptuales ("que es", "como funciona", "explica") → dejar a Gemini
        _conceptual = [
            "que es",
            "qué es",
            "como funciona",
            "cómo funciona",
            "explica",
            "explicame",
            "explícame",
            "describe",
            "para que sirve",
            "para qué sirve",
            "en que consiste",
            "como opera",
            "cómo opera",
            "que hace",
            "qué hace",
            "definicion",
            "definición",
            "diferencia entre",
        ]
        if modelo and any(t in q for t in _conceptual):
            return None

        # Detectar preguntas sobre "quien gana" sin modelo especifico
        if not modelo and any(t in q for t in ["gana", "ganador", "campeon", "winner", "domina"]):
            dist = s.get("dist_motor", {})
            total = s.get("total_modelos", 333)
            lines = [f"**Distribución de modelos ganadores** ({total} series):\n"]
            for m, c in sorted(dist.items(), key=lambda x: -x[1]):
                pct = round(c / total * 100, 1)
                lines.append(f"- **{m}**: {c} series ({pct}%)")
            lines.append(
                f"\nMotor campeón global: **{s.get('motor_ganador')}** "
                f"con {s.get('motor_ganador_pct')}% de las series."
            )
            return "\n".join(lines)

        if not modelo:
            return None

        # Metricas del motor
        motor_stats = s.get("por_motor", {}).get(modelo)
        dist = s.get("dist_motor", {})
        n_wins = dist.get(modelo, 0)
        total = s.get("total_modelos", 333)

        lines = [f"**{modelo}**:\n"]
        if n_wins:
            pct = round(n_wins / total * 100, 1)
            lines.append(f"- Series ganadas: {n_wins} de {total} ({pct}%)")

        if motor_stats:
            for met, label in [
                ("smape_mean", "SMAPE medio"),
                ("smape_median", "SMAPE mediano"),
                ("mase_mean", "MASE medio"),
                ("mase_median", "MASE mediano"),
                ("rmse_mean", "RMSE medio"),
                ("mae_mean", "MAE medio"),
            ]:
                val = motor_stats.get(met)
                if val is not None:
                    unit = "%" if "smape" in met else ""
                    lines.append(f"- {label}: {val}{unit}")

        # Por padecimiento
        for pad, pinfo in s.get("por_pad", {}).items():
            pd_dist = pinfo.get("dist_motor", {})
            n = pd_dist.get(modelo, 0)
            if n:
                lines.append(f"- En {pad}: gana {n} de {pinfo['n']} series")

        return "\n".join(lines) if len(lines) > 1 else None

    def _answer_sexo(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre analisis por sexo/genero."""
        triggers = ["sexo", "genero", "hombre", "mujer", "masculino", "femenino"]
        if not any(t in q for t in triggers):
            return None

        sexo = ent.get("sexo")
        por_sexo = s.get("por_sexo", {})

        if sexo and sexo in por_sexo:
            info = por_sexo[sexo]
            lines = [f"**{sexo.title()}** ({info['n']} modelos):\n"]
            sm = info.get("smape_mean")
            ms = info.get("mase_mean")
            if sm:
                lines.append(f"- SMAPE promedio: {sm}%")
            if ms:
                lines.append(f"- MASE promedio: {ms}")
            return "\n".join(lines)

        # Comparativa completa
        lines = ["**Análisis por sexo**:\n"]
        for sx, info in por_sexo.items():
            sm = info.get("smape_mean", "?")
            ms = info.get("mase_mean", "?")
            lines.append(f"- **{sx}**: {info['n']} modelos, SMAPE={sm}%, MASE={ms}")
        return "\n".join(lines) if len(lines) > 1 else None

    def _answer_demografica(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre composicion demografica por padecimiento."""
        triggers = [
            "composicion demografica",
            "composicion por sexo",
            "distribucion demografica",
            "distribucion por sexo",
            "demografia",
            "demografico",
            "demografica",
            "hombres.*mujeres",
            "mujeres.*hombres",
            "proporcion.*sexo",
            "ratio.*sexo",
            "desglose.*sexo",
        ]
        if not any(t in q for t in triggers):
            # Tambien detectar "sexo" + "padecimiento" en combinacion
            has_sex = any(t in q for t in ["sexo", "genero"])
            has_pad = any(
                t in q for t in ["padecimiento", "enfermedad", "diagnostico", "segun", "por cada"]
            )
            if not (has_sex and has_pad):
                return None

        por_pad = s.get("por_pad", {})
        if not por_pad:
            return None

        # Si hay un padecimiento especifico detectado, solo mostrar ese
        pad_filtro = ent.get("padecimiento")
        # Normalizar para buscar (ej: "Depresion" vs "Depresión")
        pad_key = None
        if pad_filtro:
            pf = _norm(pad_filtro)
            for k in por_pad:
                if _norm(k) == pf:
                    pad_key = k
                    break

        lines = ["**Composicion demografica por padecimiento**\n"]
        pads_to_show = {pad_key: por_pad[pad_key]} if pad_key else por_pad
        demo_hist = s.get("demo_historica", {})

        for pad, pinfo in pads_to_show.items():
            pad_sexo = pinfo.get("por_sexo", {})
            lines.append(f"**{pad}** ({pinfo['n']} modelos):")

            # --- Historico (boletin, datos reales acumulados) ---
            hist = demo_hist.get(pad)
            if hist:
                lines.append(f"  Historico acumulado (2014-2026): **{hist['total']:,} casos**")
                ratio_h = hist["ratio_mh"]
                if ratio_h >= 1.1:
                    predom = "predominancia femenina"
                elif ratio_h <= 0.9:
                    predom = "predominancia masculina"
                else:
                    predom = "equilibrado"
                lines.append(
                    f"  Hombres: {hist['hombres']:,} ({hist['pct_h']}%)  |  "
                    f"Mujeres: {hist['mujeres']:,} ({hist['pct_m']}%)"
                )
                lines.append(f"  Ratio M/H: {ratio_h}:1 ({predom})")

            # --- Pronostico (modelos de produccion, 52 sem futuras) ---
            if pad_sexo:
                nac_h = pad_sexo.get("hombres", {}).get("casos_nacional")
                nac_m = pad_sexo.get("mujeres", {}).get("casos_nacional")
                nac_g = pad_sexo.get("general", {}).get("casos_nacional")

                if nac_g:
                    lines.append(f"  Pronostico 52 sem: **{nac_g:,} casos** (Nacional)")
                if nac_h is not None and nac_m is not None:
                    total_hm = nac_h + nac_m
                    if total_hm > 0:
                        pct_h = round(nac_h / total_hm * 100, 1)
                        pct_m = round(nac_m / total_hm * 100, 1)
                        lines.append(
                            f"  Pron. H: {nac_h:,} ({pct_h}%)  |  Pron. M: {nac_m:,} ({pct_m}%)"
                        )

            # SMAPE por sexo
            if pad_sexo:
                smape_parts = []
                for sx_key, sx_label in [
                    ("general", "Gral"),
                    ("hombres", "H"),
                    ("mujeres", "M"),
                ]:
                    sx_data = pad_sexo.get(sx_key, {})
                    sm = sx_data.get("smape_prod_median")
                    if sm is not None:
                        smape_parts.append(f"{sx_label}={sm}%")
                if smape_parts:
                    lines.append(f"  SMAPE mediano: {', '.join(smape_parts)}")

            lines.append("")  # linea en blanco entre padecimientos

        return "\n".join(lines) if len(lines) > 1 else None

    def _answer_metrica_global(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre metricas globales."""
        metric_map = {
            "smape": "smape_prod",
            "mase": "mase_prod",
            "rmse": "rmse_prod",
            "mae": "mae_prod",
        }
        found_metric = None
        for keyword, prefix in metric_map.items():
            if keyword in q:
                found_metric = prefix
                break

        if not found_metric:
            # Busca "metrica" o "metricas" generico
            if any(t in q for t in ["metrica", "rendimiento", "performance", "como va"]):
                lines = ["**Métricas globales de producción** (333 modelos):\n"]
                for prefix, label in [
                    ("smape_prod", "SMAPE"),
                    ("mase_prod", "MASE"),
                    ("rmse_prod", "RMSE"),
                    ("mae_prod", "MAE"),
                ]:
                    mean = s.get(f"{prefix}_mean")
                    med = s.get(f"{prefix}_median")
                    if mean is not None:
                        unit = "%" if "smape" in prefix else ""
                        lines.append(f"- **{label}**: media={mean}{unit}, mediana={med}{unit}")
                return "\n".join(lines)
            return None

        # Metrica especifica
        label = found_metric.replace("_prod", "").upper()
        mean = s.get(f"{found_metric}_mean")
        med = s.get(f"{found_metric}_median")
        mn = s.get(f"{found_metric}_min")
        mx = s.get(f"{found_metric}_max")
        std = s.get(f"{found_metric}_std")
        unit = "%" if "smape" in found_metric else ""

        if mean is None:
            return None

        lines = [f"**{label} global** (333 modelos de producción):\n"]
        lines.append(f"- Media: **{mean}{unit}**")
        lines.append(f"- Mediana: **{med}{unit}**")
        lines.append(f"- Mínimo: {mn}{unit}")
        lines.append(f"- Máximo: {mx}{unit}")
        lines.append(f"- Desv. estándar: {std}{unit}")

        # Desglose por padecimiento
        lines.append("\nPor padecimiento:")
        for pad, pinfo in s.get("por_pad", {}).items():
            pm = pinfo.get(f"{found_metric}_mean")
            pmd = pinfo.get(f"{found_metric}_median")
            if pm is not None:
                lines.append(f"  - {pad}: media={pm}{unit}, mediana={pmd}{unit}")

        return "\n".join(lines)

    def _answer_ranking(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre rankings y mejores/peores modelos."""
        is_best = any(t in q for t in ["mejor", "top", "mas bajo", "menor error", "mas preciso"])
        is_worst = any(
            t in q
            for t in ["peor", "bottom", "mas alto", "mayor error", "menos preciso", "problematico"]
        )
        is_ranking = any(t in q for t in ["ranking", "rank", "clasificacion", "lista", "orden"])

        if not (is_best or is_worst or is_ranking):
            return None

        lines = []
        if is_best or is_ranking:
            top5 = s.get("top5_smape", [])
            if top5:
                lines.append("**Top 5 mejores modelos** (menor SMAPE):\n")
                for i, m in enumerate(top5, 1):
                    lines.append(
                        f"{i}. {m['padecimiento']} - {m['entidad']} ({m['sexo']}): "
                        f"SMAPE={m['smape']}%, motor={m['motor']}"
                    )

        if is_worst or is_ranking:
            bot5 = s.get("bottom5_smape", [])
            if bot5:
                if lines:
                    lines.append("")
                lines.append("**Top 5 peores modelos** (mayor SMAPE):\n")
                for i, m in enumerate(reversed(bot5), 1):
                    lines.append(
                        f"{i}. {m['padecimiento']} - {m['entidad']} ({m['sexo']}): "
                        f"SMAPE={m['smape']}%, motor={m['motor']}"
                    )

        return "\n".join(lines) if lines else None

    def _answer_diagnosticos(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre diagnosticos de overfitting y leakage."""
        triggers = [
            "overfitting",
            "sobreajuste",
            "leakage",
            "fuga",
            "diagnostico",
            "salud de",
            "fallback",
            "regional",
        ]
        if not any(t in q for t in triggers):
            return None

        lines = ["**Diagnósticos de los 333 modelos**:\n"]
        lines.append("Overfitting (ratio SMAPE test/train):")
        lines.append(f"  - OK: {s.get('overfitting_ok', '?')}")
        lines.append(f"  - Moderado: {s.get('overfitting_moderado', '?')}")
        lines.append(f"  - Alto: {s.get('overfitting_alto', '?')}")
        lines.append(f"  - N/D: {s.get('overfitting_nd', '?')}")
        lines.append("")
        lines.append("Leakage (SMAPE train < 0.5%):")
        lines.append(f"  - OK: {s.get('leakage_ok', '?')}")
        lines.append(f"  - Sospechoso: {s.get('leakage_sospechoso', '?')}")

        fb = s.get("fallback_n", 0)
        if fb:
            lines.append(f"\nFallback regional: {fb} series usan modelo regional:")
            for det in s.get("fallback_detalles", []):
                lines.append(f"  - {det}")

        return "\n".join(lines)

    def _answer_validacion(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre validacion semanal, precision historica y pronostico vs real."""
        triggers = [
            "validacion",
            "semanal",
            "real vs",
            "predicho vs real",
            "precision historica",
            "acierto",
            "pronosticado",
            "pronosticamos",
            "pronosticaste",
            "predijimos",
            "predijeron",
            "habiamos pronosticado",
            "habias pronosticado",
            "pronostico vs",
            "vs realidad",
            "vs real",
            "acertamos",
            "acertaron",
            "le atinamos",
            "atinamos",
            "fallamos",
            "comparar",
            "compara",
            "comparacion",
            "que tan bien",
            "que tan preciso",
            "como le fue",
            "como nos fue",
            "como le atino",
        ]
        if not any(t in q for t in triggers):
            return None

        prod = self.cache.prod_models
        pad = ent.get("padecimiento")
        estado = ent.get("estado")
        sexo = ent.get("sexo")

        # Si preguntan cuanto pronosticamos, mostrar pron_sem_previa vs realidad
        is_forecast_q = any(
            t in q
            for t in [
                "pronosticado",
                "pronosticamos",
                "pronosticaste",
                "predijimos",
                "predijeron",
                "habiamos pronosticado",
                "habias pronosticado",
                "acertamos",
                "acertaron",
                "le atinamos",
                "atinamos",
                "fallamos",
                "comparar",
                "compara",
                "comparacion",
                "que tan bien",
                "que tan preciso",
                "como le fue",
                "como nos fue",
                "como le atino",
                "vs real",
                "vs realidad",
                "pronostico vs",
                "real vs",
                "validacion",
            ]
        )

        if is_forecast_q and prod is not None and not prod.empty:
            df = prod.copy()
            # Filtrar por entidades detectadas
            if pad:
                pad_n = _norm(pad)
                df = df[df["padecimiento"].apply(lambda x: _norm(str(x)) == pad_n)]
            if estado and estado != "Nacional":
                est_n = _norm(estado)
                df = df[df["entidad"].apply(lambda x: est_n in _norm(str(x)))]
            if sexo:
                df = df[df["sexo"].str.lower() == sexo.lower()]

            if "pron_sem_previa" in df.columns and "realidad_sem_previa" in df.columns:
                pron_total = int(df["pron_sem_previa"].fillna(0).sum())
                real_total = int(df["realidad_sem_previa"].fillna(0).sum())

                # Detectar cual semana es
                sem_label = "la semana previa"
                weeks = ent.get("_weeks", [])
                if weeks:
                    sem_label = f"la semana {weeks[0]}"

                lines = [f"**Pronóstico vs realidad ({sem_label})**\n"]
                lines.append(f"- Casos pronosticados: **{pron_total:,}**")
                lines.append(f"- Casos reales: **{real_total:,}**")
                diff = pron_total - real_total
                if real_total > 0:
                    error_pct = abs(diff) / real_total * 100
                    direction = "sobreestimamos" if diff > 0 else "subestimamos"
                    lines.append(f"- Diferencia: {diff:+,} ({direction} por {error_pct:.1f}%)")

                # Desglose por padecimiento si no se filtro
                if not pad and "padecimiento" in df.columns:
                    lines.append("\n**Desglose por padecimiento**:")
                    for p in sorted(df["padecimiento"].unique()):
                        sub = df[df["padecimiento"] == p]
                        p_pron = int(sub["pron_sem_previa"].fillna(0).sum())
                        p_real = int(sub["realidad_sem_previa"].fillna(0).sum())
                        p_diff = p_pron - p_real
                        lines.append(
                            f"- {p}: pronóstico {p_pron:,} vs real {p_real:,} ({p_diff:+,})"
                        )

                # Desglose por sexo si se filtro por padecimiento pero no por sexo
                if pad and not sexo and "sexo" in df.columns:
                    lines.append(f"\n**Desglose por sexo ({pad})**:")
                    for sx in sorted(df["sexo"].unique()):
                        sub = df[df["sexo"] == sx]
                        s_pron = int(sub["pron_sem_previa"].fillna(0).sum())
                        s_real = int(sub["realidad_sem_previa"].fillna(0).sum())
                        lines.append(f"- {sx}: pronóstico {s_pron:,} vs real {s_real:,}")

                return "\n".join(lines)

        # Respuesta generica de validacion
        lines = ["**Validación**:\n"]
        vs = s.get("validacion_semanal")
        if vs:
            lines.append("Semana previa (pronóstico vs real):")
            lines.append(f"  - Error absoluto medio: {vs['error_abs_medio']}")
            lines.append(f"  - Error absoluto mediano: {vs['error_abs_mediano']}")
        ph_mean = s.get("precision_historica_mean")
        ph_med = s.get("precision_historica_median")
        if ph_mean:
            lines.append("\nPrecisión histórica (52 semanas pronos/real):")
            lines.append(f"  - Media: {ph_mean}%")
            lines.append(f"  - Mediana: {ph_med}%")

        return "\n".join(lines) if len(lines) > 1 else None

    def _answer_infra(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre infraestructura y pipeline."""
        triggers = [
            "test",
            "prueba",
            "cobertura",
            "coverage",
            "linea",
            "codigo",
            "infraestructura",
            "pipeline",
            "cicd",
            "ci cd",
            "ci/cd",
            "comando",
            "make",
            "horizonte",
            "evaluacion",
        ]
        if not any(t in q for t in triggers):
            return None

        if any(t in q for t in ["test", "prueba", "cobertura", "coverage"]):
            return (
                f"**Testing**:\n"
                f"- Tests totales: **{s.get('tests', 849)}**\n"
                f"- Archivos de test: {s.get('archivos_test', 46)}\n"
                f"- Cobertura: >{s.get('cobertura', 70)}%\n"
                f"- Comando: `make quality` (lint + typecheck + tests)"
            )

        if any(t in q for t in ["linea", "codigo"]):
            return (
                f"**Código fuente**:\n"
                f"- Líneas de código (src/epiforecast/): ~{s.get('lineas_codigo', 13000):,}\n"
                f"- Modelos evaluados: {s.get('evaluaciones_totales', 1332):,} "
                f"(4 motores x {s.get('total_modelos', 333)} series)"
            )

        if "horizonte" in q:
            return f"El horizonte de pronóstico es de **{s.get('horizonte', 52)} semanas**."

        return None

    def _answer_conteo(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre conteos y distribucion de modelos."""
        triggers = [
            "cuanto",
            "cuanta",
            "cuantos",
            "cuantas",
            "total de",
            "numero de",
            "cantidad",
            "evaluacion",
        ]
        if not any(t in q for t in triggers):
            return None

        if any(t in q for t in ["modelo", "serie"]):
            dist = s.get("dist_motor", {})
            total = s.get("total_modelos", 333)
            lines = [
                f"**{total} modelos de producción** (3 padecimientos x 37 geografías x 3 sexos):\n"
            ]
            for m, c in sorted(dist.items(), key=lambda x: -x[1]):
                pct = round(c / total * 100, 1)
                lines.append(f"- {m}: {c} ({pct}%)")
            return "\n".join(lines)

        if any(t in q for t in ["estado", "entidad"]):
            return "**37 geografías**: 32 entidades federativas + 4 regiones INEGI + 1 nacional."

        if any(t in q for t in ["padecimiento", "enfermedad"]):
            return (
                "**3 padecimientos**:\n"
                "- Depresión (F32): ~111 modelos\n"
                "- Parkinson (G20): ~111 modelos\n"
                "- Alzheimer (G30): ~111 modelos"
            )

        if any(t in q for t in ["evaluacion"]):
            return (
                f"**{s.get('evaluaciones_totales', 1332):,} evaluaciones totales** "
                f"(4 motores x {s.get('total_modelos', 333)} series)."
            )

        return None

    def _answer_pronostico(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre pronosticos acumulados."""
        triggers = [
            "pronostico",
            "forecast",
            "prediccion",
            "proyeccion",
            "proyect",
            "se espera",
            "futuro",
            "predice",
        ]
        # "caso" e "incidencia" solo cuentan si hay contexto de futuro
        future_ctx = any(t in q for t in triggers)
        general_triggers = ["caso", "incidencia"]
        has_general = any(t in q for t in general_triggers)

        if not future_ctx and not has_general:
            return None
        # Si solo tiene triggers generales sin contexto de futuro, no capturar
        if has_general and not future_ctx:
            return None

        pad = ent.get("padecimiento")
        if pad:
            info = s.get("por_pad", {}).get(pad)
            if info:
                cas = info.get("casos_futuro_total")
                if cas:
                    return f"Pronóstico acumulado de **{pad}** para 52 semanas: **{cas:,} casos**."

        total = s.get("pronostico_total")
        lines = [f"**Pronóstico acumulado 52 semanas**: {total:,} casos totales\n"]
        for pad_name, pinfo in s.get("por_pad", {}).items():
            cas = pinfo.get("casos_futuro_total", 0)
            lines.append(f"- {pad_name}: {cas:,} casos")
        return "\n".join(lines) if total else None

    def _answer_definicion(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde definiciones de terminos tecnicos."""
        defs: dict[str, str] = {
            "smape": (
                "**SMAPE** (Symmetric Mean Absolute Percentage Error) mide el error "
                "porcentual simétrico entre predicción y realidad. Rango [0%, 200%]. "
                "Es la métrica **primaria** de selección de modelos en EpiForecast-MX.\n\n"
                f"SMAPE global actual: media={s.get('smape_prod_mean', '?')}%, "
                f"mediana={s.get('smape_prod_median', '?')}%"
            ),
            "mase": (
                "**MASE** (Mean Absolute Scaled Error) compara el error del modelo "
                "contra un pronóstico naive estacional (lag-52 semanas). MASE < 1 "
                "significa que el modelo supera al baseline naive. Se usa como "
                "**desempate** (umbral 5%) cuando dos motores tienen SMAPE similar.\n\n"
                f"MASE global actual: media={s.get('mase_prod_mean', '?')}, "
                f"mediana={s.get('mase_prod_median', '?')}"
            ),
            "rmse": (
                "**RMSE** (Root Mean Squared Error) penaliza errores grandes al "
                "elevar al cuadrado antes de promediar. Está en las mismas unidades "
                "que la variable objetivo (casos/semana). Se usa como segundo "
                "desempate en la selección de modelos.\n\n"
                f"RMSE global actual: media={s.get('rmse_prod_mean', '?')}, "
                f"mediana={s.get('rmse_prod_median', '?')}"
            ),
            "mae": (
                "**MAE** (Mean Absolute Error) es el error promedio absoluto. "
                "Robusto a outliers. En las mismas unidades que la variable.\n\n"
                f"MAE global actual: media={s.get('mae_prod_mean', '?')}, "
                f"mediana={s.get('mae_prod_median', '?')}"
            ),
            "prophet": (
                "**Prophet** es un modelo aditivo de Meta (2018) que descompone "
                "series temporales en tendencia + estacionalidad + regresores. "
                f"En EpiForecast-MX gana {s.get('dist_motor', {}).get('Prophet', 0)} de "
                f"{s.get('total_modelos', 333)} series."
            ),
            "deepar": (
                "**DeepAR** es una red neuronal autoregresiva probabilística (Amazon, 2020) "
                "que aprende la distribución conjunta de múltiples series de tiempo "
                "(cross-learning). Usa LSTM + PyTorch via GluonTS. "
                f"En EpiForecast-MX gana **{s.get('dist_motor', {}).get('DeepAR', 0)}** de "
                f"{s.get('total_modelos', 333)} series ({s.get('motor_ganador_pct', '?')}%)."
            ),
            "ensemble": (
                "**Ensemble** combina Prophet (componente de tendencia/estacionalidad) "
                "con XGBoost (captura residuales no lineales). "
                f"Gana {s.get('dist_motor', {}).get('Ensemble', 0)} de "
                f"{s.get('total_modelos', 333)} series."
            ),
            "stacking": (
                "**Stacking** es un meta-aprendizaje donde 3 expertos (Prophet, ETS, "
                "LightGBM) alimentan un meta-learner Ridge con pesos no negativos. "
                f"Gana {s.get('dist_motor', {}).get('Stacking', 0)} de "
                f"{s.get('total_modelos', 333)} series."
            ),
            "overfitting": (
                "**Overfitting** (sobreajuste) se detecta comparando SMAPE de test vs train. "
                "Umbrales: OK (<1.3x), Moderado (1.3-2x), Alto (>2x).\n\n"
                f"Estado actual: OK={s.get('overfitting_ok', '?')}, "
                f"Moderado={s.get('overfitting_moderado', '?')}, "
                f"Alto={s.get('overfitting_alto', '?')}"
            ),
            "leakage": (
                "**Leakage** (fuga de datos) se sospecha cuando SMAPE de train es "
                "anormalmente bajo (<0.5%). Significa que información del test "
                "se filtró al entrenamiento.\n\n"
                f"Estado actual: OK={s.get('leakage_ok', '?')}, "
                f"Sospechoso={s.get('leakage_sospechoso', '?')}"
            ),
            "fallback": (
                "**Fallback regional**: cuando una serie estatal tiene incidencia "
                "demasiado baja (<5 casos en 52 sem), se usa el modelo de la "
                f"región INEGI correspondiente. Actualmente {s.get('fallback_n', 0)} "
                "series usan fallback."
            ),
        }

        for keyword, definition in defs.items():
            if keyword in q and (
                "que es" in q or "define" in q or "explica" in q or "significa" in q
            ):
                return definition

        return None

    # ------------------------------------------------------------------
    # Contexto enriquecido para Gemini
    # ------------------------------------------------------------------

    def build_rich_context(self, query: str) -> str:
        """Construye contexto ultra-detallado para system prompt de Gemini."""
        s = self._ensure_stats()
        entities = _detect_entities(query)
        parts: list[str] = []

        parts.append("=== BASE DE CONOCIMIENTO EpiForecast-MX ===\n")
        parts.append(f"Modelo activo: {s.get('modelo_activo', '?')}")
        parts.append(f"Total modelos producción: {s.get('total_modelos', 333)}")
        parts.append(f"Horizonte: {s.get('horizonte', 52)} semanas")
        parts.append(
            f"Evaluaciones totales: {s.get('evaluaciones_totales', 1332)} (4 motores x 333 series)"
        )

        # Distribucion de motores
        dist = s.get("dist_motor", {})
        if dist:
            parts.append("\nMotor ganador global:")
            for m, c in sorted(dist.items(), key=lambda x: -x[1]):
                pct = round(c / s.get("total_modelos", 333) * 100, 1)
                parts.append(f"  {m}: {c} series ({pct}%)")

        # Metricas globales
        parts.append("\nMétricas globales de producción:")
        for prefix, label in [
            ("smape_prod", "SMAPE"),
            ("mase_prod", "MASE"),
            ("rmse_prod", "RMSE"),
            ("mae_prod", "MAE"),
        ]:
            mean = s.get(f"{prefix}_mean")
            med = s.get(f"{prefix}_median")
            if mean is not None:
                unit = "%" if "smape" in prefix else ""
                parts.append(f"  {label}: media={mean}{unit}, mediana={med}{unit}")

        # Por padecimiento
        for pad, pinfo in s.get("por_pad", {}).items():
            parts.append(f"\n--- {pad} ---")
            parts.append(f"  Series: {pinfo['n']}")
            sm = pinfo.get("smape_prod_mean")
            if sm:
                parts.append(f"  SMAPE: media={sm}%, mediana={pinfo.get('smape_prod_median')}%")
            ms = pinfo.get("mase_prod_mean")
            if ms:
                parts.append(f"  MASE: media={ms}, mediana={pinfo.get('mase_prod_median')}")
            cas = pinfo.get("casos_futuro_total")
            if cas:
                parts.append(f"  Pronóstico 52 sem: {cas:,} casos")
            pd_dist = pinfo.get("dist_motor", {})
            for m, c in sorted(pd_dist.items(), key=lambda x: -x[1]):
                parts.append(f"  {m}: {c} series")

        # Diagnosticos
        parts.append("\nDiagnósticos:")
        parts.append(
            f"  Overfitting: OK={s.get('overfitting_ok')}, Mod={s.get('overfitting_moderado')}, Alto={s.get('overfitting_alto')}"
        )
        parts.append(
            f"  Leakage: OK={s.get('leakage_ok')}, Sospechoso={s.get('leakage_sospechoso')}"
        )
        parts.append(f"  Fallback regional: {s.get('fallback_n', 0)} series")

        # Por sexo
        for sx, sinfo in s.get("por_sexo", {}).items():
            parts.append(
                f"  Sexo {sx}: SMAPE={sinfo.get('smape_mean')}%, MASE={sinfo.get('mase_mean')}"
            )

        # Metricas por motor (comparativa)
        parts.append("\nComparativa de motores (todas las series):")
        for motor, minfo in s.get("por_motor", {}).items():
            sm = minfo.get("smape_mean", "?")
            ms = minfo.get("mase_mean", "?")
            parts.append(f"  {motor}: SMAPE={sm}%, MASE={ms}")

        # Contexto filtrado segun la pregunta
        pad = entities.get("padecimiento")
        estado = entities.get("estado")

        if estado:
            prod = self.cache.prod_models
            if prod is not None:
                est_n = _norm(estado)
                sub = prod[prod["entidad"].apply(lambda x: est_n in _norm(str(x)))]
                if not sub.empty:
                    parts.append(f"\n=== DETALLE {estado.upper()} ===")
                    for _, r in sub.iterrows():
                        parts.append(
                            f"  {r.get('padecimiento', '?')} / {r.get('sexo', '?')}: "
                            f"motor={r.get('modelo_produccion', '?')}, SMAPE={r.get('smape_prod', '?')}%, "
                            f"MASE={r.get('mase_prod', '?')}, casos_52s={r.get('casos_52_semanas_futuro', '?')}, "
                            f"overfitting={r.get('overfitting', '?')}, leakage={r.get('leakage', '?')}"
                        )

        if pad and not estado:
            prod = self.cache.prod_models
            if prod is not None:
                pad_n = _norm(pad)
                sub = prod[prod["padecimiento"].apply(lambda x: _norm(str(x)) == pad_n)]
                if not sub.empty:
                    parts.append(f"\n=== DETALLE {pad.upper()} (muestra 15 series) ===")
                    for _, r in sub.head(15).iterrows():
                        parts.append(
                            f"  {r.get('entidad', '?')} / {r.get('sexo', '?')}: "
                            f"motor={r.get('modelo_produccion', '?')}, SMAPE={r.get('smape_prod', '?')}%, "
                            f"MASE={r.get('mase_prod', '?')}, casos={r.get('casos_52_semanas_futuro', '?')}"
                        )

        # Pronostico total
        total = s.get("pronostico_total")
        if total:
            parts.append(f"\nPronóstico total 52 sem: {total:,} casos")

        # Precision historica
        ph = s.get("precision_historica_mean")
        if ph:
            parts.append(f"Precisión histórica media: {ph}%")

        # --- Datos historicos del boletin (si la pregunta lo requiere) ---
        years: list[int] = entities.get("_years", [])  # type: ignore[assignment]
        hist_kw = any(
            t in _norm(query)
            for t in [
                "caso",
                "historico",
                "tendencia",
                "hubo",
                "boletin",
                "anual",
                "covid",
                "pandemia",
                "incidencia",
                "registro",
            ]
        )
        if years or hist_kw:
            df_bol = self.cache.boletin
            if df_bol is not None:
                parts.append("\n=== BOLETÍN EPIDEMIOLÓGICO (datos históricos) ===")
                parts.append(f"Registros totales: {len(df_bol):,} (2014-2026)")
                parts.append(
                    "Columnas: Anio, Semana, Entidad, Padecimiento, Casos_semana, "
                    "Acumulado_hombres, Acumulado_mujeres, Acumulado_anio_anterior"
                )

                # Resumen por padecimiento y ano
                by_yp = (
                    df_bol.groupby(["Anio", "Padecimiento"])["Casos_semana"]
                    .sum()
                    .unstack(fill_value=0)
                )
                parts.append("\nCasos anuales por padecimiento:")
                for y in by_yp.index:
                    vals = [f"{p}={int(by_yp.loc[y, p]):,}" for p in by_yp.columns]
                    parts.append(f"  {y}: {', '.join(vals)}")

                # Filtro especifico si hay estado
                if estado:
                    est_n = _norm(estado)
                    if est_n in ("ciudad de mexico", "distrito federal", "cdmx"):
                        sub_e = df_bol[
                            df_bol["Entidad"].apply(
                                lambda x: _norm(str(x)) in ("ciudad de mexico", "distrito federal")
                            )
                        ]
                    else:
                        sub_e = df_bol[df_bol["Entidad"].apply(lambda x: est_n in _norm(str(x)))]
                    if not sub_e.empty:
                        by_yp2 = (
                            sub_e.groupby(["Anio", "Padecimiento"])["Casos_semana"]
                            .sum()
                            .unstack(fill_value=0)
                        )
                        parts.append(f"\nCasos anuales en {estado}:")
                        for y in by_yp2.index:
                            vals = [f"{p}={int(by_yp2.loc[y, p]):,}" for p in by_yp2.columns]
                            parts.append(f"  {y}: {', '.join(vals)}")

        # Infraestructura
        parts.append(
            f"\nInfraestructura: {s.get('tests')} tests, ~{s.get('lineas_codigo'):,} líneas, >{s.get('cobertura')}% cobertura"
        )

        return "\n".join(parts)

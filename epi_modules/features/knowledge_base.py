"""Base de conocimiento del proyecto EpiForecast-MX.

Pre-computa estadisticas profundas desde los datos reales del proyecto
y responde preguntas con precision sin necesidad de IA externa.
"""

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


def _detect_entities(q: str) -> dict[str, str | None]:
    """Detecta padecimiento, estado, sexo y modelo en la pregunta."""
    qn = _norm(q)
    result: dict[str, str | None] = {
        "padecimiento": None,
        "estado": None,
        "sexo": None,
        "modelo": None,
    }
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
                    ps["casos_futuro_total"] = int(sub["casos_52_semanas_futuro"].sum())
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
            stats["pronostico_total"] = int(df["casos_52_semanas_futuro"].sum())

        # --- INFRAESTRUCTURA ---
        stats["tests"] = 849
        stats["lineas_codigo"] = 13000
        stats["cobertura"] = 70
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
            # Consultas especificas (padecimiento + estado + metrica)
            ("_answer_specific_series",),
            # Consultas por estado
            ("_answer_estado",),
            # Consultas por padecimiento
            ("_answer_padecimiento",),
            # Consultas por modelo/motor
            ("_answer_motor",),
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

        lines = [f"**{pad} en {estado}**" + (f" ({sexo})" if sexo else "") + ":\n"]
        for _, r in sub.iterrows():
            sex_label = r.get("sexo", "")
            motor = r.get("modelo_produccion", "?")
            smape = r.get("smape_prod", 0)
            mase = r.get("mase_prod", 0)
            rmse = r.get("rmse_prod", 0)
            casos = r.get("casos_52_semanas_futuro", 0)
            ov = r.get("overfitting", "?")
            just = r.get("justificacion", "")
            lines.append(
                f"- **{sex_label}**: motor={motor}, SMAPE={smape:.1f}%, MASE={mase:.2f}, RMSE={rmse:.1f}"
            )
            lines.append(f"  Pronostico 52 sem: {casos:,} casos | Overfitting: {ov}")
            if just:
                lines.append(f"  Justificacion: {just}")

        pron = sub.get("pron_sem_previa")
        real = sub.get("realidad_sem_previa")
        if pron is not None and real is not None:
            for _, r in sub.iterrows():
                p = r.get("pron_sem_previa", "?")
                re_ = r.get("realidad_sem_previa", "?")
                lines.append(f"  Semana previa: pronostico={p}, real={re_}")

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

        lines = [f"**{estado}** ({info['n']} modelos de produccion):\n"]
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
            lines.append(f"- Pronostico total 52 sem: {cas:,} casos")

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

        lines = [f"**{pad}** ({info['n']} modelos de produccion):\n"]
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
            lines.append("- Distribucion de motores:")
            for m, c in sorted(dist.items(), key=lambda x: -x[1]):
                pct = round(c / info["n"] * 100, 1)
                lines.append(f"  - {m}: {c} ({pct}%)")

        cas = info.get("casos_futuro_total")
        if cas:
            lines.append(f"- Pronostico acumulado 52 sem: **{cas:,} casos**")

        return "\n".join(lines)

    def _answer_motor(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde sobre un motor/modelo especifico."""
        modelo = ent.get("modelo")

        # Detectar preguntas sobre "quien gana" sin modelo especifico
        if not modelo and any(t in q for t in ["gana", "ganador", "campeon", "winner", "domina"]):
            dist = s.get("dist_motor", {})
            total = s.get("total_modelos", 333)
            lines = [f"**Distribucion de modelos ganadores** ({total} series):\n"]
            for m, c in sorted(dist.items(), key=lambda x: -x[1]):
                pct = round(c / total * 100, 1)
                lines.append(f"- **{m}**: {c} series ({pct}%)")
            lines.append(
                f"\nMotor campeon global: **{s.get('motor_ganador')}** "
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
        lines = ["**Analisis por sexo**:\n"]
        for sx, info in por_sexo.items():
            sm = info.get("smape_mean", "?")
            ms = info.get("mase_mean", "?")
            lines.append(f"- **{sx}**: {info['n']} modelos, SMAPE={sm}%, MASE={ms}")
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
                lines = ["**Metricas globales de produccion** (333 modelos):\n"]
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

        lines = [f"**{label} global** (333 modelos de produccion):\n"]
        lines.append(f"- Media: **{mean}{unit}**")
        lines.append(f"- Mediana: **{med}{unit}**")
        lines.append(f"- Minimo: {mn}{unit}")
        lines.append(f"- Maximo: {mx}{unit}")
        lines.append(f"- Desv. estandar: {std}{unit}")

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

        lines = ["**Diagnosticos de los 333 modelos**:\n"]
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
        """Responde sobre validacion semanal y precision historica."""
        triggers = [
            "validacion",
            "semanal",
            "real vs",
            "predicho vs real",
            "precision historica",
            "acierto",
        ]
        if not any(t in q for t in triggers):
            return None

        lines = ["**Validacion**:\n"]
        vs = s.get("validacion_semanal")
        if vs:
            lines.append("Semana previa (pronostico vs real):")
            lines.append(f"  - Error absoluto medio: {vs['error_abs_medio']}")
            lines.append(f"  - Error absoluto mediano: {vs['error_abs_mediano']}")
        ph_mean = s.get("precision_historica_mean")
        ph_med = s.get("precision_historica_median")
        if ph_mean:
            lines.append("\nPrecision historica (52 semanas pronos/real):")
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
                f"**Codigo fuente**:\n"
                f"- Lineas de codigo (src/epiforecast/): ~{s.get('lineas_codigo', 13000):,}\n"
                f"- Modelos evaluados: {s.get('evaluaciones_totales', 1332):,} "
                f"(4 motores x {s.get('total_modelos', 333)} series)"
            )

        if "horizonte" in q:
            return f"El horizonte de pronostico es de **{s.get('horizonte', 52)} semanas**."

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
                f"**{total} modelos de produccion** (3 padecimientos x 37 geografias x 3 sexos):\n"
            ]
            for m, c in sorted(dist.items(), key=lambda x: -x[1]):
                pct = round(c / total * 100, 1)
                lines.append(f"- {m}: {c} ({pct}%)")
            return "\n".join(lines)

        if any(t in q for t in ["estado", "entidad"]):
            return "**37 geografias**: 32 entidades federativas + 4 regiones INEGI + 1 nacional."

        if any(t in q for t in ["padecimiento", "enfermedad"]):
            return (
                "**3 padecimientos**:\n"
                "- Depresion (F32): ~111 modelos\n"
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
        triggers = ["pronostico", "forecast", "caso", "incidencia", "prediccion", "proyeccion"]
        if not any(t in q for t in triggers):
            return None

        pad = ent.get("padecimiento")
        if pad:
            info = s.get("por_pad", {}).get(pad)
            if info:
                cas = info.get("casos_futuro_total")
                if cas:
                    return f"Pronostico acumulado de **{pad}** para 52 semanas: **{cas:,} casos**."

        total = s.get("pronostico_total")
        lines = [f"**Pronostico acumulado 52 semanas**: {total:,} casos totales\n"]
        for pad_name, pinfo in s.get("por_pad", {}).items():
            cas = pinfo.get("casos_futuro_total", 0)
            lines.append(f"- {pad_name}: {cas:,} casos")
        return "\n".join(lines) if total else None

    def _answer_definicion(self, q: str, ent: dict, s: dict) -> str | None:
        """Responde definiciones de terminos tecnicos."""
        defs: dict[str, str] = {
            "smape": (
                "**SMAPE** (Symmetric Mean Absolute Percentage Error) mide el error "
                "porcentual simetrico entre prediccion y realidad. Rango [0%, 200%]. "
                "Es la metrica **primaria** de seleccion de modelos en EpiForecast-MX.\n\n"
                f"SMAPE global actual: media={s.get('smape_prod_mean', '?')}%, "
                f"mediana={s.get('smape_prod_median', '?')}%"
            ),
            "mase": (
                "**MASE** (Mean Absolute Scaled Error) compara el error del modelo "
                "contra un pronostico naive estacional (lag-52 semanas). MASE < 1 "
                "significa que el modelo supera al baseline naive. Se usa como "
                "**desempate** (umbral 5%) cuando dos motores tienen SMAPE similar.\n\n"
                f"MASE global actual: media={s.get('mase_prod_mean', '?')}, "
                f"mediana={s.get('mase_prod_median', '?')}"
            ),
            "rmse": (
                "**RMSE** (Root Mean Squared Error) penaliza errores grandes al "
                "elevar al cuadrado antes de promediar. Esta en las mismas unidades "
                "que la variable objetivo (casos/semana). Se usa como segundo "
                "desempate en la seleccion de modelos.\n\n"
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
                "**DeepAR** es una red neuronal autoregresiva probabilistica (Amazon, 2020) "
                "que aprende la distribucion conjunta de multiples series de tiempo "
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
                "anormalmente bajo (<0.5%). Significa que informacion del test "
                "se filtro al entrenamiento.\n\n"
                f"Estado actual: OK={s.get('leakage_ok', '?')}, "
                f"Sospechoso={s.get('leakage_sospechoso', '?')}"
            ),
            "fallback": (
                "**Fallback regional**: cuando una serie estatal tiene incidencia "
                "demasiado baja (<5 casos en 52 sem), se usa el modelo de la "
                f"region INEGI correspondiente. Actualmente {s.get('fallback_n', 0)} "
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
        parts.append(f"Total modelos produccion: {s.get('total_modelos', 333)}")
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
        parts.append("\nMetricas globales de produccion:")
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
                parts.append(f"  Pronostico 52 sem: {cas:,} casos")
            pd_dist = pinfo.get("dist_motor", {})
            for m, c in sorted(pd_dist.items(), key=lambda x: -x[1]):
                parts.append(f"  {m}: {c} series")

        # Diagnosticos
        parts.append("\nDiagnosticos:")
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
            parts.append(f"\nPronostico total 52 sem: {total:,} casos")

        # Precision historica
        ph = s.get("precision_historica_mean")
        if ph:
            parts.append(f"Precision historica media: {ph}%")

        # Infraestructura
        parts.append(
            f"\nInfraestructura: {s.get('tests')} tests, ~{s.get('lineas_codigo'):,} lineas, >{s.get('cobertura')}% cobertura"
        )

        return "\n".join(parts)

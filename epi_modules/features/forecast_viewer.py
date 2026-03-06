"""Visor de pronosticos con sparklines Unicode."""

import unicodedata

import numpy as np
import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table

from .data_cache import ProjectDataCache


def _strip_accents(text: str) -> str:
    """Elimina acentos para comparacion insensible."""
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


SPARK_CHARS = "\u2581\u2582\u2583\u2584\u2585\u2586\u2587\u2588"


def _sparkline(values: list[float], width: int = 52) -> str:
    """Genera sparkline Unicode de una serie de valores."""
    if not values:
        return ""
    vals = [v for v in values if not (isinstance(v, float) and np.isnan(v))]
    if not vals:
        return "[gris]-[/gris]"
    mn, mx = min(vals), max(vals)
    rng = mx - mn if mx != mn else 1.0
    chars = []
    for v in vals[:width]:
        idx = int((v - mn) / rng * (len(SPARK_CHARS) - 1))
        idx = max(0, min(idx, len(SPARK_CHARS) - 1))
        chars.append(SPARK_CHARS[idx])
    return f"[dorado]{''.join(chars)}[/dorado]"


def _find_series(
    df: pd.DataFrame,
    estado: str,
    padecimiento: str,
) -> pd.DataFrame | None:
    """Busca una serie en tableau y la devuelve ordenada por fecha."""
    mask = pd.Series([True] * len(df), index=df.index)

    estado_norm = _strip_accents(estado)
    padecimiento_norm = _strip_accents(padecimiento)

    # Filtrar por estado (sin acentos)
    for col in ["entidad", "Entidad", "estado"]:
        if col in df.columns:
            col_norm = df[col].astype(str).apply(_strip_accents)
            m = col_norm.str.contains(estado_norm, na=False)
            if m.any():
                mask = mask & m
                break

    # Filtrar por padecimiento (sin acentos)
    for col in ["padecimiento", "Padecimiento"]:
        if col in df.columns:
            col_norm = df[col].astype(str).apply(_strip_accents)
            m = col_norm.str.contains(padecimiento_norm, na=False)
            if m.any():
                mask = mask & m
                break

    # Filtrar por modo general (exacto)
    for col in ["meta_modo", "modo", "sexo"]:
        if col in df.columns:
            gen_mask = df[col].astype(str).str.lower() == "general"
            if gen_mask.any():
                mask = mask & gen_mask
                break

    result = df[mask]
    if result.empty:
        return None

    # Ordenar por fecha
    for ds_col in ["ds", "fecha", "Fecha", "date"]:
        if ds_col in result.columns:
            result = result.copy()
            result[ds_col] = pd.to_datetime(result[ds_col], errors="coerce")
            result = result.sort_values(ds_col).reset_index(drop=True)
            break

    return result


def _show_forecast(
    console: Console,
    df: pd.DataFrame,
    estado: str,
    padecimiento: str,
) -> None:
    """Muestra pronostico de una serie."""
    console.print()

    # Detectar columna de fecha
    ds_col = next((c for c in ["ds", "fecha", "Fecha", "date"] if c in df.columns), None)

    # Detectar columna de yhat (productivo)
    yhat_col = next((c for c in ["yhat", "yhat_prod"] if c in df.columns), None)

    # Detectar columnas de modelos individuales (legacy tableau.csv)
    model_cols = {
        "Prophet": "yhat_prophet",
        "DeepAR": "yhat_deepar",
        "Ensemble": "yhat_ensemble",
        "Stacking": "yhat_stacking",
    }
    has_model_cols = any(c in df.columns for c in model_cols.values())

    # Separar datos reales vs pronostico
    incr_col = "incrementos_total"
    has_real = incr_col in df.columns

    # Identificar filas con datos reales vs solo pronostico
    if has_real and yhat_col:
        real_mask = df[incr_col].notna()
        forecast_only = df[~real_mask] if real_mask.any() else df
    else:
        forecast_only = df

    # --- Sparkline del pronostico productivo ---
    spark_table = Table(
        title=f"[dorado]PRONOSTICO: {padecimiento.title()} · {estado.title()}[/dorado]",
        show_header=True,
        header_style="dorado",
        box=box.SIMPLE,
        padding=(0, 1),
        expand=True,
    )
    spark_table.add_column("Serie", style="blanco", min_width=16)
    spark_table.add_column("Sparkline (52 sem)", min_width=54)
    spark_table.add_column("Total", justify="right", style="dorado", width=12)

    if has_model_cols:
        # Legacy: mostrar sparkline por cada modelo
        for model_name, col_name in model_cols.items():
            if col_name in df.columns:
                vals = df[col_name].dropna().tolist()
                if vals:
                    last52 = vals[-52:]
                    spark = _sparkline(last52)
                    total = int(sum(last52))
                    spark_table.add_row(model_name, spark, f"{total:,}")

    if yhat_col and yhat_col in df.columns:
        forecast_vals = forecast_only[yhat_col].dropna().tolist()
        if forecast_vals:
            last52 = forecast_vals[-52:]
            spark = _sparkline(last52)
            total = int(sum(last52))
            label = "[verde]Productivo[/verde]" if has_model_cols else "Pronostico"
            total_fmt = f"[verde]{total:,}[/verde]" if has_model_cols else f"{total:,}"
            spark_table.add_row(label, spark, total_fmt)

    # Sparkline de datos reales historicos
    if has_real:
        real_vals = df.loc[df[incr_col].notna(), incr_col].tolist()
        if real_vals:
            last52_real = real_vals[-52:]
            spark_real = _sparkline(last52_real)
            total_real = int(sum(last52_real))
            spark_table.add_row(
                "[gris]Historico (52 sem)[/gris]",
                spark_real,
                f"[gris]{total_real:,}[/gris]",
            )

    console.print(spark_table)

    # --- Detalle semanal: ultimas 10 semanas del pronostico ---
    if yhat_col and yhat_col in df.columns and ds_col:
        tail10 = forecast_only.tail(10)
        pred_vals = tail10[yhat_col].tolist()

        # Semanas epidemiologicas desde fechas
        parsed = pd.to_datetime(tail10[ds_col], errors="coerce").dropna()
        week_labels = [d.isocalendar()[1] for d in parsed]

        detail_table = Table(
            show_header=True,
            header_style="dorado",
            box=box.SIMPLE,
            padding=(0, 1),
            expand=True,
        )
        detail_table.add_column("", style="blanco", width=16)
        detail_table.add_column("Detalle semanal (ultimas 10)", style="gris")
        detail_table.add_column("Total", justify="right", style="dorado", width=12)

        if week_labels:
            week_str = "  ".join(f"{'S' + str(w):>5}" for w in week_labels)
            detail_table.add_row("[sutil]Semana[/sutil]", f"[sutil]{week_str}[/sutil]", "")

        if pred_vals:
            pred_str = "  ".join(f"{int(v):>5}" for v in pred_vals)
            detail_table.add_row("Pronostico", pred_str, f"{int(sum(pred_vals)):,}")

        console.print(detail_table)

    # --- Metricas del modelo productivo ---
    metric_names = {"SMAPE": "smape", "MASE": "mase", "RMSE": "rmse", "MAE": "mae"}
    metrics_found = {}
    for label, col_name in metric_names.items():
        if col_name in df.columns:
            vals = df[col_name].dropna()
            if not vals.empty:
                val = float(vals.iloc[0])
                if val > 0:
                    metrics_found[label] = val

    if metrics_found:
        m_parts = [f"{label}: {val:.2f}" for label, val in metrics_found.items()]
        console.print(f"\n  [sutil]Metricas (productivo): {' \u00b7 '.join(m_parts)}[/sutil]")

    # Nombre del modelo productivo
    if "modelo_productivo" in df.columns:
        prod = df["modelo_productivo"].dropna()
        if not prod.empty:
            console.print(f"  [sutil]Modelo seleccionado: [dorado]{prod.iloc[0]}[/dorado][/sutil]")

    console.print()


def show_forecast_viewer(
    console: Console,
    cache: ProjectDataCache,
    args: str = "",
) -> None:
    """Punto de entrada del visor de pronosticos."""
    parts = args.strip().split()
    if len(parts) < 2:
        console.print(
            "[alerta]Uso: pronostico <estado> <padecimiento>[/alerta]\n"
            "[sutil]  Ejemplo: pronostico jalisco depresion[/sutil]",
        )
        return

    # Detectar padecimiento en cualquier posicion
    padecimientos = {"depresion", "alzheimer", "parkinson"}
    padecimiento = None
    estado_parts = []
    for p in parts:
        if _strip_accents(p) in padecimientos and padecimiento is None:
            padecimiento = p
        else:
            estado_parts.append(p)

    if not padecimiento:
        # Fallback: ultimo token es padecimiento
        padecimiento = parts[-1]
        estado_parts = parts[:-1]

    estado = " ".join(estado_parts)

    tableau = cache.tableau
    if tableau is None:
        console.print("[gris]  No se encontro tableau_model.xlsx ni tableau.csv[/gris]")
        return

    series = _find_series(tableau, estado, padecimiento)
    if series is None:
        console.print(
            f"[alerta]No se encontro serie para '{estado}' + '{padecimiento}'.[/alerta]",
        )
        return

    _show_forecast(console, series, estado, padecimiento)

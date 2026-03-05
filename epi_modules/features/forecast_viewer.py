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
    """Busca una serie en tableau.csv y la devuelve ordenada por fecha."""
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
            result = result.sort_values(ds_col).reset_index(drop=True)
            break

    return result


def _week_labels_from_dates(dates: pd.Series, n: int = 10) -> list[int]:
    """Extrae numeros de semana ISO de las ultimas n fechas."""
    parsed = pd.to_datetime(dates, errors="coerce").dropna().tail(n)
    return [d.isocalendar()[1] for d in parsed]


def _show_forecast(
    console: Console,
    df: pd.DataFrame,
    estado: str,
    padecimiento: str,
) -> None:
    """Muestra pronostico de una serie."""
    console.print()

    model_cols = {
        "Prophet": "yhat_prophet",
        "DeepAR": "yhat_deepar",
        "Ensemble": "yhat_ensemble",
        "Stacking": "yhat_stacking",
    }

    yhat_col = None
    for col in ["yhat", "yhat_prod"]:
        if col in df.columns:
            yhat_col = col
            break

    # Tabla de comparacion de modelos (ultimas 52 semanas = pronostico)
    model_table = Table(
        title=f"[dorado]PRONOSTICO: {estado.title()} \u00b7 {padecimiento.title()}[/dorado]",
        show_header=True,
        header_style="dorado",
        box=box.SIMPLE,
        padding=(0, 1),
        expand=True,
    )
    model_table.add_column("Modelo", style="blanco", min_width=12)
    model_table.add_column("Sparkline (52 sem)", min_width=54)
    model_table.add_column("Total", justify="right", style="dorado", width=12)

    for model_name, col_name in model_cols.items():
        if col_name in df.columns:
            vals = df[col_name].dropna().tolist()
            if vals:
                last52 = vals[-52:]
                spark = _sparkline(last52)
                total = int(sum(last52))
                model_table.add_row(model_name, spark, f"{total:,}")

    # Modelo productivo
    if yhat_col and yhat_col in df.columns:
        vals = df[yhat_col].dropna().tolist()
        if vals:
            last52 = vals[-52:]
            spark = _sparkline(last52)
            total = int(sum(last52))
            model_table.add_row(
                "[verde]Productivo[/verde]",
                spark,
                f"[verde]{total:,}[/verde]",
            )

    console.print(model_table)

    # Detalle semanal: ultimas 10 semanas del pronostico productivo
    if yhat_col and yhat_col in df.columns:
        tail10 = df.tail(10)
        pred_vals = tail10[yhat_col].tolist()

        # Semanas epidemiologicas
        ds_col = None
        for col in ["ds", "fecha", "Fecha", "date"]:
            if col in tail10.columns:
                ds_col = col
                break
        week_labels = _week_labels_from_dates(tail10[ds_col], 10) if ds_col else []

        detail_table = Table(
            show_header=True,
            header_style="dorado",
            box=box.SIMPLE,
            padding=(0, 1),
            expand=True,
        )
        detail_table.add_column("", style="blanco", width=12)
        detail_table.add_column("Detalle semanal (ultimas 10)", style="gris")
        detail_table.add_column("Total", justify="right", style="dorado", width=12)

        # Fila de semanas
        if week_labels:
            week_str = "  ".join(f"{'S' + str(w):>5}" for w in week_labels)
            detail_table.add_row("[sutil]Semana[/sutil]", f"[sutil]{week_str}[/sutil]", "")

        # Fila de pronostico
        if pred_vals:
            pred_str = "  ".join(f"{int(v):>5}" for v in pred_vals)
            detail_table.add_row("Pronostico", pred_str, f"{int(sum(pred_vals)):,}")

        console.print(detail_table)

    # Metricas del modelo productivo
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
            console.print(f"  [sutil]Modelo seleccionado: {prod.iloc[0]}[/sutil]")

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

    # El ultimo token es el padecimiento, el resto es el estado
    padecimiento = parts[-1]
    estado = " ".join(parts[:-1])

    tableau = cache.tableau
    if tableau is None:
        console.print("[gris]  No se encontro tableau.csv[/gris]")
        return

    series = _find_series(tableau, estado, padecimiento)
    if series is None:
        console.print(
            f"[alerta]No se encontro serie para '{estado}' + '{padecimiento}'.[/alerta]",
        )
        return

    _show_forecast(console, series, estado, padecimiento)

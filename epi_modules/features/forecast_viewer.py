"""Visor de pronosticos con sparklines Unicode."""

import numpy as np
import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table

from .data_cache import ProjectDataCache

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
    """Busca una serie en tableau.csv."""
    mask = pd.Series([True] * len(df), index=df.index)

    # Filtrar por estado
    for col in ["entidad", "Entidad", "estado"]:
        if col in df.columns:
            m = df[col].astype(str).str.lower().str.contains(estado.lower(), na=False)
            if m.any():
                mask = mask & m
                break

    # Filtrar por padecimiento
    for col in ["padecimiento", "Padecimiento"]:
        if col in df.columns:
            m = (
                df[col]
                .astype(str)
                .str.lower()
                .str.contains(
                    padecimiento.lower(),
                    na=False,
                )
            )
            if m.any():
                mask = mask & m
                break

    # Filtrar por modo general
    for col in ["modo", "sexo"]:
        if col in df.columns:
            gen_mask = df[col].astype(str).str.lower().str.contains("general", na=False)
            if gen_mask.any():
                mask = mask & gen_mask
                break

    result = df[mask]
    return result if not result.empty else None


def _show_forecast(
    console: Console,
    df: pd.DataFrame,
    estado: str,
    padecimiento: str,
) -> None:
    """Muestra pronostico de una serie."""
    console.print()

    # Buscar columnas de yhat por modelo

    model_cols = {
        "Prophet": "yhat_prophet",
        "DeepAR": "yhat_deepar",
        "Ensemble": "yhat_ensemble",
        "Stacking": "yhat_stacking",
    }

    # Buscar datos historicos y pronostico
    y_real_col = None
    for col in ["y_real", "y", "casos", "Casos"]:
        if col in df.columns:
            y_real_col = col
            break

    yhat_col = None
    for col in ["yhat", "yhat_prod"]:
        if col in df.columns:
            yhat_col = col
            break

    # Tabla de comparacion de modelos
    model_table = Table(
        title=f"[dorado]PRONÓSTICO: {estado.title()} · {padecimiento.title()}[/dorado]",
        show_header=True,
        header_style="dorado",
        box=box.SIMPLE,
        padding=(0, 1),
        expand=True,
    )
    model_table.add_column("Modelo", style="blanco", min_width=12)
    model_table.add_column("Sparkline (52 sem)", min_width=54)
    model_table.add_column("Total", justify="right", style="dorado", width=10)

    for model_name, col_name in model_cols.items():
        if col_name in df.columns:
            vals = df[col_name].dropna().tolist()
            if vals:
                spark = _sparkline(vals)
                total = int(sum(vals))
                model_table.add_row(model_name, spark, f"{total:,}")

    # Modelo productivo
    if yhat_col and yhat_col in df.columns:
        vals = df[yhat_col].dropna().tolist()
        if vals:
            spark = _sparkline(vals)
            total = int(sum(vals))
            model_table.add_row(
                "[verde]Productivo[/verde]",
                spark,
                f"[verde]{total:,}[/verde]",
            )

    console.print(model_table)

    # Historico vs pronostico (ultimas 10 semanas de cada uno)
    if y_real_col and yhat_col:
        hist_table = Table(
            show_header=True,
            header_style="dorado",
            box=box.SIMPLE,
            padding=(0, 1),
            expand=True,
        )
        hist_table.add_column("Tipo", style="blanco", width=12)
        hist_table.add_column("Valores (últimas 10 semanas)", style="gris")
        hist_table.add_column("Total", justify="right", style="dorado", width=10)

        real_vals = df[y_real_col].dropna().tail(10).tolist()
        if real_vals:
            real_str = "  ".join(f"{int(v):>4}" for v in real_vals)
            hist_table.add_row("Real", real_str, f"{int(sum(real_vals)):,}")

        pred_vals = df[yhat_col].dropna().tail(10).tolist()
        if pred_vals:
            pred_str = "  ".join(f"{int(v):>4}" for v in pred_vals)
            hist_table.add_row("Pronóstico", pred_str, f"{int(sum(pred_vals)):,}")

        console.print(hist_table)

    # Metricas
    metric_cols = {
        "SMAPE": "smape",
        "MASE": "mase",
        "RMSE": "rmse",
        "MAE": "mae",
    }
    metrics_found = {}
    for label, prefix in metric_cols.items():
        for col in df.columns:
            if col.lower().startswith(prefix) and "prod" in col.lower():
                vals = df[col].dropna()
                if not vals.empty:
                    metrics_found[label] = vals.iloc[0]
                break

    if metrics_found:
        m_parts = []
        for label, val in metrics_found.items():
            try:
                m_parts.append(f"{label}: {float(val):.2f}")
            except (ValueError, TypeError):
                m_parts.append(f"{label}: {val}")
        console.print(f"\n  [sutil]Métricas: {' · '.join(m_parts)}[/sutil]")

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
            "[alerta]Uso: pronóstico <estado> <padecimiento>[/alerta]\n"
            "[sutil]  Ejemplo: pronóstico jalisco depresión[/sutil]",
        )
        return

    # El ultimo token es el padecimiento, el resto es el estado
    padecimiento = parts[-1]
    estado = " ".join(parts[:-1])

    tableau = cache.tableau
    if tableau is None:
        console.print("[gris]  No se encontró tableau.csv[/gris]")
        return

    series = _find_series(tableau, estado, padecimiento)
    if series is None:
        console.print(
            f"[alerta]No se encontró serie para '{estado}' + '{padecimiento}'.[/alerta]",
        )
        return

    _show_forecast(console, series, estado, padecimiento)

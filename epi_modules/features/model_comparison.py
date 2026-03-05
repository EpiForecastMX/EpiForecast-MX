"""Tabla comparativa rapida de metricas entre los 4 modelos."""

import unicodedata

import pandas as pd
from rich import box
from rich.console import Console
from rich.table import Table


def _strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


_MODELS = ["prophet", "deepar", "ensemble", "stacking"]
_METRICS = ["smape", "mase", "rmse", "mae"]
_METRIC_LABELS = {
    "smape": "SMAPE (%)",
    "mase": "MASE",
    "rmse": "RMSE",
    "mae": "MAE",
}


def show_model_comparison(console: Console, args: str = "") -> None:
    """Muestra tabla comparativa de metricas de los 4 modelos."""
    parts = args.strip().split()
    if not parts:
        console.print(
            "[alerta]Uso: compara <padecimiento> [estado][/alerta]\n"
            "[sutil]  Ejemplo: compara depresion[/sutil]\n"
            "[sutil]  Ejemplo: compara alzheimer jalisco[/sutil]",
        )
        return

    padecimiento = parts[0]
    estado = " ".join(parts[1:]) if len(parts) > 1 else "nacional"

    # Cargar tabla de produccion
    try:
        df = pd.read_excel(
            "reports/ProdDetails/tabla_333_modelos_produccion.xlsx",
            sheet_name=0,
        )
    except FileNotFoundError:
        console.print("[gris]  No se encontro tabla_333_modelos_produccion.xlsx[/gris]")
        return

    # Buscar serie (sin acentos)
    pad_norm = _strip_accents(padecimiento)
    est_norm = _strip_accents(estado)

    mask = df["padecimiento"].apply(_strip_accents).str.contains(pad_norm, na=False) & df[
        "entidad"
    ].apply(_strip_accents).str.contains(est_norm, na=False)
    # Filtrar por general
    if "sexo" in df.columns:
        mask = mask & (df["sexo"].str.lower() == "general")

    result = df[mask]
    if result.empty:
        console.print(
            f"[alerta]No se encontro '{estado}' + '{padecimiento}'.[/alerta]",
        )
        return

    row = result.iloc[0]
    prod_model = str(row.get("modelo_produccion", "")).lower()

    # Extraer metricas por modelo
    data: dict[str, dict[str, float]] = {}
    for model in _MODELS:
        data[model] = {}
        for metric in _METRICS:
            col = f"{model}_{metric}"
            if col in row.index:
                val = row[col]
                data[model][metric] = float(val) if pd.notna(val) else 0.0

    # Encontrar mejor (menor) por metrica
    best_per_metric: dict[str, str] = {}
    worst_per_metric: dict[str, str] = {}
    for metric in _METRICS:
        vals = {m: data[m].get(metric, 999) for m in _MODELS}
        valid = {m: v for m, v in vals.items() if v > 0}
        if valid:
            best_per_metric[metric] = min(valid, key=lambda m: valid[m])
            worst_per_metric[metric] = max(valid, key=lambda m: valid[m])

    # Construir tabla
    pad_display = row.get("padecimiento", padecimiento.title())
    est_display = row.get("entidad", estado.title())

    table = Table(
        title=(f"[dorado]COMPARATIVA: {est_display} \u00b7 {pad_display}[/dorado]"),
        show_header=True,
        header_style="dorado",
        border_style="verde.dim",
        box=box.ROUNDED,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("Metrica", style="blanco", min_width=12)
    for model in _MODELS:
        is_prod = model == prod_model
        header = model.capitalize()
        if is_prod:
            header += " *"
        table.add_column(header, justify="right", min_width=12)

    for metric in _METRICS:
        label = _METRIC_LABELS[metric]
        cells = [label]
        for model in _MODELS:
            val = data[model].get(metric, 0.0)
            if val == 0.0:
                cells.append("[gris]-[/gris]")
                continue
            fmt = f"{val:.2f}" if metric in ("smape", "mase") else f"{val:.2f}"
            if model == best_per_metric.get(metric):
                cells.append(f"[verde]{fmt}[/verde]")
            elif model == worst_per_metric.get(metric):
                cells.append(f"[guinda]{fmt}[/guinda]")
            else:
                cells.append(fmt)
        table.add_row(*cells)

    # Fila de modelo productivo
    table.add_row("", "", "", "", "", end_section=True)
    prod_cells = ["[dorado]Productivo[/dorado]"]
    for model in _MODELS:
        if model == prod_model:
            prod_cells.append("[verde]\u2714[/verde]")
        else:
            prod_cells.append("[gris]\u00b7[/gris]")
    table.add_row(*prod_cells)

    console.print()
    console.print(table)

    # Resumen
    if prod_model:
        console.print(
            f"\n  [sutil]* Modelo de produccion: {prod_model.capitalize()} "
            f"(seleccionado por menor SMAPE)[/sutil]",
        )
    console.print()

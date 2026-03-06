"""Navegador de 333 modelos de produccion."""

import re

import pandas as pd
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .data_cache import ProjectDataCache

PAGE_SIZE = 20


def _format_smape(val: object) -> str:
    """Formatea SMAPE con color segun valor."""
    try:
        v = float(val)  # type: ignore[arg-type]
    except (ValueError, TypeError):
        return "[gris]-[/gris]"
    if v < 20:
        return f"[verde]{v:.1f}%[/verde]"
    if v < 50:
        return f"[dorado]{v:.1f}%[/dorado]"
    return f"[guinda]{v:.1f}%[/guinda]"


def _format_diag(val: object) -> str:
    """Formatea diagnostico con color."""
    s = str(val).strip() if val else "-"
    if not s or s in ("nan", "-", "N/D"):
        return "[gris]-[/gris]"
    if "Alto" in s:
        return f"[guinda]{s}[/guinda]"
    if "Moderado" in s:
        return f"[dorado]{s}[/dorado]"
    if "Sospechoso" in s:
        return f"[guinda]{s}[/guinda]"
    if s.startswith("OK"):
        return "[verde]OK[/verde]"
    return f"[gris]{s}[/gris]"


def _show_table(
    console: Console,
    df: pd.DataFrame,
    title: str,
    page: int = 0,
) -> None:
    """Muestra tabla paginada de modelos."""
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE
    page_df = df.iloc[start:end]

    table = Table(
        title=f"[dorado]{title}[/dorado]",
        show_header=True,
        header_style="dorado",
        box=box.SIMPLE,
        padding=(0, 1),
        expand=True,
    )
    table.add_column("#", width=4, justify="right", style="gris")
    table.add_column("Padecimiento", style="blanco", min_width=12)
    table.add_column("Entidad", style="blanco", min_width=18)
    table.add_column("Modo", style="gris", width=10)
    table.add_column("Motor", style="info", width=10)
    table.add_column("SMAPE", justify="right", width=9)
    table.add_column("MASE", justify="right", width=7)
    table.add_column("Diagnóstico", width=12)

    for idx, row in page_df.iterrows():
        num = start + page_df.index.get_loc(idx) + 1
        pad = str(row.get("padecimiento", ""))
        ent = str(row.get("entidad", ""))
        modo = str(row.get("modo", row.get("sexo", "")))
        motor = str(row.get("modelo_produccion", row.get("tipo_modelo", "")))
        smape = _format_smape(row.get("smape_prod", ""))
        mase_val = row.get("mase_prod", "")
        try:
            mase_str = f"{float(mase_val):.2f}"
        except (ValueError, TypeError):
            mase_str = "-"
        diag = _format_diag(row.get("overfitting", ""))

        table.add_row(str(num), pad, ent, modo, motor, smape, mase_str, diag)

    console.print()
    console.print(table)

    total_pages = (len(df) - 1) // PAGE_SIZE + 1
    console.print(
        f"\n  [sutil]Página {page + 1}/{total_pages} · {len(df)} modelos totales[/sutil]",
    )
    if total_pages > 1:
        hints = []
        if page + 1 < total_pages:
            hints.append(f"[dorado]modelos {page + 2}[/dorado]")
        if page > 0:
            hints.append(f"[dorado]modelos {page}[/dorado]")
        console.print(f"  [sutil]Navega con {' · '.join(hints)}[/sutil]")
    console.print()


def _show_detail(
    console: Console,
    df: pd.DataFrame,
    filtro: str,
) -> None:
    """Muestra detalle de un modelo especifico."""
    f_lower = filtro.lower()
    mask = pd.Series([True] * len(df), index=df.index)

    for col in ["padecimiento", "entidad", "modo", "sexo"]:
        if col in df.columns:
            for word in f_lower.split():
                word_mask = df[col].astype(str).str.lower().str.contains(word, na=False)
                if word_mask.any():
                    mask = mask & word_mask

    matches = df[mask]
    if matches.empty:
        console.print(f"[alerta]No se encontraron modelos para '{filtro}'.[/alerta]")
        return

    if len(matches) == 1:
        row = matches.iloc[0]
        _show_model_card(console, row)
    elif len(matches) <= PAGE_SIZE:
        _show_table(console, matches, f"MODELOS: {filtro}")
    else:
        _show_table(console, matches, f"MODELOS: {filtro} ({len(matches)} resultados)")


def _show_model_card(console: Console, row: pd.Series) -> None:
    """Card detallada de un modelo individual."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Campo", style="gris", min_width=22)
    table.add_column("Valor", style="blanco")

    fields = [
        ("Padecimiento", "padecimiento"),
        ("Entidad", "entidad"),
        ("Modo", "modo"),
        ("Motor", "modelo_produccion"),
        ("Modelo", "modelo_produccion"),
        ("Región", "region_asignada"),
        ("SMAPE", "smape_prod"),
        ("MASE", "mase_prod"),
        ("RMSE", "rmse_prod"),
        ("MAE", "mae_prod"),
        ("Overfitting", "overfitting"),
        ("Leakage", "leakage"),
        ("Casos 52 sem futuro", "casos_52_semanas_futuro"),
        ("Casos 52 sem real", "casos_prev_52_semanas_real"),
        ("Precisión histórica", "precision_historica"),
        ("Justificación", "justificacion"),
    ]

    for label, key in fields:
        val = row.get(key, "")
        if pd.notna(val) and str(val).strip():
            if key == "smape_prod":
                display = _format_smape(val)
            elif key in ("overfitting", "leakage"):
                display = _format_diag(val)
            elif key == "casos_52_semanas_futuro":
                try:
                    display = f"[dorado]{int(float(val)):,}[/dorado]"
                except (ValueError, TypeError):
                    display = str(val)
            else:
                display = str(val)
            table.add_row(label, display)

    pad = row.get("padecimiento", "?")
    ent = row.get("entidad", "?")
    console.print()
    console.print(
        Panel(
            table,
            title=f"[dorado]MODELO: {pad} · {ent}[/dorado]",
            border_style="verde.dim",
            padding=(1, 2),
        )
    )
    console.print()


def show_model_browser(
    console: Console,
    cache: ProjectDataCache,
    args: str = "",
) -> None:
    """Punto de entrada del navegador de modelos."""
    prod = cache.prod_models
    if prod is None:
        console.print(
            "[gris]  No se encontró tabla_333_modelos_produccion.xlsx[/gris]",
        )
        return

    filtro = args.strip().lower()

    # Detectar número de página: "2", "p3", "pag 5", "pagina 4"
    page_match = re.match(r"^(?:p(?:ag(?:ina)?)?\s*)?(\d+)$", filtro)
    if not filtro or page_match:
        page = (int(page_match.group(1)) - 1) if page_match else 0
        total_pages = (len(prod) - 1) // PAGE_SIZE + 1
        page = max(0, min(page, total_pages - 1))
        _show_table(console, prod, f"{len(prod)} MODELOS DE PRODUCCIÓN", page)
        return

    # Filtros especiales
    if filtro == "peores":
        if "smape_prod" in prod.columns:
            worst = prod.nlargest(20, "smape_prod")
            _show_table(console, worst, "20 PEORES MODELOS (SMAPE)")
        return

    if filtro == "mejores":
        if "smape_prod" in prod.columns:
            best = prod.nsmallest(20, "smape_prod")
            _show_table(console, best, "20 MEJORES MODELOS (SMAPE)")
        return

    # Extraer número de página del final del filtro: "alzheimer 3" → page 3
    filter_page = 0
    page_suffix = re.search(r"\s+(?:p(?:ag(?:ina)?)?\s*)?(\d+)$", filtro)
    if page_suffix:
        filter_page = int(page_suffix.group(1)) - 1
        filtro = filtro[: page_suffix.start()].strip()

    # Filtro por motor
    motors = ["ensemble", "stacking", "prophet", "deepar"]
    motor_col = "modelo_produccion" if "modelo_produccion" in prod.columns else "tipo_modelo"
    for motor in motors:
        if motor in filtro and motor_col in prod.columns:
            subset = prod[prod[motor_col].str.lower().str.contains(motor, na=False)]
            if not subset.empty:
                total_p = (len(subset) - 1) // PAGE_SIZE + 1
                pg = max(0, min(filter_page, total_p - 1))
                _show_table(console, subset, f"MODELOS {motor.upper()}", pg)
                return

    # Filtro por padecimiento
    pads = {"depresion": "Depresion", "parkinson": "Parkinson", "alzheimer": "Alzheimer"}
    for key, pad in pads.items():
        if key in filtro and "padecimiento" in prod.columns:
            subset = prod[prod["padecimiento"].str.lower().str.contains(key, na=False)]
            if not subset.empty:
                total_p = (len(subset) - 1) // PAGE_SIZE + 1
                pg = max(0, min(filter_page, total_p - 1))
                _show_table(console, subset, f"MODELOS: {pad}", pg)
                return

    # Filtro generico
    _show_detail(console, prod, filtro)
